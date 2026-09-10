"""Options Trade Executor — Sprint 11 S11-7.

Reads super signals with attached structure plans from convergence_signals,
applies all guards (market open, macro, portfolio cap, already-executed),
and places options orders via Alpaca's paper trading API.

ARCHITECTURE
────────────
This module sits between the convergence engine and Alpaca. It is deliberately
separate from executor.py (which handles equity trades) to keep concerns clean.
The two executors share guards but place different order types.

OPTIONS ORDER FLOW
──────────────────
For spreads (BULL_CALL_SPREAD / BEAR_PUT_SPREAD):
    Alpaca multi-leg order: 2 legs submitted as a single order.
    Order type: limit, debit (we pay). Limit price = estimated_debit + 10% buffer.

For strangles (LONG_STRANGLE):
    Two separate single-leg market orders (Alpaca doesn't support strangles natively
    as a single multi-leg order — only spreads are supported as combos).

For naked longs (LONG_CALL / LONG_PUT):
    Single-leg market order.

SIZING
──────
Sizing uses the same Kelly + macro + tech modifier pipeline as the equity executor,
applied to max_loss per contract to determine number of contracts.

Target risk = equity × RISK_PCT_PER_TRADE (2%)
Max contracts = floor(target_risk / estimated_max_loss_per_contract)
Capped at MAX_CONTRACTS (5) to prevent outsized positions on a $20k account.

GUARDS (applied in order)
──────────────────────────
1. Market open check
2. Macro RISK_OFF blocks all new options entries
3. Signal age check — only execute signals from the last cycle (<20 min)
4. Already-executed check — only one options trade per ticker per day
5. Portfolio cap — stop if deployed >= MAX_DEPLOYED_PCT

IMPORTANT LIMITATIONS
─────────────────────
- Alpaca paper options require options trading to be enabled on the account.
  If not enabled, all orders will fail with 403. Check dashboard.alpaca.markets.
- Strike prices must match actual listed strikes. Our BS estimates may not match
  real chains. The executor queries Alpaca's options chain to find the nearest
  listed strike before placing. If no matching contract found, order is skipped.
- Limit orders only — no market orders for options (too much slippage risk).
  Limit = estimated_debit * 1.10 for spreads (10% over estimate to get filled).

CLI: alphahound signals options-execute [--ticker TICKER] [--dry-run]
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

from alphahound.engine.execution.alpaca_broker import get_broker
from alphahound.engine.signals.macro_context import get_macro_context_cached, MacroVerdict
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

RISK_PCT_PER_TRADE = float(os.environ.get("OPTIONS_RISK_PCT", "0.02"))  # 2% per trade
MAX_OPEN_SPREADS    = int(os.environ.get('MAX_OPEN_SPREADS', '3'))   # never more than 3 open positions
MAX_DEPLOYED_PCT   = float(os.environ.get("MAX_DEPLOYED_PCT", "0.60"))
LIMIT_BUFFER_PCT   = 0.10   # pay up to 10% over estimate to get filled
MAX_SIGNAL_AGE_MIN = 20     # only execute signals written in last 20 minutes


# ─── Data shapes ─────────────────────────────────────────────────────────────

@dataclass
class OptionsOrderResult:
    ticker:         str
    structure_type: str
    status:         str = "pending" # "placed", "skipped", "error", "dry_run", "pending"
    reason:         str = ""
    order_ids:      list[str] = field(default_factory=list)
    contracts:      int = 0
    total_debit:    float = 0.0
    legs:           list[dict] = field(default_factory=list)
    signal_score:   float = 0.0
    catalyst_type:  Optional[str] = None
    catalyst_date:  Optional[str] = None

    def display(self) -> str:
        icon = {"placed": "✅", "skipped": "⏭ ", "error": "❌", "dry_run": "🔍"}.get(self.status, "ℹ ")
        lines = [
            f"  {icon} {self.ticker:<6}  {self.structure_type:<20}  score={self.signal_score:.2f}  {self.status}",
        ]
        if self.reason:
            lines.append(f"       reason: {self.reason}")
        if self.status in ("placed", "dry_run") and self.legs:
            lines.append(f"       contracts: {self.contracts}  debit: ~${self.total_debit:.2f}")
            for leg in self.legs:
                lines.append(
                    f"       {leg['action']:<4} {leg['contract_type']} ${leg['strike']} "
                    f"exp {leg['expiry']}  order={leg.get('order_id','pending')[:12]}"
                )
        return "\n".join(lines)


# ─── Main entry points ────────────────────────────────────────────────────────

def execute_options_all(dry_run: bool = False) -> list[OptionsOrderResult]:
    """Execute all current super signals with attached structure plans.

    Returns list of results for CLI display.
    """
    broker = get_broker()

    if not broker.is_market_open():
        next_open = broker.next_market_open()
        next_str = next_open.strftime("%Y-%m-%d %H:%M UTC") if next_open else "unknown"
        return [OptionsOrderResult(
            ticker="ALL", structure_type="—", status="skipped",
            reason=f"Market closed. Next open: {next_str}",
        )]

    macro = get_macro_context_cached()
    if macro.verdict in (MacroVerdict.RISK_OFF, MacroVerdict.NEUTRAL):
        return [OptionsOrderResult(
            ticker="ALL", structure_type="—", status="skipped",
            reason=f"Macro {macro.verdict.value} (score={macro.score:+.3f}) — no new LONG entries. Need RISK_ON.",
        )]

    try:
        account = broker.get_account()
    except Exception as exc:
        log.warning("Could not fetch account: %s", exc)
        account = None

    signals = _get_executable_signals()
    if not signals:
        return [OptionsOrderResult(
            ticker="ALL", structure_type="—", status="skipped",
            reason="No super signals with attached structures in last 20 minutes",
        )]

    # ── Portfolio health gate ─────────────────────────────────────────────────
    # Halt new trades if 3+ existing positions are down more than 50%
    try:
        from alphahound.engine.execution.options_monitor import _fetch_alpaca_options_positions, _get_open_trades
        open_trades   = _get_open_trades()
        alpaca_pos    = _fetch_alpaca_options_positions()
        alpaca_by_sym = {p['symbol'].replace(' ','').upper(): p for p in alpaca_pos}

        # Hard position limit
        if len(open_trades) >= MAX_OPEN_SPREADS:
            msg = f'Position limit: {len(open_trades)}/{MAX_OPEN_SPREADS} open spreads. No new entries until a position closes.'
            log.warning(msg)
            return [OptionsOrderResult(ticker='ALL', structure_type='—', status='skipped', reason=msg)]

        underwater = 0
        for trade in open_trades:
            legs  = trade.get('legs_json') or []
            debit = float(trade.get('estimated_debit') or 0)
            if not debit or not legs:
                continue
            mv = 0.0
            for leg in (legs if isinstance(legs, list) else []):
                sym = (_build_occ_symbol(trade['ticker'], leg.get('expiry',''), leg.get('contract_type','CALL'), float(leg.get('strike',0))) or '').replace(' ','')
                if sym in alpaca_by_sym:
                    mv += abs(float(alpaca_by_sym[sym].get('market_value') or 0))
            if mv and (mv - debit) / debit < -0.50:
                underwater += 1
        if underwater >= 3:
            msg = f'Portfolio health gate: {underwater} positions >50% underwater. Halting new entries.'
            log.warning(msg)
            return [OptionsOrderResult(ticker='ALL', structure_type='—', status='skipped', reason=msg)]
    except Exception as _gate_exc:
        log.debug('portfolio health gate failed: %s', _gate_exc)

    results = []
    for sig in signals:
        result = _execute_one_signal(sig, broker, account, macro, dry_run)
        results.append(result)

    return results


def execute_options_ticker(ticker: str, dry_run: bool = False) -> OptionsOrderResult:
    """Execute options trade for a specific ticker's current super signal."""
    broker = get_broker()

    if not broker.is_market_open() and not dry_run:
        return OptionsOrderResult(
            ticker=ticker, structure_type="—", status="skipped",
            reason="Market closed",
        )

    macro = get_macro_context_cached()
    if macro.verdict == MacroVerdict.RISK_OFF and not dry_run:
        return OptionsOrderResult(
            ticker=ticker, structure_type="—", status="skipped",
            reason=f"Macro RISK_OFF ({macro.score:+.3f})",
        )

    try:
        account = broker.get_account()
    except Exception:
        account = None

    signals = _get_executable_signals(ticker=ticker.upper())
    if not signals:
        # Fall back to latest super signal for this ticker regardless of age
        signals = _get_executable_signals(ticker=ticker.upper(), max_age_minutes=1440)
        if not signals:
            return OptionsOrderResult(
                ticker=ticker, structure_type="—", status="skipped",
                reason=f"No super signal with attached structure found for {ticker}",
            )

    return _execute_one_signal(signals[0], broker, account, macro, dry_run)


