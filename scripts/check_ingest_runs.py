import sys, os, subprocess
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
        # Last ingest run per adapter with error
        cur.execute("""
            SELECT adapter_id, started_at, finished_at,
                   posts_fetched, posts_written, error
            FROM ingest_runs
            WHERE started_at >= now() - interval '2 hours'
            ORDER BY started_at DESC;
        """)
        runs = cur.fetchall()

        # Check if adapters are enabled
        cur.execute("""
            SELECT adapter_id, enabled FROM source_adapters ORDER BY adapter_id;
        """)
        adapters = {r[0]: r[1] for r in cur.fetchall()}

print()
print("=" * 70)
print("  ADAPTER INGEST RUNS — LAST 2H")
print("=" * 70)
print()
print("{:<30} {:>6} {:>6} {:>6}  {}".format("ADAPTER", "FETCH", "WROTE", "DUR", "ERROR"))
print("-" * 70)

seen = set()
for adapter_id, started, finished, fetched, written, error in runs:
    if adapter_id in seen:
        continue
    seen.add(adapter_id)
    enabled = adapters.get(adapter_id, False)
    dur = round((finished-started).total_seconds(),1) if finished and started else None
    dur_str = "{}s".format(dur) if dur else "?"
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    err_str = error[:50] if error else ""
    flag = "" if enabled else " [DISABLED]"
    print("{:<30} {:>6} {:>6} {:>6}  {}{}".format(
        adapter_id, fetched or 0, written or 0, dur_str, err_str, flag))

# Show adapters with no recent runs
print()
print("ADAPTERS WITH NO RUNS IN LAST 2H:")
for adapter_id, enabled in adapters.items():
    if adapter_id not in seen:
        print("  [{}] {}".format("ON" if enabled else "OFF", adapter_id))
