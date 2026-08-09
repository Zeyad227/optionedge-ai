"""Tests for Form 4 insider cluster detection."""

from datetime import UTC, date, datetime, timedelta

from app.analysis.insider_clusters import cluster_for_symbol, detect_clusters
from app.schemas.models import InsiderTrade


def _trade(
    *,
    symbol: str,
    name: str,
    code: str,
    days_ago: int = 1,
) -> InsiderTrade:
    when = date.today() - timedelta(days=days_ago)
    return InsiderTrade(
        insider_name=name,
        company=f"{symbol} Inc",
        symbol=symbol,
        transaction_type=code,
        shares=1000,
        transaction_date=when,
        filed_at=datetime.now(UTC),
        sentiment="Neutral",
    )


def test_detects_cluster_buy():
    trades = [
        _trade(symbol="AAPL", name="Alice", code="P", days_ago=2),
        _trade(symbol="AAPL", name="Bob", code="P", days_ago=5),
        _trade(symbol="AAPL", name="Carol", code="P", days_ago=8),
    ]
    clusters = detect_clusters(trades, symbol="AAPL", min_insiders=3)
    assert len(clusters) == 1
    assert clusters[0]["direction"] == "Bullish"
    assert clusters[0]["insider_count"] == 3


def test_detects_cluster_sell():
    trades = [
        _trade(symbol="TSLA", name="Dan", code="S", days_ago=1),
        _trade(symbol="TSLA", name="Eve", code="S", days_ago=3),
        _trade(symbol="TSLA", name="Frank", code="S", days_ago=10),
    ]
    clusters = detect_clusters(trades, symbol="TSLA", min_insiders=3)
    assert len(clusters) == 1
    assert clusters[0]["direction"] == "Bearish"


def test_only_open_market_purchases_count_as_buying():
    """Grants (A) and derivative exercises (M) are compensation, not conviction."""
    trades = [
        _trade(symbol="AAPL", name="Alice", code="P", days_ago=2),
        _trade(symbol="AAPL", name="Bob", code="A", days_ago=3),
        _trade(symbol="AAPL", name="Carol", code="M", days_ago=4),
        _trade(symbol="AAPL", name="Dave", code="A", days_ago=5),
    ]
    assert detect_clusters(trades, symbol="AAPL", min_insiders=3) == []


def test_routine_grant_cycle_is_not_a_cluster_buy():
    """Four executives receiving the same annual RSU award is a calendar event."""
    trades = [
        _trade(symbol="ACME", name=f"Exec {i}", code="A", days_ago=2) for i in range(4)
    ]
    assert detect_clusters(trades, min_insiders=3) == []


def test_tax_withholding_is_not_a_cluster_sell():
    """Code F is the issuer withholding shares to cover tax — nobody chose to sell."""
    trades = [
        _trade(symbol="ACME", name=f"Exec {i}", code="F", days_ago=2) for i in range(4)
    ]
    assert detect_clusters(trades, min_insiders=3) == []


def test_dispositions_and_gifts_are_not_signal():
    for code in ("D", "G", "C", "X"):
        trades = [
            _trade(symbol="ACME", name=f"Exec {i}", code=code, days_ago=2) for i in range(4)
        ]
        assert detect_clusters(trades, min_insiders=3) == [], f"code {code} leaked into clusters"


def test_code_beats_stale_preset_sentiment():
    """A recognised code overrides a sentiment label attached upstream."""
    trades = []
    for i in range(4):
        t = _trade(symbol="ACME", name=f"Exec {i}", code="A", days_ago=2)
        t.sentiment = "Bullish"  # what the old provider mapping wrote
        trades.append(t)
    assert detect_clusters(trades, min_insiders=3) == []


def test_ignores_stale_and_insufficient():
    trades = [
        _trade(symbol="MSFT", name="One", code="P", days_ago=40),
        _trade(symbol="MSFT", name="Two", code="P", days_ago=2),
    ]
    assert detect_clusters(trades, symbol="MSFT", min_insiders=3) == []


def test_cluster_for_symbol_lookup():
    trades = [
        _trade(symbol="NVDA", name="A", code="P"),
        _trade(symbol="NVDA", name="B", code="P"),
        _trade(symbol="NVDA", name="C", code="P"),
        _trade(symbol="AMD", name="X", code="S"),
        _trade(symbol="AMD", name="Y", code="S"),
        _trade(symbol="AMD", name="Z", code="S"),
    ]
    clusters = detect_clusters(trades, min_insiders=3)
    assert cluster_for_symbol(clusters, "NVDA")["direction"] == "Bullish"
    assert cluster_for_symbol(clusters, "AMD")["direction"] == "Bearish"
    assert cluster_for_symbol(clusters, "INTC") is None
