"""Massive adapter — real-time price context for divergence alerts.

Massive = Polygon.io rebranded. Same REST API, new domain.
Plan: Stocks Starter ($29/mo) — previous-day OHLCV + date-range aggregates.

Endpoints used:
    GET /v2/aggs/ticker/{ticker}/prev
        Previous day close, open, high, low, volume, change %.

    GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}
        Daily OHLCV over a date range — used to compute 5-day change.

Writes to: price_snapshots (NOT raw_posts — price is context, not sentiment).

SPY is pulled alongside every ticker so we can compute relative performance:
    change_vs_spy = ticker_5d_change - spy_5d_change

Rate limit: Stocks Starter = 1,000 calls/min — plenty.
At 50 tickers x 2 endpoints + 1 SPY pull = ~101 calls per run. Still safe.

Env var: MASSIVE_API_KEY
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar, Iterable

import httpx
import psycopg
from psycopg.rows import dict_row

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn

from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST

log = logging.getLogger(__name__)

MASSIVE_BASE     = "https://api.polygon.io"
RATE_LIMIT_SLEEP = 0.07   # ~14 req/s — well under 1,000/min limit

WATCHLIST = FULL_WATCHLIST  # backward compat alias
SPY = "SPY"


class MassiveAdapter(BaseAdapter):
    """Pulls previous-day OHLCV and 5-day history for all watchlist tickers."""

    adapter_id: ClassVar[str] = "stocks.massive"
    source_class: ClassVar[str] = "price_data"
    tier: ClassVar[str] = "A"
    tos_basis: ClassVar[str] = (
        "Massive (formerly Polygon.io) Stocks Starter plan — $29/mo, "
        "personal research use, https://massive.com/terms"
    )

    def __init__(self, tickers: list[str] | None = None) -> None:
        self.tickers  = tickers or WATCHLIST
        self._api_key = os.environ.get("MASSIVE_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("MASSIVE_API_KEY is not set in environment / .env")

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        """Massive writes directly to price_snapshots, not raw_posts."""
        resolver    = EntityResolver()
        observed_at = datetime.now(timezone.utc)
        today       = date.today()
        five_days_ago = today - timedelta(days=7)

        with httpx.Client(
            base_url=MASSIVE_BASE,
            params={"apiKey": self._api_key},
            timeout=20.0,
        ) as client:
            spy_5d_change = self._get_5d_change(client, SPY, five_days_ago, today)
            time.sleep(RATE_LIMIT_SLEEP)

            for ticker in self.tickers:
                try:
                    self._ingest_ticker(
                        client=client,
                        ticker=ticker,
                        observed_at=observed_at,
                        five_days_ago=five_days_ago,
                        today=today,
                        spy_5d_change=spy_5d_change,
                        resolver=resolver,
                    )
                except Exception as exc:
                    log.warning("Massive: failed for %s — %s", ticker, exc)
                time.sleep(RATE_LIMIT_SLEEP)

        return iter([])

    def _ingest_ticker(
        self,
        client: httpx.Client,
        ticker: str,
        observed_at: datetime,
        five_days_ago: date,
        today: date,
        spy_5d_change: float | None,
        resolver: EntityResolver,
    ) -> None:
        prev = self._get_prev(client, ticker)
        if prev is None:
            log.debug("Massive: no prev-day data for %s — skipping", ticker)
            return

        price         = prev.get("c")
        open_         = prev.get("o")
        high          = prev.get("h")
        low           = prev.get("l")
        volume        = prev.get("v")
        change_1d_pct = prev.get("dp")

        if price is None:
            return

        change_5d_pct = self._get_5d_change(client, ticker, five_days_ago, today)
        time.sleep(RATE_LIMIT_SLEEP)

        change_vs_spy: float | None = None
        if change_5d_pct is not None and spy_5d_change is not None:
            change_vs_spy = round(change_5d_pct - spy_5d_change, 4)

        entity_id = resolver.resolve(module_id="stocks", symbol=ticker, kind="ticker")

        self._upsert_price_snapshot(
            entity_id=entity_id,
            observed_at=observed_at,
            price=price,
            open_=open_,
            high=high,
            low=low,
            volume=int(volume) if volume is not None else None,
            change_1d_pct=round(change_1d_pct, 4) if change_1d_pct is not None else None,
            change_5d_pct=round(change_5d_pct, 4) if change_5d_pct is not None else None,
            change_vs_spy=change_vs_spy,
        )
        log.info(
            "Massive: %s price=%.2f 1d=%s%% 5d=%s%% vsSPY=%s%%",
            ticker, price,
            f"{change_1d_pct:.2f}" if change_1d_pct is not None else "n/a",
            f"{change_5d_pct:.2f}" if change_5d_pct is not None else "n/a",
            f"{change_vs_spy:.2f}" if change_vs_spy is not None else "n/a",
        )

    def _get_prev(self, client: httpx.Client, ticker: str) -> dict | None:
        try:
            resp = client.get(f"/v2/aggs/ticker/{ticker}/prev")
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return results[0] if results else None
        except (httpx.HTTPError, IndexError, KeyError) as exc:
            log.warning("Massive _get_prev failed for %s: %s", ticker, exc)
            return None

    def _get_5d_change(
        self, client: httpx.Client, ticker: str, from_: date, to: date
    ) -> float | None:
        try:
            resp = client.get(
                f"/v2/aggs/ticker/{ticker}/range/1/day/{from_.strftime('%Y-%m-%d')}/{to.strftime('%Y-%m-%d')}"
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if len(results) < 2:
                return None
            first_close = results[0]["c"]
            last_close  = results[-1]["c"]
            if first_close == 0:
                return None
            return round((last_close - first_close) / first_close * 100, 4)
        except (httpx.HTTPError, KeyError, ZeroDivisionError) as exc:
            log.warning("Massive _get_5d_change failed for %s: %s", ticker, exc)
            return None

    @staticmethod
    def _upsert_price_snapshot(
        entity_id: str,
        observed_at: datetime,
        price: float,
        open_: float | None,
        high: float | None,
        low: float | None,
        volume: int | None,
        change_1d_pct: float | None,
        change_5d_pct: float | None,
        change_vs_spy: float | None,
    ) -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO price_snapshots (
                        time, entity_id,
                        price, open, high, low, volume,
                        change_1d_pct, change_5d_pct, change_vs_spy
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (entity_id, time) DO UPDATE
                        SET price         = EXCLUDED.price,
                            open          = EXCLUDED.open,
                            high          = EXCLUDED.high,
                            low           = EXCLUDED.low,
                            volume        = EXCLUDED.volume,
                            change_1d_pct = EXCLUDED.change_1d_pct,
                            change_5d_pct = EXCLUDED.change_5d_pct,
                            change_vs_spy = EXCLUDED.change_vs_spy;
                    """,
                    (
                        observed_at, entity_id,
                        price, open_, high, low, volume,
                        change_1d_pct, change_5d_pct, change_vs_spy,
                    ),
                )
            conn.commit()
