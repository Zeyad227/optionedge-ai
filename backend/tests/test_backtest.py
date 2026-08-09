"""Backtest harness tests — synthetic candles, no network."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.greeks import probability_itm_from_delta
from app.backtest import DirectionalBacktester, HistoricalLabelGenerator, compute_metrics
from app.backtest.metrics import compute_metrics as metrics_fn
from app.schemas.models import Candle
from app.stubs import BacktestConfig


def _trend_series(*, drift: float, bars: int = 160) -> list[Candle]:
    out: list[Candle] = []
    price = 100.0
    for i in range(bars):
        price *= 1 + drift
        out.append(
            Candle(
                timestamp=datetime(2024, 6, 1, tzinfo=UTC) + timedelta(days=i),
                open=price * 0.998,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1_000_000.0,
            )
        )
    return out


@pytest.mark.asyncio
async def test_label_generator_produces_rows():
    candles = _trend_series(drift=0.003)

    async def loader(symbol: str, start, end):
        return candles

    gen = HistoricalLabelGenerator(candle_loader=loader, min_history_bars=60)
    config = BacktestConfig(
        strategy="directional_factors",
        start="2024-07-01",
        end="2024-09-01",
        symbols=["TEST"],
        forward_days=2,
    )
    labels = await gen.generate(config)
    assert labels
    assert all("as_of" in row and "action" in row for row in labels)


@pytest.mark.asyncio
async def test_label_generator_counts_buy_outcomes(monkeypatch):
    candles = _trend_series(drift=0.004)
    from datetime import UTC, datetime

    from app.schemas.models import SignalResponse

    def fake_score(symbol, window, **kwargs):
        return SignalResponse(
            symbol=symbol,
            action="Buy",
            trend="Bullish",
            confidence=55.0,
            generated_at=datetime.now(UTC),
            sources=["backtest"],
        )

    monkeypatch.setattr("app.backtest.labels.score_symbol", fake_score)

    async def loader(symbol: str, start, end):
        return candles

    gen = HistoricalLabelGenerator(candle_loader=loader, min_history_bars=60)
    config = BacktestConfig(
        strategy="directional_factors",
        start="2024-07-01",
        end="2024-09-01",
        symbols=["TEST"],
        forward_days=2,
    )
    labels = await gen.generate(config)
    traded = [row for row in labels if row.get("pnl") is not None]
    assert traded
    assert all(row["action"] == "Buy" for row in traded)


@pytest.mark.asyncio
async def test_directional_backtester_metrics(monkeypatch):
    candles = _trend_series(drift=0.004)
    from datetime import UTC, datetime

    from app.schemas.models import SignalResponse

    def fake_score(symbol, window, **kwargs):
        return SignalResponse(
            symbol=symbol,
            action="Buy",
            trend="Bullish",
            confidence=55.0,
            generated_at=datetime.now(UTC),
            sources=["backtest"],
        )

    monkeypatch.setattr("app.backtest.labels.score_symbol", fake_score)

    async def loader(symbol: str, start, end):
        return candles

    gen = HistoricalLabelGenerator(candle_loader=loader, min_history_bars=60)
    config = BacktestConfig(
        strategy="directional_factors",
        start="2024-07-01",
        end="2024-09-01",
        symbols=["TEST"],
        forward_days=2,
    )
    result = await DirectionalBacktester(label_generator=gen).run(config)
    assert result.sample_count > 0
    assert 0 <= result.win_rate <= 100


def test_compute_metrics_empty():
    result = metrics_fn([])
    assert result.sample_count == 0
    assert result.win_rate == 0.0


def test_compute_metrics_win_rate():
    trades = [{"pnl": 0.02}, {"pnl": -0.01}, {"pnl": 0.015}]
    result = compute_metrics(trades)
    assert result.sample_count == 3
    assert result.win_rate == pytest.approx(66.67, rel=0.01)


def test_probability_itm_from_delta():
    assert probability_itm_from_delta(0.35, "call") == 0.35
    assert probability_itm_from_delta(-0.42, "put") == pytest.approx(0.42)
    assert probability_itm_from_delta(None, "call") is None
