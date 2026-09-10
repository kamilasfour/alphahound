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

        # Pipeline cycle timing - last 2 hours
        cur.execute("""
            SELECT step,
                   COUNT(*) as runs,
                   ROUND(AVG(duration_ms)/1000,1) as avg_s,
                   ROUND(MAX(duration_ms)/1000,1) as max_s,
                   ROUND(MIN(duration_ms)/1000,1) as min_s,
                   SUM(rows_affected) as total_rows
            FROM pipeline_runs
            WHERE started_at >= now() - interval '2 hours'
            AND status = 'ok'
            GROUP BY step
            ORDER BY avg_s DESC;
        """)
        steps = cur.fetchall()

        # Full cycle duration (ingest start to health-check end)
        cur.execute("""
            SELECT
                date_trunc('minute', started_at) as cycle,
                MIN(started_at) as cycle_start,
                MAX(started_at + (duration_ms || ' milliseconds')::interval) as cycle_end,
                COUNT(DISTINCT step) as steps_run
            FROM pipeline_runs
            WHERE started_at >= now() - interval '2 hours'
            AND status = 'ok'
            GROUP BY date_trunc('minute', started_at)
            ORDER BY cycle DESC
            LIMIT 8;
        """)
        cycles = cur.fetchall()

        # Score task timing
        cur.execute("""
            SELECT started_at, duration_ms/1000 as secs, rows_affected
            FROM pipeline_runs
            WHERE step = 'score-new' AND status='ok'
            AND started_at >= now() - interval '2 hours'
            ORDER BY started_at DESC LIMIT 10;
        """)
        score_runs = cur.fetchall()

        # Ingest timing
        cur.execute("""
            SELECT adapter_id,
                   ROUND(AVG(EXTRACT(EPOCH FROM (finished_at-started_at))),1) as avg_s,
                   ROUND(MAX(EXTRACT(EPOCH FROM (finished_at-started_at))),1) as max_s,
                   SUM(posts_fetched) as total_fetched,
                   SUM(posts_written) as total_written
            FROM ingest_runs
            WHERE started_at >= now() - interval '2 hours'
            AND finished_at IS NOT NULL
            GROUP BY adapter_id
            ORDER BY avg_s DESC;
        """)
        ingest_timing = cur.fetchall()

        # Scheduler interval check - simpler approach
        cur.execute("""
            SELECT step,
                   COUNT(*) as runs,
                   ROUND(EXTRACT(EPOCH FROM
                       (MAX(started_at) - MIN(started_at))
                   ) / NULLIF(COUNT(*)-1,0) / 60, 1) as avg_interval_mins
            FROM pipeline_runs
            WHERE started_at >= now() - interval '2 hours'
            AND status = 'ok'
            AND step IN ('ingest-all','score-new','health-check')
            GROUP BY step
            ORDER BY step;
        """)
        intervals = cur.fetchall()

print()
print("=" * 65)
print("  PERFORMANCE REPORT — {}".format(now.astimezone(PT).strftime('%I:%M %p PT')))
print("=" * 65)

print("\nPIPELINE STEP TIMINGS (last 2h):")
print("  {:25s} {:>5} {:>7} {:>7} {:>7} {:>8}".format(
    "STEP", "RUNS", "AVG(s)", "MAX(s)", "MIN(s)", "ROWS"))
print("  " + "-"*60)
for step, runs, avg, max_s, min_s, rows in steps:
    flag = " ⚠️ SLOW" if avg > 60 else ""
    print("  {:25s} {:>5} {:>7} {:>7} {:>7} {:>8,}{}".format(
        step, runs, avg, max_s, min_s, rows or 0, flag))

print("\nFULL CYCLE DURATIONS (last 2h):")
print("  {:20s} {:>8}  STEPS".format("CYCLE START PT", "DUR(s)"))
print("  " + "-"*40)
for cycle, start, end, n_steps in cycles:
    pt = start.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M:%S %p')
    dur = round((end - start).total_seconds()) if end and start else "?"
    flag = " ⚠️" if isinstance(dur, int) and dur > 120 else ""
    print("  {:20s} {:>8}s  {}/13 steps{}".format(pt, dur, n_steps, flag))

print("\nSCORING RUNS (last 2h):")
print("  {:15s} {:>6} {:>5}".format("TIME PT", "SECS", "ROWS"))
for started, secs, rows in score_runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    print("  {:15s} {:>6.0f} {:>5}".format(pt, secs or 0, rows or 0))

print("\nINGEST ADAPTER TIMING (last 2h avg):")
print("  {:30s} {:>7} {:>7} {:>8} {:>8}".format(
    "ADAPTER", "AVG(s)", "MAX(s)", "FETCHED", "WROTE"))
print("  " + "-"*60)
for adapter, avg, max_s, fetched, wrote in ingest_timing:
    print("  {:30s} {:>7} {:>7} {:>8,} {:>8,}".format(
        adapter, avg or 0, max_s or 0, int(fetched or 0), int(wrote or 0)))

print("\nSCHEDULER INTERVAL CHECK:")
for step, runs, interval in intervals:
    flag = " ⚠️ IRREGULAR" if interval and interval > 6 else ""
    print("  {:25s} {:>3} runs  avg interval: {}min{}".format(
        step, runs, interval, flag))

print()
print("=" * 65)
