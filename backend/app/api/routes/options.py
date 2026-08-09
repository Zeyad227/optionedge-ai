from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.api.forecast import with_forecast
from app.api.validation import normalize_symbol
from app.services import market as market_service

router = APIRouter()


@router.get("/chain/{symbol}")
async def chain(symbol: str, expiration: date | None = Query(None)):
    symbol = normalize_symbol(symbol)
    data = await market_service.fetch_chain(symbol, expiration)
    if not data:
        raise HTTPException(
            404,
            f"No option chain for {symbol}. Configure ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY.",
        )
    return with_forecast(data.model_dump(mode="json"))
