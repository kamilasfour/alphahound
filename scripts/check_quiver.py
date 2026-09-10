import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import httpx

key = os.environ.get("QUIVER_API_KEY", "")
print("QUIVER_API_KEY set:", bool(key), "length:", len(key))

# Test the endpoint directly
try:
    resp = httpx.get(
        "https://api.quiverquant.com/beta/live/congresstrading",
        headers={"Authorization": f"Token {key}", "Accept": "application/json"},
        timeout=15.0
    )
    print("Status:", resp.status_code)
    data = resp.json()
    if isinstance(data, list):
        print("Records returned:", len(data))
        if data:
            print("First record:", data[0])
    else:
        print("Response:", str(data)[:200])
except Exception as e:
    print("Error:", e)
