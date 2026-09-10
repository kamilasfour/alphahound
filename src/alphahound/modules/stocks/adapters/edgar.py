"""SEC EDGAR adapter — institutional filings firehose.

Source: https://www.sec.gov/
Docs:   https://www.sec.gov/os/accessing-edgar-data

Approach: pull the SEC's "latest filings" Atom feed for each form type we
care about, parse each entry into a Post. Ticker-level position data
(13F holdings, Form 4 transaction amounts) is NOT extracted in Sprint 2
— that requires XBRL parsing and per-filing HTTP calls. We extract the
filing *summary* (who filed, what form, when) and defer holdings-level
detail to Sprint 3 or later.

Form types covered:
    13F-HR  quarterly institutional holdings (Berkshire, Bridgewater, ...)
    SC 13D  activist position disclosures (>5%, intent to influence)
    SC 13G  passive position disclosures (>5%, no influence)
    4       insider transactions (officers/directors/>10% owners)

Rate limit: SEC asks for <=10 req/s with a User-Agent identifying the caller.
We run at 15-min intervals and make ~4 requests per run. Well under.

ToS basis: public SEC data, fair-use compliant per
https://www.sec.gov/os/webmaster-faq#code-support (User-Agent + rate limit).

Post shape:
    external_id = "edgar:<accession_number>:<form_type>"
    text        = "<Filer name> (CIK <cik>) filed <form_type> on <date>"
    entity_ids  = [primary ticker if resolvable, else filer's canonical symbol]
    published_at = filing timestamp from the Atom feed
    raw          = the full Atom entry dict for audit
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post

log = logging.getLogger(__name__)

EDGAR_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
USER_AGENT = "AlphaHound/0.1 (kamil.asfour.dev@gmail.com)"  # SEC requires identifying UA
RATE_LIMIT_SLEEP_SECS = 0.2  # ~5 req/s, well under SEC's 10/s ceiling

# Form types we ingest. Key = short name, value = EDGAR form-type code.
FORM_TYPES: dict[str, str] = {
    "13F-HR": "13F-HR",
    "SC 13D": "SC 13D",
    "SC 13G": "SC 13G",
    "Form 4": "4",
}

# Atom XML namespaces used by EDGAR's feeds.
NS = {
    "atom": "http://www.w3.org/2005/Atom",
}

# How many entries to pull per form type per run.
DEFAULT_COUNT_PER_FORM = 40


class EdgarAdapter(BaseAdapter):
    """Pulls the latest filings firehose across 4 form types."""

    adapter_id: ClassVar[str] = "stocks.edgar"
    source_class: ClassVar[str] = "institutional_flow"
    tier: ClassVar[str] = "B"
    tos_basis: ClassVar[str] = (
        "SEC.gov public data; <=10 req/s rate limit; "
        "User-Agent identifies AlphaHound per SEC fair-use policy "
        "(https://www.sec.gov/os/webmaster-faq#code-support)"
    )

    def __init__(self, count_per_form: int = DEFAULT_COUNT_PER_FORM) -> None:
        self.count_per_form = count_per_form

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/atom+xml",
        }
        with httpx.Client(timeout=30.0, headers=headers) as client:
            for label, form_type in FORM_TYPES.items():
                url = (
                    f"{EDGAR_BASE}"
                    f"?action=getcurrent"
                    f"&type={form_type}"
                    f"&company="
                    f"&dateb="
                    f"&owner=include"
                    f"&count={self.count_per_form}"
                    f"&output=atom"
                )
                try:
                    log.info("GET %s", url)
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    log.warning("EDGAR fetch failed for %s: %s", label, exc)
                    continue

                try:
                    root = ET.fromstring(resp.content)
                except ET.ParseError as exc:
                    log.warning("EDGAR Atom parse failed for %s: %s", label, exc)
                    continue

                for entry in root.findall("atom:entry", NS):
                    post = self._entry_to_post(entry, label, observed_at)
                    if post is not None:
                        yield post

                time.sleep(RATE_LIMIT_SLEEP_SECS)

    # ----- internal -----

    def _entry_to_post(self, entry: ET.Element, form_label: str, observed_at: datetime) -> Post | None:
        """Convert one <entry> element to a Post."""
        try:
            title_el = entry.find("atom:title", NS)
            updated_el = entry.find("atom:updated", NS)
            link_el = entry.find("atom:link", NS)
            summary_el = entry.find("atom:summary", NS)

            if title_el is None or title_el.text is None:
                return None

            title = title_el.text.strip()
            # Title format: "13F-HR - BERKSHIRE HATHAWAY INC (0001067983) (Filer)"
            filer_name, cik = self._extract_filer(title)
            if filer_name is None or cik is None:
                log.debug("Skipping EDGAR entry without parseable filer: %r", title)
                return None

            published_at = self._parse_updated(updated_el.text if updated_el is not None else None)

            # Accession number is inside the entry's <id> or link href; either works as external_id.
            accession = self._extract_accession(entry, link_el)
            if accession is None:
                return None

            # Summary contains form type + filing date confirmation.
            summary_text = summary_el.text.strip() if (summary_el is not None and summary_el.text) else ""

            # Synthetic deterministic post text — matches the pattern we set in ApeWisdom.
            text = (
                f"{filer_name} (CIK {cik}) filed {form_label} "
                f"accession={accession} published={published_at.isoformat()}"
            )
            if summary_text:
                text = f"{text} | {summary_text}"

            # Sprint 2: entity_ids = [filer name as canonical symbol]. We don't resolve
            # to underlying tickers yet — that requires holdings extraction, which is
            # a Sprint 3+ task. Filer-level entities still let us compute "how many
            # institutional filings touched this entity" which is meaningful signal.
            canonical_filer = self._canonicalize_filer(filer_name, cik)

            return Post(
                adapter_id=self.adapter_id,
                source_class=self.source_class,
                external_id=f"edgar:{accession}:{form_label}",
                author_hash=None,  # filer identity is public, not an author
                text=text,
                entity_ids=[canonical_filer],
                observed_at=observed_at,
                published_at=published_at,
                raw={
                    "form_label": form_label,
                    "filer_name": filer_name,
                    "cik": cik,
                    "accession": accession,
                    "title": title,
                    "summary": summary_text,
                    "updated": updated_el.text if updated_el is not None else None,
                },
            )
        except Exception as exc:  # robust: one bad entry shouldn't poison the batch
            log.warning("EDGAR entry parse failed: %s", exc)
            return None

    @staticmethod
    def _extract_filer(title: str) -> tuple[str | None, str | None]:
        """Parse 'FORM - FILER NAME (0001234567) (Filer)' -> ('FILER NAME', '0001234567')."""
        # Match '- ANY NAME (DIGITS) (Role)'
        m = re.search(r"-\s+(.+?)\s+\((\d{10})\)\s+\(", title)
        if not m:
            # Fallback: try without the role suffix.
            m = re.search(r"-\s+(.+?)\s+\((\d{10})\)", title)
        if m:
            return m.group(1).strip(), m.group(2)
        return None, None

    @staticmethod
    def _extract_accession(entry: ET.Element, link_el: ET.Element | None) -> str | None:
        """Accession numbers look like '0001067983-26-000045'. They're in the id or link href."""
        # Try the atom:id first.
        id_el = entry.find("atom:id", NS)
        if id_el is not None and id_el.text:
            m = re.search(r"(\d{10}-\d{2}-\d{6})", id_el.text)
            if m:
                return m.group(1)
        # Fallback to link href.
        if link_el is not None:
            href = link_el.get("href", "")
            m = re.search(r"(\d{10}-\d{2}-\d{6})", href)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _parse_updated(ts: str | None) -> datetime:
        if not ts:
            return datetime.now(timezone.utc)
        try:
            # EDGAR uses RFC 3339: '2026-04-19T14:30:00-04:00'
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _canonicalize_filer(filer_name: str, cik: str) -> str:
        """Produce a stable canonical symbol for a filer.

        We use CIK-based canonical IDs so filer rebrands don't create duplicates:
            'BERKSHIRE HATHAWAY INC' + CIK 0001067983 -> 'CIK:0001067983'

        This keeps filer entities distinct from ticker entities in the DB.
        Later sprints can add human-friendly display names via entity_aliases.
        """
        return f"CIK:{cik}"
