"""Pull full signal detail for all open positions."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.execution.alpaca_broker import get_broker
from alphahound.engine.storage import get_conn

broker    = get_broker()
positions = broker.get_all_positions()
pos_map   = {p.ticker: p for p in positions}

with get_conn() as conn:
    with conn.cursor() as cur:
        for ticker, pos in sorted(pos_map.items()):

            # Get the trade_log row with the alpaca_order_id (the real entry)
            cur.execute("""
                SELECT tl.time, tl.side, tl.size, tl.filled_price, tl.notes,
                       tl.alpaca_order_id, tl.alpaca_status
                FROM trade_log tl
                JOIN entities e ON e.entity_id = tl.entity_id
                WHERE e.canonical_symbol = %s
                  AND e.module_id = 'stocks'
                  AND tl.alpaca_order_id IS NOT NULL
                ORDER BY tl.time DESC LIMIT 1
            """, (ticker,))
            row = cur.fetchone()

            print("=" * 70)
            print(f"  {ticker}  {pos.side.upper()}")
            print("=" * 70)
            print(f"  Entry price : ${pos.avg_entry:.2f}")
            print(f"  Current     : ${pos.current_price:.2f}")
            pnl_sign = '+' if pos.unrealized_pl >= 0 else ''
            print(f"  Live P&L    : {pnl_sign}${pos.unrealized_pl:.2f} ({pnl_sign}{pos.unrealized_pl_pct:.1f}%)")

            if not row:
                print("  NOTE: No trade_log entry with order_id found")
                print()
                continue

            entered_at, side, size, fill, notes_raw, order_id, alpaca_status = row
            notes = notes_raw if isinstance(notes_raw, dict) else (json.loads(notes_raw) if notes_raw else {})

            print(f"  Entered     : {entered_at.strftime('%Y-%m-%d %H:%M PT') if entered_at else 'unknown'}")
            print(f"  Order ID    : {order_id}")
            print(f"  Size        : ${size:,.0f}")
            print(f"  D-value     : {notes.get('d_value', '?')}")
            print(f"  Signal tier : {notes.get('signal_tier', '?')}")
            print(f"  Conviction  : {notes.get('conviction', '?')}/10")
            print(f"  Signal prob : {notes.get('signal_prob', '?')}")

            # Components — why the signal fired
            components = notes.get('components', {})
            if components:
                print(f"\n  SIGNAL COMPONENTS (why we entered):")
                for source, polarity in sorted(components.items(), key=lambda x: abs(x[1]), reverse=True):
                    if source == 'narrative':
                        continue
                    direction = '▲ BULLISH' if polarity > 0 else '▼ BEARISH'
                    print(f"    {source:<25} {polarity:+.3f}  {direction}")

            # Narrative
            narrative = notes.get('narrative', '')
            if narrative:
                print(f"\n  NARRATIVE:")
                print(f"    {narrative}")

            # Exit conditions
            outlook = notes.get('outlook', {})
            if outlook:
                print(f"\n  EXIT PLAN:")
                print(f"    Hold for   : {outlook.get('days_min')}-{outlook.get('days_max')} days")
                print(f"    Resolve by : {outlook.get('resolve_by')}")
                print(f"    Catalyst   : {outlook.get('catalyst')}")
                print(f"    Exit when  : {outlook.get('exit_condition')}")
                print(f"    Basis      : {outlook.get('signal_basis')}")

            # Stop loss
            stop_pct  = notes.get('stop_pct', 0)
            stop_price = notes.get('stop_price')
            if stop_price:
                stop_hit = (pos.side == 'long' and pos.current_price <= stop_price) or \
                           (pos.side == 'short' and pos.current_price >= stop_price)
                stop_status = '🔴 STOP HIT' if stop_hit else '🟢 safe'
                print(f"\n  STOP LOSS:")
                print(f"    Stop price : ${stop_price:.2f}  ({stop_pct*100:.1f}%)")
                print(f"    Status     : {stop_status}")

            print()
