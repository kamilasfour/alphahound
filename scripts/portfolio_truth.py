import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from alphahound.engine.storage import get_conn
import httpx, os

headers = {
    'APCA-API-KEY-ID':     os.environ.get('ALPACA_API_KEY',''),
    'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY',''),
}

# Get all Alpaca positions
r = httpx.get('https://paper-api.alpaca.markets/v2/positions', headers=headers, timeout=15)
positions = r.json()

# Get account
ra = httpx.get('https://paper-api.alpaca.markets/v2/account', headers=headers, timeout=15)
account = ra.json()

print(f"Account equity:     ${float(account.get('equity',0)):,.2f}")
print(f"Account cash:       ${float(account.get('cash',0)):,.2f}")
print(f"Starting equity:    $20,000.00")
print(f"Total P&L:          ${float(account.get('equity',0))-20000:,.2f}")
print()

# Group by underlying
from collections import defaultdict
spreads = defaultdict(list)
for p in positions:
    sym = p['symbol']
    # extract underlying ticker
    import re
    m = re.match(r'^([A-Z]+)\d', sym)
    if m:
        spreads[m.group(1)].append(p)

print(f"{'Ticker':<6} {'Entry':>8} {'Current':>9} {'P&L':>8} {'%':>7}  Status")
print("-" * 60)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ticker, estimated_debit, time, status FROM options_trade_log WHERE status='placed' ORDER BY time")
        trades = {r[0]: r for r in cur.fetchall()}

total_entry = 0
total_current = 0
for ticker, legs in sorted(spreads.items()):
    entry   = abs(sum(float(l.get('cost_basis',0)) for l in legs))
    current = sum(float(l.get('market_value',0)) for l in legs)
    pl      = current - entry
    pct     = (pl/entry*100) if entry else 0
    flag    = ' 🚨 STOP LOSS' if pct <= -80 else ' ⚠️  DANGER' if pct <= -50 else ''
    total_entry   += entry
    total_current += current
    print(f"{ticker:<6} ${entry:>7.0f}  ${current:>7.0f}  ${pl:>7.0f}  {pct:>6.1f}%{flag}")

print("-" * 60)
total_pl  = total_current - total_entry
total_pct = (total_pl/total_entry*100) if total_entry else 0
print(f"{'TOTAL':<6} ${total_entry:>7.0f}  ${total_current:>7.0f}  ${total_pl:>7.0f}  {total_pct:>6.1f}%")
