"""Seed substack_feeds table with high-quality finance RSS feeds.

Adds 20+ feeds covering macro, equities, options, quant, and sector analysis.
Safe to run multiple times -- uses ON CONFLICT DO NOTHING.

Usage:
    .\.venv\Scripts\python.exe scripts\seed_feeds.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn

# High-quality finance RSS feeds -- all public, no auth required
# focus = primary content area for ticker extraction weighting
FEEDS = [
    # Already seeded -- will skip via ON CONFLICT
    ("abnormal-returns",         "Abnormal Returns",              "https://abnormalreturns.com/feed/",                                    "Tadas Viskanta", "markets",    "B", True),
    ("a-wealth-of-common-sense", "A Wealth of Common Sense",      "https://awealthofcommonsense.com/feed/",                               "Ben Carlson",    "markets",    "B", True),
    ("behavioural-investment",   "Behavioural Investment",         "https://behaviouralinvestment.com/feed/",                              "Joe Wiggins",    "markets",    "B", True),
    ("calculated-risk",          "Calculated Risk",                "https://www.calculatedriskblog.com/feeds/posts/default",               "Bill McBride",   "macro",      "B", True),
    ("macro-ops",                "Macro Ops",                     "https://macro-ops.com/feed/",                                          "Alex Barrow",    "macro",      "B", True),
    ("net-interest",             "Net Interest",                   "https://www.netinterest.co/feed",                                      "Marc Rubinstein","financials", "B", True),
    ("reformed-broker",          "The Reformed Broker",            "https://thereformedbroker.com/feed/",                                  "Josh Brown",     "markets",    "B", True),
    ("validea",                  "Validea Guru Investor",          "https://www.validea.com/guru-investor-blog/feed",                      "Validea",        "equities",   "B", True),

    # New feeds
    ("charlie-bilello",          "Charlie Bilello",                "https://charliebilello.com/feed/",                                     "Charlie Bilello","markets",    "A", True),
    ("of-dollars-and-data",      "Of Dollars and Data",            "https://ofdollarsanddata.com/feed/",                                   "Nick Maggiulli", "markets",    "B", True),
    ("dividend-growth-investor",  "Dividend Growth Investor",       "https://www.dividendgrowthinvestor.com/feeds/posts/default",            "DGI",            "equities",   "C", True),
    ("seeking-alpha-wall-st",    "Seeking Alpha Wall St Breakfast", "https://seekingalpha.com/feed/wall-street-breakfast",                  "Seeking Alpha",  "markets",    "A", True),
    ("marketbeat",               "MarketBeat Ideas",               "https://www.marketbeat.com/rss/ideas.ashx",                            "MarketBeat",     "equities",   "B", True),
    ("investors-business-daily", "IBD Market Pulse",               "https://www.investors.com/feed/",                                      "IBD",            "equities",   "A", True),
    ("wsj-markets",              "WSJ Markets",                    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                        "WSJ",            "markets",    "A", True),
    ("ft-markets",               "FT Markets",                     "https://www.ft.com/markets?format=rss",                                "FT",             "markets",    "A", True),
    ("reuters-business",         "Reuters Business",               "https://feeds.reuters.com/reuters/businessNews",                        "Reuters",        "macro",      "A", True),
    ("yahoo-finance-news",       "Yahoo Finance Top Stories",      "https://finance.yahoo.com/rss/topfinstories",                          "Yahoo Finance",  "markets",    "B", True),
    ("cnbc-top-news",            "CNBC Top News",                  "https://feeds.nbcnews.com/nbcnews/public/business",                    "CNBC",           "markets",    "B", True),
    ("marketwatch-top",          "MarketWatch Top Stories",        "https://feeds.marketwatch.com/marketwatch/topstories/",                "MarketWatch",    "markets",    "B", True),
    ("investopedia",             "Investopedia Market News",       "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline","Investopedia","markets",  "C", True),
    ("zerohedge",                "Zero Hedge",                     "https://feeds.feedburner.com/zerohedge/feed",                          "Zero Hedge",     "macro",      "C", True),
    ("the-big-picture",          "The Big Picture",                "https://ritholtz.com/feed/",                                           "Barry Ritholtz", "markets",    "B", True),
    ("alpha-architect",          "Alpha Architect",                "https://alphaarchitect.com/feed/",                                     "Wes Gray",       "quant",      "A", True),
    ("quantocracy",              "Quantocracy",                    "https://quantocracy.com/feed/",                                        "Quantocracy",    "quant",      "A", True),
    ("etf-com",                  "ETF.com News",                   "https://www.etf.com/rss/news",                                        "ETF.com",        "etfs",       "B", True),
    ("etf-trends",               "ETF Trends",                     "https://www.etftrends.com/feed/",                                      "ETF Trends",     "etfs",       "B", True),
]

with get_conn() as conn:
    with conn.cursor() as cur:
        inserted = 0
        skipped  = 0
        for row in FEEDS:
            slug, display_name, rss_url, author, focus, tier, enabled = row
            cur.execute("""
                INSERT INTO substack_feeds
                    (slug, display_name, rss_url, author, focus, tier, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    rss_url      = EXCLUDED.rss_url,
                    display_name = EXCLUDED.display_name,
                    tier         = EXCLUDED.tier,
                    enabled      = EXCLUDED.enabled;
            """, row)
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
    conn.commit()

print()
print(f"  Feed seeding complete.")
print(f"  Inserted/updated: {inserted}")
print()

# Verify
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT tier, COUNT(*) FROM substack_feeds WHERE enabled=true GROUP BY tier ORDER BY tier;")
        tiers = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM substack_feeds WHERE enabled=true;")
        total = cur.fetchone()[0]

print(f"  Total enabled feeds: {total}")
for tier, count in tiers:
    print(f"    Tier {tier}: {count} feeds")
print()
print("  Run the pipeline to start ingesting:")
print("  .\.venv\Scripts\alphahound.exe ingest stocks.substack")
print()
