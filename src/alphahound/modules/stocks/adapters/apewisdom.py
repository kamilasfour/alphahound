"""ApeWisdom adapter — Reddit ticker mention aggregator.

Source: https://apewisdom.io/api/
Docs: https://apewisdom.io/api/v1.0/filter/all-stocks/

Response shape (filter=all-stocks, page=1):
    {
        "count": int,
        "pages": int,
        "results": [
            {
                "ticker": "STNG",
                "name": "Scorpio Tankers",
                "mentions": 42,
                "upvotes": 310,
                "rank": "1",
                "rank_24h_ago": "3",
                "mentions_24h_ago": 18,
            },
            ...
        ]
    }

Note on fit: ApeWisdom gives us a ranked mention count, not individual posts.
We map each (ticker, snapshot) to a synthetic Post whose text is a
deterministic summary of the row. This is enough to drive the
"mention_volume_velocity" component (PRD B5.1). When we later add Reddit
direct ingestion we'll have real post text; for now this keeps the pipeline
shape consistent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post

log = logging.getLogger(__name__)

APEWISDOM_BASE = "https://apewisdom.io/api/v1.0/filter"


class ApeWisdomAdapter(BaseAdapter):
    """Pulls the top N mentioned tickers from ApeWisdom."""

    adapter_id: ClassVar[str] = "stocks.apewisdom"
    source_class: ClassVar[str] = "retail_social"
    tier: ClassVar[str] = "C"
    tos_basis: ClassVar[str] = (
        "ApeWisdom free API — https://apewisdom.io/api/ "
        "(public, no auth, attribution on use)"
    )

    def __init__(self, filter_name: str = "all-stocks", max_pages: int = 5, top_n: int = 100) -> None:
        self.filter_name = filter_name
        self.max_pages = max_pages
        self.top_n = top_n  # pull all meaningful tickers

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Pull current ApeWisdom snapshot.

        `since` and `cursor` are ignored — ApeWisdom only exposes a live
        snapshot, not a historical stream. Every call returns the current
        top list; dedup on (adapter_id, external_id) keeps the DB clean.
        """
        observed_at = datetime.now(timezone.utc)
        # Hour-bucketed key — one snapshot per hour per ticker is enough
        snapshot_key = observed_at.strftime("%Y%m%dT%H")

        with httpx.Client(timeout=15.0) as client:
            for page in range(1, self.max_pages + 1):
                url = f"{APEWISDOM_BASE}/{self.filter_name}/page/{page}"
                log.info("GET %s", url)
                resp = client.get(url)
                resp.raise_for_status()
                payload = resp.json()

                results = payload.get("results", [])
                # Only process top N by mention volume — rest is noise
                for row in results[:self.top_n]:
                    yield self._row_to_post(row, observed_at, snapshot_key)

    # ----- internal -----

    def _row_to_post(self, row: dict, observed_at: datetime, snapshot_key: str) -> Post:
        ticker = row["ticker"].upper()
        mentions = int(row.get("mentions", 0))
        mentions_prev = int(row.get("mentions_24h_ago", 0) or 0)
        rank = row.get("rank", "?")
        rank_prev = row.get("rank_24h_ago", "?") or "?"
        upvotes = int(row.get("upvotes", 0) or 0)
        name = row.get("name", "")

        # Synthetic post text — deterministic so text_hash dedups cleanly.
        text = (
            f"{ticker} ({name}) mentions={mentions} "
            f"(24h_ago={mentions_prev}) upvotes={upvotes} "
            f"rank={rank} (24h_ago={rank_prev}) "
            f"source=ApeWisdom:{self.filter_name}"
        )

        # One external_id per (ticker, snapshot) — lets dedup handle same-minute retries
        # but allows multiple snapshots per day.
        external_id = f"{self.filter_name}:{ticker}:{snapshot_key}"

        return Post(
            adapter_id=self.adapter_id,
            source_class=self.source_class,
            external_id=external_id,
            author_hash=None,  # aggregate, no author
            text=text,
            entity_ids=[ticker],
            observed_at=observed_at,
            published_at=observed_at,  # ApeWisdom doesn't timestamp rows
            raw=row,
        )
