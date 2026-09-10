import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta

# Only show signals from the last 2 hours -- current state only
since = datetime.now(timezone.utc) - timedelta(hours=2)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (de.entity_id)
                e.canonical_symbol, de.d_value, de.p_value, de.time
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.time >= %s
            ORDER BY de.entity_id, de.d_value DESC
        """, (since,))
        rows = cur.fetchall()

now = datetime.now(timezone.utc)
print()
print("Signals as of {} UTC (last 2 hours)".format(now.strftime('%H:%M')))
print()

if not rows:
    print("  No divergence events in last 2 hours -- engine is quiet.")
else:
    # Sort by D-value
    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    print("{:<8}  {:>7}  {:>8}  {:>6}  {}".format(
        "TICKER", "D-VALUE", "P-VALUE", "AGO", "TIER"))
    print("-" * 55)
    for sym, d, p, t in rows:
        mins_ago = int((now - t.replace(tzinfo=timezone.utc)).total_seconds() / 60)
        tier = "EXTREME" if d >= 20 else "HIGH" if d >= 8 else "STANDARD" if d >= 4 else "monitor"
        will_exec = " <-- WILL EXECUTE" if d >= 4.0 else ""
        print("{:<8}  {:>7.2f}  {:>8.4f}  {:>4}m  {}{}".format(
            sym, d, p, mins_ago, tier, will_exec))

print()
print("Execution threshold: D >= 4.0")
print("Next pipeline cycle: ~{}".format(
    (now + timedelta(minutes=15 - now.minute % 15)).strftime('%H:%M UTC')))
