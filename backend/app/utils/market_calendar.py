"""US equity session calendar helpers (America/New_York)."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

US_EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def market_now() -> datetime:
    return datetime.now(US_EASTERN)


def market_today() -> date:
    """Current calendar date in US Eastern — use for DTE and session cutoffs."""
    return market_now().date()


def is_weekday(d: date | None = None) -> bool:
    d = d or market_today()
    return d.weekday() < 5


def is_trading_session(now: datetime | None = None) -> bool:
    """True during regular NYSE hours (Mon–Fri 09:30–16:00 ET)."""
    now = now or market_now()
    if not is_weekday(now.date()):
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def should_run_market_jobs(now: datetime | None = None) -> bool:
    """Gate quota-heavy jobs (scanner, IV backfill) to regular session hours."""
    return is_trading_session(now)
