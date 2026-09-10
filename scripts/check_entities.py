import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from alphahound.modules.stocks.watchlist.watchlist import FULL_WATCHLIST

with get_conn() as conn:
    with conn.cursor() as cur:

        # How many entities exist
        cur.execute("""
            SELECT COUNT(*) FROM entities
            WHERE module_id='stocks' AND kind='ticker';
        """)
        total_entities = cur.fetchone()[0]

        # Sample entities
        cur.execute("""
            SELECT canonical_symbol FROM entities
            WHERE module_id='stocks' AND kind='ticker'
            ORDER BY canonical_symbol LIMIT 20;
        """)
        sample = [r[0] for r in cur.fetchall()]

        # Check watchlist tickers missing from entities
        wl = list(FULL_WATCHLIST)
        cur.execute("""
            SELECT canonical_symbol FROM entities
            WHERE module_id='stocks' AND kind='ticker'
            AND canonical_symbol = ANY(%s);
        """, (wl,))
        found = {r[0] for r in cur.fetchall()}
        missing = [t for t in wl if t not in found]

        # Raw posts written per adapter today
        cur.execute("""
            SELECT adapter_id, COUNT(*) as posts
            FROM raw_posts
            WHERE time >= now() - interval '2 hours'
            GROUP BY adapter_id ORDER BY posts DESC;
        """)
        recent_posts = cur.fetchall()

        # Quiver entity issue
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts
            WHERE adapter_id='stocks.quiver'
            AND time >= now() - interval '2 hours';
        """)
        quiver_posts = cur.fetchone()[0]

print()
print("ENTITIES IN DB: {:,}".format(total_entities))
print("Sample:", sample[:10])
print()
print("WATCHLIST TICKERS MISSING FROM ENTITIES ({}/{}):".format(
    len(missing), len(wl)))
for t in missing[:20]:
    print("  ", t)
if len(missing) > 20:
    print("  ... and {} more".format(len(missing)-20))

print()
print("RAW POSTS WRITTEN LAST 2H:")
for adapter, count in recent_posts:
    print("  {:35s}  {:>6,}".format(adapter, count))

print()
print("QUIVER POSTS IN DB LAST 2H:", quiver_posts)
