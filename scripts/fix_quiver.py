import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

import httpx
from alphahound.engine.storage import get_conn
from alphahound.modules.stocks.adapters.quiver import QuiverAdapter
from datetime import datetime, timezone

# Test single trade write
print("Testing Quiver write...")
adapter = QuiverAdapter()
observed_at = datetime.now(timezone.utc)

# Fetch trades
key = os.environ.get("QUIVER_API_KEY","")
resp = httpx.get(
    "https://api.quiverquant.com/beta/live/congresstrading",
    headers={"Authorization": "Token {}".format(key), "Accept": "application/json"},
    timeout=15.0
)
trades = resp.json() if isinstance(resp.json(), list) else resp.json().get("data",[])
print("Fetched:", len(trades))

# Try writing first 5
from alphahound.engine.adapters.models import Post
from alphahound.engine.storage import EntityResolver, write_posts, load_adapter_meta

meta     = load_adapter_meta("stocks.quiver")
resolver = EntityResolver()
posts    = []

for trade in trades[:5]:
    post = adapter._trade_to_post(trade, observed_at)
    if post:
        posts.append(post)
        print("  Post ticker:", post.entity_ids, "external_id:", post.external_id[:30])

print("Posts built:", len(posts))
if posts:
    try:
        written = write_posts(posts, adapter_meta=meta, resolver=resolver)
        print("Written:", written)
    except Exception as e:
        print("WRITE ERROR:", e)

# Disable StockTwits
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("UPDATE source_adapters SET enabled=false WHERE adapter_id='stocks.stocktwits';")
    conn.commit()
print("\nStockTwits disabled (403 from server IP, Cloudflare blocked)")
