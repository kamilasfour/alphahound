"""Signal lookup script — full detail on any ticker.

Usage:
    .\.venv\Scripts\python.exe scripts\lookup.py XLF
    .\.venv\Scripts\python.exe scripts\lookup.py QCOM
    .\.venv\Scripts\python.exe scripts\lookup.py SMH
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

MT = ZoneInfo("America/Los_Angeles")  # User is PST/PDT
ET = ZoneInfo("America/New_York")

def fmt_mt(dt):
    if not dt: return "—"
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MT).strftime("%b %d %I:%M %p PT")

def fmt_et(dt):
    if not dt: return "—"
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).strftime("%I:%M %p ET")

ticker = sys.argv[1].upper() if len(sys.argv) > 1 else None
if not ticker:
    print("Usage: .\.venv\Scripts\python.exe scripts\lookup.py <TICKER>")
    sys.exit(1)

with get_conn() as conn:
    with conn.cursor() as cur:

        # Entity
        cur.execute("""
            SELECT entity_id, canonical_symbol, module_id, kind
            FROM entities WHERE canonical_symbol = %s AND module_id = 'stocks'
        """, (ticker,))
        entity = cur.fetchone()

        if not entity:
            print(f"\n  {ticker} not found in entities table.\n")
            sys.exit(1)

        entity_id = entity[0]

        # Price snapshot
        cur.execute("""
            SELECT price, change_1d_pct, change_5d_pct, change_vs_spy, time
            FROM price_snapshots WHERE entity_id = %s ORDER BY time DESC LIMIT 1
        """, (entity_id,))
        price_row = cur.fetchone()

        # Divergence events (last 7 days)
        cur.execute("""
            SELECT d_value, p_value, components, time
            FROM divergence_events WHERE entity_id = %s
            AND time >= now() - interval '7 days'
            ORDER BY time DESC LIMIT 10
        """, (entity_id,))
        div_events = cur.fetchall()

        # Sentiment scores (last 24h)
        cur.execute("""
            SELECT source_class, AVG(polarity), AVG(confidence), COUNT(*)
            FROM sentiment_scores WHERE entity_id = %s
            AND time >= now() - interval '24 hours'
            GROUP BY source_class ORDER BY AVG(polarity) DESC
        """, (entity_id,))
        sentiment = cur.fetchall()

        # Trade log
        cur.execute("""
            SELECT side, size, price, alpaca_status, alpaca_order_id,
                   pnl, time, notes, closed_at
            FROM trade_log WHERE entity_id = %s
            ORDER BY time DESC LIMIT 5
        """, (entity_id,))
        trades = cur.fetchall()

        # Options flow (last 48h)
        cur.execute("""
            SELECT contract_type, sentiment, premium, unusual_score, expiry, time
            FROM options_flow WHERE entity_id = %s
            AND time >= now() - interval '48 hours'
            ORDER BY time DESC LIMIT 5
        """, (entity_id,))
        options = cur.fetchall()

        # Rhyme matches
        cur.execute("""
            SELECT event_name, similarity, prediction, confidence
            FROM rhyme_matches WHERE entity_id = %s
            ORDER BY similarity DESC LIMIT 3
        """, (entity_id,))
        rhymes = cur.fetchall()

now_pt = datetime.now(MT)
now_et = datetime.now(ET)

print()
print("=" * 65)
print(f"  SIGNAL LOOKUP — {ticker}")
print(f"  {now_pt.strftime('%a %b %d %I:%M %p PT')}  ({now_et.strftime('%I:%M %p ET')})")
print("=" * 65)

# Price
if price_row:
    price, chg1d, chg5d, vs_spy, pt = price_row
    print(f"\n  PRICE:  ${price:.2f}  "
          f"1d: {'+' if chg1d >= 0 else ''}{chg1d:.1f}%  "
          f"5d: {'+' if chg5d >= 0 else ''}{chg5d:.1f}%  "
          f"vs SPY: {'+' if vs_spy >= 0 else ''}{vs_spy:.1f}%"
          f"  (as of {fmt_mt(pt)})")
else:
    print("\n  PRICE:  No price data")

# Divergence
print(f"\n  DIVERGENCE EVENTS (last 7 days):")
if not div_events:
    print("    None")
else:
    for d_val, p_val, components, t in div_events:
        comps = dict(components) if components else {}
        narrative = comps.pop("narrative", "")
        tier = "EXTREME" if d_val >= 20 else "HIGH" if d_val >= 8 else "STANDARD" if d_val >= 4 else "monitor"
        ws = sum(float(comps.get(k,0)) for k in comps)
        direction = "LONG" if ws > 0 else "SHORT" if ws < 0 else "WATCH"
        will_exec = " ← WILL EXECUTE" if d_val >= 4.0 else ""
        print(f"    {fmt_mt(t)}  D={d_val:.2f}  p={p_val:.4f}  [{tier}]  {direction}{will_exec}")
        for src, pol in comps.items():
            if isinstance(pol, (int, float)):
                bar = "▲" if pol > 0 else "▼"
                print(f"      {bar} {src:<25} {pol:+.3f}")
        if narrative:
            print(f"      ℹ  {narrative[:100]}")
        print()

# Sentiment
print(f"  SENTIMENT (last 24h):")
if not sentiment:
    print("    No scored posts")
else:
    for src, avg_pol, avg_conf, count in sentiment:
        bar = "▲" if avg_pol > 0 else "▼"
        print(f"    {bar} {src:<25} polarity={avg_pol:+.3f}  conf={avg_conf:.2f}  ({count} posts)")

# Options
if options:
    print(f"\n  OPTIONS FLOW (last 48h):")
    for ctype, sentiment, premium, score, expiry, t in options:
        prem_str = f"${premium:,.0f}" if premium else "—"
        exp_str = expiry.strftime("%b %d") if expiry else "—"
        print(f"    {fmt_et(t)}  {ctype or '?':5s}  {sentiment or '?':8s}  premium={prem_str}  exp={exp_str}  score={score or '—'}")

# Rhyme matches
if rhymes:
    print(f"\n  RHYME ENGINE — historical pattern matches:")
    for event_name, sim, pred, conf in rhymes:
        conf_str = f"{conf:.0%}" if conf else "n/a"
        pred_str = pred or "no prediction"
        print(f"    {sim:.0%} match → '{event_name}'  prediction={pred_str}  confidence={conf_str}")

# Trade log
print(f"\n  TRADE LOG (last 5 entries):")
if not trades:
    print("    No trades logged")
else:
    for side, size, price, alpaca_status, order_id, pnl, t, notes, closed_at in trades:
        status = "CLOSED" if closed_at else ("FILLED" if alpaca_status == "filled" else ("PENDING" if order_id else "SIGNAL_ONLY"))
        pnl_str = f"  PnL=${pnl:+.2f}" if pnl is not None else ""
        print(f"    {fmt_mt(t)}  {side:5s}  ${size:.0f}  [{status}]{pnl_str}")
        if notes and isinstance(notes, dict):
            outlook = notes.get("outlook", {})
            if outlook:
                print(f"      resolve by: {outlook.get('resolve_by','?')}  catalyst: {outlook.get('catalyst','?')[:60]}")

print()
print("=" * 65)
print()
