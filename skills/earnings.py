"""Skill 3: Earnings Calendar & Tracking."""

import logging
from datetime import datetime, timedelta
import yfinance as yf

from core import config_loader

logger = logging.getLogger(__name__)


def get_upcoming_earnings(days_ahead: int = 30) -> list[dict]:
    wl = config_loader.watchlist()
    results = []
    now = datetime.now()

    for item in wl:
        ticker = item["ticker"]
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is None:
                continue
            # calendar can be a dict or DataFrame depending on yfinance version
            if hasattr(cal, "to_dict"):
                cal = cal.to_dict()
            earnings_date = cal.get("Earnings Date")
            if not earnings_date:
                continue
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0]
            if hasattr(earnings_date, "to_pydatetime"):
                earnings_date = earnings_date.to_pydatetime()
            if not isinstance(earnings_date, datetime):
                earnings_date = datetime(earnings_date.year, earnings_date.month, earnings_date.day)
            days_until = (earnings_date - now).days
            if 0 <= days_until <= days_ahead:
                results.append({
                    "ticker": ticker,
                    "earnings_date": earnings_date.strftime("%Y-%m-%d"),
                    "days_until": days_until,
                })
        except Exception as e:
            logger.warning("earnings fetch failed for %s: %s", ticker, e)
            continue

    return sorted(results, key=lambda x: x["days_until"])


def get_upcoming_earnings_message() -> str:
    upcoming = get_upcoming_earnings(days_ahead=30)
    if not upcoming:
        return "No earnings scheduled in the next 30 days for watchlist tickers."

    lines = ["📅 *Upcoming Earnings* (next 30 days)", "━━━━━━━━━━━━━━━━━━━"]
    for e in upcoming:
        days = e["days_until"]
        when = "tomorrow" if days == 1 else f"in {days}d" if days > 0 else "today"
        lines.append(f"*{e['ticker']}* — {e['earnings_date']} ({when})")
    return "\n".join(lines)


def get_calendar_message() -> str:
    upcoming = get_upcoming_earnings(days_ahead=7)
    lines = ["📅 *Next Week Calendar*", "━━━━━━━━━━━━━━━━━━━"]
    if upcoming:
        lines.append("*Earnings:*")
        for e in upcoming:
            lines.append(f"  {e['ticker']} — {e['earnings_date']}")
    else:
        lines.append("No watchlist earnings next week.")
    return "\n".join(lines)
