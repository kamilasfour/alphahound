import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Check price_snapshots schema
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'price_snapshots' ORDER BY ordinal_position;
        """)
        print("price_snapshots:", [r[0] for r in cur.fetchall()])

        # Check tech_indicators schema
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tech_indicators' ORDER BY ordinal_position;
        """)
        print("tech_indicators:", [r[0] for r in cur.fetchall()])

        # Check macro_snapshots
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'macro_snapshots' ORDER BY ordinal_position;
        """)
        print("macro_snapshots:", [r[0] for r in cur.fetchall()])

        # Read macro_context.py to understand actual scoring
        cur.execute("""
            SELECT e.canonical_symbol, ps.price, ps.change_5d_pct, ps.time
            FROM price_snapshots ps
            JOIN entities e ON e.entity_id = ps.entity_id
            WHERE e.canonical_symbol IN ('SPY','QQQ','TLT','HYG','UVXY','UUP','EEM','VIX')
            AND e.module_id = 'stocks'
            ORDER BY e.canonical_symbol, ps.time DESC;
        """)
        rows = cur.fetchall()
        seen = set()
        print("\nMarket instruments:")
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0])
                chg = r[2] or 0
                print(f"  {r[0]:<6} ${r[1]:>8.2f}  5d={chg:>+6.2f}%")
