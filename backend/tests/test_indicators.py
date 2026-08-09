"""Indicator unit tests against fixture goldens."""

from __future__ import annotations

import math

from app.analysis.greeks import black_scholes, implied_volatility
from app.analysis.indicators import (
    adx,
    atr,
    bollinger,
    candles_to_df,
    cci,
    cmf,
    compute_all,
    ema,
    keltner,
    macd,
    obv,
    rsi,
    stochastic_rsi,
    supertrend,
    vwap,
)
from tests.fixtures.ohlcv_fixture import INDICATOR_GOLDENS, fixture_candles

TOL = 1e-9


def test_ema_rsi_macd_match_goldens():
    df = candles_to_df(fixture_candles())
    close = df["close"]
    assert math.isclose(ema(close, 9).iloc[-1], INDICATOR_GOLDENS["ema_9"], rel_tol=TOL)
    assert math.isclose(ema(close, 20).iloc[-1], INDICATOR_GOLDENS["ema_20"], rel_tol=TOL)
    assert math.isclose(rsi(close).iloc[-1], INDICATOR_GOLDENS["rsi"], rel_tol=TOL)
    line, signal, hist = macd(close)
    assert math.isclose(line.iloc[-1], INDICATOR_GOLDENS["macd"], rel_tol=TOL)
    assert math.isclose(signal.iloc[-1], INDICATOR_GOLDENS["macd_signal"], rel_tol=TOL)
    assert math.isclose(hist.iloc[-1], INDICATOR_GOLDENS["macd_hist"], rel_tol=TOL)
    assert math.isclose(hist.iloc[-1], line.iloc[-1] - signal.iloc[-1], rel_tol=TOL)


def test_stoch_rsi_cci_adx_atr_supertrend_goldens():
    df = candles_to_df(fixture_candles())
    close = df["close"]
    assert math.isclose(
        stochastic_rsi(close).iloc[-1], INDICATOR_GOLDENS["stoch_rsi"], abs_tol=TOL
    )
    assert math.isclose(cci(df).iloc[-1], INDICATOR_GOLDENS["cci"], rel_tol=TOL)
    assert math.isclose(atr(df).iloc[-1], INDICATOR_GOLDENS["atr"], rel_tol=TOL)
    assert math.isclose(adx(df).iloc[-1], INDICATOR_GOLDENS["adx"], rel_tol=TOL)
    assert math.isclose(supertrend(df).iloc[-1], INDICATOR_GOLDENS["supertrend"], rel_tol=TOL)


def test_bollinger_mid_is_sma20_hand_checked():
    df = candles_to_df(fixture_candles())
    upper, mid, lower = bollinger(df["close"])
    # Last 20 closes sum to 2154 → SMA = 107.7
    assert math.isclose(mid.iloc[-1], 107.7, abs_tol=1e-12)
    assert math.isclose(upper.iloc[-1], INDICATOR_GOLDENS["bb_upper"], rel_tol=TOL)
    assert math.isclose(lower.iloc[-1], INDICATOR_GOLDENS["bb_lower"], rel_tol=TOL)


def test_keltner_obv_cmf_vwap_goldens():
    df = candles_to_df(fixture_candles())
    ku, km, kl = keltner(df)
    assert math.isclose(ku.iloc[-1], INDICATOR_GOLDENS["kc_upper"], rel_tol=TOL)
    assert math.isclose(km.iloc[-1], INDICATOR_GOLDENS["kc_mid"], rel_tol=TOL)
    assert math.isclose(kl.iloc[-1], INDICATOR_GOLDENS["kc_lower"], rel_tol=TOL)
    assert math.isclose(obv(df).iloc[-1], INDICATOR_GOLDENS["obv"], abs_tol=TOL)
    assert math.isclose(cmf(df).iloc[-1], INDICATOR_GOLDENS["cmf"], rel_tol=TOL)
    assert math.isclose(vwap(df).iloc[-1], INDICATOR_GOLDENS["vwap"], rel_tol=TOL)


def test_compute_all_exposes_full_indicator_set():
    snap = compute_all(fixture_candles())
    required = {
        "ema_9",
        "ema_20",
        "ema_50",
        "ema_200",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "stoch_rsi",
        "cci",
        "adx",
        "atr",
        "supertrend",
        "bb_upper",
        "bb_mid",
        "bb_lower",
        "kc_upper",
        "kc_mid",
        "kc_lower",
        "obv",
        "cmf",
        "vwap",
        "relative_volume",
    }
    assert required.issubset(snap.keys())
    assert snap["bb_mid"] == INDICATOR_GOLDENS["bb_mid"]
    assert snap["rsi"] is not None
    assert 0 <= snap["rsi"] <= 100


def test_rsi_bounded_on_fixture():
    df = candles_to_df(fixture_candles())
    values = rsi(df["close"]).dropna()
    assert values.min() >= 0
    assert values.max() <= 100


def test_black_scholes_call_delta_between_0_1():
    g = black_scholes(100, 100, 0.5, 0.04, 0.25, "call")
    assert 0 < g.delta < 1
    assert g.gamma > 0
    assert g.vega > 0


def test_iv_roundtrip():
    spot, strike, t, r, iv = 100.0, 100.0, 0.5, 0.04, 0.3
    price = black_scholes(spot, strike, t, r, iv, "call").price
    solved = implied_volatility(price, spot, strike, t, r, "call")
    assert solved is not None
    assert abs(solved - iv) < 1e-3
