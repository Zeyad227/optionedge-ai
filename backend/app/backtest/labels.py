"""Generate supervised labels by replaying the factor engine over history."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ai.scoring import MIN_HISTORY_BARS, score_symbol
from app.schemas.models import Candle
from app.stubs import BacktestConfig, LabelGenerator


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _forward_return(candles: list[Candle], index: int, forward_days: int) -> float | None:
    if index + forward_days >= len(candles):
        return None
    start = candles[index].close
    end = candles[index + forward_days].close
    if start <= 0:
        return None
    return (end - start) / start


def _label_hit(action: str, forward_ret: float) -> bool | None:
    if action == "Buy":
        return forward_ret > 0
    if action == "Sell":
        return forward_ret < 0
    return None


class HistoricalLabelGenerator(LabelGenerator):
    """Replay ``score_symbol`` on rolling windows and label forward outcomes."""

    def __init__(
        self,
        *,
        candle_loader=None,
        min_history_bars: int = MIN_HISTORY_BARS,
    ) -> None:
        self._load_candles = candle_loader or self._default_loader
        self._min_history_bars = min_history_bars

    async def _default_loader(self, symbol: str, start: date, end: date) -> list[Candle]:
        from app.services import market as market_service

        sourced = await market_service.fetch_ohlcv(symbol, period="2y", adjusted=True)
        if not sourced:
            return []
        candles = list(sourced.value)
        return [c for c in candles if start <= c.timestamp.date() <= end]

    async def generate(self, config: BacktestConfig) -> list[dict[str, Any]]:
        start = _parse_day(config.start)
        end = _parse_day(config.end)
        forward_days = max(1, config.forward_days)
        labels: list[dict[str, Any]] = []

        for symbol in config.symbols:
            candles = await self._load_candles(symbol, start, end)
            if len(candles) < self._min_history_bars + forward_days:
                continue

            for i in range(self._min_history_bars - 1, len(candles) - forward_days):
                window = candles[: i + 1]
                as_of = window[-1].timestamp.date()
                if as_of < start or as_of > end:
                    continue

                signal = score_symbol(symbol, window, candle_source="backtest")
                fwd = _forward_return(candles, i, forward_days)
                if fwd is None:
                    continue

                hit = _label_hit(signal.action, fwd)
                row: dict[str, Any] = {
                    "symbol": symbol.upper(),
                    "as_of": as_of.isoformat(),
                    "action": signal.action,
                    "confidence": signal.confidence,
                    "trend": signal.trend,
                    "forward_days": forward_days,
                    "forward_return": round(fwd, 6),
                    "hit": hit,
                    "skipped": signal.action == "Avoid",
                }
                if signal.action in {"Buy", "Sell"} and hit is not None:
                    row["pnl"] = fwd if signal.action == "Buy" else -fwd
                labels.append(row)

        return labels
