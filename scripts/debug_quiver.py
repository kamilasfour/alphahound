import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import httpx
from datetime import datetime, timezone
from alphahound.engine.storage import get_conn

key = os.environ.get("QUIVER_API_KEY", "")

# Fetch trades
resp = httpx.get(
    "https://api.quiverquant.com/beta/live/congresstrading",
    headers={"Authorization": "Token {}".format(key), "Accept": "application/json"},
    timeout=15.0
)
trades = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
print("Fetched: {} trades".format(len(trades)))

# Check a sample
sample = trades[:3]
for t in sample:
    print("  Sample:", t.get("Representative"), t.get("Ticker"), t.get("Date"), t.get("Transaction"))

# Check how many already exist in raw_posts
from alphahound.modules.stocks.adapters.quiver import QuiverAdapter
import hashlib

adapter = QuiverAdapter()
external_ids = []
for trade in trades[:50]:
    ticker = (trade.get("Ticker") or "").strip().upper()
    rep    = (trade.get("Representative") or "").strip()
    txn    = (trade.get("Transaction") or "").strip()
    date   = (trade.get("Date") or "").strip()
    if not ticker or not rep or not txn:
        continue
    id_src = "quiver:{}:{}:{}:{}".format(rep, ticker, date, txn)
    external_id = "quiver:" + hashlib.sha256(id_src.encode()).hexdigest()[:16]
    external_ids.append(external_id)

if external_ids:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM raw_posts
                WHERE external_id = ANY(%s)
                AND adapter_id = 'stocks.quiver';
            """, (external_ids,))
            existing = cur.fetchone()[0]
    print("\nOf first 50 trades:")
    print("  Already in DB: {}".format(existing))
    print("  Would be new:  {}".format(len(external_ids) - existing))

# Check total quiver posts in DB
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), MAX(time) FROM raw_posts WHERE adapter_id='stocks.quiver';")
        row = cur.fetchone()
        print("\nTotal quiver posts in DB: {}  latest: {}".format(row[0], row[1]))

        # Check if write_posts is finding entity_ids
        cur.execute("""
            SELECT e.canonical_symbol, COUNT(*) FROM raw_posts rp
            JOIN entities e ON e.entity_id = rp.entity_id
            WHERE rp.adapter_id = 'stocks.quiver'
            GROUP BY e.canonical_symbol
            ORDER BY COUNT(*) DESC LIMIT 10;
        """)
        rows = cur.fetchall()
        if rows:
            print("Top tickers in quiver posts:")
            for sym, count in rows:
                print("  {}: {}".format(sym, count))
        else:
            print("NO quiver posts with valid entity_id found")