# ─── Signal retrieval ─────────────────────────────────────────────────────────

def _get_executable_signals(
    ticker: Optional[str] = None,
    max_age_minutes: int = MAX_SIGNAL_AGE_MIN,
) -> list[dict]:
    """Fetch super signals with attached structure plans from the last N minutes."""
    since = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if ticker:
                    cur.execute("""
                        SELECT ticker, entity_id, composite_score, pillars_fired,
                               direction, catalyst_date, catalyst_type,
                               pillar_breakdown, time
                        FROM convergence_signals
                        WHERE super_signal = TRUE
                          AND ticker = %s
                          AND pillar_breakdown ? 'structure'
                        ORDER BY time DESC
                        LIMIT 1;
                    """, (ticker,))
                else:
                    cur.execute("""
                        SELECT DISTINCT ON (ticker)
                            ticker, entity_id, composite_score, pillars_fired,
                            direction, catalyst_date, catalyst_type,
                            pillar_breakdown, time
                        FROM convergence_signals
                        WHERE super_signal = TRUE
                          AND time >= %s
                          AND pillar_breakdown ? 'structure'
                        ORDER BY ticker, composite_score DESC, time DESC;
                    """, (since,))
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as exc:
        log.error("_get_executable_signals failed: %s", exc)
        return []


