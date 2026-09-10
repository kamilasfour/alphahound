import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import requests

r = requests.get('http://localhost:8080/api/options-positions', timeout=10)
d = r.json()
print('options-positions:', d)

# Also check options monitor rules
r2 = requests.get('http://localhost:8080/api/options-trades', timeout=10)
d2 = r2.json()
print(f"\nOpen trades: {d2.get('open')}")
for t in d2.get('trades', []):
    if t.get('status') == 'placed':
        print(f"  {t['ticker']} {t['structure_type']} - score={t['composite_score']} debit=${t['estimated_debit']} status={t['status']}")
