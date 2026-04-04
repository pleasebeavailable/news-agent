"""Load and hot-reload config files."""

from pathlib import Path
import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

_cache: dict[str, dict] = {}


def _load(filename: str, bust: bool = False) -> dict:
    if filename not in _cache or bust:
        with open(CONFIG_DIR / filename) as f:
            _cache[filename] = yaml.safe_load(f)
    return _cache[filename]


def reload_all():
    """Force reload of all cached configs."""
    _cache.clear()


def portfolio() -> dict:
    return _load("portfolio.yaml")


def watchlist() -> list[dict]:
    return portfolio()["watchlist"]


def theses() -> dict:
    return _load("theses.yaml")


def alerts_config() -> dict:
    return portfolio().get("alerts", {})


def schedule_config() -> dict:
    return portfolio().get("schedule", {})


def portfolio_keyword_terms() -> list[str]:
    """Ticker symbols + names for all watchlist holdings."""
    terms = []
    for pos in watchlist():
        terms.append(pos["ticker"])
        terms.extend(pos.get("names", []))
    return terms


def portfolio_geo_context() -> str:
    """Concise geo-risk string from theses kill conditions, grouped by theme."""
    wl = watchlist()
    th = theses()
    theme_tickers: dict[str, list[str]] = {}
    for pos in wl:
        theme_tickers.setdefault(pos.get("theme", "Other"), []).append(pos["ticker"])

    lines = ["Portfolio geo exposures:"]
    for theme, tickers in theme_tickers.items():
        kills = [f"{t}: {th[t]['kill'][:90]}" for t in tickers if th.get(t, {}).get("kill")]
        entry = "/".join(tickers)
        if kills:
            entry += " — " + "; ".join(kills)
        lines.append(f"  {entry}")
    return "\n".join(lines)


def portfolio_scoring_context() -> str:
    """Full portfolio context block for LLM prompts."""
    wl = watchlist()
    th = theses()
    theme_tickers: dict[str, list[str]] = {}
    for pos in wl:
        theme_tickers.setdefault(pos.get("theme", "Other"), []).append(pos["ticker"])

    alloc_lines = [f"{theme}: {', '.join(tickers)}" for theme, tickers in theme_tickers.items()]
    driver_lines, kill_lines = [], []
    for pos in wl:
        t = pos["ticker"]
        entry = th.get(t, {})
        if entry.get("thesis"):
            driver_lines.append(f"- {t}: {entry['thesis'].replace(chr(10), ' ').strip()[:100]}")
        if entry.get("kill"):
            kill_lines.append(f"- {t}: {entry['kill'][:100]}")

    return (
        "PORTFOLIO HOLDINGS:\n" + "\n".join(alloc_lines) + "\n\n"
        "KEY THESIS DRIVERS:\n" + "\n".join(driver_lines) + "\n\n"
        "KILL SWITCHES (immediate alert if triggered):\n" + "\n".join(kill_lines)
    )
