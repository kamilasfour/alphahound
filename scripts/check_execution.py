import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
PT = ZoneInfo("America/Los_Angeles")
now = datetime.now(timezone.utc)

with get_conn() as conn:
    with conn.cursor() as cur:

        # All trade_log entries
        cur.execute("""
            SELECT e.canonical_symbol, tl.side, tl.size, tl.venue,
                   tl.alpaca_order_id, tl.alpaca_status, tl.notes, tl.time
            FROM trade_log tl
            JOIN entities e ON e.entity_id = tl.entity_id
            ORDER BY tl.time DESC LIMIT 20;
        """)
        trades = cur.fetchall()
        cols = ['symbol','side','size','venue','alpaca_order_id','alpaca_status','notes','time']

        # Divergence events that crossed D>=4.0
        cur.execute("""
            SELECT e.canonical_symbol, de.d_value, de.time
            FROM divergence_events de
            JOIN entities e ON e.entity_id = de.entity_id
            WHERE de.d_value >= 4.0
            ORDER BY de.time DESC LIMIT 20;
        """)
        executable = cur.fetchall()

        # Execute pipeline runs
        cur.execute("""
            SELECT started_at, duration_ms/1000 as secs, rows_affected, error
            FROM pipeline_runs
            WHERE step='execute'
            ORDER BY started_at DESC LIMIT 10;
        """)
        exec_runs = cur.fetchall()

        # Trade advice runs
        cur.execute("""
            SELECT started_at, duration_ms/1000 as secs, rows_affected
            FROM pipeline_runs
            WHERE step='trade-advice'
            ORDER BY started_at DESC LIMIT 10;
        """)
        advice_runs = cur.fetchall()

print()
print("=" * 65)
print("  EXECUTION AUDIT")
print("=" * 65)

print("\nTRADE LOG (all entries):")
if not trades:
    print("  EMPTY — no trades ever logged")
else:
    for row in trades:
        d = dict(zip(cols, row))
        pt = d['time'].astimezone(PT).strftime('%m/%d %I:%M %p') if d['time'] else '?'
        alpaca = d['alpaca_order_id'] or 'no order'
        notes = d['notes'] or {}
        tier = notes.get('signal_tier','?') if isinstance(notes,dict) else '?'
        d_val = notes.get('d_value','?') if isinstance(notes,dict) else '?'
        print("  {:6s} {:5s} ${:>8.2f}  venue={:10s}  alpaca={}  tier={}  D={}  {}".format(
            d['symbol'], d['side'] or '?', d['size'] or 0,
            d['venue'] or '?', alpaca[:8] if alpaca != 'no order' else 'NONE',
            tier, d_val, pt))

print("\nDIVERGENCE EVENTS D>=4.0 (executable signals):")
if not executable:
    print("  NONE — no signal has crossed D=4.0 yet")
else:
    for sym, d_val, t in executable:
        pt = t.astimezone(PT).strftime('%m/%d %I:%M %p')
        print("  {:6s}  D={:.2f}  {}".format(sym, d_val, pt))

print("\nEXECUTE STEP RUNS (last 10):")
for started, secs, rows, err in exec_runs:
    pt = started.astimezone(PT).strftime('%I:%M %p')
    print("  {}  {:.0f}s  {} rows  {}".format(pt, secs or 0, rows or 0,
          'ERR:'+err[:40] if err else 'ok'))

print("\nTRADE-ADVICE STEP RUNS (last 10):")
for started, secs, rows in advice_runs:
    pt = started.astimezone(PT).strftime('%I:%M %p')
    print("  {}  {:.0f}s  {} rows".format(pt, secs or 0, rows or 0))

print()
