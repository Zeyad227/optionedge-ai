# Architecture

## Provenance

Every market datum flows through `Sourced[T]` (`backend/app/schemas/sourced.py`). Providers return `Sourced`; the UI renders the `source` badge. Values without a provider cannot be constructed.

## Provider fallback order

Configured in `ProviderRegistry.bootstrap()`:

| Domain | Order |
|---|---|
| Options | Alpaca → yfinance → Tradier sandbox |
| Equities | yfinance → Stooq → Twelve Data → Alpha Vantage |
| News | Finnhub (if keyed) → RSS |
| Insiders | SEC EDGAR |
| Macro | FRED (if keyed) |

HTTP providers share `providers/http.py`: retries on **429 / 5xx** (honors `Retry-After`), and EDGAR calls are throttled to ~10 req/sec. Offline contract tests live in `tests/test_providers_contract.py` (respx).

## Scoring

`ai/scoring.py` builds a `Factor` list. Confidence is coverage-aware. Missing factors are listed and **never** coerced to neutral zero. `ai/explain.py` templates prose strictly from that list — no free-text LLM path — so reasoning cannot invent factors the engine did not see.

## Extending

1. **New provider** — implement the protocol in `providers/base.py`, register in `registry.py` with an explicit position in the fallback order.
2. **New factor** — append a `Factor(...)` in `score_symbol`; the explanation updates automatically.
3. **IV rank** — daily ATM IV snapshots land in `iv_snapshots`; rank/percentile need ≥20 samples. Historical gaps are backfilled by inverting Black-Scholes on Alpaca OPRA option bar closes (Feb 2024 onward) via `analysis/iv_history.py` and the `refresh_iv_history` worker.
4. **Insiders** — Form 4 cluster detection lives in `analysis/insider_clusters.py`; top filings are enriched from ownership XML in `providers/sec_edgar.py`.
5. **ML** — `stubs.LabelGenerator` is the hook for training labels from Alpaca historical option bars (available from Feb 2024). Do not ship an untrained model with confidence numbers attached.

## Scoring / explain

`ai/scoring.py` emits factors; `ai/explain.py` templates prose strictly from that list (support/resistance are factors, not free-text appendices). `validate_explanation()` guards explanation-to-factor consistency in tests.

## API / workers

All `/api/*` routes attach `forecast_type` + disclaimer via `api/forecast.py`. `/health` reports worker job IDs and next run times. APScheduler jobs use `max_instances=1` to prevent overlap; optional cache warm on boot (`WARM_CACHE_ON_STARTUP`).

## Schema / migrations

Models live in `backend/app/db/models.py`. Alembic lives in `backend/alembic/` (revision `001` = initial tables). Local SQLite still calls `create_all` on boot; Postgres should run `alembic upgrade head`.

Workers and services persist into Postgres/SQLite via `db/repository.py`:

| Table | Written by |
|---|---|
| `iv_snapshots` | signal build (live ATM IV) + `refresh_iv_history` backfill |
| `news_articles` | `fetch_news` / news worker |
| `insider_filings` | `fetch_insiders` / insider worker |
| `scan_results` | `scan_universe` / scanner worker |

## Cache

`cache/redis_cache.py` — domain TTLs (quotes 60s, chains 5m, news 15m, insiders 1h). `cached()` is single-flight in-process; Redis adds `SET NX` locks so multiple workers do not stampede a provider on the same key.

## Local vs Docker

Default `.env` uses SQLite + in-memory cache (no Docker required). `docker-compose.yml` wires Postgres + Redis when Docker Desktop is installed.
