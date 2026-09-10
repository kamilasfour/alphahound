"""Quiver Quantitative adapter — congressional stock trades.

Source: https://api.quiverquant.com/beta/live/congresstrading
Plan: Hobbyist ($30/mo)

Pulls recent politician stock trades filed under the STOCK Act.
Fields: Ticker, Representative, Transaction, Amount, Date, Party

Two writes per trade:
    1. raw_posts — for FinBERT scoring + divergence math
    2. institutional_positions — the signal component table

Dedup strategy:
    external_id = stable hash of (rep, ticker, date, txn) — no date rotation.
    published_at = actual trade date from the STOCK Act filing.

    The dedup conflict key in raw_posts is (adapter_id, external_id, entity_id, time).
    With external_id stable and published_at = trade date, each unique congressional
    trade is written exactly once and never re-ingested. This is correct: STOCK Act
    trades are immutable once filed.

    HISTORY OF THE BUG (fixed here):
    - v1 (original): published_at = trade_date → permanent dedup, 0 writes forever.
    - v2 (Sprint 10 "fix"): external_id included today's date (daily rotation) BUT
      published_at was still midnight UTC today. Both values were identical every cycle
      all day, so the first cycle of each day wrote 1000 rows, every subsequent cycle
      hit ON CONFLICT DO NOTHING → wrote 0. Fetched 1000, wrote 0, no error logged.
    - v3 (this fix): external_id = stable per trade, published_at = actual trade date.
      Each trade writes once; subsequent cycles correctly skip it as a duplicate.

Env var: QUIVER_API_KEY
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import ClassVar, Iterable

import httpx

from alphahound.engine.adapters.base import BaseAdapter
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, get_conn

log = logging.getLogger(__name__)

QUIVER_BASE = "https://api.quiverquant.com"

AMOUNT_MAP = {
    "$1,001 - $15,000":           8_000,
    "$15,001 - $50,000":         32_500,
    "$50,001 - $100,000":        75_000,
    "$100,001 - $250,000":      175_000,
    "$250,001 - $500,000":      375_000,
    "$500,001 - $1,000,000":    750_000,
    "$1,000,001 - $5,000,000": 3_000_000,
    "$5,000,001 - $25,000,000": 15_000_000,
    "$25,000,001 - $50,000,000": 37_500_000,
}


class QuiverAdapter(BaseAdapter):
    adapter_id: ClassVar[str] = "stocks.quiver"
    source_class: ClassVar[str] = "institutional_flow"
    tier: ClassVar[str] = "B"
    tos_basis: ClassVar[str] = (
        "Quiver Quantitative Hobbyist plan — $30/mo, personal research use"
    )

    def __init__(self) -> None:
        self._api_key = os.environ.get("QUIVER_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("QUIVER_API_KEY is not set")

    def pull(self, since: datetime, cursor: str | None = None) -> Iterable[Post]:
        observed_at = datetime.now(timezone.utc)
        resolver    = EntityResolver()

        try:
            trades = self._fetch_trades()
        except Exception as exc:
            log.error("Quiver fetch failed: %s", exc)
            return

        log.info("Quiver: fetched %d congressional trades", len(trades))
        written = 0
        for trade in trades:
            post = self._trade_to_post(trade, observed_at)
            if post is None:
                continue
            self._write_institutional_position(trade, observed_at, resolver)
            written += 1
            yield post
        log.info("Quiver: yielded %d posts", written)

    def _fetch_trades(self) -> list[dict]:
        with httpx.Client(
            base_url=QUIVER_BASE,
            headers={
                "Authorization": "Token {}".format(self._api_key),
                "Accept": "application/json",
            },
            timeout=30.0,
        ) as client:
            resp = client.get("/beta/live/congresstrading")
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("results", []))
        return []

    def _trade_to_post(self, trade: dict, observed_at: datetime) -> Post | None:
        ticker = (trade.get("Ticker") or "").strip().upper()
        rep    = (trade.get("Representative") or "").strip()
        txn    = (trade.get("Transaction") or "").strip()
        amount = (trade.get("Amount") or "").strip()
        date   = (trade.get("Date") or "").strip()
        party  = (trade.get("Party") or "").strip()

        if not ticker or not rep or not txn:
            return None

        direction = "bought" if "purchase" in txn.lower() else "sold"
        text = "Representative {} ({}) {} ${} of {} on {}. Congressional STOCK Act disclosure.".format(
            rep, party, direction, amount, ticker, date
        )

        # Stable external_id: same hash forever for a given (rep, ticker, date, txn).
        # No date rotation — each unique STOCK Act trade is written exactly once.
        id_src      = "quiver:{}:{}:{}:{}".format(rep, ticker, date, txn)
        external_id = "quiver:" + hashlib.sha256(id_src.encode()).hexdigest()[:16]

        # published_at = actual trade date from the filing.
        # This makes the dedup key (adapter_id, external_id, entity_id, time) truly
        # unique per trade and stable across restarts.
        published_at = _parse_date(date) or observed_at.replace(hour=0, minute=0, second=0, microsecond=0)

        return Post(
            adapter_id   = self.adapter_id,
            source_class = "institutional_flow",
            external_id  = external_id,
            author_hash  = None,
            text         = text,
            entity_ids   = [ticker],
            observed_at  = observed_at,
            published_at = published_at,
            raw          = trade,
        )

    def _write_institutional_position(
        self,
        trade: dict,
        observed_at: datetime,
        resolver: EntityResolver,
    ) -> None:
        ticker = (trade.get("Ticker") or "").strip().upper()
        rep    = (trade.get("Representative") or "").strip()
        txn    = (trade.get("Transaction") or "").strip()
        amount = (trade.get("Amount") or "").strip()
        date   = (trade.get("Date") or "").strip()

        if not ticker or not rep:
            return

        # Resolve entity — auto-create if not in watchlist
        entity_id = None
        try:
            entity_id = resolver.resolve(
                module_id="stocks", symbol=ticker, kind="ticker"
            )
        except Exception:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO entities (module_id, canonical_symbol, kind)
                            VALUES ('stocks', %s, 'ticker')
                            ON CONFLICT (module_id, canonical_symbol, kind) DO NOTHING
                            RETURNING entity_id;
                        """, (ticker,))
                        row = cur.fetchone()
                        if not row:
                            cur.execute(
                                "SELECT entity_id FROM entities "
                                "WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                                (ticker,)
                            )
                            row = cur.fetchone()
                    conn.commit()
                    entity_id = str(row[0]) if row else None
            except Exception as exc2:
                log.warning("Quiver: could not create entity for %s: %s", ticker, exc2)
                return

        if not entity_id:
            return

        id_src    = "quiver:{}:{}:{}:{}".format(rep, ticker, date, txn)
        filing_id = "quiver:" + hashlib.sha256(id_src.encode()).hexdigest()[:16]
        shares    = _parse_amount(amount)
        filed_at  = _parse_date(date) or observed_at

        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO institutional_positions
                            (filing_id, filer, entity_id, shares, filed_at, kind)
                        VALUES (%s, %s, %s, %s, %s, 'Congress')
                        ON CONFLICT (filing_id) DO NOTHING;
                    """, (filing_id, rep, entity_id, shares, filed_at))
                conn.commit()
        except Exception as exc:
            log.warning("Quiver: institutional_positions insert failed: %s", exc)


def _parse_date(date_str: str) -> datetime | None:
    if not date_str or not date_str.strip():
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_amount(amount_str: str) -> int:
    if not amount_str:
        return 0
    midpoint = AMOUNT_MAP.get(amount_str.strip())
    if midpoint is not None:
        return midpoint
    try:
        return int(amount_str.replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0
