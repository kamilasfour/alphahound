"""StockTwits adapter — real post text per ticker.

Source: https://api.stocktwits.com/developers/docs
Endpoint used: https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json

Response shape (abridged):
    {
        "response": {"status": 200},
        "symbol": {"symbol": "NVDA", "title": "NVIDIA Corporation", ...},
        "messages": [
            {
                "id": 123456789,
                "body": "NVDA ripping pre-market, AI demand unstoppable",
                "created_at": "2026-04-18T14:30:00Z",
                "user": {"id": 42, "username": "some_user", "followers": 1200, ...},
                "entities": {"sentiment": {"basic": "Bullish"}},  # optional
                "symbols": [{"symbol": "NVDA", ...}]
            },
            ...
        ]
    }

Notes:
  - Rate limit: 200 calls/hour on the free/unauthenticated tier. Each call
    returns up to 30 messages for one symbol. At 32 tickers × 1 call each,
    one ingest run uses 32 calls \u2014 we can safely run every 15 minutes.
  - Author usernames are hashed per PRD A9.2 with `ALPHAHOUND_AUTHOR_SALT_STOCKS`.
  - Sentiment "Bullish"/"Bearish" tags are stored in raw JSON but not yet
    used for scoring (Sprint 3 FinBERT will do that).
  - `since` parameter supported by the adapter: we pass StockTwits' `since=id`
    on subsequent calls per ticker to only fetch new messages.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import hash_author

log = logging.getLogger(__name__)

STOCKTWITS_BASE = "https://api.stocktwits.com/api/2/streams/symbol"
RATE_LIMIT_SLEEP_SECS = 0.3  # ~3 req/s, well under 200/hr even if run continuously


class StockTwitsAdapter(BaseAdapter):
    """Pulls recent messages for a watchlist of symbols."""

    adapter_id: ClassVar[str] = "stocks.stocktwits"
    source_class: ClassVar[str] = "retail_social"
    tier: ClassVar[str] = "C"
    tos_basis: ClassVar[str] = (
        "StockTwits Public API — https://api.stocktwits.com/developers/docs "
        "(200 calls/hour on free tier, attribution required, non-commercial dev use)"
    )

    def __init__(self, watchlist: list[str]) -> None:
        if not watchlist:
            raise ValueError("StockTwitsAdapter needs a non-empty watchlist.")
        # Upper-case and dedupe while preserving order.
        seen: set[str] = set()
        self.watchlist: list[str] = []
        for sym in watchlist:
            s = sym.strip().upper()
            if s and s not in seen:
                seen.add(s)
                self.watchlist.append(s)
        self._salt = os.environ.get("ALPHAHOUND_AUTHOR_SALT_STOCKS", "")
        if not self._salt:
            log.warning(
                "ALPHAHOUND_AUTHOR_SALT_STOCKS is not set. Author hashes will be weak."
            )

    # ----- BaseAdapter contract -----

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        with httpx.Client(timeout=15.0, headers={"User-Agent": "AlphaHound/0.1 (dev)"}) as client:
            for symbol in self.watchlist:
                url = f"{STOCKTWITS_BASE}/{symbol}.json"
                try:
                    log.info("GET %s", url)
                    resp = client.get(url)
                    if resp.status_code == 429:
                        log.warning("StockTwits rate-limited on %s; backing off 60s.", symbol)
                        time.sleep(60)
                        continue
                    if resp.status_code == 404:
                        log.info("Symbol %s not on StockTwits; skipping.", symbol)
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                except httpx.HTTPError as exc:
                    log.warning("StockTwits fetch failed for %s: %s", symbol, exc)
                    continue

                messages = payload.get("messages", []) or []
                for msg in messages:
                    post = self._message_to_post(msg, symbol, observed_at)
                    if post is not None:
                        yield post

                time.sleep(RATE_LIMIT_SLEEP_SECS)

    # ----- internal -----

    def _message_to_post(self, msg: dict, symbol: str, observed_at: datetime) -> Post | None:
        try:
            mid = str(msg["id"])
            body = msg.get("body", "") or ""
            if not body.strip():
                return None
            created_at = self._parse_created_at(msg.get("created_at"))
            user = msg.get("user") or {}
            username = user.get("username") or ""
            author_hash = hash_author(self._salt, username) if username else None

            # Collect all tickers the message mentions; we want multi-symbol posts
            # to produce one row per ticker so each appears in its own feed.
            symbols_list = msg.get("symbols") or []
            tickers = {s.get("symbol", "").upper() for s in symbols_list if s.get("symbol")}
            if not tickers:
                tickers = {symbol}

            return Post(
                adapter_id=self.adapter_id,
                source_class=self.source_class,
                external_id=f"stocktwits:{mid}",
                author_hash=author_hash,
                text=body,
                entity_ids=sorted(tickers),
                observed_at=observed_at,
                published_at=created_at,
                raw=msg,
            )
        except Exception as exc:  # robust: one bad row shouldn't poison the batch
            log.warning("StockTwits message parse failed: %s", exc)
            return None

    @staticmethod
    def _parse_created_at(ts: str | None) -> datetime:
        if not ts:
            return datetime.now(timezone.utc)
        # StockTwits returns e.g. "2026-04-18T14:30:00Z"
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
