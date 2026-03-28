"""NemoClaw Phase 2 — Telegram command router and scheduler."""

import fcntl
import logging
import logging.handlers
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

_LOG_DIR = os.environ.get("NEMOCLAW_LOG_DIR", "/sandbox/workspace/logs")
os.makedirs(_LOG_DIR, exist_ok=True)
try:
    _LOG_RETENTION_DAYS = int(os.environ.get("NEMOCLAW_LOG_RETENTION_DAYS", "30"))
except ValueError:
    _LOG_RETENTION_DAYS = 30
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"

_CATEGORIES = {
    "app":  ("__main__", "core.telegram_bot", "core.stock_data", "skills.stock_price",
             "skills.research", "skills.earnings", "skills.morning_brief", "skills.weekly_summary"),
    "news": ("core.news_fetcher", "core.news_scorer", "core.news_store", "skills.news_monitor"),
    "llm":  ("core.llm_client",),
    "geo":  ("skills.geopolitical",),
}


class _CategoryFilter(logging.Filter):
    def __init__(self, prefixes):
        super().__init__()
        self._prefixes = prefixes

    def filter(self, record):
        return record.name.startswith(self._prefixes)


_formatter = logging.Formatter(_LOG_FORMAT)
_handlers = []

for _cat, _prefixes in _CATEGORIES.items():
    _h = logging.handlers.TimedRotatingFileHandler(
        os.path.join(_LOG_DIR, f"{_cat}.log"),
        when="midnight", backupCount=_LOG_RETENTION_DAYS, utc=True,
    )
    _h.setFormatter(_formatter)
    _h.addFilter(_CategoryFilter(_prefixes))
    _handlers.append(_h)

# all.log — no filter, catches everything including third-party libs
_all_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(_LOG_DIR, "all.log"),
    when="midnight", backupCount=_LOG_RETENTION_DAYS, utc=True,
)
_all_handler.setFormatter(_formatter)
_handlers.append(_all_handler)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_handlers.append(_console_handler)

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, handlers=_handlers)
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

# ── Skill auto-discovery ─────────────────────────────────────────────
import importlib
import pkgutil
import re

_COMMANDS = None   # list of (cmd_dict, module)
_SCHEDULES = None  # list of (sched_dict, module)


def _discover_skills():
    """Scan skills/ package, collect COMMANDS and SCHEDULE metadata."""
    import skills
    commands, schedules = [], []
    for _, modname, _ in pkgutil.iter_modules(skills.__path__, skills.__name__ + "."):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            logger.warning("Failed to import skill %s — skipping", modname, exc_info=True)
            continue
        for cmd in getattr(mod, "COMMANDS", []):
            commands.append((cmd, mod))
        for sched in getattr(mod, "SCHEDULE", []):
            schedules.append((sched, mod))
    # Sort: type first (exact < prefix < regex), then priority within type
    type_order = {"exact": 0, "prefix": 1, "regex": 2}
    commands.sort(key=lambda c: (type_order.get(c[0]["type"], 9), c[0].get("priority", 50)))
    return commands, schedules


def _ensure_discovered():
    global _COMMANDS, _SCHEDULES
    if _COMMANDS is None:
        _COMMANDS, _SCHEDULES = _discover_skills()


def _try_command(cmd, mod, text, text_lower):
    """Match one command spec. Return response string or None."""
    ctype = cmd["type"]
    if ctype == "exact":
        if text_lower != cmd["pattern"]:
            return None
        args = ()
    elif ctype == "prefix":
        if not text_lower.startswith(cmd["pattern"]):
            return None
        args = (text[len(cmd["pattern"]):].strip(),)
    elif ctype == "regex":
        m = re.match(cmd["pattern"], text)
        if not m:
            return None
        arg_mode = cmd.get("args")
        if arg_mode == "upper":
            args = tuple(g.upper() for g in m.groups())
        elif arg_mode == "raw":
            args = m.groups()
        else:
            args = ()
    else:
        return None

    func = getattr(mod, cmd["call"])
    logger.info("routing: %s.%s%s", mod.__name__, cmd["call"],
                ("(" + ", ".join(repr(a) for a in args) + ")") if args else "")

    if cmd.get("thread"):
        threading.Thread(target=func, args=args, daemon=True).start()
        return cmd.get("ack", "Working on it...")
    return func(*args)


def _help_text():
    _ensure_discovered()
    seen, sections = set(), []
    for _, mod in _COMMANDS:
        if mod.__name__ not in seen:
            seen.add(mod.__name__)
            h = getattr(mod, "HELP", None)
            if h:
                order = getattr(mod, "HELP_ORDER", 99)
                sections.append((order, h))
    sections.sort(key=lambda x: x[0])
    return (
        "*NemoClaw Phase 2 — Commands*\n\n"
        + "\n\n".join(s for _, s in sections)
        + "\n\n*System*\n"
        "`status` — bot health check\n"
        "`reload` — reload config without restarting\n"
        "`help` — this message"
    )


def handle_message(text: str) -> str:
    """Route an incoming Telegram message to the right skill."""
    _ensure_discovered()
    t = text.strip()
    tl = t.lower()

    # Built-in commands (touch main.py internals, can't live in skills)
    if tl == "reload":
        logger.info("routing: reload")
        config_loader.reload_all()
        return "Config reloaded."
    if tl == "status":
        logger.info("routing: status")
        return "NemoClaw Phase 2 running. All systems go."
    if tl in ("help", "/help"):
        logger.info("routing: help")
        return _help_text()

    # Skill commands via metadata
    for cmd, mod in _COMMANDS:
        result = _try_command(cmd, mod, t, tl)
        if result is not None:
            return result

    # Single-ticker fallback (returns None → fall through to chat)
    if re.match(r"^[A-Z0-9.]{1,10}$", t.upper()) and len(t.split()) == 1:
        from skills import stock_price
        result = stock_price.get_quote_message(t.upper())
        if result is not None:
            return result

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
    """Background thread: register scheduled tasks from skill metadata, then tick."""
    _ensure_discovered()
    sched_cfg = config_loader.schedule_config()

    for sched, mod in _SCHEDULES:
        func = getattr(mod, sched["func"])
        if "interval" in sched:
            minutes = sched_cfg.get(sched["interval"], sched["default"])
            schedule.every(minutes).minutes.do(func)
            logger.info("Scheduled %s.%s every %d min", mod.__name__, sched["func"], minutes)
        elif "days" in sched:
            for day in sched["days"]:
                getattr(schedule.every(), day).at(sched["at"]).do(func)
            logger.info("Scheduled %s.%s on %s at %s",
                        mod.__name__, sched["func"], ",".join(sched["days"]), sched["at"])

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
    _ensure_discovered()
    logger.info("NemoClaw Phase 2 starting up — %d commands, %d schedules",
                len(_COMMANDS), len(_SCHEDULES))

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Run startup tasks from skill metadata
    for sched, mod in _SCHEDULES:
        if sched.get("run_at_startup"):
            func = getattr(mod, sched["func"])
            threading.Thread(target=func, daemon=True, name=f"startup-{sched['func']}").start()
            logger.info("Startup task: %s.%s", mod.__name__, sched["func"])

    if telegram_bot.send("NemoClaw Phase 2 online. Send `help` for commands."):
        logger.info("Startup message sent to Telegram")
    else:
        logger.warning("Could not send startup message — Telegram may not be reachable yet")
    poll_loop()
