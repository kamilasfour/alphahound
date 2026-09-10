import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT step, status, error, started_at
            FROM pipeline_runs
            WHERE step = 'massive-history'
            ORDER BY started_at DESC LIMIT 5;
        """)
        rows = cur.fetchall()

print()
for step, status, error, started in rows:
    print("{} [{}] {}".format(
        started.astimezone(PT).strftime('%I:%M %p PT'),
        status,
        step
    ))
    if error:
        print("  ERROR: {}".format(error[:300]))
    print()
