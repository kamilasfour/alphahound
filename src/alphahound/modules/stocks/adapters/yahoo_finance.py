"""Yahoo Finance RSS adapter — news headlines per ticker.

Source: Yahoo Finance RSS feeds (public, no auth required)
Endpoint: https://feeds.finance.yahoo.com/rss/2.0/headline?s={TICKER}&region=US&lang=en-US

What we pull:
  News headlines for each ticker in the watchlist. Each headline becomes
  one Post with source_class='news_wire', tier='C'. FinBERT scores the
  headline text for sentiment polarity.

Why this matters for divergence:
  ApeWisdom gives us retail_social sentiment per ticker.
  Yahoo Finance gives us news_wire sentiment per ticker.
  When these two disagree (e.g. retail is bullish but news is bearish),
  that's a real divergence signal — exactly what PRD §A7.1 is designed to catch.

Rate limiting:
  Yahoo Finance RSS is public and generous. We pull one ticker at a time
  with a small sleep between requests. At 20 tickers × 1 req each = 20 req/run,
  every 15 minutes = ~0.02 req/sec. Zero risk of hitting limits.

ToS basis (Stage 1):
  Yahoo Finance RSS is a public feed intended for syndication. Personal use
  for sentiment research is within the spirit of the feed. Stage 2 review
  needed before commercial redistribution of derived signals.

Post shape:
  external_id = "yahoo:{ticker}:{guid}"   (guid from RSS item)
  text        = headline title + ". " + description (if present)
  entity_ids  = [ticker]
  published_at = pubDate from RSS item
  source_class = 'news_wire'
  tier         = 'C'
"""
from __future__ import annotations

import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.modules.stocks.watchlist.watchlist import SENTIMENT_WATCHLIST, resolve_watchlist

log = logging.getLogger(__name__)

YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
USER_AGENT = "AlphaHound/0.1 (sentiment research; kamil.asfour.dev@gmail.com)"
RATE_LIMIT_SLEEP_SECS = 0.5
DEFAULT_WATCHLIST_SIZE = 20


class YahooFinanceAdapter(BaseAdapter):
    """Pulls news headlines from Yahoo Finance RSS for a watchlist of tickers."""

    adapter_id: ClassVar[str] = "stocks.yahoo_finance"
    source_class: ClassVar[str] = "news_wire"
    tier: ClassVar[str] = "C"
    tos_basis: ClassVar[str] = (
        "Yahoo Finance RSS public feed — "
        "https://feeds.finance.yahoo.com/rss/2.0/headline "
        "(public syndication feed, personal sentiment research use, Stage 1 only)"
    )

    def __init__(self, watchlist: list[str] | None = None) -> None:
        self.watchlist = watchlist or SENTIMENT_WATCHLIST

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        headers = {"User-Agent": USER_AGENT}

        with httpx.Client(timeout=15.0, headers=headers) as client:
            for ticker in self.watchlist:
                try:
                    posts = list(self._pull_ticker(client, ticker, observed_at))
                    yield from posts
                    log.info("Yahoo Finance: %s -> %d headlines", ticker, len(posts))
                except Exception as exc:
                    log.warning("Yahoo Finance fetch failed for %s: %s", ticker, exc)
                time.sleep(RATE_LIMIT_SLEEP_SECS)

    # ----- internal -----

    def _pull_ticker(
        self, client: httpx.Client, ticker: str, observed_at: datetime
    ) -> Iterable[Post]:
        params = {
            "s": ticker,
            "region": "US",
            "lang": "en-US",
        }
        resp = client.get(YAHOO_RSS_URL, params=params)
        if resp.status_code == 404:
            log.info("No Yahoo Finance feed for %s", ticker)
            return
        resp.raise_for_status()

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            log.warning("Yahoo Finance RSS parse failed for %s: %s", ticker, exc)
            return

        channel = root.find("channel")
        if channel is None:
            return

        for item in channel.findall("item"):
            post = self._item_to_post(item, ticker, observed_at)
            if post is not None:
                yield post

    def _item_to_post(
        self, item: ET.Element, ticker: str, observed_at: datetime
    ) -> Post | None:
        try:
            title_el = item.find("title")
            desc_el = item.find("description")
            guid_el = item.find("guid")
            pubdate_el = item.find("pubDate")

            if title_el is None or not (title_el.text or "").strip():
                return None

            title = title_el.text.strip()
            description = ""
            if desc_el is not None and desc_el.text:
                # Strip HTML tags from description (Yahoo includes some markup).
                import re
                description = re.sub(r"<[^>]+>", "", desc_el.text).strip()

            # Combine title + description for richer FinBERT input.
            text = title
            if description and description != title:
                text = f"{title}. {description}"

            # Published timestamp.
            published_at = observed_at
            if pubdate_el is not None and pubdate_el.text:
                try:
                    published_at = parsedate_to_datetime(pubdate_el.text.strip())
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    published_at = observed_at

            # External ID: use guid if available, otherwise hash the title.
            if guid_el is not None and guid_el.text:
                guid = guid_el.text.strip()
            else:
                guid = hashlib.sha256(text.encode()).hexdigest()[:16]

            external_id = f"yahoo:{ticker}:{guid}"

            return Post(
                adapter_id=self.adapter_id,
                source_class=self.source_class,
                external_id=external_id,
                author_hash=None,  # news articles don't have a meaningful author for our purposes
                text=text,
                entity_ids=[ticker.upper()],
                observed_at=observed_at,
                published_at=published_at,
                raw={"ticker": ticker, "title": title, "guid": guid},
            )
        except Exception as exc:
            log.warning("Yahoo Finance item parse failed for %s: %s", ticker, exc)
            return None
