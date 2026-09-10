import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import httpx

# Test Quiver directly
key = os.environ.get("QUIVER_API_KEY", "")
resp = httpx.get(
    "https://api.quiverquant.com/beta/live/congresstrading",
    headers={"Authorization": "Token {}".format(key), "Accept": "application/json"},
    timeout=15.0
)
data = resp.json()
trades = data if isinstance(data, list) else data.get("data", [])
print("Quiver trades fetched:", len(trades))

if trades:
    # Check which tickers are in entities
    from alphahound.engine.storage import get_conn
    tickers = list({t.get("Ticker","").strip().upper() for t in trades if t.get("Ticker")})
    print("Unique tickers in trades:", len(tickers))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT canonical_symbol FROM entities
                WHERE module_id='stocks' AND kind='ticker'
                AND canonical_symbol = ANY(%s);
            """, (tickers,))
            found = {r[0] for r in cur.fetchall()}

    missing = [t for t in tickers if t not in found]
    print("In entities:", len(found))
    print("NOT in entities:", len(missing))
    print("Sample missing:", missing[:10])

# Test StockTwits
print()
print("Testing StockTwits...")
try:
    resp2 = httpx.get(
        "https://api.stocktwits.com/api/2/streams/symbol/AAPL.json",
        timeout=10.0
    )
    print("StockTwits status:", resp2.status_code)
    if resp2.status_code == 200:
        msgs = resp2.json().get("messages", [])
        print("Messages returned:", len(msgs))
    else:
        print("Response:", resp2.text[:200])
except Exception as e:
    print("StockTwits error:", e)

# Test Unusual Whales
print()
print("Testing Unusual Whales...")
uw_key = os.environ.get("UNUSUAL_WHALES_API_KEY", "")
try:
    resp3 = httpx.get(
        "https://api.unusualwhales.com/api/option-trades/flow-alerts",
        headers={"Authorization": "Bearer {}".format(uw_key)},
        params={"limit": 5},
        timeout=10.0
    )
    print("UW status:", resp3.status_code)
    if resp3.status_code != 200:
        print("UW response:", resp3.text[:200])
    else:
        data = resp3.json()
        print("UW records:", len(data.get("data", [])))
except Exception as e:
    print("UW error:", e)
