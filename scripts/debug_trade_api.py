import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import requests

base = 'http://localhost:8080'

print('=== /api/options-trades ===')
try:
    r = requests.get(f'{base}/api/options-trades', timeout=10)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text[:300]}')
except Exception as e:
    print(f'ERROR: {e}')

print('\n=== /api/convergence/history ===')
try:
    r = requests.get(f'{base}/api/convergence/history?days_back=7', timeout=10)
    print(f'Status: {r.status_code}')
    print(f'Response: {r.text[:300]}')
except Exception as e:
    print(f'ERROR: {e}')
