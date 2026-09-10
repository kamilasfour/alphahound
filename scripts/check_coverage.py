import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
since_7d = now - timedelta(days=7)

with get_conn() as conn:
    with conn.cursor() as cur:

        # All tickers that have received ANY data in last 7 days
        cur.execute("""
            SELECT DISTINCT e.canonical_symbol, COUNT(rp.external_id) as posts
            FROM entities e
            LEFT JOIN raw_posts rp ON rp.entity_id = e.entity_id
                AND rp.time >= %s
            WHERE e.module_id = 'stocks'
            GROUP BY e.canonical_symbol
            ORDER BY posts DESC;
        """, (since_7d,))
        ingested = {r[0]: r[1] for r in cur.fetchall()}

        # Tickers with divergence events (signals)
        cur.execute("""
            SELECT DISTINCT e.canonical_symbol
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= %s;
        """, (since_7d,))
        has_signals = {r[0] for r in cur.fetchall()}

        # Tickers in DB but NOT in watchlist
        cur.execute("""
            SELECT DISTINCT canonical_symbol FROM entities
            WHERE module_id = 'stocks'
            ORDER BY canonical_symbol;
        """)
        all_db_tickers = {r[0] for r in cur.fetchall()}

watchlist_set = set(FULL_WATCHLIST)

# Tickers being ingested but not in watchlist
orphans = {t for t in ingested if t not in watchlist_set and ingested[t] > 0}
# Tickers in watchlist but never ingested
missing = {t for t in watchlist_set if t not in ingested or ingested[t] == 0}
# Tickers in watchlist with active data
active = {t for t in watchlist_set if ingested.get(t, 0) > 0}

print()
print("=" * 65)
print("  DATA COVERAGE AUDIT")
print("=" * 65)
print()
print("  Watchlist size:      {:>4}".format(len(watchlist_set)))
print("  Tickers in DB:       {:>4}".format(len(all_db_tickers)))
print("  Active (7d data):    {:>4}".format(len(active)))
print("  Missing (no data):   {:>4}".format(len(missing)))
print("  Orphans (not in wl): {:>4}".format(len(orphans)))

if missing:
    print("\n  WATCHLIST TICKERS WITH NO DATA (7d):")
    for t in sorted(missing):
        print("    {}".format(t))

if orphans:
    print("\n  TICKERS INGESTED BUT NOT IN WATCHLIST:")
    for t in sorted(orphans):
        print("    {:6s}  {} posts".format(t, ingested[t]))

print("\n  TOP 20 BY POST VOLUME (7d):")
top = sorted(ingested.items(), key=lambda x: x[1], reverse=True)[:20]
for ticker, posts in top:
    in_wl = "✓" if ticker in watchlist_set else "✗ NOT IN WL"
    has_sig = "📡" if ticker in has_signals else "  "
    print("  {} {:6s}  {:>6,} posts  {}".format(has_sig, ticker, posts, in_wl))

print("\n  TICKERS WITH SIGNALS (7d):")
for t in sorted(has_signals):
    print("    {:6s}  {} posts".format(t, ingested.get(t, 0)))

print()
print("=" * 65)
