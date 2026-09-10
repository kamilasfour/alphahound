import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

# Check which API keys are actually set
keys = {
    "MASSIVE_API_KEY":          "Polygon.io / Massive   $29/mo  — price data",
    "FINNHUB_API_KEY":          "Finnhub               free    — news headlines",
    "UNUSUAL_WHALES_API_KEY":   "Unusual Whales        $125/mo — options flow",
    "QUIVER_API_KEY":           "Quiver Quant          $30/mo  — congressional trades",
    "ALPHA_VANTAGE_API_KEY":    "Alpha Vantage         free    — transcripts (disabled)",
    "ANTHROPIC_API_KEY":        "Anthropic Claude      pay/use — narratives",
    "ALPACA_API_KEY":           "Alpaca                free    — paper trading",
}

print()
print("=" * 65)
print("  API KEY & COST AUDIT")
print("=" * 65)
print()
total_monthly = 0
for env_var, description in keys.items():
    val = os.environ.get(env_var, "")
    status = "✅ SET" if val else "❌ MISSING"
    print("  {} {}".format(status, description))

print()
print("  PAID SUBSCRIPTIONS:")
print("  $125/mo  Unusual Whales   — OPTIONS FLOW")
print("  $ 29/mo  Polygon.io       — PRICE DATA")
print("  $ 30/mo  Quiver Quant     — CONGRESSIONAL TRADES")
print("  $ 30/mo  MT Newswires     — NEWS (via Claude MCP)")
print("  $250/mo  Azure VM         — SERVER")
print("  -------")
print("  ~$464/mo TOTAL")
print()
print("  FREE SOURCES ALSO RUNNING:")
print("  ApeWisdom    — Reddit mention aggregator")
print("  StockTwits   — Social sentiment posts")
print("  Substack RSS — Finance newsletters (27 feeds)")
print("  Finnhub      — News headlines (free tier)")
print("  Yahoo RSS    — News headlines")
print("  Alpaca       — Paper trading execution")
print("  Anthropic    — Claude narratives (pay per use ~$5-10/mo)")
print()
