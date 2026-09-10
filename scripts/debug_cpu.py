"""Find and kill hung DB queries, then check what's eating CPU."""
import sys
sys.path.insert(0, r'C:\alphahound_project\src')
from dotenv import load_dotenv
load_dotenv(r'C:\alphahound_project\.env')
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:

        print("=== ALL ACTIVE QUERIES ===")
        cur.execute("""
            SELECT pid,
                   now() - query_start AS duration,
                   state,
                   left(query, 100) AS query_snippet
            FROM pg_stat_activity
            WHERE state != 'idle'
              AND pid != pg_backend_pid()
            ORDER BY duration DESC NULLS LAST;
        """)
        rows = cur.fetchall()
        if not rows:
            print("  No active queries")
        for r in rows:
            print(f"\n  PID={r[0]}  duration={r[1]}  state={r[2]}")
            print(f"  query: {r[3]}")

        print("\n=== QUERIES RUNNING > 5 MINUTES ===")
        cur.execute("""
            SELECT pid, now() - query_start AS duration,
                   application_name,
                   left(query, 150) AS query_snippet
            FROM pg_stat_activity
            WHERE state = 'active'
              AND pid != pg_backend_pid()
              AND now() - query_start > interval '5 minutes'
            ORDER BY duration DESC;
        """)
        stuck = cur.fetchall()
        if not stuck:
            print("  None")
        else:
            for r in stuck:
                print(f"\n  PID={r[0]}  duration={r[1]}  app={r[2]}")
                print(f"  query: {r[3]}")

        print("\n=== TERMINATE QUERIES RUNNING > 10 MINUTES? ===")
        cur.execute("""
            SELECT pid, now() - query_start AS duration,
                   left(query, 100) AS q
            FROM pg_stat_activity
            WHERE state = 'active'
              AND pid != pg_backend_pid()
              AND now() - query_start > interval '10 minutes';
        """)
        to_kill = cur.fetchall()
        if not to_kill:
            print("  No queries over 10 minutes")
        else:
            for r in to_kill:
                print(f"\n  Killing PID={r[0]}  duration={r[1]}")
                print(f"  was running: {r[2]}")
                cur.execute("SELECT pg_terminate_backend(%s);", (r[0],))
                result = cur.fetchone()
                print(f"  terminated: {result[0]}")

        print("\n=== CONNECTION COUNT BY APP ===")
        cur.execute("""
            SELECT application_name, state, COUNT(*) as cnt
            FROM pg_stat_activity
            WHERE pid != pg_backend_pid()
            GROUP BY application_name, state
            ORDER BY cnt DESC;
        """)
        for r in cur.fetchall():
            print(f"  {r[0] or 'unknown':<40} {r[1]:<10} {r[2]} connections")

        print("\n=== TABLE SIZES (top 10) ===")
        cur.execute("""
            SELECT relname,
                   pg_size_pretty(pg_total_relation_size(relid)) AS size,
                   n_live_tup AS rows
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10;
        """)
        for r in cur.fetchall():
            print(f"  {r[0]:<40} {r[1]:<12} {r[2]:,} rows")

    conn.commit()

print("\nDone.")
