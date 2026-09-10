import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import httpx, os
from alphahound.modules.stocks.watchlist.watchlist import OPTIONS_WATCHLIST

key = os.environ.get('UNUSUAL_WHALES_API_KEY', '')
watchlist_set = set(OPTIONS_WATCHLIST)

with httpx.Client(
    base_url='https://api.unusualwhales.com',
    headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
    timeout=20.0,
) as client:
    r = client.get('/api/option-trades/flow-alerts')
    data = r.json().get('data', [])

print(f"Total alerts: {len(data)}")
print(f"Watchlist size: {len(watchlist_set)}")

# Show field names from first record
if data:
    print(f"\nField names in API response: {list(data[0].keys())}")

# Which tickers match our watchlist
matches = [d for d in data if d.get('ticker','').upper() in watchlist_set]
print(f"\nAlerts matching our watchlist: {len(matches)}")
for m in matches[:10]:
    print(f"  {m.get('ticker')} | premium={m.get('total_premium') or m.get('total_ask_side_prem')} | vol={m.get('volume') or m.get('total_size')}")

# Show what we're missing
all_tickers = set(d.get('ticker','').upper() for d in data)
print(f"\nAll tickers in response (first 20): {sorted(all_tickers)[:20]}")
print(f"Tickers in response that ARE in watchlist: {sorted(all_tickers & watchlist_set)}")
