import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import httpx, os

headers = {
    'APCA-API-KEY-ID':     os.environ.get('ALPACA_API_KEY',''),
    'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY',''),
    'Content-Type': 'application/json',
}
base = 'https://paper-api.alpaca.markets'

# Try closing AVGO long leg directly
# First get the actual position symbol from Alpaca
r = httpx.get(f'{base}/v2/positions', headers=headers, timeout=10)
positions = r.json()
avgo_legs = [p for p in positions if 'AVGO' in p.get('symbol','')]
print("AVGO positions on Alpaca:")
for p in avgo_legs:
    print(f"  symbol={p['symbol']} qty={p['qty']} side={p.get('side')} asset_class={p.get('asset_class')}")

# Try the simplest close — DELETE /v2/positions/{symbol}
if avgo_legs:
    sym = avgo_legs[0]['symbol']
    print(f"\nTrying DELETE /v2/positions/{sym}")
    r2 = httpx.delete(f'{base}/v2/positions/{sym}', headers=headers, timeout=10)
    print(f"Status: {r2.status_code}")
    print(f"Response: {r2.text[:300]}")
