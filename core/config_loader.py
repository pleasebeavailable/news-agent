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
