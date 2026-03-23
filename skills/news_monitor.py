"""Skill 2: News monitoring — fetch, score, alert."""

import json
import logging

from core import news_fetcher, news_scorer, news_store, telegram_bot, config_loader

logger = logging.getLogger(__name__)


def run_news_cycle():
    """Fetch → score → store → alert. Call this on a schedule (e.g. every 15 min)."""
    try:
        articles = news_fetcher.fetch_all() + news_fetcher.fetch_research_urls()
        if not articles:
            logger.info("News cycle: no new articles from any feed")
            return
        logger.info("News cycle: %d raw articles fetched", len(articles))

        scored = news_scorer.score_batch(articles)
        logger.info("News cycle: %d articles scored ≥5", len(scored))
        alerts_cfg = config_loader.alerts_config()
        immediate_threshold = alerts_cfg.get("news_score_immediate", 7)

        for article in scored:
            news_store.save_article(article)

            if article["score"] >= immediate_threshold:
                msg = _format_alert(article)
                telegram_bot.send(msg)
                logger.info(f"Alert sent for: {article['title'][:60]}")
    except Exception as e:
        logger.error(f"News cycle failed: {e}")
        try:
            telegram_bot.send(f"⚠️ News cycle failed: {e}")
        except Exception:
            logger.error("Could not send news cycle failure alert to Telegram")


def _format_alert(article: dict) -> str:
    tickers = ", ".join(article.get("affected_tickers") or [])
    kill = "⚠️ *Kill switch proximity detected*\n" if article.get("kill_switch_triggered") else ""
    return (
        f"🚨 *ALERT* (Score: {article['score']}/10)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📰 {article['title']}\n"
        f"📡 Source: {article['source']} (Tier {article.get('source_tier', '?')})\n\n"
        f"*What happened:*\n{article.get('summary', '')}\n\n"
        f"*Portfolio impact:*\n{article.get('portfolio_impact', 'n/a')}\n\n"
        f"*Consider:*\n{article.get('suggested_action', 'No action needed')}\n\n"
        f"{kill}"
        f"🏷️ {article.get('category', '')} | Tickers: {tickers or 'none'}"
    )


def get_recent_news(min_score: int = 5, limit: int = 5) -> str:
    articles = news_store.get_recent(since_hours=24, min_score=min_score, limit=limit)
    if not articles:
        logger.info("get_recent_news: no articles found (24h, score>=%d)", min_score)
        return "No scored news in the last 24 hours."

    lines = [f"📰 *Recent News* (last 24h, score ≥{min_score})", "━━━━━━━━━━━━━━━━━━━"]
    for a in articles:
        tickers = ", ".join(json.loads(a.get("affected_tickers") or "[]"))
        lines.append(
            f"[{a['score']}/10] {a['title']}\n"
            f"  _{a.get('portfolio_impact', '')}_"
            + (f"\n  Tickers: {tickers}" if tickers else "")
        )
    return "\n\n".join(lines)


def get_news_by_topic(topic: str) -> str:
    # Simple: search recent scored articles for topic keyword
    articles = news_store.get_recent(since_hours=48, min_score=4, limit=20)
    topic_lower = topic.lower()
    matches = [
        a for a in articles
        if topic_lower in (a.get("title") or "").lower()
        or topic_lower in (a.get("summary") or "").lower()
        or topic_lower in (a.get("category") or "").lower()
    ]
    if not matches:
        logger.info("get_news_by_topic(%s): no matches found", topic)
        return f"No recent news found for '{topic}'."

    lines = [f"📰 *News: {topic}*", "━━━━━━━━━━━━━━━━━━━"]
    for a in matches[:5]:
        lines.append(f"[{a['score']}/10] {a['title']}\n  _{a.get('summary', '')[:100]}_")
    return "\n\n".join(lines)


def get_recent_alerts() -> str:
    articles = news_store.get_recent(since_hours=48, min_score=7, limit=10)
    if not articles:
        return "No high-score alerts in the last 48 hours."
    lines = [f"🚨 *Recent Alerts* (score ≥7, last 48h)", "━━━━━━━━━━━━━━━━━━━"]
    for a in articles:
        lines.append(f"[{a['score']}/10] {a['title']}")
    return "\n".join(lines)


def get_kill_switch_status() -> str:
    theses = config_loader.theses()
    lines = ["⚔️ *Kill Switch Status*", "━━━━━━━━━━━━━━━━━━━"]
    for ticker, t in theses.items():
        kill = t.get("kill", "n/a")
        lines.append(f"*{ticker}*: {kill}")
    return "\n\n".join(lines)
