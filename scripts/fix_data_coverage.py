import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST

watchlist_set = set(FULL_WATCHLIST)

with get_conn() as conn:
    with conn.cursor() as cur:

        # 1. Disable EDGAR - it creates CIK entities not ticker entities
        cur.execute("""
            UPDATE source_adapters SET enabled = false
            WHERE adapter_id = 'stocks.edgar';
        """)
        print("Disabled stocks.edgar (CIK entities, not tickers -- Sprint 3 task)")

        # 2. Count CIK entities
        cur.execute("""
            SELECT COUNT(*) FROM entities
            WHERE canonical_symbol LIKE 'CIK:%';
        """)
        cik_count = cur.fetchone()[0]
        print("CIK entities in DB: {:,}".format(cik_count))

        # 3. Show orphan tickers (data ingested but not in watchlist)
        cur.execute("""
            SELECT e.canonical_symbol, COUNT(rp.external_id) as posts
            FROM entities e
            JOIN raw_posts rp ON rp.entity_id = e.entity_id
            WHERE e.module_id = 'stocks'
            AND e.canonical_symbol NOT LIKE 'CIK:%%'
            AND rp.time >= now() - interval '7 days'
            GROUP BY e.canonical_symbol
            HAVING COUNT(rp.external_id) > 5
            ORDER BY posts DESC;
        """)
        all_active = cur.fetchall()
        orphans = [(t, p) for t, p in all_active if t not in watchlist_set]

        print("\nOrphan tickers (data ingested, not in watchlist, >5 posts/7d):")
        for ticker, posts in orphans[:30]:
            print("  {:6s}  {:>5,} posts".format(ticker, posts))

        # 4. Verify adapter status
        cur.execute("""
            SELECT adapter_id, enabled FROM source_adapters ORDER BY enabled DESC, adapter_id;
        """)
        adapters = cur.fetchall()

    conn.commit()

print("\nAdapter status:")
for adapter_id, enabled in adapters:
    print("  [{}] {}".format("ON " if enabled else "OFF", adapter_id))

print("\nNote: Orphan tickers come from StockTwits/ApeWisdom mentioning")
print("tickers outside watchlist. They don't hurt -- dedup prevents")
print("duplicates and the divergence engine only fires on watchlist tickers.")
print("Add any you want to trade to the watchlist to activate them.")
