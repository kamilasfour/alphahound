"""Parallel ingest runner — runs all enabled adapters concurrently.

Replaces the sequential ingest-all CLI command for the pipeline.
Adapters are I/O bound (HTTP calls) so threading is safe and effective.
Expected speedup: 338s sequential -> ~60s parallel (6 workers).

Usage:
    .\.venv\Scripts\python.exe scripts\ingest_parallel.py
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import socket
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("ingest_parallel")

from alphahound.engine.storage import (
    EntityResolver, finish_ingest_run, get_conn,
    load_adapter_meta, start_ingest_run, write_posts
)


def get_enabled_adapters():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT adapter_id FROM source_adapters
                WHERE enabled = true ORDER BY adapter_id;
            """)
            return [r[0] for r in cur.fetchall()]


def build_adapter(adapter_id: str):
    source = adapter_id.split(".", 1)[-1]
    if source == "apewisdom":
        from alphahound.modules.stocks.adapters.apewisdom import ApeWisdomAdapter
        return ApeWisdomAdapter(max_pages=5)
    if source == "finnhub":
        from alphahound.modules.stocks.adapters.finnhub import FinnhubAdapter
        return FinnhubAdapter()
    if source == "stocktwits":
        from alphahound.modules.stocks.adapters.stocktwits import StockTwitsAdapter
        from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST
        return StockTwitsAdapter(watchlist=FULL_WATCHLIST)
    if source == "unusual_whales":
        from alphahound.modules.stocks.adapters.unusual_whales import UnusualWhalesAdapter
        return UnusualWhalesAdapter()
    if source == "quiver":
        from alphahound.modules.stocks.adapters.quiver import QuiverAdapter
        return QuiverAdapter()
    if source == "substack":
        from alphahound.modules.stocks.adapters.substack import SubstackAdapter
        return SubstackAdapter()
    if source == "massive":
        from alphahound.modules.stocks.adapters.massive import MassiveAdapter
        return MassiveAdapter()
    if source == "kalshi":
        from alphahound.modules.stocks.adapters.kalshi import KalshiAdapter
        return KalshiAdapter()
    if source == "yahoo_finance":
        from alphahound.modules.stocks.adapters.yahoo_finance import YahooFinanceAdapter
        return YahooFinanceAdapter()
    if source == "earnings_calendar":
        from alphahound.engine.signals.earnings_calendar import EarningsCalendarAdapter
        return EarningsCalendarAdapter()
    if source == "alpha_vantage":
        from alphahound.modules.stocks.adapters.alpha_vantage import AlphaVantageAdapter
        return AlphaVantageAdapter()
    return None


def run_one(adapter_id: str) -> dict:
    try:
        adapter = build_adapter(adapter_id)
        if adapter is None:
            return {"adapter_id": adapter_id, "status": "skipped", "fetched": 0, "written": 0}

        meta     = load_adapter_meta(adapter_id)
        resolver = EntityResolver()  # each thread gets its own resolver
        run_id   = start_ingest_run(meta.adapter_id, host=socket.gethostname())

        try:
            since = datetime.now(timezone.utc)
            posts = list(adapter.pull(since=since))
            fetched = len(posts)
            written = write_posts(posts, adapter_meta=meta, resolver=resolver)
            finish_ingest_run(run_id, posts_fetched=fetched, posts_written=written, error=None)
            return {"adapter_id": adapter_id, "status": "ok", "fetched": fetched, "written": written}
        except Exception as exc:
            error_str = f"{type(exc).__name__}: {exc}"
            finish_ingest_run(run_id, posts_fetched=0, posts_written=0, error=error_str)
            return {"adapter_id": adapter_id, "status": "error", "fetched": 0, "written": 0, "error": error_str}

    except Exception as exc:
        return {"adapter_id": adapter_id, "status": "error", "fetched": 0, "written": 0,
                "error": f"{type(exc).__name__}: {exc}"}


def main():
    adapter_ids = get_enabled_adapters()
    if not adapter_ids:
        print("No enabled adapters found.")
        sys.exit(0)

    print(f"Running {len(adapter_ids)} adapters in parallel (max_workers=6)...")
    start = datetime.now(timezone.utc)

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_one, aid): aid for aid in adapter_ids}
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            if r["status"] == "skipped":
                print(f"  SKIP {r['adapter_id']}")
            elif r["status"] == "error":
                print(f"  FAIL {r['adapter_id']}: {r.get('error', '?')}")
                failures += 1
            else:
                print(f"  OK   {r['adapter_id']}: fetched={r['fetched']} wrote={r['written']}")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    print(f"\nIngest complete in {elapsed:.1f}s ({len(adapter_ids)} adapters, {failures} failures)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
