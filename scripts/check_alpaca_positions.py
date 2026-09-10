import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import httpx, os, json

headers = {
    'APCA-API-KEY-ID':     os.environ.get('ALPACA_API_KEY',''),
    'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY',''),
}

# 1. Get all positions
r = httpx.get('https://paper-api.alpaca.markets/v2/positions', headers=headers, timeout=15)
positions = r.json()
print(f"Total Alpaca positions: {len(positions) if isinstance(positions, list) else 'ERROR: '+str(positions)[:100]}")
if isinstance(positions, list):
    for p in positions:
        print(f"  {p.get('symbol'):<30} qty={p.get('qty')} market_value={p.get('market_value')} cost_basis={p.get('cost_basis')} unrealized_pl={p.get('unrealized_pl')}")

# 2. Check what OCC symbols are in our trade log
print("\n--- options_trade_log legs ---")
from alphahound.engine.storage import get_conn
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ticker, structure_type, estimated_debit, legs_json, order_ids
            FROM options_trade_log WHERE status='placed' ORDER BY time DESC;
        """)
        for row in cur.fetchall():
            ticker, struct, debit, legs, orders = row
            print(f"\n{ticker} {struct} debit=${debit}")
            if legs:
                for leg in (legs if isinstance(legs, list) else []):
                    print(f"  leg: {leg}")
