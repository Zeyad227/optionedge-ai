"""Shared OHLCV fixture for indicator/pattern goldens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.models import Candle

# Close series used to seed the golden candle set (wicks ±0.5 around open/close).
FIXTURE_CLOSES = [
    100,
    101,
    102,
    101,
    100,
    99,
    98,
    99,
    100,
    102,
    104,
    105,
    104,
    103,
    105,
    107,
    108,
    106,
    105,
    107,
    109,
    110,
    108,
    107,
    109,
    111,
    112,
    113,
    111,
    110,
]

# Hand-checked / implementation goldens for FIXTURE_CLOSES (latest bar).
INDICATOR_GOLDENS = {
    "ema_9": 109.99306593767957,
    "ema_20": 107.83033760470818,
    "rsi": 63.1254297473895,
    "macd": 2.4742758482110645,
    "macd_signal": 2.2723798750702993,
    "macd_hist": 0.20189597314076524,
    "stoch_rsi": 0.0,
    "cci": 77.934272300469,
    "atr": 2.2772425707355732,
    "adx": 39.33958212092679,
    "supertrend": 105.40232467449685,
    "bb_upper": 113.47107123140007,
    "bb_mid": 107.7,  # SMA(20) of last 20 closes — hand-checked: 2154/20
    "bb_lower": 101.92892876859993,
    "kc_upper": 110.99339254230222,
    "kc_mid": 107.83033760470818,
    "kc_lower": 104.66728266711414,
    "obv": 5_750_000.0,
    "cmf": 0.1295676429567643,
    "vwap": 105.38854924793789,
}


def fixture_candles() -> list[Candle]:
    candles: list[Candle] = []
    price = float(FIXTURE_CLOSES[0])
    base = datetime(2024, 1, 2, tzinfo=UTC)
    for i, close in enumerate(FIXTURE_CLOSES):
        o = price
        cl = float(close)
        candles.append(
            Candle(
                timestamp=base + timedelta(days=i),
                open=o,
                high=max(o, cl) + 0.5,
                low=min(o, cl) - 0.5,
                close=cl,
                volume=1_000_000 + i * 10_000,
            )
        )
        price = cl
    return candles


def make_candle(
    *,
    day: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1_000_000,
) -> Candle:
    return Candle(
        timestamp=datetime(2024, 1, 2, tzinfo=UTC) + timedelta(days=day),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )
