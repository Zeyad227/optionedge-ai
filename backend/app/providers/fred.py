"""FRED macro series provider (St. Louis Fed)."""

from __future__ import annotations

from app.providers.base import MacroProvider
from app.providers.http import http_get
from app.schemas.sourced import Sourced

# Common series used by the dashboard / economic calendar.
SERIES = {
    "CPIAUCSL": "CPI (All Urban Consumers)",
    "PPIACO": "PPI (All Commodities)",
    "GDP": "GDP",
    "UNRATE": "Unemployment Rate",
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "DCOILWTICO": "WTI Crude Oil",
    "GOLDAMGBD228NLBM": "Gold Fixing",
    "VIXCLS": "VIX",
}


class FredMacroProvider(MacroProvider):
    name = "fred"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def get_series(
        self,
        series_id: str,
        *,
        limit: int = 24,
    ) -> Sourced[list[dict]] | None:
        resp = await http_get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        observations = resp.json().get("observations") or []

        points = []
        for obs in observations:
            if obs.get("value") in (".", None, ""):
                continue
            points.append(
                {
                    "date": obs["date"],
                    "value": float(obs["value"]),
                    "series_id": series_id,
                    "label": SERIES.get(series_id, series_id),
                }
            )
        if not points:
            return None
        return Sourced.of(
            points,
            self.name,
            url=f"https://fred.stlouisfed.org/series/{series_id}",
        )

    async def get_dashboard_macro(self) -> Sourced[dict[str, dict]] | None:
        out: dict[str, dict] = {}
        for series_id in ("CPIAUCSL", "UNRATE", "DGS10", "DGS2", "VIXCLS", "DCOILWTICO"):
            sourced = await self.get_series(series_id, limit=2)
            if sourced and sourced.value:
                latest = sourced.value[0]
                prev = sourced.value[1] if len(sourced.value) > 1 else None
                change = None
                if prev:
                    change = latest["value"] - prev["value"]
                out[series_id] = {**latest, "change": change}
        if not out:
            return None
        return Sourced.of(out, self.name, url="https://fred.stlouisfed.org")
