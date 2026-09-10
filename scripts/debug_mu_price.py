"""
Debug: find what's wrong with MU price ($751) and the ticker cross-contamination.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

MU_EID   = '15c6d1bc-0b4d-4432-a75e-40527abf0306'
NVDA_EID = 'e581bd20-4ee6-4779-a66e-2036865dfd26'

with get_conn() as conn:
    with conn.cursor() as cur:

        # Get actual raw_posts column names first
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='raw_posts' ORDER BY ordinal_position;")
        rp_cols = [r[0] for r in cur.fetchall()]
        print(f"\n=== raw_posts columns ===\n  {rp_cols}")

        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='price_snapshots' ORDER BY ordinal_position;")
        ps_cols = [r[0] for r in cur.fetchall()]
        print(f"\n=== price_snapshots columns ===\n  {ps_cols}")

        print("\n=== price_snapshots: all distinct prices for MU ===")
        cur.execute("SELECT DISTINCT price FROM price_snapshots WHERE entity_id = %s ORDER BY price DESC LIMIT 5;", (MU_EID,))
        print(f"  MU prices: {[r[0] for r in cur.fetchall()]}")

        print("\n=== price_snapshots: all distinct prices for SPY ===")
        cur.execute("""
            SELECT DISTINCT price FROM price_snapshots
            WHERE entity_id = (SELECT entity_id FROM entities WHERE canonical_symbol='SPY' AND module_id='stocks')
            ORDER BY price DESC LIMIT 3;
        """)
        print(f"  SPY prices: {[r[0] for r in cur.fetchall()]}")

        print("\n=== price_snapshots: all distinct prices for NVDA ===")
        cur.execute("SELECT DISTINCT price FROM price_snapshots WHERE entity_id = %s ORDER BY price DESC LIMIT 3;", (NVDA_EID,))
        print(f"  NVDA prices: {[r[0] for r in cur.fetchall()]}")

        print("\n=== price_daily: MU bars ===")
        cur.execute("SELECT date, close FROM price_daily WHERE entity_id = %s ORDER BY date DESC LIMIT 5;", (MU_EID,))
        rows = cur.fetchall()
        print(f"  MU daily: {rows if rows else '(no rows)'}")

        print("\n=== MU super signal breakdown ===")
        cur.execute("SELECT pillar_breakdown FROM convergence_signals WHERE entity_id = %s ORDER BY time DESC LIMIT 1;", (MU_EID,))
        row = cur.fetchone()
        if row and row[0]:
            bd = row[0]
            print(f"  composite={bd.get('composite_score')}  direction={bd.get('direction')}")
            for p in bd.get('pillars', []):
                if p['fired']:
                    print(f"  FIRED: {p['name']}  score={p['score']}  |  {p['evidence'][:100]}")

        print("\n=== sentiment_scores: MU institutional_flow polarity ===")
        cur.execute("""
            SELECT source_class, AVG(polarity), COUNT(*)
            FROM sentiment_scores WHERE entity_id = %s AND time >= NOW() - INTERVAL '72 hours'
            GROUP BY source_class;
        """, (MU_EID,))
        for r in cur.fetchall():
            print(f"  {r[0]}: avg={r[1]:.3f}  n={r[2]}")

        print("\n=== options_flow: MU rows in last 48h ===")
        cur.execute("SELECT COUNT(*), MAX(unusual_score), AVG(unusual_score) FROM options_flow WHERE entity_id = %s AND time >= NOW() - INTERVAL '48 hours';", (MU_EID,))
        r = cur.fetchone()
        print(f"  count={r[0]}  max_unusual={r[1]}  avg_unusual={r[2]}")
