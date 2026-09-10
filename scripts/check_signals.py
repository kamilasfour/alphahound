import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.signals.trade_advisor import advise_all

recs = advise_all(min_d=4.0)

if not recs:
    print("No signals above D=4.0 right now.")
else:
    print()
    print("{:<6}  {:>6}  {:<8}  {:<8}  {:<9}  {:>7}  {}".format(
        "TICKER", "D-VAL", "TIER", "EXECUTE", "LEVERAGED", "SIZE", "DIRECTION"))
    print("-" * 65)
    for r in recs:
        print("{:<6}  {:>6.1f}  {:<8}  {:<8}  {:<9}  ${:>6.0f}  {}".format(
            r.ticker,
            r.d_value,
            r.signal_tier.value,
            r.execute_ticker,
            str(r.is_leveraged),
            r.position_usd,
            r.direction.value,
        ))
    print()
    print("Bankroll: ${}".format(
        __import__('os').environ.get('ALPHAHOUND_BANKROLL', 'NOT SET')))
