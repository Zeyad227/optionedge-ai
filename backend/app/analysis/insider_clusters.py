"""Insider buy/sell cluster detection over a rolling window."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.schemas.models import InsiderTrade, SentimentLabel
from app.utils.market_calendar import market_today

# SEC Form 4 transaction codes. Only open-market decisions carry information
# about what an insider actually believes:
#
#   P  open-market / private purchase — the insider chose to spend own money
#   S  open-market / private sale     — the insider chose to sell
#
# Everything else is compensation machinery or bookkeeping and fires on a
# calendar, not on conviction. Counting these produced false clusters: a routine
# annual RSU grant to four executives (code A) read as "cluster buy", and
# four executives having shares withheld to cover the tax on that same grant
# (code F) read as "cluster sell".
#
#   A  grant / award from the issuer            (compensation)
#   M  exercise or conversion of a derivative   (mechanical; often pre-planned)
#   F  shares withheld to pay exercise price/tax(mechanical, forced)
#   D  disposition back to the issuer           (buyback/forfeiture, not a market sale)
#   G  bona fide gift                           (estate planning)
#   C, X, I, J, K, L, U, V, W, Z  other non-discretionary or exotic events
_BUY_CODES = frozenset({"P"})
_SELL_CODES = frozenset({"S"})
_NON_SIGNAL_CODES = frozenset({"A", "M", "F", "D", "G", "C", "X"})


def code_sentiment(code: str | None) -> SentimentLabel:
    """Map a raw Form 4 transaction code to a directional reading."""
    first = (code or "").strip().upper()[:1]
    if first in _BUY_CODES:
        return "Bullish"
    if first in _SELL_CODES:
        return "Bearish"
    return "Neutral"


def _trade_sentiment(trade: InsiderTrade) -> SentimentLabel:
    code = (trade.transaction_type or "").strip().upper()[:1]
    # A recognised code is authoritative; a pre-set sentiment only fills the gap
    # when the code is absent or unrecognised (e.g. the Atom feed's placeholder).
    if code in _BUY_CODES or code in _SELL_CODES or code in _NON_SIGNAL_CODES:
        return code_sentiment(code)
    if trade.sentiment in {"Bullish", "Bearish"}:
        return trade.sentiment
    return "Neutral"


def detect_clusters(
    trades: list[InsiderTrade],
    *,
    symbol: str | None = None,
    window_days: int = 30,
    min_insiders: int = 3,
    as_of: date | None = None,
) -> list[dict]:
    """
    Detect cluster buying or selling for a symbol within a rolling window.

    A cluster requires at least ``min_insiders`` distinct insiders with the
    same directional sentiment (buy vs sell) on the same symbol.
    """
    if not trades:
        return []

    cutoff = (as_of or market_today()) - timedelta(days=window_days)
    sym = symbol.upper() if symbol else None

    by_symbol: dict[str, dict[str, list[InsiderTrade]]] = defaultdict(
        lambda: {"Bullish": [], "Bearish": []}
    )

    for trade in trades:
        if sym and (trade.symbol or "").upper() != sym:
            continue
        trade_sym = (trade.symbol or "").upper()
        if not trade_sym:
            continue
        when = trade.transaction_date or (
            trade.filed_at.date() if trade.filed_at else None
        )
        if when is None or when < cutoff:
            continue
        sentiment = _trade_sentiment(trade)
        if sentiment == "Neutral":
            continue
        by_symbol[trade_sym][sentiment].append(trade)

    clusters: list[dict] = []
    for trade_sym, sides in by_symbol.items():
        for direction in ("Bullish", "Bearish"):
            bucket = sides[direction]
            insiders = {t.insider_name for t in bucket if t.insider_name}
            if len(insiders) < min_insiders:
                continue
            total_shares = sum(t.shares or 0 for t in bucket)
            total_amount = sum(t.amount or 0 for t in bucket if t.amount)
            clusters.append(
                {
                    "symbol": trade_sym,
                    "direction": direction,
                    "insider_count": len(insiders),
                    "transaction_count": len(bucket),
                    "total_shares": total_shares or None,
                    "total_amount": total_amount or None,
                    "window_days": window_days,
                    "label": (
                        f"Cluster {'buy' if direction == 'Bullish' else 'sell'}: "
                        f"{len(insiders)} insiders / {len(bucket)} filings"
                    ),
                }
            )

    clusters.sort(key=lambda c: c["insider_count"], reverse=True)
    return clusters


def cluster_for_symbol(clusters: list[dict], symbol: str) -> dict | None:
    sym = symbol.upper()
    for cluster in clusters:
        if cluster["symbol"] == sym:
            return cluster
    return None
