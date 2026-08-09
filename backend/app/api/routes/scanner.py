from fastapi import APIRouter

from app.api.forecast import with_forecast
from app.config import get_settings
from app.services import market as market_service

router = APIRouter()


@router.get("")
async def scanner():
    settings = get_settings()
    results = await market_service.get_scanner_results(settings.universe)
    calls = [s for s in results if s.action == "Buy"]
    puts = [s for s in results if s.action == "Sell"]
    return with_forecast(
        {
            "universe": settings.universe,
            "all": [s.model_dump(mode="json") for s in results],
            "top_calls": [s.model_dump(mode="json") for s in calls[:10]],
            "top_puts": [s.model_dump(mode="json") for s in puts[:10]],
            "highest_ai_score": [s.model_dump(mode="json") for s in results[:10]],
            "highest_risk_reward": [
                s.model_dump(mode="json")
                for s in sorted(
                    [x for x in results if x.risk_reward],
                    key=lambda x: x.risk_reward or 0,
                    reverse=True,
                )[:10]
            ],
        }
    )
