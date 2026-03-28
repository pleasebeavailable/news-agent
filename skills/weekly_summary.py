"""Skill 5: Weekly Summary — sent every Saturday at 07:00 CET."""

import json
import logging
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from core import config_loader, stock_data, news_store, llm_client, telegram_bot
from skills.earnings import get_upcoming_earnings

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "weekly_summary.txt"

_BRIEF_FIELDS = ("title", "score", "source", "affected_tickers", "summary", "published_at")


def _slim(article: dict) -> dict:
    return {k: article[k] for k in _BRIEF_FIELDS if k in article}


def _weekly_perf(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            return {"ticker": ticker, "weekly_pct": None}
        open_price = hist["Close"].iloc[0]
        close_price = hist["Close"].iloc[-1]
        pct = (close_price - open_price) / open_price * 100
        return {"ticker": ticker, "weekly_pct": round(pct, 2)}
    except Exception as e:
        logger.warning("weekly perf failed for %s: %s", ticker, e)
        return {"ticker": ticker, "weekly_pct": None}


def assemble_data() -> dict:
    wl = config_loader.watchlist()
    tickers = [item["ticker"] for item in wl]

    now = datetime.now(timezone.utc)
    # True Mon 00:00 → now window so weekly summary always covers current week
    week_start_dt = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    hours_since_monday = max(1, int((now - week_start_dt).total_seconds() / 3600))
    week_start = week_start_dt.strftime("%b %-d")
    week_end = now.strftime("%b %-d, %Y")

    return {
        "performance": [_weekly_perf(t) for t in tickers],
        "benchmark": _weekly_perf("^GSPC"),
        "macro_events": [_slim(a) for a in news_store.get_recent(since_hours=hours_since_monday, min_score=6, limit=10)],
        "portfolio_news": [_slim(a) for a in news_store.get_recent(since_hours=hours_since_monday, min_score=5, limit=20)],
        "next_week_earnings": get_upcoming_earnings(days_ahead=7),
        "date_range": f"{week_start} – {week_end}",
    }


def generate_summary() -> str:
    with open(PROMPT_PATH) as f:
        template = f.read()

    data = assemble_data()
    theses = config_loader.theses()

    prompt = template.replace("{assembled_data_json}", json.dumps(data, default=str))
    prompt = prompt.replace("{theses_yaml}", yaml.dump(theses, default_flow_style=False))
    prompt = prompt.replace("{date_range}", data["date_range"])

    messages = [{"role": "user", "content": prompt}]
    return llm_client.chat(messages, temperature=0.4, max_tokens=4096)


def send_weekly_summary():
    logger.info("Generating weekly summary...")
    try:
        summary = generate_summary()
        telegram_bot.send(summary)
        logger.info("Weekly summary sent.")
    except Exception as e:
        logger.error(f"Weekly summary failed: {e}")
        telegram_bot.send(f"⚠️ Weekly summary failed: {e}")
