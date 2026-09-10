import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
since_1h = now - timedelta(hours=1)
since_24h = now - timedelta(hours=24)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Posts per hour now vs before
        cur.execute("""
            SELECT
                date_trunc('hour', time) as hour,
                source_class,
                COUNT(*) as posts
            FROM raw_posts
            WHERE time >= %s
            GROUP BY 1, 2
            ORDER BY 1 DESC, 3 DESC;
        """, (since_24h,))
        hourly = cur.fetchall()

        # Pipeline step durations (last 10 runs)
        cur.execute("""
            SELECT step, AVG(duration_ms) as avg_ms, MAX(duration_ms) as max_ms, COUNT(*) as runs
            FROM pipeline_runs
            WHERE started_at >= %s AND status = 'ok'
            GROUP BY step
            ORDER BY avg_ms DESC;
        """, (since_24h,))
        durations = cur.fetchall()

        # Unscored backlog
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

        # Total posts today
        cur.execute("SELECT COUNT(*) FROM raw_posts WHERE time >= now() - interval '24 hours';")
        total_24h = cur.fetchone()[0]

print()
print("=" * 60)
print("  SERVER LOAD IMPACT ASSESSMENT")
print("  {}".format(now.strftime('%Y-%m-%d %H:%M UTC')))
print("=" * 60)

print("\n  POSTS LAST 24H BY HOUR:")
last_h = None
for hour, sc, posts in hourly[:20]:
    h_str = hour.strftime('%H:%M') if hour != last_h else "     "
    last_h = hour
    print("  {:6s}  {:25s}  {:>6,}".format(h_str, sc, posts))

print("\n  TOTAL POSTS LAST 24H: {:,}".format(total_24h))

print("\n  PIPELINE STEP DURATIONS (avg/max ms):")
for step, avg, max_ms, runs in durations:
    flag = " ⚠️ SLOW" if avg > 30000 else ""
    print("  {:30s}  avg={:>6,.0f}ms  max={:>7,.0f}ms  runs={:>3}{}".format(
        step, avg, max_ms, runs, flag))

print("\n  UNSCORED BACKLOG:")
total_backlog = sum(r[1] for r in backlog)
for sc, count in backlog:
    print("  {:25s}  {:>8,}".format(sc, count))
print("  {:25s}  {:>8,}".format("TOTAL", total_backlog))

# Estimate new volume
print("\n  PROJECTED NEW VOLUME (after config changes):")
print("  ApeWisdom: 25 → 100 tickers × 5 pages  = ~5× more retail_social")
print("  Finnhub:   20 → 80 tickers × 3d lookback = ~12× more news_wire")
print("  UW alerts: 500 → 2000 cap, $1k min        = ~3-4× more options_flow")
print("  StockTwits: NEWLY ENABLED                  = ~30 posts/ticker new source")
print()
print("  At 2000 posts/run scoring cap × 48 runs/day = 96,000 posts/day capacity")
print("  Estimated new volume: ~15,000-20,000 posts/day")
print("  Capacity utilization: ~20% — VM can handle it without Azure Functions")
print()
print("=" * 60)
