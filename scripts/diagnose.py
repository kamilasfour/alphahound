import os
import json
from dotenv import load_dotenv
load_dotenv(r"C:\alphahound_project\.env")

import psycopg

conn_str = os.environ["DATABASE_URL"]

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:

        print("=== 1. historical_events with direction ===")
        cur.execute("SELECT COUNT(*) FROM historical_events WHERE phases->>'direction' IS NOT NULL;")
        print(cur.fetchone())

        print("\n=== 2. historical_events resolved ===")
        cur.execute("SELECT COUNT(*) FROM historical_events WHERE phases->>'outcome_correct' IS NOT NULL;")
        print(cur.fetchone())

        print("\n=== 3. price_snapshots count + range ===")
        cur.execute("SELECT COUNT(*), MIN(time), MAX(time) FROM price_snapshots;")
        print(cur.fetchone())

        print("\n=== 4. sample historical_events phases (5 rows) ===")
        cur.execute("SELECT event_id, label, start_time, phases FROM historical_events LIMIT 5;")
        for row in cur.fetchall():
            print(row[0], row[1], row[2])
            print("  phases:", json.dumps(row[3], indent=2) if row[3] else None)

        print("\n=== 5. trade_log count + sample notes ===")
        cur.execute("SELECT COUNT(*) FROM trade_log;")
        print("total rows:", cur.fetchone())
        cur.execute("SELECT entity_id, side, size, pnl, notes, time FROM trade_log ORDER BY time DESC LIMIT 5;")
        for row in cur.fetchall():
            print(row[0], row[1], row[2], "pnl:", row[3])
            print("  notes:", json.dumps(row[4], indent=2) if row[4] else None)

        print("\n=== 6. hit_rate table ===")
        cur.execute("SELECT * FROM hit_rate ORDER BY computed_at DESC LIMIT 5;")
        rows = cur.fetchall()
        print("rows:", len(rows))
        for row in rows:
            print(row)

        print("\n=== 7. divergence_events last 24h ===")
        cur.execute("""
            SELECT e.canonical_symbol, de.d_value, de.p_value, de.time
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= now() - interval '24 hours'
            ORDER BY de.d_value DESC LIMIT 10;
        """)
        for row in cur.fetchall():
            print(row)

        print("\n=== 8. pipeline_runs last 10 ===")
        cur.execute("SELECT step, status, rows_affected, duration_ms, error, started_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 10;")
        for row in cur.fetchall():
            print(row)
