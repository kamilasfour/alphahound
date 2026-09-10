import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # How old is the newest UW data?
        cur.execute("""
            SELECT COUNT(*), MAX(time), MIN(time)
            FROM options_flow
            WHERE adapter_id = 'stocks.unusual_whales'
            AND time >= now() - interval '48 hours';
        """)
        r = cur.fetchone()
        print(f"UW records (48h): {r[0]:,}  newest={r[1]}  oldest={r[2]}")

        # Check options_flow for our key tickers
        cur.execute("""
            SELECT ticker, COUNT(*), MAX(time), MAX(unusual_score)
            FROM options_flow
            WHERE time >= now() - interval '24 hours'
            GROUP BY ticker
            ORDER BY MAX(unusual_score) DESC NULLS LAST
            LIMIT 15;
        """)
        print("\nTop options flow last 24h:")
        for r in cur.fetchall():
            print(f"  {r[0]:<8} {r[1]:>4} records  last={r[2].strftime('%H:%M')}  max_score={r[3]:.0f}" if r[2] else f"  {r[0]}")

        # Check convergence_signals - why only ORCL/MU?
        cur.execute("""
            SELECT ticker, composite_score, super_signal, direction, catalyst_type, time
            FROM convergence_signals
            WHERE time >= now() - interval '2 hours'
            AND composite_score >= 3.0
            ORDER BY composite_score DESC
            LIMIT 15;
        """)
        print("\nTop convergence signals (last 2h, score >= 3.0):")
        for r in cur.fetchall():
            print(f"  {r[0]:<8} score={r[1]:.2f}  super={r[2]}  dir={r[3]}  cat={r[4]}  time={r[5].strftime('%H:%M')}")
