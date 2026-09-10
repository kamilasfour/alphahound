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

with get_conn() as conn:
    with conn.cursor() as cur:

        # Latest pipeline run
        cur.execute("""
            SELECT step, status, rows_affected, duration_ms, started_at, error
            FROM pipeline_runs ORDER BY started_at DESC LIMIT 15;
        """)
        runs = cur.fetchall()

        # Active signals
        cur.execute("""
            SELECT DISTINCT ON (de.entity_id)
                e.canonical_symbol, de.d_value, de.p_value, de.time
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= now() - interval '2 hours'
            ORDER BY de.entity_id, de.d_value DESC;
        """)
        signals = sorted(cur.fetchall(), key=lambda r: r[1], reverse=True)

        # Posts last hour by source
        cur.execute("""
            SELECT source_class, COUNT(*) as posts
            FROM raw_posts WHERE time >= now() - interval '1 hour'
            GROUP BY source_class ORDER BY posts DESC;
        """)
        posts_1h = cur.fetchall()

        # Hit rate
        cur.execute("SELECT window_days, hit_rate_pct, total_signals FROM hit_rate ORDER BY computed_at DESC LIMIT 3;")
        hr = cur.fetchall()

        # Open positions
        cur.execute("""
            SELECT e.canonical_symbol, tl.side, tl.size, tl.alpaca_status
            FROM trade_log tl JOIN entities e ON e.entity_id = tl.entity_id
            WHERE tl.alpaca_order_id IS NOT NULL AND tl.closed_at IS NULL;
        """)
        positions = cur.fetchall()

print()
print("=" * 60)
print("  STATUS — {}".format(now.astimezone(PT).strftime('%a %b %d %I:%M %p PT')))
print("=" * 60)

print("\nPIPELINE (last 15 steps):")
for step, status, rows, dur, started, err in runs:
    mins = int((now - started.replace(tzinfo=timezone.utc)).total_seconds()/60)
    icon = "OK " if status == "ok" else "ERR"
    err_str = " ERR: {}".format(err[:50]) if err else ""
    print("  [{}] {:22s} {:>4}m ago  {:>5} rows{}".format(icon, step, mins, rows or 0, err_str))

print("\nSIGNALS (last 2h):")
if not signals:
    print("  None above D=2.0")
for sym, d, p, t in signals:
    tier = "EXTREME" if d>=20 else "HIGH" if d>=8 else "STANDARD" if d>=4 else "monitor"
    exec_flag = " << WILL EXECUTE" if d >= 4.0 else ""
    print("  {:6s}  D={:.2f}  [{}]{}".format(sym, d, tier, exec_flag))

print("\nPOSTS LAST 1H:")
for sc, count in posts_1h:
    print("  {:25s}  {:>5,}".format(sc, count))

print("\nHIT RATE:")
if not hr:
    print("  Pending — populates May 14-15")
for w, rate, total in hr:
    print("  {}d window: {:.1f}%  ({} signals)".format(w, rate, total))

print("\nOPEN POSITIONS:")
if not positions:
    print("  None")
for sym, side, size, status in positions:
    print("  {:6s}  {:5s}  ${:.0f}  {}".format(sym, side, size or 0, status))

print()
print("=" * 60)
