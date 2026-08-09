from fastapi import APIRouter, HTTPException, Query

from app.api.forecast import with_forecast
from app.services import market as market_service

router = APIRouter()


@router.get("")
async def insiders(limit: int = Query(40, ge=1, le=100)):
    data = await market_service.fetch_insiders(limit=limit)
    if not data:
        raise HTTPException(404, "No insider filings available")
    payload = data.model_dump(mode="json")
    payload["clusters"] = data.clusters
    return with_forecast(payload)
