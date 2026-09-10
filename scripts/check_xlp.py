import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Get actual columns
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'trade_log' ORDER BY ordinal_position;
        """)
        cols = [r[0] for r in cur.fetchall()]
        print("trade_log columns:", cols)

        # All entries last 3h
        cur.execute("""
            SELECT * FROM trade_log
            WHERE time >= now() - interval '3 hours'
            ORDER BY time DESC LIMIT 20;
        """)
        rows = cur.fetchall()
        col_names = [d.name for d in cur.description]

        # Execute pipeline runs
        cur.execute("""
            SELECT step, status, started_at, duration_ms, rows_affected, error
            FROM pipeline_runs
            WHERE step IN ('execute','trade-advice','divergence-scan')
            AND started_at >= now() - interval '3 hours'
            ORDER BY started_at DESC LIMIT 15;
        """)
        exec_runs = cur.fetchall()

print("\nTRADE LOG LAST 3H:")
if not rows:
    print("  EMPTY — nothing written to trade_log in last 3h")
else:
    for row in rows:
        d = dict(zip(col_names, row))
        print("  " + str({k: v for k, v in d.items() if v is not None})[:120])

print("\nEXECUTE PIPELINE RUNS:")
for step, status, started, dur, rows_aff, err in exec_runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    print("  {} {:20s} {:>5.0f}s {:>4} rows {}{}".format(
        "✅" if status=="ok" else "❌",
        step, (dur or 0)/1000, rows_aff or 0, pt,
        "  ERR:"+err[:60] if err else ""))
