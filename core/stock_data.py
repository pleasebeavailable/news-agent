"""yfinance wrapper with simple caching."""

import logging
import time
import yfinance as yf

# In-memory cache: ticker -> (data_dict, fetched_at)
_price_cache: dict[str, tuple[dict, float]] = {}

PRICE_TTL = 300    # 5 min

logger = logging.getLogger(__name__)


def get_quote(ticker: str) -> dict:
    """Current price + key fundamentals. Cached 5 min."""
    now = time.time()
    if ticker in _price_cache:
        data, ts = _price_cache[ticker]
        if now - ts < PRICE_TTL:
            logger.debug("quote %s — cache hit", ticker)
            return data

    logger.info("fetching quote %s", ticker)
    t = yf.Ticker(ticker)
    info = t.info
    data = {
        "ticker": ticker,
        "price": info.get("regularMarketPrice") or info.get("currentPrice"),
        "change": info.get("regularMarketChange"),
        "change_pct": info.get("regularMarketChangePercent"),
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "market_cap": info.get("marketCap"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "currency": info.get("currency", "USD"),
        "name": info.get("shortName") or info.get("longName", ticker),
        "volume": info.get("regularMarketVolume"),
        "avg_volume": info.get("averageVolume"),
    }
    _price_cache[ticker] = (data, now)
    price = data.get("price")
    chg = data.get("change_pct")
    sign = "+" if (chg or 0) >= 0 else ""
    logger.info("quote %s — $%s (%s%.2f%%)", ticker, price, sign, chg or 0)
    return data


def get_watchlist(watchlist: list[dict]) -> list[dict]:
    """Quote for every ticker in the watchlist config."""
    results = []
    for item in watchlist:
        q = get_quote(item["ticker"])
        q["theme"] = item.get("theme", "")
        q["shares"] = item.get("shares", 0)
        q["cost"] = item.get("cost", 0.0)
        results.append(q)
    return results


def get_futures() -> dict:
    """S&P 500 and Nasdaq futures + VIX."""
    return {
        "sp500": get_quote("ES=F"),
        "nasdaq": get_quote("NQ=F"),
        "vix": get_quote("^VIX"),
    }


def get_premarket_movers(watchlist: list[dict], threshold_pct: float = 3.0) -> list[dict]:
    """Watchlist tickers moving more than threshold_pct pre-market."""
    movers = []
    for item in get_watchlist(watchlist):
        pct = item.get("change_pct") or 0
        if abs(pct) >= threshold_pct:
            movers.append(item)
    return sorted(movers, key=lambda x: abs(x.get("change_pct") or 0), reverse=True)