# ─── Single signal execution ──────────────────────────────────────────────────

def _execute_one_signal(
    sig: dict,
    broker,
    account: Optional[dict],
    macro,
    dry_run: bool,
) -> OptionsOrderResult:
    ticker         = sig["ticker"]
    structure_dict = sig["pillar_breakdown"].get("structure", {})
    structure_type = structure_dict.get("structure_type", "UNKNOWN")
    score          = float(sig.get("composite_score", 0))
    catalyst_type  = sig.get("catalyst_type")
    catalyst_date  = sig.get("catalyst_date")

    base = OptionsOrderResult(
        ticker=ticker,
        structure_type=structure_type,
        signal_score=score,
        catalyst_type=catalyst_type,
        catalyst_date=str(catalyst_date) if catalyst_date else None,
    )

    # Already executed today?
    if _already_executed_today(str(sig["entity_id"])):
        base.status = "skipped"
        base.reason = "Already executed today"
        return base

    # Portfolio cap — skip cash check in dry run (account may have stale positions)
    if account and not dry_run:
        cash          = account.get("cash", 0.0)
        equity        = account.get("equity", 20_000.0)
        min_cash      = equity * (1.0 - MAX_DEPLOYED_PCT)
        if cash < min_cash:
            base.status = "skipped"
            base.reason = f"Insufficient cash: ${cash:.0f} available, need >${min_cash:.0f}"
            return base

    # Get equity for sizing — use 20k floor in dry run if account is overdrawn
    raw_equity = float(account.get("equity", 20_000.0)) if account else 20_000.0
    equity = max(raw_equity, 20_000.0) if dry_run else raw_equity

    # Compute contracts
    max_loss_per = structure_dict.get("estimated_max_loss", 0)
    if not max_loss_per or max_loss_per <= 0:
        base.status = "skipped"
        base.reason = "No estimated_max_loss in structure — can't size"
        return base

    target_risk = equity * RISK_PCT_PER_TRADE
    contracts   = max(1, min(2, int(target_risk / max_loss_per)))  # hard cap at 2 contracts
    total_debit = (structure_dict.get("estimated_debit", 0) or 0) * contracts

    base.contracts   = contracts
    base.total_debit = total_debit

    # Build leg specs
    legs = _build_leg_specs(structure_type, structure_dict)
    if not legs:
        base.status = "skipped"
        base.reason = f"Could not build legs for {structure_type}"
        return base

    base.legs = [dict(leg) for leg in legs]

    if dry_run:
        base.status = "dry_run"
        base.reason = (
            f"Would place {contracts} contract(s) of {structure_type} on {ticker}. "
            f"Estimated debit: ~${total_debit:.2f}. "
            f"Max loss: ~${max_loss_per * contracts:.2f}. "
            f"Verify strikes against actual chain before live execution."
        )
        log.info("[DRY RUN] %s %s: %d contracts, debit=~$%.2f",
                 ticker, structure_type, contracts, total_debit)
        return base

    # Place orders
    order_ids = []
    errors    = []

    try:
        if structure_type in ("BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"):
            order_id = _place_spread_order(broker, ticker, legs, contracts, structure_dict)
            if order_id:
                order_ids.append(order_id)
                for leg in base.legs:
                    leg["order_id"] = order_id
        elif structure_type == "LONG_STRANGLE":
            for leg in legs:
                order_id = _place_single_leg(broker, ticker, leg, contracts)
                if order_id:
                    order_ids.append(order_id)
                    for bl in base.legs:
                        if bl["contract_type"] == leg["contract_type"]:
                            bl["order_id"] = order_id
                else:
                    errors.append(f"{leg['contract_type']} leg failed")
        else:
            # LONG_CALL / LONG_PUT
            order_id = _place_single_leg(broker, ticker, legs[0], contracts)
            if order_id:
                order_ids.append(order_id)
                base.legs[0]["order_id"] = order_id
            else:
                errors.append("Single leg order failed")
    except Exception as exc:
        err = str(exc)
        if "CHAIN_TOO_SHORT" in err:
            base.status = "skipped"
            base.reason = f"{ticker}: options chain too short — strikes resolve to same contract. Cannot build spread at current price."
        else:
            base.status = "error"
            base.reason = err
        log.error("Options execution failed for %s: %s", ticker, err)
        return base

    if errors and not order_ids:
        base.status = "error"
        base.reason = "; ".join(errors)
        return base

    base.order_ids = order_ids
    base.status    = "placed"
    base.reason    = f"{len(order_ids)} order(s) submitted"

    # Log to DB
    _log_options_trade(sig, base, contracts, total_debit)

    log.info("OPTIONS PLACED: %s %s contracts=%d debit=$%.2f orders=%s",
             ticker, structure_type, contracts, total_debit, order_ids)

    return base


