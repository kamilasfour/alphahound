"""Close all open Alpaca paper positions immediately at market price.

Usage:
    .\.venv\Scripts\python.exe scripts\close_all_positions.py
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.execution.alpaca_broker import get_broker

broker = get_broker()

print()
print('=' * 50)
print('  CLOSE ALL POSITIONS')
print('=' * 50)

positions = broker.get_all_positions()

if not positions:
    print('  No open positions -- nothing to close.')
else:
    print('  Found {} open position(s):'.format(len(positions)))
    print()
    for pos in positions:
        print('    {:6s}  {:5s}  qty={:.4f}  P&L={:+.2f} ({:+.1f}%)'.format(
            pos.ticker, pos.side, pos.qty, pos.unrealized_pl, pos.unrealized_pl_pct))
    print()
    print('  Closing all...')
    print()

    results = broker.close_all_positions()
    for r in results:
        tag = 'OK ' if r['status'] != 'error' else 'ERR'
        print('    [{}]  {:6s}  status={}  order={}'.format(
            tag, r['ticker'], r['status'], r['order_id']))

    print()
    closed = sum(1 for r in results if r['status'] != 'error')
    print('  Done. {}/{} positions closed.'.format(closed, len(results)))

print('=' * 50)
print()
