import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()
from alphahound.engine.storage import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        # Re-enable StockTwits
        cur.execute("""
            UPDATE source_adapters SET enabled = true
            WHERE adapter_id = 'stocks.stocktwits';
        """)
        # Check what we have
        cur.execute("""
            SELECT adapter_id, source_class, tier, enabled
            FROM source_adapters ORDER BY enabled DESC, tier, adapter_id;
        """)
        rows = cur.fetchall()
    conn.commit()

print()
print("StockTwits re-enabled. Current adapter status:")
print()
for adapter_id, sc, tier, enabled in rows:
    status = "ON " if enabled else "OFF"
    print("  [{}] {:35s} {:22s} Tier {}".format(status, adapter_id, sc, tier))
print()
