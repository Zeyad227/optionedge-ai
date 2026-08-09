import pytest

from app.backtest import HistoricalLabelGenerator
from app.stubs import AlertRule, BacktestConfig


def test_alert_rule_shape():
    rule = AlertRule(symbol="AAPL", condition="ai_buy", channels=["browser"])
    assert rule.symbol == "AAPL"


@pytest.mark.asyncio
async def test_label_generator_interface():
    """Concrete implementation satisfies the LabelGenerator contract."""

    async def loader(symbol: str, start, end):
        return []

    gen = HistoricalLabelGenerator(candle_loader=loader)
    result = await gen.generate(
        BacktestConfig("directional_factors", "2024-02-01", "2025-01-01", ["AAPL"])
    )
    assert result == []
