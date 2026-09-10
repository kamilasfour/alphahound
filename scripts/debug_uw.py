import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import httpx, os, json

key = os.environ.get('UNUSUAL_WHALES_API_KEY', '')
print(f"API key present: {'yes' if key else 'NO KEY FOUND'}")

with httpx.Client(
    base_url='https://api.unusualwhales.com',
    headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
    timeout=20.0,
) as client:
    # Test flow alerts
    print('\n=== /api/option-trades/flow-alerts ===')
    r = client.get('/api/option-trades/flow-alerts')
    print(f'Status: {r.status_code}')
    data = r.json()
    if isinstance(data, list):
        print(f'Records: {len(data)}')
        if data: print(f'First record keys: {list(data[0].keys())}')
        if data: print(f'Sample: {json.dumps(data[0], indent=2)[:400]}')
    else:
        print(f'Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')
        print(f'Response: {str(data)[:400]}')
