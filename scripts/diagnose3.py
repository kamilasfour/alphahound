import os
import json
from dotenv import load_dotenv
load_dotenv(r"C:\alphahound_project\.env")
import psycopg

conn_str = os.environ["DATABASE_URL"]

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:

        print("=== raw notes from 3 trade_log rows ===")
        cur.execute("""
            SELECT trade_id, side, notes
            FROM trade_log
            WHERE venue = 'signal'
            ORDER BY time DESC
            LIMIT 3;
        """)
        for row in cur.fetchall():
            print("trade_id:", row[0])
            print("side:", row[1])
            raw = row[2]
            print("notes type:", type(raw))
            print("notes raw:", repr(raw[:200]) if raw else None)
            # Try parsing
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                print("resolve_by:", parsed.get("outlook", {}).get("resolve_by"))
                print("stop_price:", parsed.get("stop_price"))
            except Exception as e:
                print("parse error:", e)
            print()

        print("=== check notes::jsonb cast works ===")
        cur.execute("""
            SELECT 
                trade_id,
                notes::jsonb->'outlook'->>'resolve_by' as resolve_by
            FROM trade_log
            WHERE venue = 'signal'
            ORDER BY time DESC
            LIMIT 5;
        """)
        for row in cur.fetchall():
            print(row)
