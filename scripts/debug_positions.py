import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import requests, json

r = requests.get('http://localhost:8080/api/positions', timeout=10)
d = r.json()
print(f"Count: {d.get('count')}")
for p in d.get('positions', []):
    print(f"\nTicker: {p.get('ticker')}")
    print(f"  Keys: {list(p.keys())}")
    print(f"  d_value={p.get('d_value')} conviction={p.get('conviction')} tier={p.get('signal_tier')}")
    print(f"  narrative={p.get('narrative')}")
    print(f"  components={p.get('components')}")
