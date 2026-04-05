"""Skill 8: Portfolio Manager — structured portfolio updates via Telegram."""

import logging
import re
from pathlib import Path

import yaml

from core import config_loader, telegram_bot
import core.news_fetcher as _news_fetcher
import core.news_scorer as _news_scorer

logger = logging.getLogger(__name__)

COMMANDS = [
    {"type": "exact", "pattern": "portfolio", "call": "show_portfolio"},
    {"type": "prefix", "pattern": "portfolio update ", "call": "start_portfolio_update"},
    {"type": "prefix", "pattern": ">>>", "call": "start_portfolio_update"},
    {"type": "exact", "pattern": "portfolio sync", "call": "sync_portfolio"},
    {"type": "exact", "pattern": "portfolio prompt", "call": "send_portfolio_prompt"},
    {"type": "exact", "pattern": "skill prompt", "call": "send_skill_prompt"},
    {"type": "prefix", "pattern": "thesis ", "call": "update_thesis"},
    {"type": "prefix", "pattern": "kill ", "call": "update_kill"},
    {"type": "exact", "pattern": "confirm", "call": "confirm_update"},
    {"type": "exact", "pattern": "yes", "call": "confirm_update"},
    {"type": "exact", "pattern": "cancel", "call": "cancel_update"},
]
HELP_ORDER = 9
HELP = (
    "*Portfolio*\n"
    "`portfolio` — show current holdings\n"
    "`portfolio update <lines>` or `>>> <lines>` — update via structured format\n"
    "`yes` / `cancel` — after an update preview\n"
    "`thesis TICKER <text>` — update thesis directly\n"
    "`kill TICKER <text>` — update kill condition directly\n"
    "`portfolio sync` — hot-reload configs after manual edits\n"
    "`portfolio prompt` — send update format template\n"
    "`skill prompt` — send new-skill meta-prompt for Claude"
)

PORTFOLIO_PATH = Path(__file__).parent.parent / "config" / "portfolio.yaml"
THESES_PATH = Path(__file__).parent.parent / "config" / "theses.yaml"
SKILL_META_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "new_skill_meta_prompt.txt"
PORTFOLIO_COMPOSER_PATH = Path(__file__).parent.parent / "prompts" / "portfolio_update_composer.txt"

_PENDING_UPDATE: dict | None = None

# Regex patterns for the three line types
_TICKER = r'([A-Z0-9][A-Z0-9._-]*)'
_CURRENCY = r'(?:[$€£]|[A-Z]{2,3})?'
_RE_REMOVE = re.compile(rf'^-{_TICKER}\s*$', re.IGNORECASE)
_RE_UPDATE = re.compile(rf'^{_TICKER}\s+(\d+)\s+@{_CURRENCY}([0-9.]+)\s*$', re.IGNORECASE)
_RE_ADD = re.compile(
    rf'^\+?{_TICKER}\s+(\d+)\s+@{_CURRENCY}([0-9.]+)\s+(\S+)\s+([^|]+?)(?:\|(.+))?$',
    re.IGNORECASE,
)


def _parse_update_text(text: str) -> tuple[list[dict], list[str]]:
    # If delimiter present, take only what comes after the last ---
    if '---' in text:
        text = text.split('---')[-1]

    changes, errors = [], []
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue

        m = _RE_REMOVE.match(line)
        if m:
            changes.append({"ticker": m.group(1).upper(), "remove": True})
            continue

        m = _RE_ADD.match(line)
        if m:
            ticker = m.group(1).upper()
            change = {
                "ticker": ticker,
                "remove": False,
                "shares": int(m.group(2)),
                "cost": float(m.group(3)),
                "exchange": m.group(4).upper(),
                "theme": m.group(5).strip(),
            }
            if m.group(6):
                for part in m.group(6).split('|'):
                    part = part.strip()
                    if ':' not in part:
                        continue
                    key, val = part.split(':', 1)
                    key, val = key.strip().lower(), val.strip()
                    if key == 'names':
                        change['names'] = [n.strip() for n in val.split(',') if n.strip()]
                    elif key in ('thesis', 'kill', 'stance', 'strategy'):
                        change[key] = val
            changes.append(change)
            continue

        m = _RE_UPDATE.match(line)
        if m:
            changes.append({
                "ticker": m.group(1).upper(),
                "remove": False,
                "shares": int(m.group(2)),
                "cost": float(m.group(3)),
            })
            continue

        errors.append(line)

    return changes, errors


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

    lines.append("\n_Send `portfolio prompt` for update format._")
    return "\n".join(lines)


