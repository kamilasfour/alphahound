"""Massive daily price history adapter — Sprint 9.5.

Pulls daily OHLCV bars from Massive (Polygon.io) into price_daily table.

Two modes:
    backfill  — pulls 60 trading days of history per ticker (run once)
    topup     — pulls last 5 days only (run daily via scheduler)

Called by:
    alphahound ingest --source massive_history          (topup, default)
    alphahound ingest --source massive_history --backfill  (full 60d backfill)

Also exposed as:
    alphahound signals tech-backfill   (one-time setup command)

Rate limit: Stocks Starter = 1,000 calls/min.
At 37 tickers x 1 call = 37 calls per topup. Safe.
Backfill: 37 tickers x 1 call each = 37 calls total. Still safe.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn
from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST

log = logging.getLogger(__name__)

MASSIVE_BASE     = "https://api.polygon.io"
RATE_LIMIT_SLEEP = 0.07   # ~14 req/s
BACKFILL_DAYS    = 60     # enough for MACD(26) + EMA(20) + buffer
TOPUP_DAYS       = 5


class MassiveHistoryAdapter(BaseAdapter):
    """Pulls daily OHLCV bars into price_daily for technical analysis."""

    adapter_id: ClassVar[str] = "stocks.massive_history"
    source_class: ClassVar[str] = "price_data"
    tier: ClassVar[str] = "A"
    tos_basis: ClassVar[str] = (
        "Massive (formerly Polygon.io) Stocks Starter plan — $29/mo, "
        "personal research use, https://massive.com/terms"
    )

    def __init__(self, tickers: list[str] | None = None, backfill: bool = False) -> None:
        self.tickers  = tickers or FULL_WATCHLIST
        self.backfill = backfill
        self._api_key = os.environ.get("MASSIVE_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("MASSIVE_API_KEY is not set in environment / .env")

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Pull daily bars and write directly to price_daily. Returns empty iterator."""
        today     = date.today()
        days_back = BACKFILL_DAYS if self.backfill else TOPUP_DAYS
        from_date = today - timedelta(days=days_back + 10)  # +10 buffer for weekends

        resolver   = EntityResolver()
        total_rows = 0

        with httpx.Client(
            base_url=MASSIVE_BASE,
            params={"apiKey": self._api_key},
            timeout=30.0,
        ) as client:
            for ticker in self.tickers:
                try:
                    rows = self._pull_ticker(client, ticker, from_date, today, resolver)
                    total_rows += rows
                except Exception as exc:
                    log.warning("MassiveHistory: failed for %s — %s", ticker, exc)
                time.sleep(RATE_LIMIT_SLEEP)

        mode = "backfill" if self.backfill else "topup"
        log.info("MassiveHistory %s complete: %d rows written for %d tickers",
                 mode, total_rows, len(self.tickers))
        return iter([])

    def _pull_ticker(
        self,
        client: httpx.Client,
        ticker: str,
        from_date: date,
        to_date: date,
        resolver: EntityResolver,
    ) -> int:
        """Pull daily bars for one ticker, write to price_daily. Returns rows written."""
        from_str = from_date.strftime("%Y-%m-%d")
        to_str   = to_date.strftime("%Y-%m-%d")

        resp = client.get(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{from_str}/{to_str}",
            params={"adjusted": "true", "sort": "asc", "limit": 120},
        )
        resp.raise_for_status()
        data    = resp.json()
        results = data.get("results", [])

        if not results:
            log.debug("MassiveHistory: no bars for %s", ticker)
            return 0

        entity_id = resolver.resolve(
            module_id="stocks",
            symbol=ticker,
            kind="ticker",
        )

        rows_written = 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                for bar in results:
                    bar_date = date.fromtimestamp(bar["t"] / 1000)  # ms → seconds → date
                    cur.execute(
                        """
                        INSERT INTO price_daily
                            (date, entity_id, open, high, low, close, volume, vwap, transactions)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (entity_id, date) DO UPDATE
                            SET open         = EXCLUDED.open,
                                high         = EXCLUDED.high,
                                low          = EXCLUDED.low,
                                close        = EXCLUDED.close,
                                volume       = EXCLUDED.volume,
                                vwap         = EXCLUDED.vwap,
                                transactions = EXCLUDED.transactions;
                        """,
                        (
                            bar_date,
                            entity_id,
                            bar.get("o"),
                            bar.get("h"),
                            bar.get("l"),
                            bar.get("c"),
                            int(bar["v"]) if bar.get("v") is not None else None,
                            bar.get("vw"),
                            bar.get("n"),
                        ),
                    )
                    rows_written += 1
            conn.commit()

        log.info("MassiveHistory: %s — %d daily bars written (%s to %s)",
                 ticker, rows_written, from_str, to_str)
        return rows_written
