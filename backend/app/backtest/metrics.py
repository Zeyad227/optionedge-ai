"""Backtest metrics from labelled trade outcomes."""

from __future__ import annotations

import math
import statistics

from app.stubs import BacktestResult


def compute_metrics(trades: list[dict]) -> BacktestResult:
    """Aggregate directional trade labels into robustness metrics."""
    returns = [float(t["pnl"]) for t in trades if t.get("pnl") is not None]
    if not returns:
        return BacktestResult(
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe=0.0,
            avg_return=0.0,
            sample_count=0,
            skipped_avoid=0,
        )

    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / len(returns) * 100.0

    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

    avg_return = sum(returns) / len(returns)

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    if len(returns) > 1:
        std = statistics.stdev(returns)
        sharpe = (avg_return / std) * math.sqrt(252) if std > 0 else 0.0
    else:
        sharpe = 0.0

    return BacktestResult(
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 3),
        max_drawdown=round(max_dd * 100, 2),
        sharpe=round(sharpe, 3),
        avg_return=round(avg_return * 100, 3),
        sample_count=len(returns),
        skipped_avoid=0,
    )
