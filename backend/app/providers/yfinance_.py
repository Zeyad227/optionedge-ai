"""Yahoo Finance market + options provider (unofficial; can break without notice)."""

from __future__ import annotations

import asyncio
from datetime import UTC, date

import yfinance as yf

from app.analysis.options_expiry import pick_expiration
from app.config import get_settings
from app.providers.base import MarketDataProvider, OptionsProvider
from app.providers.numeric import finite as _f, finite_int as _i
from app.schemas.models import Candle, OptionContract, Quote
from app.schemas.sourced import Sourced
from app.utils.market_calendar import market_today


def _run(fn, *args, **kwargs):
    return asyncio.to_thread(fn, *args, **kwargs)


class YFinanceMarketProvider(MarketDataProvider):
    name = "yfinance"

    async def get_quote(self, symbol: str) -> Sourced[Quote] | None:
        def _fetch() -> Quote | None:
            t = yf.Ticker(symbol)
            info = t.fast_info if hasattr(t, "fast_info") else {}
            price = _f(getattr(info, "last_price", None) or getattr(info, "lastPrice", None))
            if price is None:
                hist = t.history(period="5d")
                closes = hist["Close"].dropna() if not hist.empty else hist
                if closes.empty:
                    return None
                price = _f(closes.iloc[-1])
            if price is None:
                return None
            prev = _f(getattr(info, "previous_close", None) or getattr(info, "previousClose", None))
            change = None
            if prev:
                change = (price - prev) / prev * 100
            return Quote(
                symbol=symbol.upper(),
                price=price,
                change_pct=change,
                volume=float(getattr(info, "last_volume", 0) or 0) or None,
                market_cap=float(getattr(info, "market_cap", 0) or 0) or None,
            )

        quote = await _run(_fetch)
        if quote is None:
            return None
        return Sourced.of(quote, self.name, url=f"https://finance.yahoo.com/quote/{symbol}")

    async def get_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
        adjusted: bool = True,
    ) -> Sourced[list[Candle]] | None:
        def _fetch() -> list[Candle]:
            t = yf.Ticker(symbol)
            df = t.history(period=period, interval=interval, auto_adjust=adjusted)
            candles: list[Candle] = []
            for idx, row in df.iterrows():
                # Yahoo emits a placeholder row for the session in progress whose
                # OHLC is NaN until the bar closes. Keeping it would make the last
                # candle — the one every indicator reads — undefined.
                ohlc = [_f(row[field]) for field in ("Open", "High", "Low", "Close")]
                if any(value is None for value in ohlc):
                    continue
                open_, high, low, close = ohlc
                ts = idx.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                candles.append(
                    Candle(
                        timestamp=ts,
                        open=open_,
                        high=high,
                        low=low,
                        close=close,
                        volume=_f(row["Volume"]) or 0.0,
                    )
                )
            return candles

        candles = await _run(_fetch)
        if not candles:
            return None
        return Sourced.of(candles, self.name, url=f"https://finance.yahoo.com/quote/{symbol}/history")


class YFinanceOptionsProvider(OptionsProvider):
    name = "yfinance"

    async def get_expirations(self, symbol: str) -> Sourced[list[date]] | None:
        def _fetch() -> list[date]:
            t = yf.Ticker(symbol)
            return [date.fromisoformat(e) for e in (t.options or [])]

        expirations = await _run(_fetch)
        if not expirations:
            return None
        return Sourced.of(expirations, self.name)

    async def get_chain(
        self,
        symbol: str,
        expiration: date | None = None,
    ) -> Sourced[list[OptionContract]] | None:
        def _fetch() -> list[OptionContract]:
            t = yf.Ticker(symbol)
            expiries = list(t.options or [])
            if not expiries:
                return []
            exp_dates = [date.fromisoformat(e) for e in expiries]
            if expiration:
                exp = expiration.isoformat()
            else:
                min_dte = get_settings().min_option_dte
                chosen = pick_expiration(exp_dates, min_dte=min_dte, as_of=market_today())
                exp = chosen.isoformat() if chosen else expiries[0]
            if exp not in expiries:
                exp = expiries[0]
            chain = t.option_chain(exp)
            exp_date = date.fromisoformat(exp)
            contracts: list[OptionContract] = []
            for kind, frame in (("call", chain.calls), ("put", chain.puts)):
                for _, row in frame.iterrows():
                    contracts.append(
                        OptionContract(
                            symbol=str(row.get("contractSymbol", "")),
                            underlying=symbol.upper(),
                            expiration=exp_date,
                            strike=float(row["strike"]),
                            option_type=kind,  # type: ignore[arg-type]
                            bid=_f(row.get("bid")),
                            ask=_f(row.get("ask")),
                            last=_f(row.get("lastPrice")),
                            volume=_i(row.get("volume")),
                            open_interest=_i(row.get("openInterest")),
                            implied_volatility=_f(row.get("impliedVolatility")),
                            greeks_source=None,
                        )
                    )
            return contracts

        contracts = await _run(_fetch)
        if not contracts:
            return None
        return Sourced.of(
            contracts,
            self.name,
            note="yfinance does not supply reliable greeks; use Alpaca or Black-Scholes fallback",
        )
