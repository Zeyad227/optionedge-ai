# OptionEdge AI

Probabilistic options-trading signal platform. Every number carries its source; every recommendation is labeled a forecast, not a guarantee.

**Not financial advice.** Signals are probabilistic. Past patterns do not guarantee future results. Markets can and do invalidate models without warning.

## Architecture

| Layer | Stack |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind, TradingView Lightweight Charts |
| Backend | Python FastAPI |
| Data | SQLite (default) or Postgres; in-memory cache or Redis |
| AI | Deterministic factor scoring + local FinBERT news sentiment |

## Data sources & rate limits

| Domain | Primary | Fallback | Rate limit / notes | Key |
|---|---|---|---|---|
| Option chains + greeks + IV | Alpaca (indicative / free) | yfinance → Tradier sandbox | Alpaca ~200 historical calls/min; Tradier sandbox has OI/volume, **no greeks** | Alpaca (required for options slice) |
| Equity OHLCV | yfinance | Stooq → Twelve Data → Alpha Vantage | yfinance is an unofficial scraper and can break; Twelve Data ~800/day; Alpha Vantage **25/day — fallback only, never hot path** | No (keyless first) |
| News | Finnhub + RSS | — | Finnhub ~60 req/min | Finnhub optional |
| Insider Form 4 | SEC EDGAR | — | ~10 req/sec; requires descriptive `User-Agent` | No (User-Agent only) |
| Macro (CPI, GDP, yields, …) | FRED | — | Per FRED key quota | FRED optional |
| Polygon / Massive | Registered but **off** | — | Free tier ~5 calls/min EOD — unusable for a scanner | N/A |

Alpaca free options history starts **February 2024**. Historical bars are real OPRA (free tier only blocks the latest 15 minutes). Live quotes on the free plan are *indicative* — fine for signal generation, **not** for execution.

## Quick start (no Docker)

```bash
# 1. Env
cp .env.example .env
# Paste ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY into .env yourself — never commit them.

# 2. Backend
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
# Optional if using Postgres instead of SQLite defaults:
# alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. API docs: http://localhost:8000/docs.

## Optional: Docker

If you install Docker Desktop later:

```bash
docker compose up --build
```

Set `DATABASE_URL` and `REDIS_URL` as shown in `docker-compose.yml`. For Postgres schema management:

```bash
docker compose exec backend alembic upgrade head
```

Local SQLite still uses `create_all` on boot so the API starts without a migrate step.
If that DB already exists and you later introduce Alembic, sync once with:

```bash
cd backend && alembic stamp head
```


## Migrations

See `backend/alembic/`. Initial revision `001` creates `iv_snapshots`, `news_articles`, `insider_filings`, and `scan_results`.

## Disclaimer

OptionEdge AI produces **probabilistic forecasts**, not certainties and not personalized investment advice. You are solely responsible for any trading decisions. Consult a licensed professional if you need advice.
