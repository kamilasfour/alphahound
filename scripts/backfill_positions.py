"""Backfill fill prices and open status for existing Alpaca positions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.execution.alpaca_broker import get_broker
from alphahound.engine.storage import get_conn

broker    = get_broker()
positions = broker.get_all_positions()

print(f"\nFound {len(positions)} open positions in Alpaca:\n")

with get_conn() as conn:
    with conn.cursor() as cur:

        # First — check actual column names in trade_log
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trade_log' ORDER BY ordinal_position
        """)
        cols = [r[0] for r in cur.fetchall()]
        print(f"trade_log columns: {cols}\n")

        for pos in positions:
            print(f"  {pos.ticker:6s} {pos.side:5s}  entry=${pos.avg_entry:.2f}  "
                  f"current=${pos.current_price:.2f}  "
                  f"P&L=${pos.unrealized_pl:+.2f} ({pos.unrealized_pl_pct:+.1f}%)")

            cur.execute(
                "SELECT entity_id FROM entities "
                "WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker'",
                (pos.ticker,)
            )
            row = cur.fetchone()
            if not row:
                print(f"    WARNING: No entity found for {pos.ticker}")
                continue

            entity_id = str(row[0])

            # Check what's currently in trade_log for this entity
            cur.execute(
                "SELECT time, side, size, filled_price, alpaca_order_id, alpaca_status "
                "FROM trade_log WHERE entity_id=%s ORDER BY time DESC LIMIT 3",
                (entity_id,)
            )
            rows = cur.fetchall()
            for r in rows:
                print(f"    DB row: {r}")

            # Update — set filled_price where alpaca_order_id exists
            cur.execute(
                """
                UPDATE trade_log
                SET filled_price = %s
                WHERE entity_id = %s
                  AND alpaca_order_id IS NOT NULL
                  AND filled_price IS NULL
                """,
                (pos.avg_entry, entity_id)
            )
            updated = cur.rowcount
            print(f"    Updated {updated} row(s) with fill price ${pos.avg_entry:.2f}\n")

    conn.commit()

print("Done.")
