"""Debug trade_log notes for open positions."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()
from alphahound.engine.storage import get_conn

tickers = ['CTSH', 'CVNA', 'DVN', 'FIS', 'IT', 'KLAC', 'PANW', 'TXN', 'UPS']

with get_conn() as conn:
    with conn.cursor() as cur:
        for ticker in tickers:
            cur.execute("""
                SELECT tl.time, tl.side, tl.size, tl.filled_price,
                       tl.alpaca_order_id, tl.alpaca_status,
                       tl.notes IS NOT NULL as has_notes,
                       CASE WHEN tl.notes IS NOT NULL
                            THEN LEFT(tl.notes::text, 100)
                            ELSE 'NULL' END as notes_preview
                FROM trade_log tl
                JOIN entities e ON e.entity_id = tl.entity_id
                WHERE e.canonical_symbol = %s AND e.module_id = 'stocks'
                ORDER BY tl.time DESC LIMIT 4
            """, (ticker,))
            rows = cur.fetchall()
            print(f"\n{ticker}:")
            for r in rows:
                t, side, size, fill, order_id, status, has_notes, notes_prev = r
                print(f"  {str(t)[:16]} side={side} size={size} fill={fill} "
                      f"order={'YES' if order_id else 'NO'} status={status} "
                      f"notes={'YES' if has_notes else 'NO'} | {notes_prev[:80]}")
