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
et_now = now.astimezone(ET)

# Market status
h, m, dow = et_now.hour, et_now.minute, et_now.weekday()
mkt_open = dow < 5 and (h > 9 or (h == 9 and m >= 30)) and h < 16
et_open = et_now.replace(hour=9, minute=30, second=0, microsecond=0)
if et_now >= et_open: et_open += timedelta(days=1)
mins_to_open = max(0, int((et_open - et_now).total_seconds() / 60))

with get_conn() as conn:
    with conn.cursor() as cur:

        # Latest pipeline run
        cur.execute("""
            SELECT step, status, started_at, duration_ms, rows_affected, error
            FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;
        """)
        pipeline = cur.fetchall()

        # Active signals
        cur.execute("""
            SELECT DISTINCT ON (de.entity_id)
                e.canonical_symbol, de.d_value, de.time, de.components
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= now() - interval '4 hours'
            ORDER BY de.entity_id, de.d_value DESC;
        """)
        signals = sorted(cur.fetchall(), key=lambda r: r[1], reverse=True)

        # Posts last hour
        cur.execute("""
            SELECT source_class, COUNT(*) FROM raw_posts
            WHERE time >= now() - interval '1 hour'
            GROUP BY source_class ORDER BY COUNT(*) DESC;
        """)
        posts_1h = cur.fetchall()

        # Unscored backlog
        cur.execute("""
            SELECT COUNT(*) FROM raw_posts rp
            WHERE source_class IN ('news_wire','retail_social','analyst_curated')
            AND NOT EXISTS (
                SELECT 1 FROM sentiment_scores ss
                WHERE ss.entity_id=rp.entity_id
                AND ss.source_class=rp.source_class
                AND ss.time=rp.time
            );
        """)
        backlog = cur.fetchone()[0]

        # Open positions
        cur.execute("""
            SELECT e.canonical_symbol, tl.side, tl.size, tl.alpaca_status
            FROM trade_log tl JOIN entities e ON e.entity_id=tl.entity_id
            WHERE tl.alpaca_order_id IS NOT NULL AND tl.closed_at IS NULL;
        """)
        positions = cur.fetchall()

        # Backlog only — skip alpaca_snapshots

print()
print("=" * 60)
print("  STATUS — {} PT ({} ET)".format(
    now.astimezone(PT).strftime('%I:%M %p'),
    et_now.strftime('%I:%M %p')))
print("  MARKET {}{}".format(
    "OPEN" if mkt_open else "CLOSED",
    " — opens in {}m".format(mins_to_open) if not mkt_open else ""))
print("=" * 60)

print("\nPIPELINE:")
for step, status, started, dur, rows, err in pipeline:
    mins = int((now - started.replace(tzinfo=timezone.utc)).total_seconds()/60)
    icon = "✅" if status=="ok" else "❌"
    dur_s = "{:.0f}s".format(dur/1000) if dur else "running"
    err_s = " — {}".format(err[:40]) if err else ""
    print("  {} {:25s} {:>4}m ago  {:>5}s  {:>5} rows{}".format(
        icon, step, mins, dur_s, rows or 0, err_s))

print("\nSIGNALS (last 4h):")
if not signals:
    print("  None above D=2.0 — engine watching")
for sym, d, t, comps in signals:
    tier = "EXTREME" if d>=20 else "HIGH" if d>=8 else "STANDARD" if d>=4 else "monitor"
    exec_flag = " ← EXECUTE" if d>=4.0 else ""
    age = (now - t.replace(tzinfo=timezone.utc)).total_seconds()/3600
    print("  {:6s}  D={:.2f}  [{:8s}]  {:.1f}h ago{}".format(
        sym, d, tier, age, exec_flag))

print("\nPOSTS LAST 1H:")
total = sum(c for _, c in posts_1h)
for sc, count in posts_1h:
    print("  {:25s}  {:>5,}".format(sc, count))
print("  {:25s}  {:>5,}  backlog={:,}".format("TOTAL", total, backlog))

print("\nPOSITIONS:")
if not positions:
    print("  None open — $20,000 fully available")
for sym, side, size, status in positions:
    print("  {:6s}  {:5s}  ${:.0f}  {}".format(sym, side, size or 0, status))

print()
print("=" * 60)
