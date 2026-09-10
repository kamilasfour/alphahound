import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'institutional_positions'
            ORDER BY ordinal_position;
        """)
        print("institutional_positions columns:")
        for r in cur.fetchall():
            print(f"  {r[0]:<25} {r[1]}")

        cur.execute("""
            SELECT ip.filer, ip.shares, ip.filed_at, e.canonical_symbol
            FROM institutional_positions ip
            JOIN entities e ON e.entity_id = ip.entity_id
            WHERE ip.kind = 'Congress'
            ORDER BY ip.filed_at DESC LIMIT 5;
        """)
        print("\nMost recent congressional trades:")
        for r in cur.fetchall():
            print(f"  {r[2].strftime('%Y-%m-%d')}  {r[3]:<6}  {r[0][:40]}  ${r[1]:,}")
