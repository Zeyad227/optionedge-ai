"""IV history backfill and IV rank/percentile from accumulated snapshots."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.utils.market_calendar import market_today

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.greeks import implied_volatility
from app.db.models import IVSnapshot
from app.schemas.models import Candle

logger = logging.getLogger(__name__)

# Alpaca historical option bars available from Feb 2024 onward.
ALPACA_IV_EARLIEST = date(2024, 2, 1)
DEFAULT_RISK_FREE = 0.045
MIN_SAMPLES_FOR_RANK = 20


async def upsert_iv(
    session: AsyncSession,
    *,
    symbol: str,
    as_of: date,
    iv: float,
    source: str,
    note: str | None = None,
) -> None:
    existing = await session.scalar(
        select(IVSnapshot).where(IVSnapshot.symbol == symbol.upper(), IVSnapshot.as_of == as_of)
    )
    if existing:
        existing.iv = iv
        existing.source = source
        existing.note = note
    else:
        session.add(
            IVSnapshot(
                symbol=symbol.upper(),
                as_of=as_of,
                iv=iv,
                source=source,
                note=note,
            )
        )
    await session.commit()


async def snapshot_dates(
    session: AsyncSession,
    symbol: str,
    *,
    since: date,
) -> set[date]:
    rows = (
        await session.scalars(
            select(IVSnapshot.as_of).where(
                IVSnapshot.symbol == symbol.upper(),
                IVSnapshot.as_of >= since,
            )
        )
    ).all()
    return set(rows)


async def iv_rank_percentile(
    session: AsyncSession,
    symbol: str,
    *,
    lookback_days: int = 365,
) -> dict | None:
    """Return IV rank and percentile, or None if history is insufficient."""
    cutoff = market_today() - timedelta(days=lookback_days)
    rows = (
        await session.scalars(
            select(IVSnapshot)
            .where(IVSnapshot.symbol == symbol.upper(), IVSnapshot.as_of >= cutoff)
            .order_by(IVSnapshot.as_of)
        )
    ).all()
    if len(rows) < MIN_SAMPLES_FOR_RANK:
        return None

    values = [r.iv for r in rows]
    current = values[-1]
    lo, hi = min(values), max(values)
    rank = 50.0 if hi == lo else (current - lo) / (hi - lo) * 100
    below = sum(1 for v in values if v <= current)
    percentile = below / len(values) * 100

    return {
        "iv": current,
        "iv_rank": round(rank, 1),
        "iv_percentile": round(percentile, 1),
        "samples": len(values),
        "lookback_days": lookback_days,
        "from": rows[0].as_of.isoformat(),
        "to": rows[-1].as_of.isoformat(),
        "source": rows[-1].source,
        # "partial" means the window is not fully covered. Comparing against
        # ALPACA_IV_EARLIEST as well made this unconditionally true for every
        # date after Feb 2024, so every reading was labelled partial. History
        # simply cannot start before that date, so it is a floor, not a defect.
        "partial": rows[0].as_of > max(cutoff, ALPACA_IV_EARLIEST),
    }


def atm_iv_from_chain(
    contracts,
    spot: float,
    *,
    min_dte: int = 7,
    as_of: date | None = None,
) -> float | None:
    """Pick nearest ATM contract with IV, preferring at least ``min_dte`` days out."""
    today = as_of or market_today()
    with_iv = [
        c
        for c in contracts
        if c.implied_volatility
        and c.implied_volatility > 0
        and (c.expiration - today).days >= min_dte
    ]
    if not with_iv:
        with_iv = [c for c in contracts if c.implied_volatility and c.implied_volatility > 0]
    if not with_iv:
        return None
    with_iv.sort(key=lambda c: abs(c.strike - spot))
    return with_iv[0].implied_volatility


def iv_from_option_bar(
    *,
    spot: float,
    strike: float,
    expiration: date,
    bar_close: float,
    as_of: date,
    option_type: str = "call",
    rate: float = DEFAULT_RISK_FREE,
) -> float | None:
    """Invert Black-Scholes on a historical option bar close."""
    days = (expiration - as_of).days
    if days <= 0 or bar_close <= 0 or spot <= 0 or strike <= 0:
        return None
    t = days / 365.0
    return implied_volatility(bar_close, spot, strike, t, rate, option_type)


def _candidate_candle_days(
    candles: list[Candle],
    *,
    since: date,
    existing: set[date],
    limit: int,
) -> list[Candle]:
    out: list[Candle] = []
    for candle in candles:
        day = candle.timestamp.date()
        if day < since or day >= market_today() or day in existing:
            continue
        out.append(candle)
    # Oldest first so backfill progresses through history.
    out.sort(key=lambda c: c.timestamp)
    return out[:limit]


async def backfill_iv_from_bars(
    session: AsyncSession,
    alpaca,
    symbol: str,
    candles: list[Candle],
    *,
    lookback_days: int = 365,
    max_days_per_run: int = 20,
) -> dict:
    """
    Backfill daily IV snapshots by inverting BS on Alpaca historical option bars.

    Uses equity closes as spot and picks a ~1-week+ DTE ATM call per day.
    """
    since = max(ALPACA_IV_EARLIEST, market_today() - timedelta(days=lookback_days))
    existing = await snapshot_dates(session, symbol, since=since)
    todo = _candidate_candle_days(candles, since=since, existing=existing, limit=max_days_per_run)

    written = 0
    skipped = 0
    errors = 0

    for candle in todo:
        day = candle.timestamp.date()
        spot = candle.close
        try:
            meta = await alpaca.pick_atm_call(symbol, spot, day)
            if not meta:
                skipped += 1
                continue
            option_sym = meta["symbol"]
            expiration = date.fromisoformat(meta["expiration_date"])
            strike = float(meta["strike_price"])
            bars = await alpaca.get_option_bars([option_sym], day, day)
            rows = bars.get(option_sym) or []
            if not rows:
                skipped += 1
                continue
            bar_close = float(rows[-1].get("c") or 0)
            iv = iv_from_option_bar(
                spot=spot,
                strike=strike,
                expiration=expiration,
                bar_close=bar_close,
                as_of=day,
            )
            if iv is None or iv <= 0:
                skipped += 1
                continue
            await upsert_iv(
                session,
                symbol=symbol,
                as_of=day,
                iv=iv,
                source="alpaca-bars",
                note="BS invert on OPRA daily bar close",
            )
            written += 1
        except Exception:  # noqa: BLE001
            logger.exception("IV backfill failed for %s on %s", symbol, day)
            errors += 1

    return {
        "symbol": symbol.upper(),
        "written": written,
        "skipped": skipped,
        "errors": errors,
        "queued": len(todo),
        "since": since.isoformat(),
    }


async def ensure_iv_rank(
    session: AsyncSession,
    symbol: str,
    *,
    alpaca=None,
    candles: list[Candle] | None = None,
    live_iv: float | None = None,
    live_source: str = "options",
    lookback_days: int = 365,
    max_backfill_days: int = 20,
) -> dict | None:
    """
    Return IV rank stats, backfilling from Alpaca bars when samples are low.

    Optionally upserts today's IV from a live chain reading before ranking.
    """
    if live_iv is not None and live_iv > 0:
        await upsert_iv(
            session,
            symbol=symbol,
            as_of=market_today(),
            iv=live_iv,
            source=live_source,
            note="ATM IV from live chain",
        )

    stats = await iv_rank_percentile(session, symbol, lookback_days=lookback_days)
    if stats is not None:
        return stats

    if alpaca is not None and candles:
        await backfill_iv_from_bars(
            session,
            alpaca,
            symbol,
            candles,
            lookback_days=lookback_days,
            max_days_per_run=max_backfill_days,
        )
        return await iv_rank_percentile(session, symbol, lookback_days=lookback_days)

    return None
