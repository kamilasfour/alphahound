"""Debug substack ticker extraction -- shows why articles get 0 posts.

Usage:
    .\.venv\Scripts\python.exe scripts\debug_feeds.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

import httpx
from datetime import datetime, timedelta, timezone
from alphahound.modules.stocks.adapters.substack import (
    _fetch_feed, _extract_tickers, _clean_html, LOOKBACK_HOURS
)
from alphahound.engine.storage import get_conn

# Test feeds that returned 0 posts
TEST_FEEDS = [
    {"slug": "ft-markets",     "display_name": "FT Markets",         "rss_url": "https://www.ft.com/markets?format=rss"},
    {"slug": "yahoo-finance-news", "display_name": "Yahoo Finance",  "rss_url": "https://finance.yahoo.com/rss/topfinstories"},
    {"slug": "zerohedge",      "display_name": "Zero Hedge",         "rss_url": "https://feeds.feedburner.com/zerohedge/feed"},
    {"slug": "cnbc-top-news",  "display_name": "CNBC",               "rss_url": "https://feeds.nbcnews.com/nbcnews/public/business"},
]

since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
}

print()
with httpx.Client(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
    for feed in TEST_FEEDS:
        print("=" * 60)
        print("FEED: {}".format(feed["display_name"]))
        print("=" * 60)
        try:
            articles = _fetch_feed(client, feed, since)
            print("  {} articles found".format(len(articles)))
            for i, a in enumerate(articles[:5]):
                title = a["title"]
                text  = a["text"][:200] if a["text"] else ""
                full  = "{title}. {text}".format(title=title, text=text)
                tickers = _extract_tickers(full)
                print()
                print("  Article {}: {}".format(i+1, title[:70]))
                print("  Text preview: {}...".format(text[:100]))
                print("  Tickers found: {}".format(tickers if tickers else "NONE"))
        except Exception as e:
            print("  ERROR: {}".format(e))
        print()
