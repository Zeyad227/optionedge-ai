"""Application settings loaded from environment / .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Alpaca
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_data_feed: Literal["indicative", "opra"] = "indicative"

    # Other providers
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    tradier_sandbox_token: str = ""
    twelve_data_api_key: str = ""
    alpha_vantage_api_key: str = ""
    # EDGAR rejects requests without a contactable User-Agent; operators must supply
    # their own via SEC_EDGAR_USER_AGENT rather than reuse this placeholder.
    sec_edgar_user_agent: str = "OptionEdge AI (set SEC_EDGAR_USER_AGENT to your name and email)"

    # Infrastructure
    database_url: str = "sqlite+aiosqlite:///./data/optionedge.db"
    redis_url: str = ""
    cache_backend: Literal["memory", "redis"] = "memory"
    cors_origins: str = "http://localhost:3000"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    scanner_universe: str = "SPY,QQQ,IWM,AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,JPM,XOM"
    refresh_interval_seconds: int = 60
    disclaimer_enabled: bool = True
    iv_backfill_days_per_run: int = 20
    insider_enrich_limit: int = 5
    workers_enabled: bool = True
    warm_cache_on_startup: bool = True
    scan_concurrency: int = 4
    scan_retention_days: int = 30
    min_option_dte: int = 7
    worker_leader_lock: bool = True
    api_key: str = ""
    rate_limit_per_minute: int = 120
    scanner_rate_limit_per_minute: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def universe(self) -> list[str]:
        return [s.strip().upper() for s in self.scanner_universe.split(",") if s.strip()]

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key_id and self.alpaca_api_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
