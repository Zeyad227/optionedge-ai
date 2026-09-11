from fastapi import APIRouter, HTTPException, Query

from app.api.forecast import with_forecast
from app.api.validation import normalize_symbol
from app.services import market as market_service

router = APIRouter()


@router.get("")
async def news(symbol: str | None = Query(None), limit: int = Query(20, ge=1, le=100)):
    if symbol is not None:
        symbol = normalize_symbol(symbol)
    data = await market_service.fetch_news(symbol, limit=limit)
    if not data:
        raise HTTPException(404, "No news available")
    return with_forecast(data.model_dump(mode="json"))
