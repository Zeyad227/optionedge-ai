"""Technical indicators — hand-rolled on pandas/numpy (pandas-ta is unmaintained)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.models import Candle


def candles_to_df(candles: list[Candle]) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
    )
    return df.sort_values("timestamp").reset_index(drop=True)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI.

    An unbroken run of up-bars drives ``avg_loss`` to zero. Masking that to NaN
    would discard the strongest possible reading, so the zero-division is left
    to produce ``inf`` (RSI 100); a genuinely flat series resolves to 50.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    flat = (avg_gain == 0) & (avg_loss == 0)
    return out.mask(flat, 50.0)


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, fast) - ema(close, slow)
    signal_line = ema(line, signal)
    hist = line - signal_line
    return line, signal_line, hist


def stochastic_rsi(
    close: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
) -> pd.Series:
    r = rsi(close, rsi_period)
    low = r.rolling(stoch_period).min()
    high = r.rolling(stoch_period).max()
    return (r - low) / (high - low).replace(0, np.nan) * 100


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return (tp - sma) / (0.015 * mad.replace(0, np.nan))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def directional_movement(
    df: pd.DataFrame,
    period: int = 14,
    *,
    atr_series: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (+DI, -DI, ADX).

    ADX alone is unsigned — it measures how strongly a market trends, not which
    way. Callers that need direction must compare +DI against -DI, so both legs
    are returned rather than discarded.
    """
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr_atr = atr(df, period) if atr_series is None else atr_series

    def _smooth(values) -> pd.Series:
        return pd.Series(values, index=df.index).ewm(
            alpha=1 / period, min_periods=period, adjust=False
        ).mean()

    plus_di = 100 * _smooth(plus_dm) / tr_atr.replace(0, np.nan)
    minus_di = 100 * _smooth(minus_dm) / tr_atr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    adx_line = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return plus_di, minus_di, adx_line


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return directional_movement(df, period)[2]


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    atr_v = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr_v
    lower = hl2 - multiplier * atr_v
    st = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(1, index=df.index)
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = upper.iloc[i]
            continue
        if df["close"].iloc[i] > st.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < st.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
        if direction.iloc[i] == 1:
            st.iloc[i] = max(lower.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == 1 else lower.iloc[i]
        else:
            st.iloc[i] = min(upper.iloc[i], st.iloc[i - 1]) if direction.iloc[i - 1] == -1 else upper.iloc[i]
    return st


def bollinger(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    return mid + num_std * std, mid, mid - num_std * std


def keltner(
    df: pd.DataFrame, period: int = 20, multiplier: float = 1.5
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = ema(df["close"], period)
    atr_v = atr(df, period)
    return mid + multiplier * atr_v, mid, mid - multiplier * atr_v


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    mfv = mfm * df["volume"]
    return mfv.rolling(period).sum() / df["volume"].rolling(period).sum().replace(0, np.nan)


def vwap(df: pd.DataFrame) -> pd.Series:
    """Anchored VWAP measured from the first bar of the series.

    Only meaningful when the series start is itself meaningful (a session open,
    an earnings date, a swing low). On a multi-month daily series this converges
    on a long-run average and should not be read as "the" VWAP — use
    :func:`rolling_vwap` for that.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3
    return (typical * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, np.nan)


def rolling_vwap(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Volume-weighted average price over a trailing window."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = (typical * df["volume"]).rolling(period).sum()
    vol = df["volume"].rolling(period).sum().replace(0, np.nan)
    return pv / vol


def compute_all(candles: list[Candle]) -> dict:
    """Return the latest indicator snapshot.

    ``vwap`` is the trailing 20-session volume-weighted price, which is what a
    daily chart implies by "VWAP". The whole-history anchored figure is still
    reported separately as ``vwap_anchored``.
    """
    df = candles_to_df(candles)
    close = df["close"]
    macd_line, macd_signal, macd_hist = macd(close)
    bb_upper, bb_mid, bb_lower = bollinger(close)
    kc_upper, kc_mid, kc_lower = keltner(df)
    atr_14 = atr(df)
    di_plus, di_minus, adx_line = directional_movement(df, atr_series=atr_14)

    latest = {
        "ema_9": _last(ema(close, 9)),
        "ema_20": _last(ema(close, 20)),
        "ema_50": _last(ema(close, 50)),
        "ema_200": _last(ema(close, 200)),
        "rsi": _last(rsi(close)),
        "macd": _last(macd_line),
        "macd_signal": _last(macd_signal),
        "macd_hist": _last(macd_hist),
        "stoch_rsi": _last(stochastic_rsi(close)),
        "cci": _last(cci(df)),
        "adx": _last(adx_line),
        "di_plus": _last(di_plus),
        "di_minus": _last(di_minus),
        "atr": _last(atr_14),
        "supertrend": _last(supertrend(df)),
        "bb_upper": _last(bb_upper),
        "bb_mid": _last(bb_mid),
        "bb_lower": _last(bb_lower),
        "kc_upper": _last(kc_upper),
        "kc_mid": _last(kc_mid),
        "kc_lower": _last(kc_lower),
        "obv": _last(obv(df)),
        "cmf": _last(cmf(df)),
        "vwap": _last(rolling_vwap(df)),
        "vwap_anchored": _last(vwap(df)),
        "close": float(close.iloc[-1]),
        "volume": float(df["volume"].iloc[-1]),
        "avg_volume_20": float(df["volume"].tail(20).mean()) if len(df) >= 20 else None,
    }
    relative_volume = None
    if latest["avg_volume_20"]:
        relative_volume = latest["volume"] / latest["avg_volume_20"]
    latest["relative_volume"] = relative_volume
    return latest


def _last(series: pd.Series) -> float | None:
    if series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)
