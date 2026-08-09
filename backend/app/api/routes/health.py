from fastapi import APIRouter

from app.config import get_settings
from app.providers.health import check_provider_health
from app.providers.registry import get_registry
from app.schemas.models import HealthResponse, WorkerJobStatus
from app.workers.jobs import worker_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    registry = get_registry()
    workers = worker_status()
    providers = await check_provider_health(settings, registry)
    return HealthResponse(
        status="ok",
        providers=providers,
        cache_backend=settings.cache_backend,
        database="sqlite" if settings.database_url.startswith("sqlite") else "postgres",
        workers_enabled=workers["enabled"],
        worker_jobs=[WorkerJobStatus(**job) for job in workers["jobs"]],
    )
