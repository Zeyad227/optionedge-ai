"""Contract tests for HTTP providers using respx-recorded fixtures (offline)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from app.providers.alpaca import AlpacaOptionsProvider
from app.providers.alpha_vantage import AlphaVantageMarketProvider
from app.providers.finnhub import FinnhubNewsProvider
from app.providers.fred import FredMacroProvider
from app.providers.http import http_get
from app.providers.sec_edgar import ATOM, SecEdgarInsiderProvider
from app.providers.stooq import StooqMarketProvider
from app.providers.tradier import TradierOptionsProvider
from app.providers.twelve_data import TwelveDataMarketProvider

STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2026-07-30,100,102,99,101,1000000
2026-07-31,101,103,100,102,1100000
2026-08-01,102,104,101,103,1200000
"""

ALPACA_CONTRACTS = {
    "option_contracts": [
        {
            "symbol": "AAPL260821C00150000",
            "expiration_date": "2026-08-21",
            "strike_price": "150",
            "type": "call",
            "open_interest": "500",
        },
        {
            "symbol": "AAPL260821P00150000",
            "expiration_date": "2026-08-21",
            "strike_price": "150",
            "type": "put",
            "open_interest": "400",
        },
    ]
}

ALPACA_SNAPSHOTS = {
    "snapshots": {
        "AAPL260821C00150000": {
            "impliedVolatility": "0.32",
            "greeks": {
                "delta": "0.45",
                "gamma": "0.02",
                "theta": "-0.05",
                "vega": "0.12",
                "rho": "0.01",
            },
            "latestQuote": {"bp": "3.1", "ap": "3.2"},
            "latestTrade": {"p": "3.15"},
        },
        "AAPL260821P00150000": {
            "impliedVolatility": "0.34",
            "greeks": {"delta": "-0.42"},
            "latestQuote": {"bp": "2.8", "ap": "2.9"},
            "latestTrade": {"p": "2.85"},
        },
    }
}

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>4 - Example Corp. (0001234567) (Issuer)</title>
    <link href="https://www.sec.gov/Archives/edgar/data/123/xslF345X03/primary_doc.xml"/>
    <updated>2026-08-01T15:00:00-04:00</updated>
  </entry>
</feed>
"""


@pytest.fixture
def fast_sleep(monkeypatch: pytest.MonkeyPatch):
    async def _noop(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.providers.http.asyncio.sleep", _noop)


@respx.mock
@pytest.mark.asyncio
async def test_http_get_retries_429_then_succeeds(fast_sleep):
    route = respx.get("https://example.com/rate").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}, text="slow down"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    resp = await http_get("https://example.com/rate")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_stooq_ohlcv_contract(fast_sleep):
    respx.get(url__regex=r"https://stooq\.com/q/d/l/\?s=aapl\.us&i=d").mock(
        return_value=httpx.Response(200, text=STOOQ_CSV)
    )
    provider = StooqMarketProvider()
    result = await provider.get_ohlcv("AAPL", period="1mo")
    assert result is not None
    assert result.source == "stooq"
    assert len(result.value) == 3
    assert result.value[-1].close == 103.0


@respx.mock
@pytest.mark.asyncio
async def test_alpaca_chain_contract(fast_sleep):
    respx.get("https://paper-api.alpaca.markets/v2/options/contracts").mock(
        return_value=httpx.Response(200, json=ALPACA_CONTRACTS)
    )
    respx.get("https://data.alpaca.markets/v1beta1/options/snapshots").mock(
        return_value=httpx.Response(200, json=ALPACA_SNAPSHOTS)
    )
    provider = AlpacaOptionsProvider("key", "secret", feed="indicative")
    chain = await provider.get_chain("AAPL", expiration=date(2026, 8, 21))
    assert chain is not None
    assert chain.source == "alpaca"
    assert len(chain.value) == 2
    call = next(c for c in chain.value if c.option_type == "call")
    assert call.implied_volatility == pytest.approx(0.32)
    assert call.delta == pytest.approx(0.45)
    assert call.greeks_source == "alpaca"


@respx.mock
@pytest.mark.asyncio
async def test_finnhub_news_contract(fast_sleep):
    respx.get("https://finnhub.io/api/v1/company-news").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "headline": "AAPL rises",
                    "url": "https://example.com/aapl",
                    "source": "Finnhub",
                    "datetime": 1722513600,
                    "summary": "up",
                }
            ],
        )
    )
    provider = FinnhubNewsProvider("token")
    news = await provider.get_news("AAPL", limit=5)
    assert news is not None
    assert news.source == "finnhub"
    assert news.value[0].title == "AAPL rises"
    assert "AAPL" in news.value[0].related_symbols


@respx.mock
@pytest.mark.asyncio
async def test_tradier_expirations_contract(fast_sleep):
    respx.get("https://sandbox.tradier.com/v1/markets/options/expirations").mock(
        return_value=httpx.Response(200, json={"expirations": {"date": ["2026-08-21", "2026-09-18"]}})
    )
    provider = TradierOptionsProvider("sandbox-token")
    exps = await provider.get_expirations("AAPL")
    assert exps is not None
    assert exps.source == "tradier-sandbox"
    assert exps.value[0] == date(2026, 8, 21)


@respx.mock
@pytest.mark.asyncio
async def test_alpha_vantage_quote_contract(fast_sleep):
    respx.get("https://www.alphavantage.co/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "Global Quote": {
                    "05. price": "190.5",
                    "10. change percent": "1.25%",
                    "06. volume": "1000000",
                }
            },
        )
    )
    provider = AlphaVantageMarketProvider("demo")
    quote = await provider.get_quote("AAPL")
    assert quote is not None
    assert quote.source == "alpha-vantage"
    assert quote.value.price == pytest.approx(190.5)
    assert "25 requests/day" in (quote.note or "")


@respx.mock
@pytest.mark.asyncio
async def test_twelve_data_quote_contract(fast_sleep):
    respx.get("https://api.twelvedata.com/quote").mock(
        return_value=httpx.Response(
            200,
            json={"close": "200", "previous_close": "195", "volume": "500000"},
        )
    )
    provider = TwelveDataMarketProvider("key")
    quote = await provider.get_quote("MSFT")
    assert quote is not None
    assert quote.source == "twelve-data"
    assert quote.value.price == pytest.approx(200.0)
    assert quote.value.change_pct == pytest.approx((200 - 195) / 195 * 100)


@respx.mock
@pytest.mark.asyncio
async def test_fred_series_contract(fast_sleep):
    respx.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-07-01", "value": "3.1"},
                    {"date": "2026-06-01", "value": "."},
                ]
            },
        )
    )
    provider = FredMacroProvider("fred-key")
    series = await provider.get_series("DGS10", limit=2)
    assert series is not None
    assert series.source == "fred"
    assert len(series.value) == 1
    assert series.value[0]["value"] == pytest.approx(3.1)


@respx.mock
@pytest.mark.asyncio
async def test_sec_edgar_atom_contract(fast_sleep):
    respx.get(ATOM).mock(return_value=httpx.Response(200, text=ATOM_XML))
    provider = SecEdgarInsiderProvider("Test Agent test@example.com")
    filings = await provider.get_recent(limit=10)
    assert filings is not None
    assert filings.source == "sec-edgar"
    assert filings.value[0].company == "Example Corp."
    assert filings.value[0].sentiment == "Neutral"
