"""Debug: check entity_id resolution and convergence_signals for NVDA vs MU."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv; load_dotenv()

from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:

        print("\n=== ENTITY LOOKUP ===")
        for sym in ("NVDA", "MU"):
            cur.execute(
                "SELECT entity_id, canonical_symbol FROM entities "
                "WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';", (sym,)
            )
            print(f"  {sym}: {cur.fetchall()}")

        print("\n=== CONVERGENCE_SIGNALS columns ===")
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='convergence_signals' ORDER BY ordinal_position;"
        )
        cols = [r[0] for r in cur.fetchall()]
        print(f"  {cols}")

        print("\n=== CONVERGENCE_SIGNALS latest rows ===")
        cur.execute("SELECT ticker, entity_id, composite_score, direction, time FROM convergence_signals ORDER BY time DESC LIMIT 10;")
        for row in cur.fetchall():
            print(f"  {row}")

        print("\n=== PRICE_SNAPSHOTS: what entity_id does price=$751 belong to? ===")
        cur.execute(
            "SELECT ps.entity_id, e.canonical_symbol, ps.price, ps.time "
            "FROM price_snapshots ps "
            "JOIN entities e ON e.entity_id = ps.entity_id "
            "WHERE ps.price BETWEEN 740 AND 760 "
            "ORDER BY ps.time DESC LIMIT 5;"
        )
        for row in cur.fetchall():
            print(f"  {row}")

        print("\n=== PRICE_SNAPSHOTS for NVDA ===")
        cur.execute(
            "SELECT price, time FROM price_snapshots "
            "WHERE entity_id='e581bd20-4ee6-4779-a66e-2036865dfd26' "
            "ORDER BY time DESC LIMIT 3;"
        )
        print(f"  NVDA: {cur.fetchall()}")

        print("\n=== PRICE_SNAPSHOTS for MU ===")
        cur.execute(
            "SELECT price, time FROM price_snapshots "
            "WHERE entity_id='15c6d1bc-0b4d-4432-a75e-40527abf0306' "
            "ORDER BY time DESC LIMIT 3;"
        )
        print(f"  MU: {cur.fetchall()}")

        print("\n=== score_ticker path: what does convergence_signals have for NVDA entity? ===")
        cur.execute(
            "SELECT ticker, composite_score, direction, time "
            "FROM convergence_signals "
            "WHERE entity_id='e581bd20-4ee6-4779-a66e-2036865dfd26' "
            "ORDER BY time DESC LIMIT 3;"
        )
        print(f"  NVDA convergence rows: {cur.fetchall()}")

        print("\n=== score_ticker path: what does convergence_signals have for MU entity? ===")
        cur.execute(
            "SELECT ticker, composite_score, direction, time "
            "FROM convergence_signals "
            "WHERE entity_id='15c6d1bc-0b4d-4432-a75e-40527abf0306' "
            "ORDER BY time DESC LIMIT 3;"
        )
        print(f"  MU convergence rows: {cur.fetchall()}")
