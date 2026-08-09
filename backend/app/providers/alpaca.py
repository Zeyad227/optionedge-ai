"""Alpaca options provider — primary source for chains, IV, and greeks."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.analysis.options_expiry import pick_expiration
from app.config import get_settings
from app.providers.base import OptionsProvider
from app.providers.http import http_get
from app.schemas.models import OptionContract
from app.schemas.sourced import Sourced
from app.utils.market_calendar import market_today

DATA_URL = "https://data.alpaca.markets"
TRADING_URL = "https://paper-api.alpaca.markets"


class AlpacaOptionsProvider(OptionsProvider):
    name = "alpaca"

    def __init__(self, key_id: str, secret: str, *, feed: str = "indicative") -> None:
        self.key_id = key_id
        self.secret = secret
        self.feed = feed
        self._headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret,
        }

    async def _fetch_contract_pages(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        metas: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params["page_token"] = page_token
            resp = await http_get(
                f"{TRADING_URL}/v2/options/contracts",
                headers=self._headers,
                params=page_params,
                timeout=45.0,
            )
            resp.raise_for_status()
            payload = resp.json()
            metas.extend(payload.get("option_contracts") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return metas

    async def get_expirations(self, symbol: str) -> Sourced[list[date]] | None:
        params = {
            "underlying_symbols": symbol.upper(),
            "status": "active",
            "limit": 1000,
        }
        contracts = await self._fetch_contract_pages(params)
        expirations = sorted(
            {
                date.fromisoformat(c["expiration_date"])
                for c in contracts
                if c.get("expiration_date")
            }
        )
        if not expirations:
            return None
        return Sourced.of(
            expirations,
            self.name,
            url="https://docs.alpaca.markets/docs/options-contracts",
            note=f"feed={self.feed}",
        )

    async def get_chain(
        self,
        symbol: str,
        expiration: date | None = None,
    ) -> Sourced[list[OptionContract]] | None:
        params: dict[str, Any] = {
            "underlying_symbols": symbol.upper(),
            "status": "active",
            "limit": 1000,
        }
        if expiration:
            params["expiration_date"] = expiration.isoformat()

        metas = await self._fetch_contract_pages(params)
        if not metas:
            return None

        if expiration is None:
            expirations = sorted(
                {date.fromisoformat(c["expiration_date"]) for c in metas if c.get("expiration_date")}
            )
            min_dte = get_settings().min_option_dte
            chosen = pick_expiration(expirations, min_dte=min_dte, as_of=market_today())
            if chosen is None:
                return None
            chosen_str = chosen.isoformat()
            metas = [c for c in metas if c["expiration_date"] == chosen_str]

        by_symbol = {c["symbol"]: c for c in metas}
        symbols = list(by_symbol.keys())
        snapshots: dict[str, Any] = {}
        for i in range(0, len(symbols), 100):
            batch = symbols[i : i + 100]
            snap_resp = await http_get(
                f"{DATA_URL}/v1beta1/options/snapshots",
                headers=self._headers,
                params={
                    "symbols": ",".join(batch),
                    "feed": self.feed,
                    "limit": 1000,
                },
                timeout=45.0,
            )
            if snap_resp.status_code == 403:
                continue
            snap_resp.raise_for_status()
            snapshots.update(snap_resp.json().get("snapshots") or {})

        contracts: list[OptionContract] = []
        for sym, meta in by_symbol.items():
            snap = snapshots.get(sym) or {}
            greeks = snap.get("greeks") or {}
            quote = snap.get("latestQuote") or {}
            trade = snap.get("latestTrade") or {}
            daily_bar = snap.get("dailyBar") or {}
            contracts.append(
                OptionContract(
                    symbol=sym,
                    underlying=symbol.upper(),
                    expiration=date.fromisoformat(meta["expiration_date"]),
                    strike=float(meta["strike_price"]),
                    option_type=meta["type"].lower(),  # type: ignore[arg-type]
                    bid=_f(quote.get("bp")),
                    ask=_f(quote.get("ap")),
                    last=_f(trade.get("p")),
                    volume=_i(daily_bar.get("v")),
                    open_interest=_i(meta.get("open_interest")),
                    implied_volatility=_f(snap.get("impliedVolatility")),
                    delta=_f(greeks.get("delta")),
                    gamma=_f(greeks.get("gamma")),
                    theta=_f(greeks.get("theta")),
                    vega=_f(greeks.get("vega")),
                    rho=_f(greeks.get("rho")),
                    greeks_source=self.name if greeks else None,
                )
            )

        return Sourced.of(
            contracts,
            self.name,
            url="https://docs.alpaca.markets/reference/optionchain",
            note=(
                "Free Basic plan uses indicative live quotes (not OPRA). "
                "Historical bars older than 15 minutes are real OPRA data."
            ),
        )

    async def list_call_contracts(
        self,
        symbol: str,
        *,
        expiration_gte: date,
    ) -> list[dict[str, Any]]:
        """List active call contracts expiring on or after ``expiration_gte``."""
        params: dict[str, Any] = {
            "underlying_symbols": symbol.upper(),
            "status": "active",
            "type": "call",
            "expiration_date_gte": expiration_gte.isoformat(),
            "limit": 1000,
        }
        return await self._fetch_contract_pages(params)

    async def pick_atm_call(
        self,
        symbol: str,
        spot: float,
        as_of: date,
    ) -> dict[str, Any] | None:
        """Nearest ATM call with expiry at least ~1 week after ``as_of``."""
        min_expiry = as_of + timedelta(days=7)
        contracts = await self.list_call_contracts(symbol, expiration_gte=min_expiry)
        if not contracts:
            return None
        return min(
            contracts,
            key=lambda c: (
                abs(float(c["strike_price"]) - spot),
                c.get("expiration_date") or "9999-99-99",
            ),
        )

    async def get_option_bars(
        self,
        option_symbols: list[str],
        start: date,
        end: date,
        *,
        timeframe: str = "1Day",
    ) -> dict[str, list[dict[str, Any]]]:
        """Historical OPRA option bars (free tier blocks only the latest ~15 minutes)."""
        if not option_symbols:
            return {}
        out: dict[str, list[dict[str, Any]]] = {}
        for i in range(0, len(option_symbols), 100):
            batch = option_symbols[i : i + 100]
            resp = await http_get(
                f"{DATA_URL}/v1beta1/options/bars",
                headers=self._headers,
                params={
                    "symbols": ",".join(batch),
                    "timeframe": timeframe,
                    "start": f"{start.isoformat()}T00:00:00Z",
                    "end": f"{end.isoformat()}T23:59:59Z",
                    "limit": 10000,
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            bars = resp.json().get("bars") or {}
            for sym, rows in bars.items():
                out[sym] = list(rows)
        return out


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    f = _f(v)
    return int(f) if f is not None else None
