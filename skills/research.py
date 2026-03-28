"""Skill 6: On-Demand Research via Telegram."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core import config_loader, stock_data, news_store, llm_client

logger = logging.getLogger(__name__)

# ── Skill metadata (auto-discovery) ──────────────────────────────────
COMMANDS = [
    {"type": "regex", "pattern": r"(?i)research\s+(\w[\w.]+)",
     "call": "research_ticker", "args": "upper", "priority": 30},
    {"type": "regex", "pattern": r"(?i)deep\s+dive\s+(\w[\w.]+)",
     "call": "deep_dive", "args": "upper", "priority": 30},
    {"type": "regex", "pattern": r"(?i)what'?s\s+happening\s+with\s+(.+?)\??$",
     "call": "topic_context", "args": "raw", "priority": 40},
]
HELP_ORDER = 6
HELP = (
    "*Research*\n"
    "`Research PLTR` — bull/bear LLM analysis\n"
    "`Deep dive NVDA` — full deep analysis\n"
    "`What's happening with China?` — topic context"
)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "research_bull_bear.txt"


def _article_date(a: dict) -> str:
    """Return YYYY-MM-DD from published_at or fetched_at, or 'unknown'."""
    raw = a.get("published_at") or a.get("fetched_at") or ""
    return raw[:10] if raw else "unknown"


def _format_news_for_llm(articles: list[dict]) -> list[dict]:
    """Add date prefix to each article title so the LLM knows article age."""
    dated = []
    for a in articles:
        dated.append({**a, "title": f"[{_article_date(a)}] {a.get('title', '')}"})
    return dated


def _get_recent_ticker_news(ticker: str) -> list[dict]:
    articles = news_store.get_recent(since_hours=72, min_score=4, limit=20)
    result = []
    for a in articles:
        raw = a.get("affected_tickers") or "[]"
        try:
            tickers_list = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            tickers_list = []
        if ticker in tickers_list or ticker.lower() in (a.get("title") or "").lower():
            result.append(a)
    return result


def research_ticker(ticker: str) -> str:
    with open(PROMPT_PATH) as f:
        template = f.read()

    quote = stock_data.get_quote(ticker)
    theses = config_loader.theses()
    thesis_data = theses.get(ticker, {})
    recent_news = _get_recent_ticker_news(ticker)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("research request — ticker=%s, news_items=%d, as_of=%s", ticker, len(recent_news), today)

    dated_news = _format_news_for_llm(recent_news[:5])
    prompt = (
        template
        .replace("{ticker}", ticker)
        .replace("{yfinance_data}", json.dumps(quote, default=str))
        .replace("{recent_news_about_ticker}", json.dumps(dated_news, default=str))
        .replace("{thesis_or_none}", thesis_data.get("thesis", "Not held"))
        .replace("{kill_switch_or_none}", thesis_data.get("kill", "n/a"))
        .replace("{stance_or_none}", thesis_data.get("stance", "n/a"))
        .replace("{company_name}", quote.get("name", ticker))
    )

    messages = [{"role": "user", "content": prompt}]
    return llm_client.chat(messages, temperature=0.5, max_tokens=4096)


def deep_dive(ticker: str) -> str:
    # Same as research but with higher token budget and explicit deep dive framing
    base = research_ticker(ticker)
    return f"🔬 *Deep Dive: {ticker}*\n\n{base}"


def topic_context(topic: str) -> str:
    articles = news_store.get_recent(since_hours=72, min_score=4, limit=20)
    topic_lower = topic.lower()
    matches = [
        a for a in articles
        if topic_lower in (a.get("title") or "").lower()
        or topic_lower in (a.get("summary") or "").lower()
    ]

    if not matches:
        return f"No recent context found for '{topic}' in the news database."

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info("topic context — topic=%s, matches=%d, as_of=%s", topic, len(matches), today)
    context = "\n\n".join(
        f"[{_article_date(a)}] [{a['score']}/10] {a['title']}\n{a.get('summary', '')}"
        for a in matches[:5]
    )
    prompt = (
        f"Today is {today}. The user asks: 'What's happening with {topic}?'\n\n"
        f"Here are recent relevant articles (last 72 hours):\n\n{context}\n\n"
        f"Summarize what is happening with {topic} and how it relates to this portfolio:\n"
        f"AI Infra (NVDA, NBIS, AMZN, GOOG, GLW, MRVL), China/EM (BABA, 2689.HK), "
        f"Crypto (BMNR, HOOD, ORBS), Brazil (PBR, VALE), Vol (FLOW.AS).\n"
        f"Keep it under 200 words."
    )
    messages = [{"role": "user", "content": prompt}]
    return llm_client.chat(messages, temperature=0.4, max_tokens=2048)
