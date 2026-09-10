import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn
import requests, json
from datetime import date

print("=" * 60)
print("ALPHAHOUND SYSTEM CHECK — Jun 4")
print("=" * 60)

base = 'http://localhost:8080'

# API checks
for endpoint, label in [
    ('/api/macro', 'MACRO'),
    ('/api/pipeline', 'PIPELINE'),
    ('/api/execution-log', 'EXEC LOG'),
]:
    try:
        r = requests.get(base + endpoint, timeout=8)
        d = r.json()
        if label == 'MACRO':
            print(f"Macro: {d.get('verdict')} score={d.get('score'):.3f} modifier={d.get('size_modifier')}")
        elif label == 'PIPELINE':
            print(f"Last cycle: {d.get('last_cycle_mins')}m ago | Backlog: {d.get('backlog')}")
        elif label == 'EXEC LOG':
            entries = d.get('entries', [])
            today = [e for e in entries if '06-04' in (e.get('time_pt') or '')]
            print(f"Exec log today: {len(today)} entries")
            for e in today[:5]:
                print(f"  {e.get('ticker')} {e.get('outcome')} — {(e.get('reason') or '')[:60]}")
    except Exception as ex:
        print(f"{label} ERROR: {ex}")

# DB checks
with get_conn() as conn:
    with conn.cursor() as cur:
        # Open positions
        cur.execute("""
            SELECT ticker, structure_type, estimated_debit, status
            FROM options_trade_log WHERE status='placed'
            ORDER BY time DESC;
        """)
        rows = cur.fetchall()
        print(f"\nOpen positions in DB: {len(rows)}")
        for r in rows:
            print(f"  {r[0]:<6} {r[1]:<22} ${r[2]:>7.0f} {r[3]}")

        # Convergence signals today
        cur.execute("""
            SELECT COUNT(*), MAX(time)
            FROM convergence_signals
            WHERE time >= now() - interval '1 hour'
            AND super_signal = TRUE;
        """)
        r = cur.fetchone()
        print(f"\nSuper signals last 1h: {r[0]} (newest: {r[1].strftime('%H:%M') if r[1] else 'none'})")

        # Adapter freshness
        cur.execute("""
            SELECT adapter_id, MAX(started_at), SUM(posts_fetched), SUM(posts_written)
            FROM ingest_runs
            WHERE started_at >= now() - interval '2 hours'
            GROUP BY adapter_id
            ORDER BY MAX(started_at) DESC;
        """)
        print("\nAdapter runs last 2h:")
        for r in cur.fetchall():
            mins = int(((__import__('datetime').datetime.now(__import__('datetime').timezone.utc) - r[1]).total_seconds()) / 60)
            print(f"  {r[0].replace('stocks.',''):<20} {mins}m ago  fetched={r[2]}  wrote={r[3]}")
