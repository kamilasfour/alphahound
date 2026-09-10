import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        for ticker in ['MU', 'ORCL']:
            cur.execute("""
                SELECT price, change_5d_pct, time
                FROM price_snapshots ps
                JOIN entities e ON e.entity_id = ps.entity_id
                WHERE e.canonical_symbol = %s AND e.module_id = 'stocks'
                ORDER BY ps.time DESC LIMIT 1;
            """, (ticker,))
            row = cur.fetchone()
            print(f"{ticker}: price=${row[0]:.2f}  5d={row[1]:.1f}%  as_of={row[2]}" if row else f"{ticker}: NO PRICE DATA")
