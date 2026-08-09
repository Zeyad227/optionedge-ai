"""Tradier sandbox options provider — chains with OI/volume; no greeks in sandbox."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.providers.base import OptionsProvider
from app.providers.http import http_get
from app.schemas.models import OptionContract
from app.schemas.sourced import Sourced

BASE = "https://sandbox.tradier.com/v1"


class TradierOptionsProvider(OptionsProvider):
    name = "tradier-sandbox"

    def __init__(self, token: str) -> None:
        self.token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def get_expirations(self, symbol: str) -> Sourced[list[date]] | None:
        resp = await http_get(
            f"{BASE}/markets/options/expirations",
            headers=self._headers,
            params={"symbol": symbol.upper()},
            timeout=30.0,
        )
        resp.raise_for_status()
        payload = resp.json().get("expirations") or {}
        dates = payload.get("date") or []
        if isinstance(dates, str):
            dates = [dates]
        expirations = [date.fromisoformat(d) for d in dates]
        if not expirations:
            return None
        return Sourced.of(
            expirations,
            self.name,
            note="Sandbox is 15-minute delayed; greeks are NOT available in sandbox",
        )

    async def get_chain(
        self,
        symbol: str,
        expiration: date | None = None,
    ) -> Sourced[list[OptionContract]] | None:
        if expiration is None:
            exp_resp = await self.get_expirations(symbol)
            if not exp_resp or not exp_resp.value:
                return None
            expiration = exp_resp.value[0]
        resp = await http_get(
            f"{BASE}/markets/options/chains",
            headers=self._headers,
            params={"symbol": symbol.upper(), "expiration": expiration.isoformat()},
            timeout=45.0,
        )
        resp.raise_for_status()
        options = (resp.json().get("options") or {}).get("option") or []
        if isinstance(options, dict):
            options = [options]

        contracts = [
            OptionContract(
                symbol=str(o.get("symbol", "")),
                underlying=symbol.upper(),
                expiration=date.fromisoformat(o["expiration_date"]),
                strike=float(o["strike"]),
                option_type=str(o.get("option_type", "call")).lower(),  # type: ignore[arg-type]
                bid=_f(o.get("bid")),
                ask=_f(o.get("ask")),
                last=_f(o.get("last")),
                volume=_i(o.get("volume")),
                open_interest=_i(o.get("open_interest")),
                greeks_source=None,
            )
            for o in options
        ]
        if not contracts:
            return None
        return Sourced.of(
            contracts,
            self.name,
            url="https://docs.tradier.com/docs/market-data",
            note="Sandbox: delayed data, no greeks (ORATS greeks only on funded brokerage API)",
        )


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    f = _f(v)
    return int(f) if f is not None else None
