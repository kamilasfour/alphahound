import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import httpx

with httpx.Client(timeout=15.0) as client:
    resp = client.get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1")
    data = resp.json()
    print("Total count:", data.get("count"))
    print("Total pages:", data.get("pages"))
    print("Results per page:", len(data.get("results", [])))
    print()
    print("First 5 tickers:", [r["ticker"] for r in data["results"][:5]])
