"""Options metrics: max pain, put/call ratio, contract selection."""

from __future__ import annotations

from datetime import date

from app.analysis.greeks import enrich_contract_greeks
from app.schemas.models import OptionContract


def front_expiration(contracts: list[OptionContract]) -> date | None:
    """Nearest expiration present in the chain."""
    expirations = {c.expiration for c in contracts}
    return min(expirations) if expirations else None


def for_expiration(
    contracts: list[OptionContract],
    expiration: date | None = None,
) -> list[OptionContract]:
    """Slice the chain to one expiration, defaulting to the front month.

    Open interest accumulates over the life of a contract, so a single LEAP
    strike can carry orders of magnitude more OI than an entire weekly expiry.
    Blending expirations therefore lets distant positioning swamp the near-term
    reading these metrics are supposed to describe.
    """
    target = expiration or front_expiration(contracts)
    if target is None:
        return []
    return [c for c in contracts if c.expiration == target]


def put_call_ratio(
    contracts: list[OptionContract],
    expiration: date | None = None,
    *,
    all_expirations: bool = False,
) -> float | None:
    """Open-interest put/call ratio for a single expiration by default.

    This measures accumulated *positioning*, not today's flow; intraday volume
    is required for a true flow reading.
    """
    scoped = contracts if all_expirations else for_expiration(contracts, expiration)
    call_oi = sum(c.open_interest or 0 for c in scoped if c.option_type == "call")
    put_oi = sum(c.open_interest or 0 for c in scoped if c.option_type == "put")
    if call_oi <= 0:
        return None
    return put_oi / call_oi


def max_pain(
    contracts: list[OptionContract],
    expiration: date | None = None,
    *,
    all_expirations: bool = False,
) -> float | None:
    """Strike minimising total intrinsic value of open contracts at settlement.

    Max pain is only defined per expiration — options settle on their own date,
    so summing payoffs across expirations describes nothing real.
    """
    scoped = contracts if all_expirations else for_expiration(contracts, expiration)
    strikes = sorted({c.strike for c in scoped})
    if not strikes:
        return None
    best_strike = None
    best_pain = None
    for strike in strikes:
        pain = 0.0
        for c in scoped:
            oi = c.open_interest or 0
            if c.option_type == "call":
                pain += max(strike - c.strike, 0) * oi * 100
            else:
                pain += max(c.strike - strike, 0) * oi * 100
        if best_pain is None or pain < best_pain:
            best_pain = pain
            best_strike = strike
    return best_strike


def mid_price(c: OptionContract) -> float | None:
    if c.bid is not None and c.ask is not None and c.ask >= c.bid:
        return (c.bid + c.ask) / 2
    return c.last


def is_liquid(c: OptionContract, *, min_oi: int = 100, max_spread_pct: float = 0.15) -> bool:
    if (c.open_interest or 0) < min_oi:
        return False
    if c.bid is None or c.ask is None or c.bid <= 0:
        return False
    mid = (c.bid + c.ask) / 2
    if mid <= 0:
        return False
    spread = (c.ask - c.bid) / mid
    return spread <= max_spread_pct


def suggest_contract(
    contracts: list[OptionContract],
    *,
    spot: float,
    direction: str,
    target_delta: float = 0.35,
) -> OptionContract | None:
    """Pick a liquid contract near target delta from the real chain — never synthesize."""
    want = "call" if direction == "bullish" else "put"
    target = target_delta if want == "call" else -target_delta

    enriched: list[OptionContract] = []
    for c in contracts:
        if c.option_type != want:
            continue
        enrich_contract_greeks(c, spot)
        if not is_liquid(c):
            continue
        if c.delta is None:
            continue
        enriched.append(c)

    if not enriched:
        # Relax liquidity, still require delta.
        for c in contracts:
            if c.option_type != want:
                continue
            enrich_contract_greeks(c, spot)
            if c.delta is None:
                continue
            enriched.append(c)

    if not enriched:
        return None

    enriched.sort(key=lambda c: abs((c.delta or 0) - target))
    return enriched[0]


def chain_summary(contracts: list[OptionContract], spot: float) -> dict:
    """Front-expiration metrics, with the blended figures kept for comparison."""
    front = front_expiration(contracts)
    return {
        "contract_count": len(contracts),
        "front_expiration": front.isoformat() if front else None,
        "front_contract_count": len(for_expiration(contracts)),
        "put_call_ratio": put_call_ratio(contracts),
        "max_pain": max_pain(contracts),
        "put_call_ratio_all_expirations": put_call_ratio(contracts, all_expirations=True),
        "expirations": sorted({c.expiration.isoformat() for c in contracts}),
        "spot": spot,
    }
