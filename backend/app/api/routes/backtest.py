"""Walk-forward backtest API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.forecast import with_forecast
from app.backtest import HistoricalLabelGenerator, compute_metrics
from app.stubs import BacktestConfig

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy: str = "directional_factors"
    start: str
    end: str
    symbols: list[str] = Field(min_length=1, max_length=20)
    forward_days: int = Field(default=2, ge=1, le=20)


class BacktestMetricsResponse(BaseModel):
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe: float
    avg_return: float
    sample_count: int
    skipped_avoid: int


class BacktestRunResponse(BaseModel):
    config: BacktestRequest
    metrics: BacktestMetricsResponse
    label_count: int
    sample_labels: list[dict] = Field(default_factory=list)


@router.post("/run")
async def run_backtest(body: BacktestRequest):
    config = BacktestConfig(
        strategy=body.strategy,
        start=body.start,
        end=body.end,
        symbols=[s.upper() for s in body.symbols],
        forward_days=body.forward_days,
    )
    labels = await HistoricalLabelGenerator().generate(config)
    traded = [row for row in labels if row.get("pnl") is not None]
    skipped = sum(1 for row in labels if row.get("skipped"))
    metrics = compute_metrics(traded)
    metrics.skipped_avoid = skipped
    metrics.sample_count = len(traded)

    payload = BacktestRunResponse(
        config=body,
        metrics=BacktestMetricsResponse(
            win_rate=metrics.win_rate,
            profit_factor=metrics.profit_factor,
            max_drawdown=metrics.max_drawdown,
            sharpe=metrics.sharpe,
            avg_return=metrics.avg_return,
            sample_count=metrics.sample_count,
            skipped_avoid=metrics.skipped_avoid,
        ),
        label_count=len(labels),
        sample_labels=labels[:10],
    )
    return with_forecast(payload.model_dump(mode="json"))
