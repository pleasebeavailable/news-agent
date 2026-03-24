"""Skill 4: Morning Brief — assembled and sent at 07:00 CET weekdays."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core import config_loader, stock_data, news_store, llm_client, telegram_bot
from skills.earnings import get_upcoming_earnings

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "morning_brief.txt"


def _article_date(a: dict) -> str:
    raw = a.get("published_at") or a.get("fetched_at") or ""
    return raw[:10] if raw else "unknown"


def assemble_data() -> dict:
    wl = config_loader.watchlist()
    alerts_cfg = config_loader.alerts_config()
    raw_news = news_store.get_recent(since_hours=16, min_score=5, limit=10)
    # Stamp each article with its date so LLM knows article age
    dated_news = [{**a, "title": f"[{_article_date(a)}] {a.get('title', '')}"} for a in raw_news]
    return {
        "futures": stock_data.get_futures(),
        "news": dated_news,
        "earnings_today": get_upcoming_earnings(days_ahead=1),
        "movers": stock_data.get_premarket_movers(
            wl, threshold_pct=alerts_cfg.get("premarket_mover_pct", 3.0)
        ),
        "date": datetime.now(timezone.utc).strftime("%A, %B %-d %Y"),
    }


def generate_brief() -> str:
    with open(PROMPT_PATH) as f:
        template = f.read()

    data = assemble_data()
    data_json = json.dumps(data, default=str)
    prompt = template.replace("{assembled_data_json}", data_json)
    prompt = prompt.replace("{date}", data["date"])

    logger.info("Brief prompt: %d chars, news=%d, movers=%d",
                len(prompt), len(data.get("news", [])), len(data.get("movers", [])))
    messages = [{"role": "user", "content": prompt}]
    return llm_client.chat(messages, temperature=0.4, max_tokens=4096)


def send_morning_brief():
    logger.info("Generating morning brief...")
    try:
        brief = generate_brief()
        if not brief or not brief.strip():
            logger.error("Morning brief: LLM returned empty response, skipping send.")
            telegram_bot.send("⚠️ Morning brief skipped: LLM returned an empty response.")
            return
        telegram_bot.send(brief)
        logger.info("Morning brief sent.")
    except Exception as e:
        logger.error("Morning brief failed: %s", e)
        telegram_bot.send("⚠️ Morning brief failed: %s" % e)
