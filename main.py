"""NemoClaw Phase 2 — Telegram command router and scheduler."""

import fcntl
import logging
import os
import sys
import threading
import time

import schedule

# Load .env before any other imports that read env vars.
# Checks workspace-local .env first, then persistent storage fallback.
for _env_path in ("/sandbox/workspace/.env", "/sandbox/.openclaw-data/.env"):
    if os.path.isfile(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    if _line.startswith("export "):
                        _line = _line[7:]
                    _k, _v = _line.split("=", 1)
                    _v = _v.strip()
                    if len(_v) >= 2 and _v[0] == _v[-1] and _v[0] in ("'", '"'):
                        _v = _v[1:-1]
                    else:
                        # Strip inline comments for unquoted values
                        _v = _v.split("#", 1)[0].strip()
                    os.environ.setdefault(_k.strip(), _v)
        break

# Single-instance lock — prevents 409 conflicts from multiple bot processes
_LOCK_FILE = "/tmp/nemoclaw.lock"
_lock_fh = open(_LOCK_FILE, "w")
try:
    fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    _lock_fh.write(str(os.getpid()))
    _lock_fh.flush()
    # Note: logger not yet configured at this point; lock success logged after basicConfig below
except BlockingIOError:
    # logger not yet configured — write directly to stderr
    import sys as _sys
    _sys.stderr.write("NemoClaw is already running. Exiting.\n")
    sys.exit(1)

from core import telegram_bot, config_loader, news_store, llm_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("Lock acquired (PID=%d)", os.getpid())

_SYSTEM_PROMPT = (
    "You are Rich, a sharp and direct portfolio intelligence assistant. "
    "The user's portfolio: AI Infra 46.8% (NVDA, NBIS, AMZN, GOOG, GLW, MRVL), "
    "China/EM 11% (BABA, 2689.HK), Crypto 17.8% (BMNR, HOOD, ORBS), "
    "Brazil 8.4% (PBR, VALE), Vol 6.1% (FLOW.AS), Satellites (OPEN, SKYX). "
    "Be concise. No fluff."
)
_CHAT_HISTORY: list[dict] = []
_CHAT_HISTORY_MAX = 20  # keep last 20 exchanges (~10 back-and-forth)
_CHAT_LOCK = threading.Lock()

# Import skills lazily to avoid startup errors if a dep is missing
def _skills():
    from skills import (
        stock_price,
        news_monitor,
        earnings,
        morning_brief,
        weekly_summary,
        research,
        geopolitical,
    )
    return {
        "stock": stock_price,
        "news": news_monitor,
        "earnings": earnings,
        "morning": morning_brief,
        "weekly": weekly_summary,
        "research": research,
        "geo": geopolitical,
    }


def handle_message(text: str) -> str:
    """Route an incoming Telegram message to the right skill."""
    import re

    s = _skills()
    t = text.strip()
    tl = t.lower()

    # Config commands
    if tl == "reload":
        logger.info("routing: reload config")
        config_loader.reload_all()
        return "Config reloaded."

    if tl == "status":
        logger.info("routing: status")
        return "NemoClaw Phase 2 running. All systems go."

    if tl in ("help", "/help"):
        logger.info("routing: help")
        return (
            "*NemoClaw Phase 2 — Commands*\n\n"
            "*Briefs*\n"
            "`morning brief` — run morning brief now\n"
            "`weekly summary` — run weekly summary now\n\n"
            "*Portfolio*\n"
            "`watchlist` — live prices for all positions\n"
            "`portfolio` — positions with themes & P&L\n"
            "`NVDA` — quote for any ticker\n"
            "`NVDA vs AMD` — side-by-side comparison\n\n"
            "*Geopolitics*\n"
            "`geo` — geopolitical brief from recent news\n\n"
            "*News*\n"
            "`news` — latest scored headlines\n"
            "`news AI` — headlines filtered by topic\n"
            "`Any news on NVDA?` — news for a ticker\n"
            "`alerts` — high-score alerts only\n"
            "`kills` — kill switch status\n\n"
            "*Earnings*\n"
            "`earnings` — upcoming earnings for your tickers\n"
            "`calendar` — full earnings calendar\n\n"
            "*Research*\n"
            "`Research PLTR` — bull/bear LLM analysis\n"
            "`Deep dive NVDA` — full deep analysis\n"
            "`What's happening with China?` — topic context\n\n"
            "*System*\n"
            "`status` — bot health check\n"
            "`reload` — reload config without restarting\n"
            "`help` — this message"
        )

    # Brief commands
    if tl in ("morning brief", "brief"):
        logger.info("routing: morning brief on-demand")
        threading.Thread(target=s["morning"].send_morning_brief, daemon=True).start()
        return "Generating morning brief..."
    if tl in ("weekly summary", "summary", "saturday brief"):
        logger.info("routing: weekly summary on-demand")
        threading.Thread(target=s["weekly"].send_weekly_summary, daemon=True).start()
        return "Generating weekly summary..."

    # News commands
    if tl == "news":
        logger.info("routing: news → get_recent_news")
        return s["news"].get_recent_news()
    if tl.startswith("news "):
        logger.info("routing: news → topic=%s", t[5:].strip())
        return s["news"].get_news_by_topic(t[5:].strip())
    if tl == "alerts":
        logger.info("routing: news → alerts")
        return s["news"].get_recent_alerts()
    if tl == "kills":
        logger.info("routing: news → kill_switch_status")
        return s["news"].get_kill_switch_status()

    # Portfolio commands
    if tl == "watchlist":
        return s["stock"].get_watchlist_message()
    if tl == "portfolio":
        return s["stock"].get_portfolio_message()

    # Geopolitical
    if tl in ("geo", "geopolitical", "geopolitics"):
        logger.info("routing: geo brief")
        return s["geo"].get_geo_brief()

    # Earnings
    if tl == "earnings":
        logger.info("routing: earnings")
        return s["earnings"].get_upcoming_earnings_message()
    if tl == "calendar":
        logger.info("routing: calendar")
        return s["earnings"].get_calendar_message()

    # Research — "Research PLTR" / "Deep dive NVDA"
    if m := re.match(r"(?i)research\s+(\w[\w.]+)", t):
        logger.info("routing: research → %s", m.group(1).upper())
        return s["research"].research_ticker(m.group(1).upper())
    if m := re.match(r"(?i)deep\s+dive\s+(\w[\w.]+)", t):
        logger.info("routing: deep_dive → %s", m.group(1).upper())
        return s["research"].deep_dive(m.group(1).upper())
    if m := re.match(r"(?i)any\s+news\s+on\s+(.+?)\??$", t):
        logger.info("routing: news → topic=%s", m.group(1))
        return s["news"].get_news_by_topic(m.group(1))
    if m := re.match(r"(?i)what'?s\s+happening\s+with\s+(.+?)\??$", t):
        logger.info("routing: topic_context → %s", m.group(1))
        return s["research"].topic_context(m.group(1))

    # Single ticker or comparison — must be last before free-form chat
    if m := re.match(r"(?i)(\w[\w.]+)\s+vs\s+(\w[\w.]+)", t):
        return s["stock"].compare(m.group(1).upper(), m.group(2).upper())
    if re.match(r"^[A-Z0-9.]{1,10}$", t.upper()) and len(t.split()) == 1:
        result = s["stock"].get_quote_message(t.upper())
        if result is not None:
            return result
        # Not a valid ticker — fall through to free-form chat

    # Free-form chat fallback — stateful conversation with history
    logger.info("routing: free-form chat")
    with _CHAT_LOCK:
        _CHAT_HISTORY.append({"role": "user", "content": t})
        if len(_CHAT_HISTORY) > _CHAT_HISTORY_MAX:
            del _CHAT_HISTORY[:-_CHAT_HISTORY_MAX]
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}] + list(_CHAT_HISTORY)

    reply = llm_client.chat(messages, temperature=0.7, max_tokens=2048)

    with _CHAT_LOCK:
        _CHAT_HISTORY.append({"role": "assistant", "content": reply})
        if len(_CHAT_HISTORY) > _CHAT_HISTORY_MAX:
            del _CHAT_HISTORY[:-_CHAT_HISTORY_MAX]

    return reply


