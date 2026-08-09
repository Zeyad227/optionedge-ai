from fastapi import APIRouter, HTTPException

from app.api.forecast import with_forecast
from app.api.validation import normalize_symbol
from app.services import market as market_service

router = APIRouter()


@router.get("/{symbol}")
async def signal(symbol: str):
    symbol = normalize_symbol(symbol)
    data = await market_service.build_signal(symbol)
    if not data:
        raise HTTPException(404, f"Unable to build signal for {symbol}")
    return with_forecast(data.model_dump(mode="json"))
