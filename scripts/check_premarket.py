import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

# Pre-market window: 4am-9:30am ET today
et_now = now.astimezone(ET)
premarket_start = et_now.replace(hour=4, minute=0, second=0, microsecond=0)
since_24h = now - timedelta(hours=24)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Posts ingested by hour in last 24h
        cur.execute("""
            SELECT
                date_trunc('hour', time AT TIME ZONE 'America/New_York') as hour_et,
                source_class,
                COUNT(*) as posts
            FROM raw_posts
            WHERE time >= %s
            GROUP BY 1, 2
            ORDER BY 1 DESC, 3 DESC;
        """, (since_24h,))
        hourly = cur.fetchall()

        # Divergence events in last 24h by hour
        cur.execute("""
            SELECT
                date_trunc('hour', time AT TIME ZONE 'America/New_York') as hour_et,
                COUNT(*) as events,
                MAX(d_value) as max_d
            FROM divergence_events
            WHERE time >= %s
            GROUP BY 1
            ORDER BY 1 DESC;
        """, (since_24h,))
        div_by_hour = cur.fetchall()

        # Pre-market specific (4am-9:30am ET)
        cur.execute("""
            SELECT source_class, COUNT(*) as posts, MAX(time) as latest
            FROM raw_posts
            WHERE time >= now() - interval '6 hours'
            GROUP BY source_class
            ORDER BY posts DESC;
        """)
        premarket_posts = cur.fetchall()

print()
print("=" * 65)
print("  PRE-MARKET DATA ANALYSIS")
print("  Now: {} PT ({} ET)".format(
    now.astimezone(PT).strftime('%I:%M %p'),
    now.astimezone(ET).strftime('%I:%M %p')))
print("=" * 65)

print("\n  POSTS BY HOUR (last 24h, ET):")
print("  {:20s} {:15s} {:>6}".format("HOUR ET", "SOURCE", "POSTS"))
print("  " + "-"*45)
last_hour = None
for hour, source, posts in hourly[:30]:
    h_str = hour.strftime('%a %I:%M %p') if hour != last_hour else "              "
    last_hour = hour
    print("  {:20s} {:15s} {:>6,}".format(h_str, source, posts))

print("\n  DIVERGENCE EVENTS BY HOUR (last 24h, ET):")
if not div_by_hour:
    print("  None")
for hour, count, max_d in div_by_hour[:12]:
    print("  {} ET  {:>3} events  max D={:.2f}".format(
        hour.strftime('%a %I:%M %p'), count, max_d or 0))

print("\n  LAST 6 HOURS — POSTS BY SOURCE:")
if not premarket_posts:
    print("  No posts in last 6 hours!")
for sc, count, latest in premarket_posts:
    latest_pt = latest.astimezone(PT).strftime('%I:%M %p PT') if latest else '?'
    print("  {:25s} {:>6,} posts  latest={}".format(sc, count, latest_pt))

print()
print("=" * 65)
