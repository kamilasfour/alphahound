"""
Tech gate tester - check what the tech gate says for any ticker.

Usage:
    .\.venv\Scripts\python.exe scripts\check_tech_gate.py XLP SHORT
    .\.venv\Scripts\python.exe scripts\check_tech_gate.py META SHORT
    .\.venv\Scripts\python.exe scripts\check_tech_gate.py NVDA LONG
    .\.venv\Scripts\python.exe scripts\check_tech_gate.py          (checks all active signals)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.execution.technical_gate import check, TechVerdict
from alphahound.engine.signals.trade_advisor import advise_all
from alphahound.engine.storage import get_conn
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")

def get_entity_id(ticker):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id FROM entities WHERE canonical_symbol=%s AND module_id='stocks' AND kind='ticker'",
                (ticker.upper(),)
            )
            row = cur.fetchone()
    return str(row[0]) if row else None

def check_ticker(ticker, direction):
    eid = get_entity_id(ticker)
    if not eid:
        print("  {} not found in entities".format(ticker))
        return

    # Get daily bar count
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), MAX(date), MIN(date) FROM price_daily WHERE entity_id=%s",
                (eid,)
            )
            bars, latest, oldest = cur.fetchone()

    print()
    print("=" * 55)
    print("  TECH GATE: {} {}".format(ticker, direction))
    print("  Daily bars: {}  ({} to {})".format(bars, oldest, latest))
    print("=" * 55)

    result = check(eid, ticker, direction)
    print(result.display())

    # Color verdict
    color = {
        TechVerdict.CONFIRM: "EXECUTE FULL SIZE",
        TechVerdict.WEAK:    "EXECUTE 50% SIZE",
        TechVerdict.REJECT:  "BLOCKED",
        TechVerdict.NO_DATA: "PASS-THROUGH (no data)",
    }.get(result.verdict, "?")
    print()
    print("  >> OUTCOME: {}".format(color))
    print()

if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Single ticker check
        check_ticker(sys.argv[1].upper(), sys.argv[2].upper())
    elif len(sys.argv) == 2:
        # Just ticker, guess direction from current signal
        ticker = sys.argv[1].upper()
        recs = advise_all(min_d=2.0)
        rec = next((r for r in recs if r.ticker == ticker), None)
        if rec:
            check_ticker(ticker, rec.direction.value)
        else:
            print("No active signal for {} -- specify direction: LONG or SHORT".format(ticker))
    else:
        # Check all active executable signals
        print()
        print("Checking tech gate for all active signals (D>=2.0)...")
        recs = advise_all(min_d=2.0)
        if not recs:
            print("No active signals")
        for rec in recs:
            check_ticker(rec.ticker, rec.direction.value)
