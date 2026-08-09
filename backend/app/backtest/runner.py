"""Walk-forward backtest runner."""

from __future__ import annotations

from app.backtest.labels import HistoricalLabelGenerator
from app.backtest.metrics import compute_metrics
from app.stubs import BacktestConfig, Backtester, BacktestResult, LabelGenerator


class DirectionalBacktester(Backtester):
    """Evaluate directional signals against realised forward returns."""

    def __init__(
        self,
        *,
        label_generator: LabelGenerator | None = None,
    ) -> None:
        self._labels = label_generator or HistoricalLabelGenerator()

    async def run(self, config: BacktestConfig) -> BacktestResult:
        labels = await self._labels.generate(config)
        traded = [row for row in labels if row.get("pnl") is not None]
        skipped = sum(1 for row in labels if row.get("skipped"))
        result = compute_metrics(traded)
        result.skipped_avoid = skipped
        result.sample_count = len(traded)
        return result
