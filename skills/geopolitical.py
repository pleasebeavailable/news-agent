"""Skill 7: Geopolitical News Monitor — scheduled scan + on-demand."""

import logging
from datetime import datetime, timezone
from core import news_store, news_fetcher, news_scorer, llm_client, telegram_bot

logger = logging.getLogger(__name__)


def _article_date(a: dict) -> str:
    raw = a.get("published_at") or a.get("fetched_at") or ""
    return raw[:10] if raw else "unknown"

_GEO_CATEGORIES = {"geopolitics", "china", "macro"}

_PORTFOLIO_GEO_CONTEXT = (
    "Portfolio geo exposures: "
    "BABA/2689.HK — US-China binary risk (delisting, tariffs, regulatory thaw); "
    "NVDA/NBIS/MRVL/GLW — export controls, chip ban, CHIPS Act; "
    "PBR/VALE — Brazil macro, Lula policy, commodity demand from China; "
    "BMNR/HOOD/ORBS — crypto regulation, SEC, stablecoin legislation; "
    "FLOW.AS — vol exposure to geopolitical shocks."
)


def _get_recent_geo_news(since_hours: int = 30, min_score: int = 5) -> list[dict]:
    articles = news_store.get_recent(since_hours=since_hours, min_score=min_score, limit=30)
    return [a for a in articles if (a.get("category") or "").lower() in _GEO_CATEGORIES]


def get_geo_brief() -> str:
    """On-demand: return a geopolitical brief from recent scored news."""
    articles = _get_recent_geo_news(since_hours=48, min_score=4)
    if not articles:
        logger.info("get_geo_brief: no geo articles found (48h, score>=4)")
        return "No significant geopolitical news in the last 48h matching your portfolio exposures."

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    headlines = "\n".join(
        f"[{_article_date(a)}] [{a['score']}/10] [{a.get('category','?').upper()}] {a['title']} — {a.get('portfolio_impact','')}"
        for a in articles[:8]
    )

    prompt = (
        f"Today is {today}. You are a geopolitical risk analyst. Synthesize these recent news items into a "
        f"brief geopolitical situational report for an investor.\n\n"
        f"{_PORTFOLIO_GEO_CONTEXT}\n\n"
        f"RECENT GEO NEWS (last 48h):\n{headlines}\n\n"
        f"FORMAT:\n"
        f"🌍 *Geo Brief*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"For each relevant region/theme (US-China, Brazil, Macro, Crypto Regulation):\n"
        f"  - One line: what's happening\n"
        f"  - One line: portfolio implication\n\n"
        f"End with: *Biggest geo risk right now:* one sentence.\n"
        f"Keep under 300 words. Skip regions with no news."
    )
    return llm_client.chat([{"role": "user", "content": prompt}], temperature=0.4, max_tokens=2048)


def _fetch_geo_articles() -> int:
    """Fetch only geo RSS feeds, score, and store. Returns count of new articles."""
    try:
        raw = news_fetcher.fetch_all(source_filter=news_fetcher.GEO_SOURCES)
        if not raw:
            return 0
        scored = news_scorer.score_batch(raw)
        for article in scored:
            news_store.save_article(article)
        logger.info("Geo fetch: %d raw → %d scored (≥5)", len(raw), len(scored))
        return len(scored)
    except Exception as e:
        logger.error("Geo fetch failed: %s", e)
        return 0


def run_geo_scan() -> None:
    """Scheduled: fetch geo feeds, score, store, then alert on high-impact items."""
    _fetch_geo_articles()

    articles = _get_recent_geo_news(since_hours=2, min_score=7)
    alerted = [a for a in articles if not a.get("alerted")]

    for article in alerted:
        if not news_store.try_mark_alerted(article["id"]):
            continue  # another thread already sent this alert
        score = article['score']
        if score >= 9:
            # High importance — full detail with summary
            msg = (
                f"🌍 *Geo Alert* (Score: {score}/10)\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📰 {article['title']}\n"
                f"📡 {article.get('source', '?')}\n\n"
                f"*What happened:*\n{article.get('summary', 'N/A')}\n\n"
                f"*Impact:* {article.get('portfolio_impact', 'N/A')}\n"
                f"*Consider:* {article.get('suggested_action', 'N/A')}"
            )
        else:
            # Score 7-8 — short format
            kill = "\n⚠️ *Kill switch*" if article.get("kill_switch_triggered") else ""
            msg = (
                f"🌍 [{score}/10] {article['title']}\n"
                f"💡 {article.get('portfolio_impact', 'N/A')}"
                f"{kill}"
            )
        telegram_bot.send(msg)
        logger.info("Geo alert sent: %s", article['title'])

    if not alerted:
        logger.info("Geo scan: no new high-impact geo news")
