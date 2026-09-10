import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

MISSING_ADAPTERS = [
    # adapter_id, module_id, source_class, tier, tos_basis
    ("stocks.massive_history", "stocks", "price_data", "A",
     "Polygon.io daily OHLCV bars — licensed API key, personal research use"),
    ("stocks.yahoo_finance", "stocks", "news_wire", "B",
     "Yahoo Finance RSS — public feed, personal research use, no redistribution"),
]

with get_conn() as conn:
    with conn.cursor() as cur:
        for adapter_id, module_id, source_class, tier, tos in MISSING_ADAPTERS:
            cur.execute("""
                INSERT INTO source_adapters
                    (adapter_id, module_id, source_class, tier, tos_basis, enabled)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (adapter_id) DO UPDATE SET
                    enabled    = true,
                    tier       = EXCLUDED.tier,
                    tos_basis  = EXCLUDED.tos_basis;
            """, (adapter_id, module_id, source_class, tier, tos))
            print("Registered: {}".format(adapter_id))
    conn.commit()

print()
print("Done. Verifying all adapters:")
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT adapter_id, source_class, tier, enabled
            FROM source_adapters ORDER BY adapter_id;
        """)
        for row in cur.fetchall():
            status = "ON " if row[3] else "OFF"
            print("  [{}] {:35s} {:22s} Tier {}".format(
                status, row[0], row[1], row[2]))
