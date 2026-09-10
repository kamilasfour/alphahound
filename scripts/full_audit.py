import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
ET = ZoneInfo("America/New_York")
now = datetime.now(timezone.utc)
since_24h = now - timedelta(hours=24)
since_1h  = now - timedelta(hours=1)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Posts by source last 24h
        cur.execute("""
            SELECT source_class, adapter_id, COUNT(*) as posts, MAX(time) as latest
            FROM raw_posts WHERE time >= %s
            GROUP BY source_class, adapter_id
            ORDER BY source_class, posts DESC;
        """, (since_24h,))
        posts_24h = cur.fetchall()

        # Scored vs unscored
        cur.execute("""
            SELECT rp.source_class,
                COUNT(*) as total,
                SUM(CASE WHEN ss.entity_id IS NOT NULL THEN 1 ELSE 0 END) as scored
            FROM raw_posts rp
            LEFT JOIN sentiment_scores ss
                ON ss.entity_id=rp.entity_id AND ss.source_class=rp.source_class AND ss.time=rp.time
            WHERE rp.time >= %s
            AND rp.source_class IN ('news_wire','retail_social','analyst_curated')
            GROUP BY rp.source_class;
        """, (since_24h,))
        scored = cur.fetchall()

        # Active signals right now
        cur.execute("""
            SELECT DISTINCT ON (de.entity_id)
                e.canonical_symbol, de.d_value, de.time,
                de.components->>'narrative' as narrative
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= now() - interval '24 hours'
            ORDER BY de.entity_id, de.d_value DESC;
        """)
        signals = sorted(cur.fetchall(), key=lambda r: r[1], reverse=True)

        # Options flow last 24h
        cur.execute("""
            SELECT e.canonical_symbol, COUNT(*) as contracts,
                   SUM(CASE WHEN sentiment='bullish' THEN 1 ELSE 0 END) as bullish,
                   SUM(CASE WHEN sentiment='bearish' THEN 1 ELSE 0 END) as bearish,
                   MAX(time) as latest
            FROM options_flow of2
            JOIN entities e ON e.entity_id = of2.entity_id
            WHERE of2.time >= %s
            GROUP BY e.canonical_symbol
            ORDER BY contracts DESC LIMIT 10;
        """, (since_24h,))
        options = cur.fetchall()

        # Congressional trades last 7d
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts
            WHERE source_class='institutional_flow'
            AND adapter_id='stocks.quiver'
            AND time >= now() - interval '7 days';
        """)
        congress_count = cur.fetchone()[0]

        # Tickers with fresh signals (last 2h)
        cur.execute("""
            SELECT e.canonical_symbol, de.d_value
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= now() - interval '2 hours'
            ORDER BY de.d_value DESC;
        """)
        fresh = cur.fetchall()

et_now = now.astimezone(ET)
et_open = et_now.replace(hour=9, minute=30, second=0, microsecond=0)
if et_now >= et_open:
    et_open += timedelta(days=1)
mins_to_open = max(0, int((et_open - et_now).total_seconds() / 60))

print()
print("=" * 65)
print("  FULL DATA CAPTURE AUDIT")
print("  {} PT  ({} ET)".format(
    now.astimezone(PT).strftime('%I:%M %p'),
    now.astimezone(ET).strftime('%I:%M %p')))
print("  Market opens in ~{}m".format(mins_to_open))
print("=" * 65)

print("\nDATA SOURCES — LAST 24H:")
print("  {:25s} {:30s} {:>7s}  {}".format("SOURCE CLASS", "ADAPTER", "POSTS", "LATEST PT"))
print("  " + "-"*70)
total_posts = 0
for sc, adapter, posts, latest in posts_24h:
    age_mins = int((now - latest.replace(tzinfo=timezone.utc)).total_seconds()/60)
    latest_str = latest.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    flag = " ⚠️ STALE" if age_mins > 120 else ""
    print("  {:25s} {:30s} {:>7,}  {}{}".format(sc, adapter, posts, latest_str, flag))
    total_posts += posts
print("  {:25s} {:30s} {:>7,}".format("TOTAL", "", total_posts))

print("\nSCORING COVERAGE (24h posts):")
for sc, total, scored in scored:
    pct = round(scored/total*100) if total > 0 else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print("  {:25s} {:>6,}/{:<6,} {}% |{}|".format(sc, scored, total, pct, bar))

print("\nOPTIONS FLOW — TOP TICKERS (24h):")
if not options:
    print("  No options flow data")
for sym, contracts, bull, bear, latest in options:
    latest_str = latest.replace(tzinfo=timezone.utc).astimezone(PT).strftime('%I:%M %p')
    print("  {:6s}  {:>3} contracts  bull={} bear={}  latest={}".format(
        sym, contracts, bull, bear, latest_str))

print("\nCONGRESSIONAL TRADES (7d): {:,}".format(congress_count))

print("\nACTIVE SIGNALS (24h):")
if not signals:
    print("  None")
for sym, d, t, narr in signals:
    tier = "EXTREME" if d>=20 else "HIGH" if d>=8 else "STANDARD" if d>=4 else "monitor"
    exec_flag = " ← EXECUTABLE" if d >= 4.0 else ""
    age_h = (now - t.replace(tzinfo=timezone.utc)).total_seconds()/3600
    print("  {:6s}  D={:.2f}  [{:8s}]  {:.1f}h ago{}".format(
        sym, d, tier, age_h, exec_flag))

print("\nFRESH SIGNALS (last 2h):")
if not fresh:
    print("  None — engine is watching pre-market")
for sym, d in fresh:
    print("  {:6s}  D={:.2f}".format(sym, d))

print()
print("=" * 65)