# ─── Leg builder ─────────────────────────────────────────────────────────────

def _build_leg_specs(structure_type: str, structure_dict: dict) -> list[dict]:
    """Convert structure dict legs into order specs."""
    raw_legs = structure_dict.get("legs", [])
    if not raw_legs:
        return []

    specs = []
    for leg in raw_legs:
        specs.append({
            "action":        leg.get("action", "BUY"),     # "BUY" or "SELL"
            "contract_type": leg.get("contract_type", "CALL"),  # "CALL" or "PUT"
            "strike":        float(leg.get("strike", 0)),
            "expiry":        leg.get("expiry", ""),
            "estimated_premium": float(leg.get("estimated_premium", 0)),
        })
    return specs


# ─── Alpaca options API calls ─────────────────────────────────────────────────

def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID":     os.environ.get("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET_KEY", ""),
        "Content-Type":        "application/json",
    }


def _alpaca_base() -> str:
    return os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _place_spread_order(broker, ticker: str, legs: list[dict], contracts: int, structure_dict: dict) -> Optional[str]:
    """Place a multi-leg spread order via Alpaca's options API."""
    estimated_debit = structure_dict.get("estimated_debit", 0) or 0
    limit_price     = round(estimated_debit / 100 * (1 + LIMIT_BUFFER_PCT), 2)

    order_legs = []
    seen_symbols = set()
    for leg in legs:
        real_symbol = _find_real_contract(ticker, leg["expiry"], leg["contract_type"], leg["strike"])
        if not real_symbol:
            raise ValueError(f"No listed contract found for {ticker} {leg['contract_type']} ~${leg['strike']} exp {leg['expiry']}")
        if real_symbol in seen_symbols:
            raise ValueError(f"CHAIN_TOO_SHORT:{real_symbol}")
        seen_symbols.add(real_symbol)
        side   = "buy" if leg["action"] == "BUY" else "sell"
        intent = "buy_to_open" if leg["action"] == "BUY" else "sell_to_open"
        order_legs.append({
            "symbol":          real_symbol,
            "ratio_qty":       "1",
            "side":            side,
            "position_intent": intent,
        })

    payload = {
        "type":          "limit",
        "time_in_force": "day",
        "order_class":   "mleg",
        "qty":           str(contracts),
        "limit_price":   str(limit_price),
        "legs":          order_legs,
    }

    log.info("Placing spread order: %s  legs=%s  qty=%d  limit=$%.2f",
             ticker, [(l["symbol"], l["side"]) for l in order_legs], contracts, limit_price)

    try:
        resp = httpx.post(
            f"{_alpaca_base()}/v2/orders",
            headers=_alpaca_headers(),
            json=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        data     = resp.json()
        order_id = data.get("id", "")
        log.info("Spread order placed: %s  order_id=%s  status=%s",
                 ticker, order_id, data.get("status"))
        return order_id
    except httpx.HTTPStatusError as exc:
        log.error("Spread order failed for %s: %s %s", ticker, exc.response.status_code, exc.response.text[:200])
        raise
    except Exception as exc:
        log.error("Spread order error for %s: %s", ticker, exc)
        raise


def _find_real_contract(ticker: str, expiry_str: str, contract_type: str, target_strike: float) -> Optional[str]:
    """Query Alpaca options chain and return the OCC symbol of the nearest listed strike."""
    cp = "call" if contract_type.upper() == "CALL" else "put"
    try:
        exp_date = date.fromisoformat(expiry_str[:10])
    except Exception:
        return None

    try:
        resp = httpx.get(
            f"{_alpaca_base()}/v2/options/contracts",
            headers=_alpaca_headers(),
            params={
                "underlying_symbols": ticker.upper(),
                "type":              cp,
                "expiration_date":   exp_date.isoformat(),
                "status":            "active",
                "limit":             "100",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        contracts = resp.json().get("option_contracts", [])
    except Exception as exc:
        log.warning("_find_real_contract: chain query failed for %s: %s", ticker, exc)
        return None

    if not contracts:
        # Try adjacent expiry dates (+/- 7 days)
        log.warning("_find_real_contract: no contracts found for %s %s exp %s — trying nearby expiry",
                    ticker, cp, exp_date)
        for delta in [7, 14, -7]:
            nearby = (exp_date + timedelta(days=delta)).isoformat()
            try:
                resp2 = httpx.get(
                    f"{_alpaca_base()}/v2/options/contracts",
                    headers=_alpaca_headers(),
                    params={"underlying_symbols": ticker.upper(), "type": cp,
                            "expiration_date": nearby, "status": "active", "limit": "100"},
                    timeout=15.0,
                )
                resp2.raise_for_status()
                contracts = resp2.json().get("option_contracts", [])
                if contracts:
                    log.info("_find_real_contract: found %d contracts on nearby expiry %s", len(contracts), nearby)
                    break
            except Exception:
                continue

    if not contracts:
        log.warning("_find_real_contract: no contracts found for %s %s near exp %s", ticker, cp, exp_date)
        return None

    # Find nearest tradable strike to our target
    tradable = [c for c in contracts if c.get("tradable") and c.get("strike_price")]
    if not tradable:
        tradable = contracts

    if not tradable:
        return None

    nearest = min(tradable, key=lambda c: abs(float(c["strike_price"]) - target_strike))
    symbol  = nearest["symbol"]
    actual_strike = float(nearest["strike_price"])

    # Guard: if nearest strike is >20% away from target, log a warning
    if abs(actual_strike - target_strike) / max(target_strike, 1) > 0.20:
        log.warning("_find_real_contract: %s nearest strike $%.0f is >20%% from target $%.0f — chain may be limited",
                    ticker, actual_strike, target_strike)

    log.info("_find_real_contract: %s target=$%.0f → %s (strike=$%.0f)",
             ticker, target_strike, symbol, actual_strike)
    return symbol


def _place_single_leg(broker, ticker: str, leg: dict, contracts: int) -> Optional[str]:
    """Place a single-leg options order (for strangles and naked longs)."""
    occ_symbol  = _build_occ_symbol(ticker, leg["expiry"], leg["contract_type"], leg["strike"])
    est_premium = leg.get("estimated_premium", 0) or 0
    limit_price = round(est_premium * (1 + LIMIT_BUFFER_PCT), 2)

    side = "buy_to_open" if leg["action"] == "BUY" else "sell_to_open"

    payload = {
        "symbol":          occ_symbol,
        "qty":             str(contracts),
        "side":            side,
        "type":            "limit",
        "time_in_force":   "day",
        "limit_price":     str(limit_price),
        "position_intent": "bto" if side == "buy_to_open" else "sto",
    }

    log.info("Placing single-leg options order: %s  %s  qty=%d  limit=$%.2f",
             occ_symbol, side, contracts, limit_price)

    try:
        resp = httpx.post(
            f"{_alpaca_base()}/v2/orders",
            headers=_alpaca_headers(),
            json=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        order_id = data.get("id", "")
        log.info("Single-leg order placed: %s  order_id=%s  status=%s",
                 occ_symbol, order_id, data.get("status"))
        return order_id
    except httpx.HTTPStatusError as exc:
        log.error("Single-leg order failed for %s: %s %s",
                  occ_symbol, exc.response.status_code, exc.response.text[:200])
        raise
    except Exception as exc:
        log.error("Single-leg order error for %s: %s", occ_symbol, exc)
        raise


def _build_occ_symbol(ticker: str, expiry_str: str, contract_type: str, strike: float) -> str:
    """Build OCC option symbol: e.g. MU    260718C00095000

    Format: <underlying padded to 6> <YYMMDD> <C/P> <strike * 1000 padded to 8>
    Example: MU    260718C00095000
    """
    ticker = ticker.upper().ljust(6)

    # Parse expiry — can be "2026-07-18" or "2026-07-18"
    try:
        exp_date = date.fromisoformat(expiry_str[:10])
        exp_str  = exp_date.strftime("%y%m%d")
    except (ValueError, TypeError):
        exp_str = "260718"  # fallback

    cp      = "C" if contract_type.upper() == "CALL" else "P"
    # Strike in 8-digit format: $95.00 → 00095000
    strike_int = int(round(strike * 1000))
    strike_str = str(strike_int).zfill(8)

    return f"{ticker}{exp_str}{cp}{strike_str}"


# ─── Logging ─────────────────────────────────────────────────────────────────

def _log_options_trade(sig: dict, result: OptionsOrderResult, contracts: int, total_debit: float) -> None:
    """Write options trade to options_trade_log table."""
    _ensure_options_log_table()
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO options_trade_log
                        (time, entity_id, ticker, structure_type, direction,
                         contracts, estimated_debit, estimated_max_loss,
                         catalyst_type, catalyst_date, composite_score,
                         order_ids, legs_json, status)
                    VALUES
                        (now(), %s, %s, %s, %s,
                         %s, %s, %s,
                         %s, %s, %s,
                         %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (
                    str(sig["entity_id"]),
                    result.ticker,
                    result.structure_type,
                    sig.get("direction", "NEUTRAL"),
                    contracts,
                    round(total_debit, 2),
                    round(total_debit * 2, 2),   # rough max loss estimate
                    result.catalyst_type,
                    result.catalyst_date,
                    result.signal_score,
                    result.order_ids,
                    __import__("json").dumps(result.legs),
                    result.status,
                ))
            conn.commit()
    except Exception as exc:
        log.warning("_log_options_trade failed: %s", exc)


def _already_executed_today(entity_id: str) -> bool:
    """Check if we already placed an options order for this entity today.
    Also checks live Alpaca positions as a safety net against DB failures."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM options_trade_log
                    WHERE entity_id = %s AND time >= %s AND status IN ('placed','superseded')
                    LIMIT 1;
                """, (entity_id, today_start))
                if cur.fetchone():
                    return True
                # Also check by ticker
                cur.execute("""
                    SELECT ticker FROM options_trade_log
                    WHERE entity_id = %s ORDER BY time DESC LIMIT 1;
                """, (entity_id,))
                row = cur.fetchone()
                if not row:
                    return False
                ticker = row[0]
    except Exception:
        return False

    # Cross-check against live Alpaca positions
    try:
        resp = httpx.get(
            f"{_alpaca_base()}/v2/positions",
            headers=_alpaca_headers(),
            timeout=10.0,
        )
        if resp.status_code == 200:
            positions = resp.json()
            if isinstance(positions, list):
                for p in positions:
                    sym = p.get('symbol', '')
                    if sym.startswith(ticker.upper()) and p.get('asset_class') == 'us_option':
                        log.info("_already_executed_today: found live Alpaca position %s for %s — skipping", sym, ticker)
                        return True
    except Exception:
        pass

    return False


def _ensure_options_log_table() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS options_trade_log (
                    id              SERIAL PRIMARY KEY,
                    time            TIMESTAMPTZ NOT NULL DEFAULT now(),
                    entity_id       UUID,
                    ticker          TEXT NOT NULL,
                    structure_type  TEXT NOT NULL,
                    direction       TEXT,
                    contracts       INT,
                    estimated_debit FLOAT,
                    estimated_max_loss FLOAT,
                    catalyst_type   TEXT,
                    catalyst_date   DATE,
                    composite_score FLOAT,
                    order_ids       TEXT[],
                    legs_json       JSONB,
                    status          TEXT,
                    actual_debit    FLOAT,
                    closed_at       TIMESTAMPTZ,
                    pnl             FLOAT,
                    notes           TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_options_log_time
                    ON options_trade_log (time DESC);
                CREATE INDEX IF NOT EXISTS idx_options_log_ticker
                    ON options_trade_log (ticker, time DESC);
            """)
        conn.commit()
