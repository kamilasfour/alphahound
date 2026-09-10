import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Mark duplicate earlier entries as closed (superseded)
        # Keep: id=8 (ADBE $892), id=10 (IONQ $756), id=11 (TLT $752)
        # Close: id=2 (ADBE $830), id=4 (IONQ $960), id=7 (TLT $910)
        cur.execute("""
            UPDATE options_trade_log
            SET status = 'superseded', closed_at = now(), notes = 'duplicate — superseded by later entry'
            WHERE id IN (2, 4, 7);
        """)
        print(f"Marked {cur.rowcount} duplicate entries as superseded")

        # Verify final state
        cur.execute("""
            SELECT id, ticker, estimated_debit, status, time::date
            FROM options_trade_log ORDER BY id;
        """)
        print("\nFinal options_trade_log:")
        for r in cur.fetchall():
            print(f"  id={r[0]} {r[1]:<6} ${r[2]:>7.0f} {r[3]:<12} {r[4]}")
    conn.commit()
print("\nDone.")
