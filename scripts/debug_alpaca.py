"""Debug: check what API keys the broker is actually using."""
import sys, os
sys.path.insert(0, r'C:\alphahound_project\src')
from dotenv import load_dotenv
load_dotenv(r'C:\alphahound_project\.env')

key    = os.environ.get('ALPACA_API_KEY', 'NOT SET')
secret = os.environ.get('ALPACA_SECRET_KEY', 'NOT SET')
base   = os.environ.get('ALPACA_BASE_URL', 'NOT SET')

print(f"ALPACA_API_KEY:    {key[:8]}...{key[-4:] if len(key) > 12 else '(short)'}")
print(f"ALPACA_SECRET_KEY: {secret[:4]}...{secret[-4:] if len(secret) > 8 else '(short)'}")
print(f"ALPACA_BASE_URL:   {base}")

# Try a direct API call
import requests
resp = requests.get(
    f"{base}/v2/account",
    headers={
        "APCA-API-KEY-ID":     key,
        "APCA-API-SECRET-KEY": secret,
    },
    timeout=10
)
print(f"\nStatus: {resp.status_code}")
print(f"Response: {resp.text[:300]}")
