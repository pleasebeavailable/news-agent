"""Skill 8: Portfolio Manager — NL portfolio updates via Telegram."""

import logging
from pathlib import Path

import yaml

from core import config_loader, llm_client, telegram_bot
import core.news_fetcher as _news_fetcher
import core.news_scorer as _news_scorer

logger = logging.getLogger(__name__)

COMMANDS = [
    {"type": "exact", "pattern": "portfolio", "call": "show_portfolio"},
    {"type": "prefix", "pattern": "portfolio update ", "call": "start_portfolio_update"},
    {"type": "exact", "pattern": "portfolio sync", "call": "sync_portfolio"},
    {"type": "exact", "pattern": "confirm", "call": "confirm_update"},
    {"type": "exact", "pattern": "cancel", "call": "cancel_update"},
]
HELP_ORDER = 9
HELP = (
    "*Portfolio*\n"
    "`portfolio` — show current holdings\n"
    "`portfolio update <desc>` — update via natural language\n"
    "`portfolio sync` — hot-reload configs after manual edits\n"
    "`confirm` / `cancel` — after an update preview"
)

PORTFOLIO_PATH = Path(__file__).parent.parent / "config" / "portfolio.yaml"
THESES_PATH = Path(__file__).parent.parent / "config" / "theses.yaml"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "portfolio_update.txt"

_PENDING_UPDATE: dict | None = None


def show_portfolio() -> str:
    wl = config_loader.watchlist()
    th = config_loader.theses()
    theme_map: dict[str, list[dict]] = {}
    for pos in wl:
        theme_map.setdefault(pos.get("theme", "Other"), []).append(pos)

    lines = ["📊 *Portfolio Holdings*", "━━━━━━━━━━━━━━━━━━━"]
    for theme, positions in theme_map.items():
        lines.append(f"\n*{theme}*")
        for pos in positions:
            t = pos["ticker"]
            stance = th.get(t, {}).get("stance", "")
            short_stance = stance.split(".")[0] if stance else "—"
            lines.append(f"  {t}: {pos['shares']} shares @ ${pos['cost']:.2f}  _{short_stance}_")

    lines.append("\n_Send `portfolio update <description>` to update holdings._")
    return "\n".join(lines)


def start_portfolio_update(text: str) -> str:
    global _PENDING_UPDATE

    with open(PORTFOLIO_PATH) as f:
        portfolio_yaml = f.read()
    with open(THESES_PATH) as f:
        theses_yaml = f.read()
    with open(PROMPT_PATH) as f:
        prompt_template = f.read()

    prompt = prompt_template.replace("{current_portfolio_yaml}", portfolio_yaml)
    prompt = prompt.replace("{current_theses_yaml}", theses_yaml)
    prompt = prompt.replace("{user_message}", text)

    try:
        result = llm_client.json_chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=2048)
    except Exception as e:
        logger.error("Portfolio update LLM call failed: %s", e)
        return f"⚠️ Failed to parse update: {e}"

    if not isinstance(result, dict) or "changes" not in result:
        logger.error("Portfolio update: unexpected LLM response: %s", result)
        return "⚠️ Could not parse portfolio changes. Try rephrasing."

    changes = result.get("changes", [])
    summary = result.get("summary", "")

    if not changes:
        return "No changes detected. Try describing what you bought, sold, or trimmed."

    _PENDING_UPDATE = result

    # Build preview
    preview_lines = [f"📋 *Portfolio Update Preview*", "━━━━━━━━━━━━━━━━━━━", f"_{summary}_", ""]
    for c in changes:
        ticker = c.get("ticker", "?")
        if c.get("remove"):
            preview_lines.append(f"❌ Remove *{ticker}*")
        else:
            parts = [f"• *{ticker}*"]
            if c.get("shares") is not None:
                parts.append(f"{c['shares']} shares")
            if c.get("cost") is not None:
                parts.append(f"@ ${c['cost']:.2f}")
            if c.get("theme"):
                parts.append(f"({c['theme']})")
            if c.get("thesis") is None and not c.get("remove"):
                parts.append("⚠️ _no thesis — will ask_")
            preview_lines.append(" ".join(parts))

    preview_lines.append("\nSend `confirm` to apply or `cancel` to abort.")

    missing_thesis = [c["ticker"] for c in changes if not c.get("remove") and not c.get("thesis")]
    if missing_thesis:
        preview_lines.append(
            f"\n_Missing thesis for: {', '.join(missing_thesis)}. "
            f"After confirming, send: `thesis TICKER your thesis text`_"
        )

    return "\n".join(preview_lines)


def confirm_update() -> str:
    global _PENDING_UPDATE
    if not _PENDING_UPDATE:
        return "No pending update. Send `portfolio update <description>` first."

    changes = _PENDING_UPDATE.get("changes", [])

    # Load current configs
    with open(PORTFOLIO_PATH) as f:
        portfolio = yaml.safe_load(f)
    with open(THESES_PATH) as f:
        theses = yaml.safe_load(f) or {}

    wl: list[dict] = portfolio.get("watchlist", [])
    ticker_index = {pos["ticker"]: i for i, pos in enumerate(wl)}
    to_remove: set[str] = set()

    applied = 0
    for change in changes:
        ticker = change.get("ticker")
        if not ticker:
            continue

        if change.get("remove"):
            if ticker in ticker_index:
                to_remove.add(ticker)
                theses.pop(ticker, None)
                applied += 1
            continue

        if ticker in ticker_index:
            pos = wl[ticker_index[ticker]]
            if change.get("shares") is not None:
                pos["shares"] = change["shares"]
            if change.get("cost") is not None:
                pos["cost"] = change["cost"]
            if change.get("names") is not None:
                pos["names"] = change["names"]
        else:
            new_pos = {
                "ticker": ticker,
                "type": change.get("type", "stock"),
                "exchange": change.get("exchange", "NASDAQ"),
                "theme": change.get("theme", "Other"),
                "shares": change.get("shares", 0),
                "cost": change.get("cost", 0.0),
                "names": change.get("names", []),
            }
            wl.append(new_pos)

        # Update thesis
        if change.get("thesis") or change.get("kill"):
            thesis_entry = theses.get(ticker, {})
            if change.get("thesis"):
                thesis_entry["thesis"] = change["thesis"]
            if change.get("kill"):
                thesis_entry["kill"] = change["kill"]
            if change.get("stance"):
                thesis_entry["stance"] = change["stance"]
            if change.get("strategy"):
                thesis_entry["strategy"] = change["strategy"]
            theses[ticker] = thesis_entry

        applied += 1

    if to_remove:
        wl = [p for p in wl if p["ticker"] not in to_remove]
    portfolio["watchlist"] = wl

    with open(PORTFOLIO_PATH, "w") as f:
        yaml.dump(portfolio, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(THESES_PATH, "w") as f:
        yaml.dump(theses, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Hot-reload everything
    config_loader.reload_all()
    _news_fetcher._keywords_cache = None
    _news_scorer._prompt_template = None

    _PENDING_UPDATE = None
    return f"✅ Portfolio updated. {applied} holding(s) changed. News pipeline reloaded."


def cancel_update() -> str:
    global _PENDING_UPDATE
    if not _PENDING_UPDATE:
        return "Nothing to cancel."
    _PENDING_UPDATE = None
    return "Cancelled."


def sync_portfolio() -> str:
    config_loader.reload_all()
    _news_fetcher._keywords_cache = None
    _news_scorer._prompt_template = None
    return "✅ Configs reloaded. Portfolio, theses, keywords, and scoring prompt are now up to date."
