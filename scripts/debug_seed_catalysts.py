"""Debug script — run seed manually with full exception traces."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

from alphahound.engine.storage import get_conn

# ── Test DB connection ────────────────────────────────────────────────────────
print("\n=== DB CONNECTION ===")
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user;")
            print("OK:", cur.fetchone())
except Exception as e:
    print("FAILED:", e)
    sys.exit(1)

# ── Check if tables exist ─────────────────────────────────────────────────────
print("\n=== TABLE CHECK ===")
with get_conn() as conn:
    with conn.cursor() as cur:
        for tbl in ("fomc_calendar", "pdufa_calendar", "entities"):
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name=%s);",
                (tbl,)
            )
            exists = cur.fetchone()[0]
            print(f"  {tbl}: {'EXISTS' if exists else 'MISSING'}")

# ── Try FOMC insert directly ──────────────────────────────────────────────────
print("\n=== FOMC DIRECT INSERT TEST ===")
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fomc_calendar (meeting_date, meeting_end_date, statement_time, press_conf, notes)
                VALUES ('2026-06-09', '2026-06-10', '14:00:00', TRUE, 'test row')
                ON CONFLICT (meeting_date) DO NOTHING;
            """)
            print(f"  rowcount after insert: {cur.rowcount}")
            cur.execute("SELECT 1 FROM fomc_calendar WHERE meeting_date='2026-06-09';")
            row = cur.fetchone()
            print(f"  row present after insert (before commit): {row}")
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fomc_calendar;")
            print(f"  fomc_calendar count after commit: {cur.fetchone()[0]}")
except Exception as e:
    import traceback
    print("FAILED:"); traceback.print_exc()

# ── Try PDUFA entity + insert ─────────────────────────────────────────────────
print("\n=== PDUFA DIRECT INSERT TEST (VRDN) ===")
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Check entity
            cur.execute(
                "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol='VRDN' AND kind='ticker';"
            )
            row = cur.fetchone()
            if row:
                entity_id = str(row[0])
                print(f"  VRDN entity exists: {entity_id}")
            else:
                print("  VRDN entity NOT found — inserting...")
                cur.execute(
                    "INSERT INTO entities (module_id, canonical_symbol, kind) VALUES ('stocks','VRDN','ticker') RETURNING entity_id;"
                )
                row = cur.fetchone()
                entity_id = str(row[0]) if row else None
                conn.commit()
                print(f"  VRDN entity created: {entity_id}")

            if entity_id:
                cur.execute(
                    "SELECT 1 FROM pdufa_calendar WHERE entity_id=%s AND pdufa_date='2026-06-30';",
                    (entity_id,)
                )
                exists = cur.fetchone()
                print(f"  VRDN PDUFA row already exists: {bool(exists)}")
                if not exists:
                    cur.execute("""
                        INSERT INTO pdufa_calendar
                            (entity_id, ticker, pdufa_date, drug_name, indication, application_type, notes, source)
                        VALUES (%s, 'VRDN', '2026-06-30', 'Veligrotug', 'Thyroid Eye Disease', 'BLA', 'test', 'manual_seed');
                    """, (entity_id,))
                    print(f"  rowcount: {cur.rowcount}")
                conn.commit()
                cur.execute("SELECT COUNT(*) FROM pdufa_calendar;")
                print(f"  pdufa_calendar count after commit: {cur.fetchone()[0]}")
except Exception as e:
    import traceback
    print("FAILED:"); traceback.print_exc()

# ── Run full seed with DEBUG ──────────────────────────────────────────────────
print("\n=== FULL SEED RUN ===")
from alphahound.engine.signals.catalyst_calendar import seed_static_catalysts
pdufa_n, fomc_n = seed_static_catalysts()
print(f"Result: {pdufa_n} PDUFA, {fomc_n} FOMC")
