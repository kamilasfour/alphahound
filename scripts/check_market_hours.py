import sys, json
sys.path.insert(0, r'C:\alphahound_project\src')
from dotenv import load_dotenv
load_dotenv(r'C:\alphahound_project\.env')
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

utc = datetime.now(timezone.utc)
et  = utc.astimezone(ZoneInfo('America/New_York'))
pt  = utc.astimezone(ZoneInfo('America/Los_Angeles'))

h, m, dow = et.hour, et.minute, et.weekday()
open_ = dow < 5 and (h > 9 or (h == 9 and m >= 30)) and h < 16

result = {
    "utc": utc.strftime('%Y-%m-%d %H:%M:%S'),
    "et":  et.strftime('%Y-%m-%d %H:%M:%S'),
    "pt":  pt.strftime('%Y-%m-%d %H:%M:%S'),
    "weekday": dow,
    "market_open_by_et": open_,
}

print(json.dumps(result, indent=2))

# Also test the broker directly
from alphahound.engine.execution.alpaca_broker import AlpacaBroker
b = AlpacaBroker()
print(f"\nbroker.is_market_open(): {b.is_market_open()}")

import inspect
src = inspect.getsource(b.is_market_open)
print(f"\nis_market_open source snippet:\n{src[:300]}")
