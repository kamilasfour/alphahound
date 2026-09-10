import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import requests

r = requests.get('http://localhost:8080/api/congress', timeout=10)
print(f"Status: {r.status_code}")
import json
d = r.json()
print(f"Count: {d.get('count')}")
print(f"Trades: {len(d.get('trades', []))}")
if d.get('error'):
    print(f"Error: {d['error']}")
if d.get('trades'):
    print(f"First trade: {d['trades'][0]}")
