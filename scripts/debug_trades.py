import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Check if table exists
        cur.execute("SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name='options_trade_log');")
        exists = cur.fetchone()[0]
        print(f"options_trade_log exists: {exists}")

        if not exists:
            print("Creating table...")
            from alphahound.engine.execution.options_executor import _ensure_options_log_table
            _ensure_options_log_table()
            print("Created.")

        # Check API endpoint directly
        cur.execute("SELECT COUNT(*) FROM options_trade_log;")
        print(f"Row count: {cur.fetchone()[0]}")

        # Check convergence_signals
        cur.execute("SELECT COUNT(*) FROM convergence_signals WHERE time >= now() - interval '7 days';")
        print(f"Convergence signals (7d): {cur.fetchone()[0]}")
