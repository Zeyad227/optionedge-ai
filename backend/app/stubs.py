"""Scaffold modules for later phases — interfaces only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# --- Alerts (TODO) ---


@dataclass
class AlertRule:
    symbol: str
    condition: str  # rsi | macd_cross | ema_cross | insider | news | price | ai_buy | ai_sell
    threshold: float | None = None
    channels: list[str] | None = None  # email | sms | browser | discord | telegram


class AlertDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, rule: AlertRule, payload: dict[str, Any]) -> None:
        """TODO: email / SMS / browser / Discord webhook / Telegram bot."""


# --- Portfolio (TODO) ---


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    asset_type: str  # equity | option


class PortfolioService(ABC):
    @abstractmethod
    async def positions(self) -> list[Position]:
        """TODO: track positions, P/L, greeks exposure, heat map."""


# --- Backtesting / label generation (TODO train, interface ready) ---


@dataclass
class BacktestConfig:
    strategy: str
    start: str
    end: str
    symbols: list[str]
    forward_days: int = 2


@dataclass
class BacktestResult:
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    avg_return: float
    sample_count: int = 0
    skipped_avoid: int = 0


class LabelGenerator(ABC):
    """Build training labels from historical option bars + factor snapshots."""

    @abstractmethod
    async def generate(self, config: BacktestConfig) -> list[dict[str, Any]]:
        """TODO: replay factors forward over Alpaca option bars (from Feb 2024)."""


class Backtester(ABC):
    @abstractmethod
    async def run(self, config: BacktestConfig) -> BacktestResult:
        """TODO: simulate strategies; report robustness metrics, never claim guarantees."""


# --- Auth (TODO) ---


class AuthService(ABC):
    @abstractmethod
    async def login(self, email: str, password: str) -> str:
        """TODO: JWT sessions."""


# --- Institutional / 13F (TODO) ---


class InstitutionalProvider(ABC):
    @abstractmethod
    async def latest_13f(self, cik: str) -> dict[str, Any]:
        """TODO: parse SEC 13F holdings."""
