from fastapi import APIRouter, HTTPException, Query

from app.api.forecast import with_forecast
from app.api.validation import normalize_symbol
from app.services import market as market_service

router = APIRouter()


@router.get("/quote/{symbol}")
async def quote(symbol: str):
    symbol = normalize_symbol(symbol)
    data = await market_service.fetch_quote(symbol)
    if not data:
        raise HTTPException(404, f"No quote for {symbol}")
    return with_forecast(data.model_dump(mode="json"))


@router.get("/ohlcv/{symbol}")
async def ohlcv(symbol: str, period: str = Query("6mo")):
    symbol = normalize_symbol(symbol)
    data = await market_service.fetch_ohlcv(symbol, period=period)
    if not data:
        raise HTTPException(404, f"No OHLCV for {symbol}")
    return with_forecast(data.model_dump(mode="json"))


@router.get("/ticker/{symbol}")
async def ticker(symbol: str):
    symbol = normalize_symbol(symbol)
    return with_forecast(await market_service.ticker_detail(symbol))
