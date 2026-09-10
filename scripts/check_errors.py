import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
since = now - timedelta(hours=1)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT step, status, rows_affected, duration_ms, error, started_at
            FROM pipeline_runs
            WHERE started_at >= %s
            ORDER BY started_at DESC;
        """, (since,))
        rows = cur.fetchall()

print()
for step, status, rows_aff, dur, error, started in rows:
    mins_ago = int((now - started.replace(tzinfo=timezone.utc)).total_seconds() / 60)
    print("[{}] {:20s}  {}m ago".format(status.upper(), step, mins_ago))
    if error:
        print("     ERROR: {}".format(error))
    print()
