import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")

with get_conn() as conn:
    with conn.cursor() as cur:

        # Unscored news_wire breakdown by age
        cur.execute("""
            SELECT
                CASE
                    WHEN time >= now() - interval '24 hours' THEN 'last 24h'
                    WHEN time >= now() - interval '72 hours' THEN '24-72h'
                    WHEN time >= now() - interval '7 days'  THEN '3-7 days'
                    ELSE 'older than 7d'
                END as age_bucket,
                COUNT(*) as unscored
            FROM raw_posts rp
            WHERE source_class = 'news_wire'
            AND NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND date_trunc('hour', ss.time) = date_trunc('hour', rp.time)
            )
            GROUP BY 1
            ORDER BY 1;
        """)
        age_buckets = cur.fetchall()

        # Scoring watermark for news_wire
        cur.execute("""
            SELECT last_scored_at FROM scoring_watermark
            WHERE source_class = 'news_wire';
        """)
        wm = cur.fetchone()

        # Current batch size setting
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts
            WHERE source_class = 'news_wire'
            AND time >= now() - interval '24 hours';
        """)
        posts_24h = cur.fetchone()[0]

        # How many score runs in last 24h
        cur.execute("""
            SELECT COUNT(*), MAX(started_at) FROM pipeline_runs
            WHERE step = 'score-new' AND status = 'ok'
            AND started_at >= now() - interval '24 hours';
        """)
        score_runs = cur.fetchone()

        # Total unscored
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts rp
            WHERE source_class = 'news_wire'
            AND NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND date_trunc('hour', ss.time) = date_trunc('hour', rp.time)
            );
        """)
        total_unscored = cur.fetchone()[0]

now = datetime.now(timezone.utc)
print()
print("=" * 60)
print("  NEWS_WIRE SCORING BACKLOG REPORT")
print("  {}".format(now.astimezone(PT).strftime('%a %b %d %I:%M %p PT')))
print("=" * 60)
print()
print("  Unscored by age:")
for bucket, count in age_buckets:
    bar = "#" * min(40, count // 10)
    print("  {:20s} {:>6,}  {}".format(bucket, count, bar))
print()
print("  Total unscored       : {:,}".format(total_unscored))
print("  New posts last 24h   : {:,}".format(posts_24h))
print()
print("  Score runs last 24h  : {}".format(score_runs[0] if score_runs else 0))
print("  Last score run       : {}".format(
    score_runs[1].astimezone(PT).strftime('%I:%M %p PT') if score_runs and score_runs[1] else "never"))
print("  Watermark            : {}".format(
    wm[0].astimezone(PT).strftime('%I:%M %p PT') if wm and wm[0] else "never"))
print()
score_runs_per_day = score_runs[0] if score_runs else 0
cap = 500
capacity = score_runs_per_day * cap
print("  At {} posts/run x {} runs/day = {:,} posts/day capacity".format(
    cap, score_runs_per_day, capacity))
if capacity > 0:
    days_to_clear = total_unscored / capacity
    print("  Backlog clears in    : {:.1f} days at current rate".format(days_to_clear))
else:
    print("  No score runs detected in last 24h!")
print()
print("=" * 60)