_OFFSET_FILE = "/sandbox/workspace/data/telegram_offset"


def _load_offset() -> int:
    try:
        with open(_OFFSET_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    try:
        os.makedirs(os.path.dirname(_OFFSET_FILE), exist_ok=True)
        with open(_OFFSET_FILE, "w") as f:
            f.write(str(offset))
    except Exception as e:
        logger.warning("Could not save offset: %s", e)


def poll_loop():
    """Long-poll Telegram for incoming messages."""
    offset = _load_offset()
    logger.info("Telegram poll loop started (offset=%d)", offset)
    while True:
        try:
            updates = telegram_bot.get_updates(offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                _save_offset(offset)
                msg = update.get("message") or update.get("edited_message")
                if not msg:
                    continue
                if msg.get("chat", {}).get("id") != telegram_bot.chat_id():
                    logger.warning("Ignoring message from unknown chat %s", msg.get("chat", {}).get("id"))
                    continue
                text = msg.get("text", "").strip()
                if not text:
                    continue
                logger.info("Received: %r", text)
                reply = handle_message(text)
                telegram_bot.send(reply)
        except Exception as e:
            logger.error("Poll loop error: %s", e)
            time.sleep(5)


def run_scheduler():
    """Background thread: news cycle every 60 min, geo every 5 min, briefs on schedule."""
    from skills.news_monitor import run_news_cycle
    from skills.morning_brief import send_morning_brief
    from skills.weekly_summary import send_weekly_summary
    from skills.geopolitical import run_geo_scan

    poll_minutes = config_loader.schedule_config().get("news_poll_minutes", 15)
    schedule.every(poll_minutes).minutes.do(run_news_cycle)
    logger.info("News polling every %d min", poll_minutes)
    schedule.every(5).minutes.do(run_geo_scan)
    logger.info("Geo scan every 5 min")
    schedule.every().monday.at("07:00").do(send_morning_brief)
    schedule.every().tuesday.at("07:00").do(send_morning_brief)
    schedule.every().wednesday.at("07:00").do(send_morning_brief)
    schedule.every().thursday.at("07:00").do(send_morning_brief)
    schedule.every().friday.at("07:00").do(send_morning_brief)
    schedule.every().saturday.at("07:00").do(send_weekly_summary)

    logger.info("Scheduler started")
    _start = time.time()
    _tick = 0
    while True:
        schedule.run_pending()
        _tick += 1
        if _tick % 20 == 0:  # every ~10min
            uptime_m = int((time.time() - _start) / 60)
            next_job = schedule.next_run()
            next_in = int((next_job - __import__('datetime').datetime.now()).total_seconds() / 60) if next_job else -1
            logger.info("heartbeat — uptime %dm, next job in %dm", uptime_m, next_in)
        time.sleep(30)


if __name__ == "__main__":
    news_store.init_db()
    logger.info("NemoClaw Phase 2 starting up")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    if telegram_bot.send("NemoClaw Phase 2 online. Send `watchlist` to test."):
        logger.info("Startup message sent to Telegram")
    else:
        logger.warning("Could not send startup message — Telegram may not be reachable yet")
    poll_loop()
