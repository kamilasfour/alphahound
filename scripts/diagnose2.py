import os
import json
from dotenv import load_dotenv
load_dotenv(r"C:\alphahound_project\.env")
import psycopg

conn_str = os.environ["DATABASE_URL"]

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:

        print("=== trade_log columns ===")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trade_log' 
            ORDER BY ordinal_position;
        """)
        for row in cur.fetchall():
            print(row)

        print("\n=== trade_log rows with resolve_by ===")
        cur.execute("""
            SELECT time, side, price,
                   notes::jsonb->>'resolve_by' as resolve_by
            FROM trade_log
            WHERE venue = 'signal'
              AND notes::jsonb->>'resolve_by' IS NOT NULL
            ORDER BY time ASC
            LIMIT 5;
        """)
        for row in cur.fetchall():
            print(row)

        print("\n=== price_snapshots — sample for first entity in trade_log ===")
        cur.execute("""
            SELECT tl.entity_id, e.canonical_symbol
            FROM trade_log tl
            JOIN entities e ON e.entity_id = tl.entity_id
            WHERE tl.venue = 'signal'
            LIMIT 1;
        """)
        row = cur.fetchone()
        if row:
            entity_id, symbol = row
            print(f"Checking price_snapshots for {symbol} ({entity_id})")
            cur.execute("""
                SELECT time, price FROM price_snapshots
                WHERE entity_id = %s
                ORDER BY time DESC LIMIT 5;
            """, (entity_id,))
            for r in cur.fetchall():
                print(r)
