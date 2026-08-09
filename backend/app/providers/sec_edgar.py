"""SEC EDGAR Form 4 insider trading provider."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from app.analysis.insider_clusters import code_sentiment
from app.providers.base import InsiderProvider
from app.providers.http import http_get
from app.schemas.models import InsiderTrade
from app.schemas.sourced import Sourced

ATOM = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"
    "&company=&dateb=&owner=include&count=40&output=atom"
)


class SecEdgarInsiderProvider(InsiderProvider):
    name = "sec-edgar"

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    async def get_recent(self, *, limit: int = 50) -> Sourced[list[InsiderTrade]] | None:
        resp = await http_get(
            ATOM,
            headers=self._headers,
            timeout=30.0,
            edgar_throttle=True,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        trades: list[InsiderTrade] = []
        for entry in root.findall("atom:entry", ns)[:limit]:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link = entry.find("atom:link", ns)
            href = link.get("href") if link is not None else None
            updated = entry.findtext("atom:updated", default="", namespaces=ns)
            filed_at = None
            if updated:
                try:
                    filed_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except ValueError:
                    filed_at = datetime.now(UTC)

            company = title
            if " - " in title:
                company = title.split(" - ", 1)[1]
            company = company.split("(")[0].strip() or title

            trades.append(
                InsiderTrade(
                    insider_name="See Form 4",
                    position=None,
                    company=company,
                    symbol=None,
                    transaction_type="Form 4 filing",
                    shares=None,
                    amount=None,
                    transaction_date=filed_at.date() if filed_at else None,
                    filed_at=filed_at,
                    sentiment="Neutral",
                    form_url=href,
                )
            )

        if not trades:
            return None
        return Sourced.of(
            trades,
            self.name,
            url="https://www.sec.gov/cgi-bin/browse-edgar",
            note=(
                "Feed lists recent Form 4 filings. Detailed insider name/shares "
                "require fetching each filing's ownership XML (rate-limited)."
            ),
        )

    async def enrich_filing(self, form_url: str) -> Sourced[InsiderTrade] | None:
        """Fetch a single Form 4 and parse ownershipXML when available."""
        if not form_url:
            return None
        index = await http_get(
            form_url,
            headers=self._headers,
            timeout=30.0,
            edgar_throttle=True,
        )
        index.raise_for_status()
        text = index.text
        xml_url = None
        m = re.search(r'href="([^"]*ownership\.xml)"', text, re.IGNORECASE)
        if m:
            xml_url = m.group(1)
        if not xml_url:
            return None
        if xml_url.startswith("/"):
            xml_url = "https://www.sec.gov" + xml_url
        xml_resp = await http_get(
            xml_url,
            headers=self._headers,
            timeout=30.0,
            edgar_throttle=True,
        )
        xml_resp.raise_for_status()
        root = ET.fromstring(xml_resp.content)

        def findtext(*paths: str) -> str | None:
            for p in paths:
                el = root.find(p)
                if el is not None and el.text:
                    return el.text.strip()
            return None

        name = findtext(".//rptOwnerName", ".//reportingOwnerId/rptOwnerName") or "Unknown"
        role = findtext(".//officerTitle", ".//reportingOwnerRelationship/officerTitle")
        issuer = findtext(".//issuerName") or "Unknown"
        symbol = findtext(".//issuerTradingSymbol")
        shares_text = findtext(".//transactionShares/value", ".//transactionShares")
        price_text = findtext(".//transactionPricePerShare/value", ".//transactionPricePerShare")
        code = findtext(".//transactionCode") or ""
        date_text = findtext(".//transactionDate/value", ".//transactionDate")

        shares = float(shares_text) if shares_text else None
        price = float(price_text) if price_text else None
        amount = shares * price if shares is not None and price is not None else None
        sentiment = code_sentiment(code)

        trade = InsiderTrade(
            insider_name=name,
            position=role,
            company=issuer,
            symbol=symbol,
            transaction_type=code or "Form 4",
            shares=shares,
            amount=amount,
            transaction_date=datetime.fromisoformat(date_text).date() if date_text else None,
            filed_at=datetime.now(UTC),
            sentiment=sentiment,  # type: ignore[arg-type]
            form_url=form_url,
        )
        return Sourced.of(trade, self.name, url=form_url)
