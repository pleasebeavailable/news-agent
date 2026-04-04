"""Skill 1: Stock Price & Fundamentals."""

import logging

from core import config_loader, stock_data

logger = logging.getLogger(__name__)

# ── Skill metadata (auto-discovery) ──────────────────────────────────
COMMANDS = [
    {"type": "exact", "pattern": "watchlist", "call": "get_watchlist_message"},
    {"type": "exact", "pattern": "portfolio", "call": "get_portfolio_message"},
    {"type": "regex", "pattern": r"(?i)(\w[\w.]+)\s+vs\s+(\w[\w.]+)",
     "call": "compare", "args": "upper", "priority": 50},
]
HELP_ORDER = 2
HELP = (
    "*Prices*\n"
    "`watchlist` — live prices for all positions\n"
    "`portfolio` — positions with themes & P&L\n"
    "`NVDA` — quote for any ticker\n"
    "`NVDA vs AMD` — side-by-side comparison"
)


def _fmt_pct(val) -> str:
    if val is None:
        return "n/a"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def _fmt_price(val, currency="USD") -> str:
    if val is None:
        return "n/a"
    return f"${val:,.2f}" if currency == "USD" else f"{val:,.2f} {currency}"


def _fmt_mcap(val) -> str:
    if val is None:
        return "n/a"
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    return f"${val/1e6:.0f}M"


def get_quote_message(ticker: str) -> str:
    logger.info("price request — single ticker: %s", ticker)
    q = stock_data.get_quote(ticker)
    if not q.get("price"):
        return None

    theses = config_loader.theses()
    thesis = theses.get(ticker, {})
    stance = thesis.get("stance", "")

    lines = [
        f"📊 *{ticker}* — {q.get('name', ticker)}",
        "━━━━━━━━━━━━━━━━━━━",
        f"💰 Price: {_fmt_price(q['price'], q.get('currency','USD'))} "
        f"({_fmt_pct(q.get('change_pct'))})",
    ]
    if q.get("pe"):
        lines.append(f"📈 P/E: {q['pe']:.1f}")
    if q.get("market_cap"):
        lines.append(f"🏦 Market Cap: {_fmt_mcap(q['market_cap'])}")
    if q.get("52w_high") and q.get("52w_low"):
        lines.append(
            f"📉 52W Range: {_fmt_price(q['52w_low'])} — {_fmt_price(q['52w_high'])}"
        )
    if stance:
        lines.append(f"🎯 Stance: {stance[:80]}")

    return "\n".join(lines)


def get_watchlist_message() -> str:
    logger.info("price request — watchlist")
    wl = config_loader.watchlist()
    quotes = stock_data.get_watchlist(wl)
    alerts_cfg = config_loader.alerts_config()
    mover_threshold = alerts_cfg.get("premarket_mover_pct", 3.0)

    # Group by theme
    themes: dict[str, list[dict]] = {}
    for q in quotes:
        theme = q.get("theme", "Other")
        themes.setdefault(theme, []).append(q)

    theme_icons = {
        "AI Infra": "🟢",
        "China/EM": "🟡",
        "Crypto": "🟣",
        "Brazil": "🔵",
        "Vol/Options": "💗",
        "Satellite": "⚪",
    }

    lines = ["📋 *Watchlist*", "━━━━━━━━━━━━━━━━━━━", ""]

    for theme, items in themes.items():
        icon = theme_icons.get(theme, "•")
        lines.append(f"{icon} *{theme}*")
        for q in items:
            ticker = q["ticker"]
            price = _fmt_price(q.get("price"), q.get("currency", "USD"))
            pct = _fmt_pct(q.get("change_pct"))
            mover = "🔥 " if abs(q.get("change_pct") or 0) >= mover_threshold else ""
            lines.append(f"{mover}{ticker:<8} {price:<12} {pct}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🔥 = moved >3%")
    return "\n".join(lines)


def get_portfolio_message() -> str:
    logger.info("price request — portfolio P&L")
    wl = config_loader.watchlist()
    quotes = stock_data.get_watchlist(wl)

    lines = ["💼 *Portfolio*", "━━━━━━━━━━━━━━━━━━━", ""]
    total_value = 0.0
    total_cost = 0.0

    rows = []
    for q in quotes:
        price = q.get("price") or 0
        shares = q.get("shares") or 0
        cost = q.get("cost") or 0
        value = price * shares
        cost_basis = cost * shares
        pnl = value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0
        total_value += value
        total_cost += cost_basis
        rows.append((q["ticker"], value, pnl, pnl_pct, q.get("theme", "")))

    for ticker, value, pnl, pnl_pct, theme in sorted(rows, key=lambda x: -x[1]):
        weight = (value / total_value * 100) if total_value else 0
        sign = "+" if pnl >= 0 else ""
        lines.append(
            f"{ticker:<8} ${value:>8,.0f}  {weight:>4.1f}%  "
            f"P&L: {sign}${pnl:,.0f} ({sign}{pnl_pct:.1f}%)"
        )

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"Total: ${total_value:,.0f}  P&L: {sign}${total_pnl:,.0f} ({sign}{total_pnl_pct:.1f}%)")
    return "\n".join(lines)


def compare(ticker_a: str, ticker_b: str) -> str:
    logger.info("price request — comparison: %s vs %s", ticker_a, ticker_b)
    a = stock_data.get_quote(ticker_a)
    b = stock_data.get_quote(ticker_b)

    def row(label, va, vb, fmt=str):
        return f"{label:<14} {fmt(va):<16} {fmt(vb)}"

    lines = [
        f"📊 *{ticker_a} vs {ticker_b}*",
        "━━━━━━━━━━━━━━━━━━━",
        f"{'':14} {ticker_a:<16} {ticker_b}",
        row("Price", _fmt_price(a.get("price")), _fmt_price(b.get("price"))),
        row("Change", _fmt_pct(a.get("change_pct")), _fmt_pct(b.get("change_pct"))),
        row("P/E", f"{a['pe']:.1f}" if a.get("pe") else "n/a",
            f"{b['pe']:.1f}" if b.get("pe") else "n/a"),
        row("Mkt Cap", _fmt_mcap(a.get("market_cap")), _fmt_mcap(b.get("market_cap"))),
    ]
    return "\n".join(lines)
