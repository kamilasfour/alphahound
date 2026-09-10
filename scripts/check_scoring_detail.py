import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Last 3 scoring runs
        cur.execute("""
            SELECT step, status, started_at, duration_ms, rows_affected
            FROM pipeline_runs
            WHERE step = 'score-new'
            ORDER BY started_at DESC LIMIT 5;
        """)
        score_runs = cur.fetchall()

        # Current backlog
        cur.execute("""
            SELECT source_class, COUNT(*) as unscored
            FROM raw_posts rp
            WHERE source_class IN ('news_wire','retail_social','analyst_curated')
            AND NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND ss.time = rp.time
            )
            GROUP BY source_class ORDER BY unscored DESC;
        """)
        backlog = cur.fetchall()

        # Watermarks
        cur.execute("SELECT source_class, last_scored_at FROM scoring_watermark ORDER BY source_class;")
        watermarks = cur.fetchall()

        # How many posts exist total vs scored
        cur.execute("""
            SELECT
                rp.source_class,
                COUNT(*) as total,
                SUM(CASE WHEN ss.entity_id IS NOT NULL THEN 1 ELSE 0 END) as scored
            FROM raw_posts rp
            LEFT JOIN sentiment_scores ss
                ON ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND ss.time = rp.time
            WHERE rp.source_class IN ('news_wire','retail_social','analyst_curated')
            GROUP BY rp.source_class;
        """)
        totals = cur.fetchall()

print()
print("=" * 60)
print("  SCORING DIAGNOSIS — {}".format(now.astimezone(PT).strftime('%I:%M %p PT')))
print("=" * 60)

print("\nLAST SCORING RUNS:")
for step, status, started, dur, rows in score_runs:
    pt = started.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    print("  {} {:>6.1f}s  {:>4} rows  {}".format(
        "✅" if status=="ok" else "❌", (dur or 0)/1000, rows or 0, pt))

print("\nCURRENT BACKLOG (unscored):")
total_backlog = sum(r[1] for r in backlog)
for sc, count in backlog:
    print("  {:25s}  {:>8,}".format(sc, count))
print("  {:25s}  {:>8,}".format("TOTAL", total_backlog))

print("\nTOTAL vs SCORED:")
for sc, total, scored in totals:
    pct = round(scored/total*100) if total > 0 else 0
    unscored = total - scored
    print("  {:25s}  total={:>7,}  scored={:>7,}  unscored={:>7,}  {}%".format(
        sc, total, scored, unscored, pct))

print("\nWATERMARKS:")
for sc, wm in watermarks:
    if wm:
        age = int((now - wm.replace(tzinfo=timezone.utc)).total_seconds()/60)
        print("  {:25s}  {}  ({}m ago)".format(
            sc, wm.astimezone(PT).strftime('%I:%M %p PT'), age))
    else:
        print("  {:25s}  never".format(sc))

print()
