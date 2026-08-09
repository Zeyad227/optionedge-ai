"""Background refresh jobs (APScheduler)."""

from __future__ import annotations

import logging
from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.services import market as market_service
from app.utils.market_calendar import should_run_market_jobs
from app.workers.leader import acquire_worker_leadership, release_worker_leadership

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None
_is_leader = False

_JOB_OPTS = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 120}


async def refresh_scanner() -> None:
    if not should_run_market_jobs():
        logger.debug("Skipping scanner refresh outside market hours")
        return
    settings = get_settings()
    logger.info("Refreshing scanner universe (%d symbols)", len(settings.universe))
    try:
        await market_service.scan_universe(settings.universe)
    except Exception:
        logger.exception("Scanner refresh failed")


async def refresh_news() -> None:
    try:
        await market_service.fetch_news(limit=30)
    except Exception:
        logger.exception("News refresh failed")


async def refresh_insiders() -> None:
    try:
        await market_service.fetch_insiders(limit=40)
    except Exception:
        logger.exception("Insider refresh failed")


async def refresh_iv_history() -> None:
    if not should_run_market_jobs():
        logger.debug("Skipping IV backfill outside market hours")
        return
    try:
        summaries = await market_service.backfill_iv_universe()
        if summaries:
            written = sum(s.get("written", 0) for s in summaries)
            logger.info("IV backfill wrote %d snapshots across %d symbols", written, len(summaries))
    except Exception:
        logger.exception("IV history backfill failed")


async def warm_cache() -> None:
    """Prime hot paths so first API reads are fast after boot."""
    settings = get_settings()
    logger.info("Warming cache (news + %d scanner symbols)", len(settings.universe))
    try:
        await refresh_news()
        await refresh_insiders()
        if should_run_market_jobs():
            for symbol in settings.universe[:3]:
                try:
                    await market_service.build_signal(symbol)
                except Exception:
                    logger.exception("Warm cache signal failed for %s", symbol)
    except Exception:
        logger.exception("Cache warm failed")


def worker_status() -> dict:
    if _scheduler is None or not _is_leader:
        return {"enabled": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append(
            {
                "id": job.id,
                "next_run": next_run.astimezone(UTC).isoformat() if next_run else None,
            }
        )
    return {"enabled": True, "jobs": jobs}


def start_workers() -> AsyncIOScheduler:
    global _scheduler, _is_leader
    if _scheduler is not None:
        return _scheduler
    settings = get_settings()
    if not settings.workers_enabled:
        logger.info("Background workers disabled (WORKERS_ENABLED=false)")
        return AsyncIOScheduler()

    if settings.worker_leader_lock:
        _is_leader = acquire_worker_leadership()
        if not _is_leader:
            logger.info("Background workers disabled — another process holds the leader lock")
            return AsyncIOScheduler()
    else:
        _is_leader = True

    scheduler = AsyncIOScheduler()
    interval = settings.refresh_interval_seconds
    scheduler.add_job(
        refresh_scanner,
        "interval",
        seconds=interval * 5,
        id="refresh_scanner",
        **_JOB_OPTS,
    )
    scheduler.add_job(
        refresh_news,
        "interval",
        seconds=interval * 10,
        id="refresh_news",
        **_JOB_OPTS,
    )
    scheduler.add_job(
        refresh_insiders,
        "interval",
        seconds=interval * 30,
        id="refresh_insiders",
        **_JOB_OPTS,
    )
    scheduler.add_job(
        refresh_iv_history,
        "interval",
        seconds=interval * 60,
        id="refresh_iv_history",
        **_JOB_OPTS,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def shutdown_workers() -> None:
    global _scheduler, _is_leader
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    if _is_leader:
        release_worker_leadership()
        _is_leader = False