def start_portfolio_update(text: str) -> str:
    global _PENDING_UPDATE

    changes, errors = _parse_update_text(text)

    if errors:
        err_lines = "\n".join(f"  `{e}`" for e in errors)
        return f"⚠️ Could not parse these lines:\n{err_lines}\n\nSend `portfolio prompt` for the format."

    if not changes:
        return "No changes detected. Send `portfolio prompt` for the format."

    _PENDING_UPDATE = {"changes": changes}

    preview_lines = ["📋 *Portfolio Update Preview*", "━━━━━━━━━━━━━━━━━━━", ""]
    for c in changes:
        ticker = c["ticker"]
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
            if not c.get("thesis") and not c.get("remove"):
                parts.append("⚠️ _no thesis_")
            preview_lines.append(" ".join(parts))

    preview_lines.append("\nSend `yes` to apply or `cancel` to abort.")

    missing = [c["ticker"] for c in changes if not c.get("remove") and not c.get("thesis")]
    if missing:
        preview_lines.append(
            f"\n_After confirming, add thesis for: {', '.join(missing)}_\n"
            f"_Use: `thesis TICKER your thesis text`_"
        )

    return "\n".join(preview_lines)


def confirm_update() -> str:
    global _PENDING_UPDATE
    if not _PENDING_UPDATE:
        return "No pending update. Send `portfolio update <lines>` first."

    changes = _PENDING_UPDATE.get("changes", [])

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
            wl.append({
                "ticker": ticker,
                "type": change.get("type", "stock"),
                "exchange": change.get("exchange", "NASDAQ"),
                "theme": change.get("theme", "Other"),
                "shares": change.get("shares", 0),
                "cost": change.get("cost", 0.0),
                "names": change.get("names", []),
            })

        if change.get("thesis") or change.get("kill"):
            entry = theses.get(ticker, {})
            for field in ("thesis", "kill", "stance", "strategy"):
                if change.get(field):
                    entry[field] = change[field]
            theses[ticker] = entry

        applied += 1

    if to_remove:
        wl = [p for p in wl if p["ticker"] not in to_remove]
    portfolio["watchlist"] = wl

    with open(PORTFOLIO_PATH, "w") as f:
        yaml.dump(portfolio, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    with open(THESES_PATH, "w") as f:
        yaml.dump(theses, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    config_loader.reload_all()
    _news_fetcher.clear_cache()
    _news_scorer.clear_cache()

    _PENDING_UPDATE = None
    return f"✅ Portfolio updated. {applied} holding(s) changed. News pipeline reloaded."


def cancel_update() -> str:
    global _PENDING_UPDATE
    if not _PENDING_UPDATE:
        return "Nothing to cancel."
    _PENDING_UPDATE = None
    return "Cancelled."


def update_thesis(text: str) -> str:
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: `thesis TICKER your thesis text`"
    ticker, thesis_text = parts[0].upper(), parts[1].strip()

    with open(THESES_PATH) as f:
        theses = yaml.safe_load(f) or {}
    entry = theses.get(ticker, {})
    entry["thesis"] = thesis_text
    theses[ticker] = entry
    with open(THESES_PATH, "w") as f:
        yaml.dump(theses, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    config_loader.reload_all()
    _news_scorer._prompt_template = None
    logger.info("thesis updated for %s", ticker)
    return f"✅ Thesis updated for *{ticker}*."


def update_kill(text: str) -> str:
    parts = text.strip().split(" ", 1)
    if len(parts) < 2:
        return "Usage: `kill TICKER your kill condition`"
    ticker, kill_text = parts[0].upper(), parts[1].strip()

    with open(THESES_PATH) as f:
        theses = yaml.safe_load(f) or {}
    entry = theses.get(ticker, {})
    entry["kill"] = kill_text
    theses[ticker] = entry
    with open(THESES_PATH, "w") as f:
        yaml.dump(theses, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    config_loader.reload_all()
    _news_scorer._prompt_template = None
    logger.info("kill condition updated for %s", ticker)
    return f"✅ Kill condition updated for *{ticker}*."


def sync_portfolio() -> str:
    config_loader.reload_all()
    _news_fetcher.clear_cache()
    _news_scorer.clear_cache()
    return "✅ Configs reloaded. Portfolio, theses, keywords, and scoring prompt are now up to date."


def _send_file_chunked(path: Path, label: str) -> str:
    with open(path) as f:
        text = f.read()
    chunks, current, length = [], [], 0
    for line in text.splitlines(keepends=True):
        if length + len(line) > 4000 and current:
            chunks.append("".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line)
    if current:
        chunks.append("".join(current))
    for i, chunk in enumerate(chunks):
        telegram_bot.send(chunk, parse_mode="")
        logger.info("%s: sent chunk %d/%d", label, i + 1, len(chunks))
    return f"📋 {label} sent ({len(chunks)} message(s))."


def send_portfolio_prompt() -> str:
    return _send_file_chunked(PORTFOLIO_COMPOSER_PATH, "Portfolio update format")


def send_skill_prompt() -> str:
    return _send_file_chunked(SKILL_META_PROMPT_PATH, "Skill meta-prompt")
