import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ip.filer, ip.shares, ip.filed_at, e.canonical_symbol, rp.raw
            FROM institutional_positions ip
            JOIN entities e ON e.entity_id = ip.entity_id
            LEFT JOIN raw_posts rp ON rp.adapter_id = 'stocks.quiver'
                AND rp.entity_id = ip.entity_id
                AND rp.time >= ip.filed_at - interval '1 day'
                AND rp.time <= ip.filed_at + interval '1 day'
            WHERE ip.kind = 'Congress'
            ORDER BY ip.filed_at DESC
            LIMIT 3;
        """)
        for r in cur.fetchall():
            print(f"\nFiler: {r[0]}")
            print(f"Ticker: {r[3]}, Shares: {r[1]}, Filed: {r[2].strftime('%Y-%m-%d')}")
            print(f"Raw keys: {list(r[4].keys()) if r[4] else 'None'}")
            if r[4]:
                print(f"Raw data: {r[4]}")
