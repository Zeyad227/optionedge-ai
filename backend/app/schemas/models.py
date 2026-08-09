"""Shared pydantic response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.constants import SIGNAL_DISCLAIMER

SignalAction = Literal["Buy", "Sell", "Avoid"]
TrendLabel = Literal["Bullish", "Bearish", "Sideways"]
SentimentLabel = Literal["Bullish", "Bearish", "Neutral"]


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Quote(BaseModel):
    symbol: str
    price: float
    change_pct: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    beta: float | None = None


class OptionContract(BaseModel):
    symbol: str
    underlying: str
    expiration: date
    strike: float
    option_type: Literal["call", "put"]
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    greeks_source: str | None = None


FactorRole = Literal["directional", "modulator", "context"]


class Factor(BaseModel):
    """A single piece of observed evidence behind a signal.

    ``role`` governs how the aggregator may use the factor:

    - ``directional`` — casts a signed vote and counts toward the score denominator.
    - ``modulator``   — unsigned; scales conviction only (e.g. ADX, IV rank).
    - ``context``     — reported for the reader; never affects the score.
    """

    name: str
    observed: str
    direction: Literal["bullish", "bearish", "neutral"]
    weight: float
    contribution: float
    source: str
    role: FactorRole = "directional"


class ConfidenceComponent(BaseModel):
    """One factor's share of the final confidence number, in percentage points."""

    name: str
    direction: Literal["bullish", "bearish", "neutral"]
    points: float


class SignalResponse(BaseModel):
    symbol: str
    action: SignalAction
    trend: TrendLabel
    confidence: float = Field(ge=0, le=100)
    # Names the provenance of `confidence` so no caller can present a heuristic
    # blend as if it were a backtested win probability.
    confidence_basis: Literal["heuristic_uncalibrated", "backtest_calibrated"] = (
        "heuristic_uncalibrated"
    )
    confidence_breakdown: list[ConfidenceComponent] = Field(default_factory=list)
    forecast_type: Literal["probabilistic"] = "probabilistic"
    trend_regime: Literal["uptrend", "downtrend", "range", "unknown"] = "unknown"
    volatility_regime: Literal["cheap", "mid", "expensive"] | None = None
    data_coverage: float | None = Field(default=None, ge=0, le=1)
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: list[float] = Field(default_factory=list)
    risk_reward: float | None = None
    probability_of_profit: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Risk-neutral ITM probability from option delta (not a calibrated win rate).",
    )
    probability_of_profit_basis: Literal["delta_approximation", "unavailable"] = "unavailable"
    suggested_contract: OptionContract | None = None
    factors: list[Factor] = Field(default_factory=list)
    missing_factors: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    disclaimer: str = SIGNAL_DISCLAIMER
    generated_at: datetime
    sources: list[str] = Field(default_factory=list)


class NewsArticle(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    summary: str | None = None
    sentiment: SentimentLabel | None = None
    sentiment_score: float | None = None
    impact: float | None = None
    related_symbols: list[str] = Field(default_factory=list)


class InsiderTrade(BaseModel):
    insider_name: str
    position: str | None = None
    company: str
    symbol: str | None = None
    transaction_type: str
    shares: float | None = None
    amount: float | None = None
    transaction_date: date | None = None
    filed_at: datetime | None = None
    sentiment: SentimentLabel = "Neutral"
    form_url: str | None = None


class WorkerJobStatus(BaseModel):
    id: str
    next_run: datetime | None = None


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, bool]
    cache_backend: str
    database: str
    forecast_type: Literal["probabilistic"] = "probabilistic"
    workers_enabled: bool = False
    worker_jobs: list[WorkerJobStatus] = Field(default_factory=list)


class ApiEnvelope(BaseModel):
    data: Any
    sourced: bool = True
    disclaimer: str | None = None
