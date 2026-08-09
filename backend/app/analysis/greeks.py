"""Black-Scholes greeks + IV solver (fallback when Alpaca omits greeks)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm


@dataclass
class Greeks:
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float) -> tuple[float, float]:
    if t <= 0 or sigma <= 0 or s <= 0 or k <= 0:
        raise ValueError("invalid BS inputs")
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return d1, d2


def black_scholes(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    iv: float,
    option_type: str,
) -> Greeks:
    d1, d2 = _d1_d2(spot, strike, time_years, rate, iv)
    if option_type.lower() == "call":
        price = spot * norm.cdf(d1) - strike * math.exp(-rate * time_years) * norm.cdf(d2)
        delta = norm.cdf(d1)
        rho = strike * time_years * math.exp(-rate * time_years) * norm.cdf(d2) / 100
        theta = (
            -(spot * norm.pdf(d1) * iv) / (2 * math.sqrt(time_years))
            - rate * strike * math.exp(-rate * time_years) * norm.cdf(d2)
        ) / 365
    else:
        price = strike * math.exp(-rate * time_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)
        delta = -norm.cdf(-d1)
        rho = -strike * time_years * math.exp(-rate * time_years) * norm.cdf(-d2) / 100
        theta = (
            -(spot * norm.pdf(d1) * iv) / (2 * math.sqrt(time_years))
            + rate * strike * math.exp(-rate * time_years) * norm.cdf(-d2)
        ) / 365
    gamma = norm.pdf(d1) / (spot * iv * math.sqrt(time_years))
    vega = spot * norm.pdf(d1) * math.sqrt(time_years) / 100
    return Greeks(price=price, delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    option_type: str,
    *,
    lo: float = 1e-4,
    hi: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """Binary-search IV from market option price. Returns None if unsolvable."""
    if market_price <= 0 or time_years <= 0 or spot <= 0 or strike <= 0:
        return None
    # Intrinsic floor
    if option_type.lower() == "call":
        intrinsic = max(spot - strike * math.exp(-rate * time_years), 0.0)
    else:
        intrinsic = max(strike * math.exp(-rate * time_years) - spot, 0.0)
    if market_price < intrinsic * 0.99:
        return None

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        try:
            model = black_scholes(spot, strike, time_years, rate, mid, option_type).price
        except ValueError:
            return None
        if abs(model - market_price) < tol:
            return mid
        if model > market_price:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def probability_itm_from_delta(delta: float | None, option_type: str) -> float | None:
    """Risk-neutral probability of expiring ITM, approximated by |delta|."""
    if delta is None:
        return None
    if option_type.lower() == "call":
        return max(0.0, min(1.0, delta))
    return max(0.0, min(1.0, abs(delta)))


def enrich_contract_greeks(
    contract,
    spot: float,
    *,
    rate: float = 0.045,
) -> None:
    """Fill missing greeks in-place using BS when IV and time remain."""

    if contract.delta is not None and contract.gamma is not None:
        return
    if contract.implied_volatility is None or contract.implied_volatility <= 0:
        return
    from app.utils.market_calendar import market_today

    days = (contract.expiration - market_today()).days
    if days <= 0:
        return  # 0DTE: BS time term undefined — leave None
    t = days / 365.0
    try:
        g = black_scholes(
            spot,
            contract.strike,
            t,
            rate,
            contract.implied_volatility,
            contract.option_type,
        )
    except ValueError:
        return
    contract.delta = contract.delta if contract.delta is not None else g.delta
    contract.gamma = contract.gamma if contract.gamma is not None else g.gamma
    contract.theta = contract.theta if contract.theta is not None else g.theta
    contract.vega = contract.vega if contract.vega is not None else g.vega
    contract.rho = contract.rho if contract.rho is not None else g.rho
    if contract.greeks_source is None:
        contract.greeks_source = "black-scholes-fallback"
