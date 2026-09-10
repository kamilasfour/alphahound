import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Total posts by source class
        cur.execute("""
            SELECT source_class, COUNT(*) as total,
                   MIN(time) as oldest, MAX(time) as newest
            FROM raw_posts
            GROUP BY source_class
            ORDER BY total DESC;
        """)
        posts = cur.fetchall()

        # Unscored posts by source class
        cur.execute("""
            SELECT rp.source_class, COUNT(*) as unscored
            FROM raw_posts rp
            WHERE NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id = rp.entity_id
                AND ss.source_class = rp.source_class
                AND ss.time = rp.time
            )
            GROUP BY rp.source_class
            ORDER BY unscored DESC;
        """)
        unscored = {r[0]: r[1] for r in cur.fetchall()}

        # Scoring watermarks
        cur.execute("""
            SELECT source_class, last_scored_at
            FROM scoring_watermark
            ORDER BY source_class;
        """)
        watermarks = {r[0]: r[1] for r in cur.fetchall()}

        # Total scored
        cur.execute("""
            SELECT source_class, COUNT(*) as scored
            FROM sentiment_scores
            GROUP BY source_class
            ORDER BY scored DESC;
        """)
        scored = {r[0]: r[1] for r in cur.fetchall()}

print()
print("=" * 70)
print("  RAW POSTS vs SCORED — DATA UTILIZATION REPORT")
print("  Generated: {}".format(now.strftime('%Y-%m-%d %H:%M UTC')))
print("=" * 70)
print()
print("{:<25} {:>8} {:>8} {:>8} {:>6}  {}".format(
    "SOURCE CLASS", "TOTAL", "SCORED", "UNSCORED", "UTIL%", "WATERMARK"))
print("-" * 70)

for source_class, total, oldest, newest in posts:
    sc = scored.get(source_class, 0)
    un = unscored.get(source_class, 0)
    util = round(sc / total * 100) if total > 0 else 0
    wm = watermarks.get(source_class)
    wm_str = wm.strftime('%m/%d %H:%M') if wm else "never"
    flag = " ← DEAD DATA" if util == 0 and total > 0 else ""
    flag = " ← PARTIAL" if 0 < util < 50 and total > 100 else flag
    print("{:<25} {:>8,} {:>8,} {:>8,} {:>5}%  {}{}".format(
        source_class, total, sc, un, util, wm_str, flag))

total_posts  = sum(r[1] for r in posts)
total_scored_all = sum(scored.values())
total_unscored   = sum(unscored.values())
print("-" * 70)
print("{:<25} {:>8,} {:>8,} {:>8,} {:>5}%".format(
    "TOTAL", total_posts, total_scored_all, total_unscored,
    round(total_scored_all / total_posts * 100) if total_posts > 0 else 0))

print()
print("  At 200 posts/run every 30min = 9,600 posts/day capacity")
print("  Unscored backlog would clear in: ~{} runs ({} hours)".format(
    round(total_unscored / 200),
    round(total_unscored / 200 * 0.5, 1)
))
print()
print("=" * 70)
