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

        # Pipeline runs last 2 hours with timing
        cur.execute("""
            SELECT step, status, started_at, duration_ms, rows_affected, error
            FROM pipeline_runs
            WHERE started_at >= now() - interval '2 hours'
            ORDER BY started_at DESC
            LIMIT 40;
        """)
        runs = cur.fetchall()

        # Ingest runs with per-adapter timing
        cur.execute("""
            SELECT adapter_id, started_at, finished_at, posts_fetched, posts_written, error
            FROM ingest_runs
            WHERE started_at >= now() - interval '2 hours'
            ORDER BY started_at DESC
            LIMIT 30;
        """)
        ingest_runs = cur.fetchall()

print()
print("=" * 70)
print("  PIPELINE STATUS — {}".format(now.astimezone(PT).strftime('%I:%M:%S %p PT')))
print("=" * 70)

print("\nPIPELINE STEPS (last 2h):")
print("  {:25s} {:8s} {:>7s} {:>6s}  {}".format("STEP", "STATUS", "DUR", "ROWS", "TIME PT"))
print("  " + "-"*60)

current_cycle = None
for step, status, started, dur_ms, rows, error in runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT)
    pt_str = pt.strftime('%I:%M:%S %p')
    dur_str = "{:.1f}s".format(dur_ms/1000) if dur_ms else "running..."
    status_icon = "✅" if status == "ok" else "❌" if status == "error" else "⏳"
    age_secs = (now - started.replace(tzinfo=timezone.utc)).total_seconds()
    running = " ← STILL RUNNING ({:.0f}s)".format(age_secs) if not dur_ms and age_secs > 10 else ""
    err_str = " ERR: {}".format(error[:40]) if error else ""
    print("  {} {:25s} {:>7s} {:>6}  {}{}{}".format(
        status_icon, step, dur_str, rows or 0, pt_str, running, err_str))

print("\nADAPTER INGEST RUNS (last 2h):")
print("  {:30s} {:>7s} {:>7s} {:>6s}  {:>6s}  {}".format(
    "ADAPTER", "DUR", "FETCH", "WROTE", "STATUS", "STARTED PT"))
print("  " + "-"*70)

for adapter_id, started, finished, fetched, written, error in ingest_runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT)
    pt_str = pt.strftime('%I:%M:%S %p')
    if finished:
        dur = (finished - started).total_seconds()
        dur_str = "{:.1f}s".format(dur)
        status = "✅" if not error else "❌"
    else:
        dur = (now - started.replace(tzinfo=timezone.utc)).total_seconds()
        dur_str = "{:.0f}s...".format(dur)
        status = "⏳"
    err_str = " {}".format(error[:30]) if error else ""
    print("  {} {:30s} {:>7s} {:>7} {:>6}  {}{}".format(
        status, adapter_id, dur_str, fetched or 0, written or 0, pt_str, err_str))

print()
print("=" * 70)
