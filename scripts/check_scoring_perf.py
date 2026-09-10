import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)
since_24h = now - timedelta(hours=24)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Scoring run durations
        cur.execute("""
            SELECT step, status, duration_ms, rows_affected, started_at, error
            FROM pipeline_runs
            WHERE step = 'score-new'
            AND started_at >= %s
            ORDER BY started_at DESC LIMIT 20;
        """, (since_24h,))
        score_runs = cur.fetchall()

        # All pipeline steps avg duration last 24h
        cur.execute("""
            SELECT step, 
                   AVG(duration_ms) as avg_ms,
                   MAX(duration_ms) as max_ms,
                   MIN(duration_ms) as min_ms,
                   COUNT(*) as runs,
                   SUM(rows_affected) as total_rows
            FROM pipeline_runs
            WHERE started_at >= %s AND status = 'ok'
            GROUP BY step
            ORDER BY avg_ms DESC;
        """, (since_24h,))
        all_steps = cur.fetchall()

        # Current backlog size
        cur.execute("""
            SELECT source_class, COUNT(*) as unscored
            FROM raw_posts rp
            WHERE source_class IN ('news_wire','retail_social','analyst_curated')
            AND NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND date_trunc('hour', ss.time) = date_trunc('hour', rp.time)
            )
            GROUP BY source_class;
        """)
        backlog = cur.fetchall()

        # How many posts scored per run on average
        cur.execute("""
            SELECT AVG(rows_affected), MAX(rows_affected), MIN(rows_affected)
            FROM pipeline_runs
            WHERE step = 'score-new' AND status = 'ok'
            AND started_at >= %s;
        """, (since_24h,))
        score_stats = cur.fetchone()

        # Watermarks
        cur.execute("""
            SELECT source_class, last_scored_at
            FROM scoring_watermark ORDER BY source_class;
        """)
        watermarks = cur.fetchall()

print()
print("=" * 65)
print("  SCORING PERFORMANCE REPORT")
print("  {}".format(now.astimezone(PT).strftime('%a %b %d %I:%M %p PT')))
print("=" * 65)

print("\nSCORE-NEW RUNS (last 24h):")
print("  {:20s}  {:>8}  {:>6}  {}".format("TIME PT", "DURATION", "ROWS", "STATUS"))
print("  " + "-"*55)
for step, status, dur, rows, started, err in score_runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    dur_s = "{:.1f}s".format(dur/1000) if dur else "?"
    err_str = " ERR: {}".format(err[:30]) if err else ""
    flag = " ⚠️ SLOW" if dur and dur > 120000 else ""
    print("  {:20s}  {:>8}  {:>6}  {}{}{}".format(
        pt, dur_s, rows or 0, status, flag, err_str))

if score_stats and score_stats[0]:
    print("\nSCORING STATS:")
    print("  Avg posts/run:  {:.0f}".format(score_stats[0]))
    print("  Max posts/run:  {}".format(score_stats[1]))
    print("  Min posts/run:  {}".format(score_stats[2]))

print("\nALL PIPELINE STEPS — AVG DURATION:")
for step, avg, max_ms, min_ms, runs, total_rows in all_steps:
    bar = "█" * min(30, int(avg/2000))
    flag = " ⚠️" if avg > 60000 else ""
    print("  {:28s}  {:>7.1f}s  max={:.1f}s  {}{}".format(
        step, avg/1000, max_ms/1000, bar, flag))

print("\nCURRENT BACKLOG:")
total = sum(r[1] for r in backlog)
for sc, count in backlog:
    print("  {:25s}  {:>8,}".format(sc, count))
print("  {:25s}  {:>8,}".format("TOTAL", total))

print("\nSCORING WATERMARKS:")
for sc, wm in watermarks:
    if wm:
        age_mins = int((now - wm.replace(tzinfo=timezone.utc)).total_seconds()/60)
        print("  {:25s}  last scored {}m ago".format(sc, age_mins))
    else:
        print("  {:25s}  never scored".format(sc))

print()
print("=" * 65)
