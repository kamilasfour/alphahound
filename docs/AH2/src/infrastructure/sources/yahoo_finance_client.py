"""Yahoo Finance RSS client — ported from AH1's proven adapter
(src/alphahound/modules/stocks/adapters/yahoo_finance.py in the AH1
codebase). AH1 itself is not imported or modified; this is a fresh,
AH2-native port of the same parsing logic, since AH1's package isn't
structured as an importable library for a separately-deployed Function
App.

Source: Yahoo Finance RSS feeds (public, no auth required).
Endpoint: https://feeds.finance.yahoo.com/rss/2.0/headline?s={TICKER}&region=US&lang=en-US
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterator

import httpx

from shared.retry import retry_with_backoff

log = logging.getLogger(__name__)

YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
USER_AGENT = "AH2/0.1 (sentiment research; AH2 STEP 7B migration)"
RATE_LIMIT_SLEEP_SECS = 0.5
HTTP_TIMEOUT_SECONDS = 15.0
FETCH_RETRY_ATTEMPTS = 3

# Ported from AH1's watchlist.py SEED_WATCHLIST — a curated, intentionally
# small (20-ticker) fallback list AH1 itself uses for cold-start
# scenarios, and matches yahoo_finance.py's own (previously-unused)
# DEFAULT_WATCHLIST_SIZE = 20 constant. Used here, rather than AH1's much
# larger production SENTIMENT_WATCHLIST (~89 tickers), to keep this first
# AH2 migration's data volume easy to verify end-to-end.
YAHOO_WATCHLIST: list[str] = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL",
    "MSFT", "AMD", "META", "GOOGL", "AMZN",
    "NFLX", "COIN", "PLTR", "SMCI", "AVGO",
    "IWM", "GLD", "TLT", "UVXY", "XLK",
]


@dataclass(frozen=True)
class NormalizedYahooArticle:
    """One Yahoo Finance RSS headline, normalized and ready for
    AH2 persistence. `source_record_id` is the deterministic natural key
    used for idempotency (raw_source_events.source_record_id)."""

    ticker: str
    guid: str
    title: str
    description: str
    text: str
    link: str
    published_at: datetime
    observed_at: datetime

    @property
    def source_record_id(self) -> str:
        return f"{self.ticker}:{self.guid}"


def fetch_all(
    tickers: list[str] | None = None, *, observed_at: datetime | None = None
) -> Iterator[NormalizedYahooArticle]:
    """Fetch and yield normalized headlines for every ticker in the
    watchlist. Each ticker's fetch is retried independently; a
    persistent failure for one ticker is logged and skipped rather than
    aborting the whole run (matches AH1's per-ticker error isolation)."""
    watchlist = tickers or YAHOO_WATCHLIST
    observed_at = observed_at or datetime.now(timezone.utc)
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, headers=headers) as client:
        for ticker in watchlist:
            try:
                articles = retry_with_backoff(
                    lambda t=ticker: list(_fetch_ticker(client, t, observed_at)),
                    attempts=FETCH_RETRY_ATTEMPTS,
                    description=f"Yahoo Finance fetch for {ticker}",
                )
                yield from articles
                log.info("Yahoo Finance: %s -> %d headlines", ticker, len(articles))
            except Exception as exc:
                log.warning("Yahoo Finance fetch permanently failed for %s: %s", ticker, exc)
            time.sleep(RATE_LIMIT_SLEEP_SECS)


def _fetch_ticker(
    client: httpx.Client, ticker: str, observed_at: datetime
) -> Iterator[NormalizedYahooArticle]:
    params = {"s": ticker, "region": "US", "lang": "en-US"}
    resp = client.get(YAHOO_RSS_URL, params=params)
    if resp.status_code == 404:
        log.info("No Yahoo Finance feed for %s", ticker)
        return
    resp.raise_for_status()

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        # Malformed XML from the source — log and yield nothing for this
        # ticker rather than raising (a single bad feed must not stop
        # every other ticker's ingestion).
        log.warning("Yahoo Finance RSS parse failed for %s: %s", ticker, exc)
        return

    channel = root.find("channel")
    if channel is None:
        log.info("Yahoo Finance: no <channel> in feed for %s", ticker)
        return

    for item in channel.findall("item"):
        article = _item_to_article(item, ticker, observed_at)
        if article is not None:
            yield article


def _item_to_article(
    item: ET.Element, ticker: str, observed_at: datetime
) -> NormalizedYahooArticle | None:
    try:
        title_el = item.find("title")
        desc_el = item.find("description")
        guid_el = item.find("guid")
        pubdate_el = item.find("pubDate")

        if title_el is None or not (title_el.text or "").strip():
            # A headline with no title is not usable — skip (partial/malformed item).
            return None

        title = title_el.text.strip()
        description = ""
        if desc_el is not None and desc_el.text:
            description = re.sub(r"<[^>]+>", "", desc_el.text).strip()

        text = title
        if description and description != title:
            text = f"{title}. {description}"

        published_at = observed_at
        if pubdate_el is not None and pubdate_el.text:
            try:
                published_at = parsedate_to_datetime(pubdate_el.text.strip())
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except Exception:
                published_at = observed_at

        if guid_el is not None and guid_el.text:
            guid = guid_el.text.strip()
        else:
            # No guid in the feed item — fall back to a deterministic hash
            # of the text so source_record_id stays stable across re-runs
            # for the same content (still idempotent, just hash-derived
            # instead of source-provided).
            guid = hashlib.sha256(text.encode()).hexdigest()[:16]

        link_el = item.find("link")
        link = (link_el.text or "").strip() if link_el is not None else ""

        return NormalizedYahooArticle(
            ticker=ticker.upper(),
            guid=guid,
            title=title,
            description=description,
            text=text,
            link=link,
            published_at=published_at,
            observed_at=observed_at,
        )
    except Exception as exc:
        # Any other per-item malformed data — skip this one item, keep
        # processing the rest of the feed.
        log.warning("Yahoo Finance item parse failed for %s: %s", ticker, exc)
        return None
