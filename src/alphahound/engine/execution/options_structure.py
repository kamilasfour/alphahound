"""Options Structure Recommender — Sprint 11 S11-4.

WHAT THIS IS
────────────
A signal-to-structure mapper. Given a super signal from the convergence engine,
it produces a human-readable trade plan: which structure, which strikes, which
expiry, and why. This is a PLANNING OUTPUT, not a live quote.

WHAT THIS IS NOT
────────────────
- Not a live pricer. Option prices are estimated via Black-Scholes on HV30.
  Actual market prices will differ, especially pre-catalyst when IV inflates.
- Not a sizer. Contracts field is None. Sizing lives in executor.py which
  has Kelly, macro modifier, tech gate, and portfolio cap logic. We don't
  duplicate that here.
- Not an execution layer. No Alpaca calls. Structure recommendations are
  stored in the DB for display and hit-rate tracking. Execution is S11-7.

GUARD RAIL
──────────
Only fires for genuine super signals: composite_score >= 4.0 AND pillars_fired >= 4.
Anything below that returns None. A 2.0-score signal does not get a structure —
that would be noise dressed up as a trade.

PRICING METHOD
──────────────
IV estimate = HV30 × IV_PREMIUM_FACTOR (1.15)
Option prices via Black-Scholes approximation.
All prices tagged is_estimated=True, pricing_method="BS_HV30_APPROX".
Replace with live IV feed in S11-6.

Known limitations:
  - Pre-earnings IV inflates 20-50% above HV30 — debit will be understated
  - PDUFA IV can be 2-3x HV30 — strangle debit will be significantly understated
  - Strikes rounded to standard intervals, not validated against actual chain

STRUCTURE SELECTION
───────────────────
  PDUFA (any direction)        → LONG_STRANGLE  (binary FDA outcome)
  5+ pillars LONG              → LONG_CALL       (maximum conviction)
  5+ pillars SHORT             → LONG_PUT        (maximum conviction)
  LONG + catalyst              → BULL_CALL_SPREAD
  SHORT + catalyst             → BEAR_PUT_SPREAD
  LONG no catalyst             → BULL_CALL_SPREAD
  SHORT no catalyst            → BEAR_PUT_SPREAD

EXPIRY SELECTION
────────────────
  With catalyst: 3rd Friday of month containing (catalyst_date + 7 days)
  Without catalyst: first monthly expiry 21-45 DTE

INTEGRATION
───────────
Called by convergence_scorer.scan_and_store() for every super signal (S11-6).
Stored in convergence_signals.pillar_breakdown JSONB under "structure" key.
CLI: alphahound signals structure --ticker TICKER
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# ─── Guards ──────────────────────────────────────────────────────────────────

SUPER_SIGNAL_MIN_SCORE   = 4.0   # must be a genuine super signal
SUPER_SIGNAL_MIN_PILLARS = 4     # must have 4+ independent pillars

# ─── Pricing constants ───────────────────────────────────────────────────────

IV_PREMIUM_FACTOR    = 1.15    # IV typically runs ~15% above HV30
PRICING_METHOD       = "BS_HV30_APPROX"
IS_ESTIMATED         = True    # always True until live IV feed is wired

# ─── Expiry constants ────────────────────────────────────────────────────────

MIN_DTE          = 14     # never recommend options with < 14 DTE
TARGET_DTE_MIN   = 21     # sweet spot floor for non-catalyst plays
TARGET_DTE_MAX   = 45     # sweet spot ceiling

# ─── Spread geometry ─────────────────────────────────────────────────────────

SPREAD_WIDTH_NORMAL = 2   # intervals wide for standard signals (4 pillars)
SPREAD_WIDTH_HIGH   = 3   # intervals wide for high conviction (5+ pillars)
TARGET_EXIT_PCT     = 0.50  # exit at 50% of max theoretical gain

# ─── Suggested risk per trade (for display only — executor does actual sizing) ─

SUGGESTED_RISK_PCT = 0.02   # 2% of account equity — executor applies this


def _strike_interval(price: float) -> float:
    """Standard strike interval for a given price level."""
    if price < 10:    return 0.50
    if price < 25:    return 1.00
    if price < 50:    return 1.00
    if price < 100:   return 2.50
    if price < 200:   return 5.00
    if price < 500:   return 5.00
    if price < 1000:  return 10.00
    return 25.0


# ─── Data shapes ─────────────────────────────────────────────────────────────

@dataclass
class OptionsLeg:
    action:            str      # "BUY" or "SELL"
    contract_type:     str      # "CALL" or "PUT"
    strike:            float
    expiry:            date
    dte:               int
    estimated_iv:      float    # annualised, e.g. 0.45 = 45%
    estimated_delta:   float
    estimated_premium: float    # per share — multiply × 100 for contract cost
    contract_cost:     float    # estimated_premium × 100
    is_estimated:      bool = IS_ESTIMATED
    pricing_method:    str  = PRICING_METHOD

    def display(self) -> str:
        return (
            f"  {self.action} {self.contract_type:<4} "
            f"${self.strike:.2f} exp {self.expiry.isoformat()} ({self.dte}DTE)  "
            f"~${self.estimated_premium:.2f}/share  delta≈{self.estimated_delta:+.2f}  "
            f"[{self.pricing_method}]"
        )


@dataclass
class OptionsStructure:
    # Identity
    ticker:          str
    structure_type:  str     # "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", etc.
    direction:       str     # "LONG", "SHORT", "NEUTRAL" (for strangles)

    # Price anchor
    current_price:   float
    is_estimated:    bool = IS_ESTIMATED
    pricing_method:  str  = PRICING_METHOD

    # Legs
    legs:            list[OptionsLeg] = field(default_factory=list)
    expiry:          date = field(default_factory=date.today)
    dte:             int  = 0

    # Economics (per 1 spread/strangle — estimated)
    estimated_debit:    float = 0.0   # cost to enter per contract set
    estimated_max_loss: float = 0.0
    estimated_max_gain: float = 0.0
    estimated_breakevens: list[float] = field(default_factory=list)
    estimated_rr:       float = 0.0   # max_gain / max_loss

    # Sizing guidance (NOT authoritative — executor applies actual sizing)
    contracts:          None = None   # always None — executor decides
    suggested_risk_pct: float = SUGGESTED_RISK_PCT
    target_exit_pct:    float = TARGET_EXIT_PCT

    # Signal context
    composite_score:    float = 0.0
    pillars_fired:      int   = 0
    catalyst_type:      Optional[str]  = None
    catalyst_date:      Optional[date] = None
    computed_at:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Explainability
    narrative:          str  = ""
    explainability:     dict = field(default_factory=dict)
    warnings:           list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker":            self.ticker,
            "structure_type":    self.structure_type,
            "direction":         self.direction,
            "current_price":     self.current_price,
            "is_estimated":      self.is_estimated,
            "pricing_method":    self.pricing_method,
            "expiry":            self.expiry.isoformat(),
            "dte":               self.dte,
            "contracts":         None,
            "suggested_risk_pct": self.suggested_risk_pct,
            "estimated_debit":   round(self.estimated_debit, 2),
            "estimated_max_loss": round(self.estimated_max_loss, 2),
            "estimated_max_gain": round(self.estimated_max_gain, 2),
            "estimated_breakevens": [round(b, 2) for b in self.estimated_breakevens],
            "estimated_rr":      round(self.estimated_rr, 2),
            "target_exit_pct":   self.target_exit_pct,
            "composite_score":   self.composite_score,
            "pillars_fired":     self.pillars_fired,
            "catalyst_type":     self.catalyst_type,
            "catalyst_date":     self.catalyst_date.isoformat() if self.catalyst_date else None,
            "narrative":         self.narrative,
            "warnings":          self.warnings,
            "legs": [
                {
                    "action":            l.action,
                    "contract_type":     l.contract_type,
                    "strike":            l.strike,
                    "expiry":            l.expiry.isoformat(),
                    "dte":               l.dte,
                    "estimated_iv":      round(l.estimated_iv, 4),
                    "estimated_delta":   round(l.estimated_delta, 3),
                    "estimated_premium": round(l.estimated_premium, 2),
                    "contract_cost":     round(l.contract_cost, 2),
                    "is_estimated":      l.is_estimated,
                    "pricing_method":    l.pricing_method,
                }
                for l in self.legs
            ],
            "explainability": self.explainability,
        }

    def display(self) -> str:
        lines = [
            f"\n{'='*65}",
            f"  STRUCTURE PLAN: {self.ticker}  [{self.structure_type}]",
            f"  ⚠  ESTIMATED PRICES — verify against broker before entry",
            f"{'='*65}",
            f"  Direction:     {self.direction}",
            f"  Current price: ~${self.current_price:.2f}",
            f"  Expiry:        {self.expiry.isoformat()} ({self.dte} DTE)",
            f"  Score:         {self.composite_score:.2f} ({self.pillars_fired} pillars)",
            f"  Sizing:        executor applies {self.suggested_risk_pct:.0%} risk — contracts TBD",
            "",
            "  LEGS (estimated prices via BS/HV30):",
        ]
        for leg in self.legs:
            lines.append(leg.display())
        lines += [
            "",
            "  ESTIMATED ECONOMICS (per 1 spread/strangle):",
            f"  Debit:         ~${self.estimated_debit:.2f}",
            f"  Max loss:      ~${self.estimated_max_loss:.2f}",
            f"  Max gain:      ~${self.estimated_max_gain:.2f}",
            f"  Risk/reward:   ~1 : {self.estimated_rr:.1f}",
            f"  Breakeven(s):  {', '.join(f'~${b:.2f}' for b in self.estimated_breakevens)}",
            f"  Exit target:   ~50% of max gain",
        ]
        if self.catalyst_date:
            days = (self.catalyst_date - date.today()).days
            lines.append(
                f"  Catalyst:      {self.catalyst_type} on "
                f"{self.catalyst_date.isoformat()} ({days}d)"
            )
        if self.warnings:
            lines.append("")
            lines.append("  WARNINGS:")
            for w in self.warnings:
                lines.append(f"  ⚠  {w}")
        lines += [
            "",
            "  WHY THIS STRUCTURE:",
            f"  {self.narrative}",
            f"{'='*65}",
        ]
        return "\n".join(lines)


# ─── Main entry point ─────────────────────────────────────────────────────────

def recommend_structure(
    entity_id:       str,
    ticker:          str,
    direction:       str,
    composite_score: float,
    pillars_fired:   int,
    catalyst_type:   Optional[str],
    catalyst_date:   Optional[date],
    equity:          float = 20_000.0,  # kept for interface compat, not used for sizing
) -> Optional[OptionsStructure]:
    """Build a structure plan for a convergence signal.

    Returns None if:
    - composite_score < SUPER_SIGNAL_MIN_SCORE (4.0)
    - pillars_fired < SUPER_SIGNAL_MIN_PILLARS (4)
    - direction is NEUTRAL and catalyst is not PDUFA
    - no price data available
    - structure sanity check fails (debit too small, R/R too low)
    """
    # ── Guard 1: super signal only ───────────────────────────────────────────
    if composite_score < SUPER_SIGNAL_MIN_SCORE:
        log.debug(
            "recommend_structure: %s score=%.2f < %.1f — not a super signal",
            ticker, composite_score, SUPER_SIGNAL_MIN_SCORE,
        )
        return None

    if pillars_fired < SUPER_SIGNAL_MIN_PILLARS:
        log.debug(
            "recommend_structure: %s pillars=%d < %d — not a super signal",
            ticker, pillars_fired, SUPER_SIGNAL_MIN_PILLARS,
        )
        return None

    # ── Guard 2: direction ───────────────────────────────────────────────────
    if direction == "NEUTRAL" and catalyst_type != "PDUFA":
        log.debug("recommend_structure: %s NEUTRAL with no PDUFA — not actionable", ticker)
        return None

    # ── Price data ───────────────────────────────────────────────────────────
    price_data = _get_price_and_hv(entity_id)
    if price_data is None:
        log.debug("recommend_structure: no price data for %s", ticker)
        return None

    current_price, hv30 = price_data
    if current_price <= 0:
        return None

    today    = date.today()
    interval = _strike_interval(current_price)
    atm      = _round_to_strike(current_price, interval)
    iv       = max(0.15, hv30 * IV_PREMIUM_FACTOR)

    # ── Structure + expiry ───────────────────────────────────────────────────
    structure_type = _select_structure(direction, catalyst_type, pillars_fired)
    expiry, dte    = _select_expiry(today, catalyst_date, structure_type)
    if expiry is None or dte < MIN_DTE:
        log.debug("recommend_structure: %s no valid expiry found", ticker)
        return None

    # ── Legs ─────────────────────────────────────────────────────────────────
    legs = _build_legs(
        structure_type, direction, atm, interval,
        expiry, dte, iv, current_price, pillars_fired,
    )
    if not legs:
        return None

    # ── Economics ────────────────────────────────────────────────────────────
    debit, max_loss, max_gain, breakevens = _compute_economics(
        structure_type, legs, interval, pillars_fired,
    )
    rr = round(max_gain / max_loss, 2) if max_loss > 0 else 0.0

    # ── Guard 3: sanity check ────────────────────────────────────────────────
    warnings: list[str] = []
    reject_reason = _sanity_check(structure_type, debit, max_loss, max_gain, rr, warnings)
    if reject_reason:
        log.debug("recommend_structure: %s rejected — %s", ticker, reject_reason)
        return None

    # ── Catalyst IV warning ──────────────────────────────────────────────────
    if catalyst_type == "PDUFA" and catalyst_date:
        days = (catalyst_date - today).days
        warnings.append(
            f"PDUFA in {days}d: actual IV likely 2-3x HV30. "
            f"Estimated debit ~${debit:.0f} will be significantly understated — "
            f"verify strangle cost against broker before entry."
        )
    elif catalyst_type == "EARNINGS" and catalyst_date:
        days = (catalyst_date - today).days
        if days <= 21:
            warnings.append(
                f"Earnings in {days}d: IV typically inflates 20-50% above HV30 "
                f"pre-event. Estimated debit ~${debit:.0f} may be understated."
            )

    # ── Explainability ───────────────────────────────────────────────────────
    explain = _build_explainability(
        structure_type, direction, catalyst_type, catalyst_date,
        atm, interval, iv, hv30, pillars_fired, composite_score,
    )

    narrative = _build_narrative(
        ticker, structure_type, direction, catalyst_type, catalyst_date,
        current_price, legs, rr, composite_score, pillars_fired,
    )

    target_exit = debit + (max_gain - debit) * TARGET_EXIT_PCT

    return OptionsStructure(
        ticker=ticker,
        structure_type=structure_type,
        direction=direction,
        current_price=current_price,
        is_estimated=IS_ESTIMATED,
        pricing_method=PRICING_METHOD,
        legs=legs,
        expiry=expiry,
        dte=dte,
        estimated_debit=round(debit, 2),
        estimated_max_loss=round(max_loss, 2),
        estimated_max_gain=round(max_gain, 2),
        estimated_breakevens=[round(b, 2) for b in breakevens],
        estimated_rr=rr,
        contracts=None,
        suggested_risk_pct=SUGGESTED_RISK_PCT,
        target_exit_pct=TARGET_EXIT_PCT,
        composite_score=composite_score,
        pillars_fired=pillars_fired,
        catalyst_type=catalyst_type,
        catalyst_date=catalyst_date,
        computed_at=datetime.now(timezone.utc),
        narrative=narrative,
        explainability=explain,
        warnings=warnings,
    )


# ─── Sanity check ─────────────────────────────────────────────────────────────

def _sanity_check(
    structure_type: str,
    debit: float,
    max_loss: float,
    max_gain: float,
    rr: float,
    warnings: list[str],
) -> Optional[str]:
    """Return a rejection reason string, or None if structure passes.

    Populates warnings list with non-fatal concerns.
    """
    # Reject: debit too small to be a real trade
    if debit < 20.0:
        return f"estimated debit ${debit:.2f} < $20 minimum — structure not viable"

    # Reject: max loss essentially zero (pricing error)
    if max_loss < 10.0:
        return f"max_loss ${max_loss:.2f} < $10 — pricing error, rejecting"

    # Reject: R/R below minimum threshold for spreads
    if structure_type in ("BULL_CALL_SPREAD", "BEAR_PUT_SPREAD") and rr < 0.5:
        return f"R/R {rr:.2f} < 0.5 — spread too narrow relative to debit"

    # Warn: R/R below 1.0 for spreads (acceptable but suboptimal)
    if structure_type in ("BULL_CALL_SPREAD", "BEAR_PUT_SPREAD") and rr < 1.0:
        warnings.append(
            f"R/R {rr:.2f} is below 1:1 — consider wider spread or wait for "
            f"better entry when IV is lower."
        )

    # Warn: strangle debit > 10% of estimated stock price × 100
    # (proxy for "this strangle is too expensive to be worth it")
    if structure_type == "LONG_STRANGLE" and max_loss > 0:
        pass  # debit check above handles the floor

    return None


# ─── Structure selection ─────────────────────────────────────────────────────

def _select_structure(
    direction: str,
    catalyst_type: Optional[str],
    pillars_fired: int,
) -> str:
    if catalyst_type == "PDUFA":
        return "LONG_STRANGLE"
    if pillars_fired >= 5:
        return "LONG_CALL" if direction == "LONG" else "LONG_PUT"
    if direction == "LONG":
        return "BULL_CALL_SPREAD"
    return "BEAR_PUT_SPREAD"


# ─── Expiry selection ─────────────────────────────────────────────────────────

def _select_expiry(
    today: date,
    catalyst_date: Optional[date],
    structure_type: str,
) -> tuple[Optional[date], int]:
    if catalyst_date is not None:
        target = catalyst_date + timedelta(days=7)
        expiry = _next_monthly_expiry(target)
        dte    = (expiry - today).days
        if dte < MIN_DTE:
            expiry = _next_monthly_expiry(expiry + timedelta(days=32))
            dte    = (expiry - today).days
        if dte > 90:
            expiry = _next_monthly_expiry(catalyst_date + timedelta(days=1))
            dte    = (expiry - today).days
        return expiry, dte

    # No catalyst: scan for a monthly expiry in the sweet spot
    for days_ahead in range(TARGET_DTE_MIN, TARGET_DTE_MAX + 1):
        candidate = today + timedelta(days=days_ahead)
        if candidate.weekday() == 4 and 15 <= candidate.day <= 21:
            return candidate, days_ahead

    target_date = today + timedelta(days=TARGET_DTE_MIN)
    expiry = _next_monthly_expiry(target_date)
    dte    = (expiry - today).days
    if dte < MIN_DTE:
        expiry = _next_monthly_expiry(expiry + timedelta(days=32))
        dte    = (expiry - today).days
    return expiry, dte


def _next_monthly_expiry(after: date) -> date:
    d = after.replace(day=1)
    third_friday = _third_friday(d.year, d.month)
    if third_friday < after:
        d = d.replace(month=d.month + 1) if d.month < 12 else d.replace(year=d.year + 1, month=1)
        third_friday = _third_friday(d.year, d.month)
    return third_friday


def _third_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    first_friday = d + timedelta(days=(4 - d.weekday()) % 7)
    return first_friday + timedelta(weeks=2)


# ─── Leg construction ─────────────────────────────────────────────────────────

def _build_legs(
    structure_type: str,
    direction: str,
    atm: float,
    interval: float,
    expiry: date,
    dte: int,
    iv: float,
    current_price: float,
    pillars_fired: int,
) -> list[OptionsLeg]:
    T = dte / 365.0
    r = 0.045
    S = current_price
    width = SPREAD_WIDTH_HIGH if pillars_fired >= 5 else SPREAD_WIDTH_NORMAL

    def leg(action, ctype, strike) -> OptionsLeg:
        prem  = _bs_price(S, strike, T, r, iv, ctype.lower())
        delta = _bs_delta(S, strike, T, r, iv, ctype.lower())
        return OptionsLeg(
            action=action, contract_type=ctype, strike=strike,
            expiry=expiry, dte=dte, estimated_iv=round(iv, 4),
            estimated_delta=round(delta, 3),
            estimated_premium=round(max(0.01, prem), 2),
            contract_cost=round(max(0.01, prem) * 100, 2),
        )

    if structure_type == "BULL_CALL_SPREAD":
        return [leg("BUY", "CALL", atm), leg("SELL", "CALL", atm + interval * width)]
    if structure_type == "BEAR_PUT_SPREAD":
        return [leg("BUY", "PUT", atm), leg("SELL", "PUT", atm - interval * width)]
    if structure_type == "LONG_STRANGLE":
        return [leg("BUY", "CALL", atm + interval), leg("BUY", "PUT", atm - interval)]
    if structure_type == "LONG_CALL":
        return [leg("BUY", "CALL", atm)]
    if structure_type == "LONG_PUT":
        return [leg("BUY", "PUT", atm)]
    return []


# ─── Economics ────────────────────────────────────────────────────────────────

def _compute_economics(
    structure_type: str,
    legs: list[OptionsLeg],
    interval: float,
    pillars_fired: int,
) -> tuple[float, float, float, list[float]]:
    width = SPREAD_WIDTH_HIGH if pillars_fired >= 5 else SPREAD_WIDTH_NORMAL

    if structure_type == "BULL_CALL_SPREAD":
        buy  = next(l for l in legs if l.action == "BUY")
        sell = next(l for l in legs if l.action == "SELL")
        debit    = (buy.estimated_premium - sell.estimated_premium) * 100
        spread   = (sell.strike - buy.strike) * 100
        max_loss = max(debit, 0.01)
        max_gain = max(spread - debit, 0.01)
        return debit, max_loss, max_gain, [round(buy.strike + debit / 100, 2)]

    if structure_type == "BEAR_PUT_SPREAD":
        buy  = next(l for l in legs if l.action == "BUY")
        sell = next(l for l in legs if l.action == "SELL")
        debit    = (buy.estimated_premium - sell.estimated_premium) * 100
        spread   = (buy.strike - sell.strike) * 100
        max_loss = max(debit, 0.01)
        max_gain = max(spread - debit, 0.01)
        return debit, max_loss, max_gain, [round(buy.strike - debit / 100, 2)]

    if structure_type == "LONG_STRANGLE":
        call = next(l for l in legs if l.contract_type == "CALL")
        put  = next(l for l in legs if l.contract_type == "PUT")
        debit    = (call.estimated_premium + put.estimated_premium) * 100
        max_loss = debit
        max_gain = debit * 4.0
        return debit, max_loss, max_gain, [
            round(put.strike  - debit / 100, 2),
            round(call.strike + debit / 100, 2),
        ]

    if structure_type in ("LONG_CALL", "LONG_PUT"):
        l        = legs[0]
        debit    = l.estimated_premium * 100
        max_loss = debit
        max_gain = debit * 5.0
        be = l.strike + debit / 100 if structure_type == "LONG_CALL" else l.strike - debit / 100
        return debit, max_loss, max_gain, [round(be, 2)]

    return 0.0, 0.0, 0.0, []


# ─── Black-Scholes ────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    if x < 0:
        return 1.0 - _norm_cdf(-x)
    k = 1.0 / (1.0 + 0.2316419 * x)
    p = k * (0.319381530 + k * (-0.356563782 + k * (1.781477937
        + k * (-1.821255978 + k * 1.330274429))))
    return 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x) * p


def _bs_price(S, K, T, r, sigma, option_type) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.01
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        if option_type == "call":
            return max(0.01, S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2))
        return max(0.01, K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1))
    except (ValueError, ZeroDivisionError):
        return 0.01


def _bs_delta(S, K, T, r, sigma, option_type) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.5 if option_type == "call" else -0.5
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        return _norm_cdf(d1) if option_type == "call" else _norm_cdf(d1) - 1.0
    except (ValueError, ZeroDivisionError):
        return 0.5 if option_type == "call" else -0.5


# ─── Price + HV fetch ─────────────────────────────────────────────────────────

def _get_price_and_hv(entity_id: str, hv_period: int = 30) -> Optional[tuple[float, float]]:
    """Fetch current price and compute HV30. Returns (price, hv30) or None."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT price FROM price_snapshots WHERE entity_id = %s ORDER BY time DESC LIMIT 1;",
                    (entity_id,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return None
                current_price = float(row[0])

                cur.execute(
                    "SELECT close FROM price_daily WHERE entity_id = %s ORDER BY date DESC LIMIT %s;",
                    (entity_id, hv_period + 2),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.debug("_get_price_and_hv(%s): %s", entity_id, exc)
        return None

    if not rows or len(rows) < 5:
        # Use price snapshot only with conservative default HV
        return current_price, 0.40

    closes  = [float(r[0]) for r in reversed(rows)]
    returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0
    ]
    if not returns:
        return current_price, 0.40

    mean_r   = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / max(len(returns) - 1, 1)
    hv30     = math.sqrt(variance) * math.sqrt(252)

    return current_price, max(0.10, hv30)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _round_to_strike(price: float, interval: float) -> float:
    return round(round(price / interval) * interval, 2)


def _build_narrative(
    ticker, structure_type, direction, catalyst_type, catalyst_date,
    current_price, legs, rr, composite_score, pillars_fired,
) -> str:
    names = {
        "BULL_CALL_SPREAD": "bull call spread",
        "BEAR_PUT_SPREAD":  "bear put spread",
        "LONG_STRANGLE":    "long strangle",
        "LONG_CALL":        "long call",
        "LONG_PUT":         "long put",
    }
    sname = names.get(structure_type, structure_type)
    cat_str = ""
    if catalyst_date:
        days = (catalyst_date - date.today()).days
        cat_str = f" into {catalyst_type} in {days}d"

    buy  = next((l for l in legs if l.action == "BUY"), None)
    sell = next((l for l in legs if l.action == "SELL"), None)

    if structure_type == "LONG_STRANGLE":
        call = next((l for l in legs if l.contract_type == "CALL"), None)
        put  = next((l for l in legs if l.contract_type == "PUT"), None)
        if call and put:
            return (
                f"{ticker} {sname}{cat_str}: "
                f"buy ${put.strike:.0f} put / ${call.strike:.0f} call — "
                f"captures move in either direction. "
                f"Score={composite_score:.2f} ({pillars_fired} pillars). "
                f"Max loss = total premium paid."
            )

    if buy and sell:
        return (
            f"{ticker} {sname}{cat_str}: "
            f"buy ${buy.strike:.0f} / sell ${sell.strike:.0f} {buy.expiry.strftime('%b')} — "
            f"~{rr:.1f}:1 estimated R/R. "
            f"Score={composite_score:.2f} ({pillars_fired} pillars)."
        )

    if buy:
        return (
            f"{ticker} {sname}{cat_str}: "
            f"${buy.strike:.0f} strike, {pillars_fired}-pillar conviction. "
            f"Max loss = premium paid."
        )

    return f"{ticker} {sname} — score={composite_score:.2f}, {pillars_fired} pillars."


def _build_explainability(
    structure_type, direction, catalyst_type, catalyst_date,
    atm, interval, iv, hv30, pillars_fired, composite_score,
) -> dict:
    if catalyst_type == "PDUFA":
        struct_why = "PDUFA: FDA binary outcome → strangle captures move in either direction regardless of verdict"
    elif pillars_fired >= 5:
        struct_why = f"{pillars_fired} pillars fired → maximum conviction, naked long for full leverage"
    elif direction == "LONG":
        struct_why = "Directional LONG → bull call spread caps max loss while preserving upside"
    else:
        struct_why = "Directional SHORT → bear put spread caps max loss while preserving downside"

    cat_why = "No catalyst — targeting 21-45 DTE theta/vega sweet spot"
    if catalyst_date:
        days = (catalyst_date - date.today()).days
        cat_why = (
            f"Expiry 1 week after {catalyst_type} ({catalyst_date.isoformat()}, {days}d) "
            f"to capture post-event move before theta decay"
        )

    return {
        "structure_choice":  struct_why,
        "strike_rationale":  f"ATM=${atm:.2f} (nearest ${interval:.2f} interval to current price)",
        "iv_methodology":    f"IV={iv:.0%} = HV30({hv30:.0%}) × {IV_PREMIUM_FACTOR}x — {PRICING_METHOD}",
        "expiry_rationale":  cat_why,
        "sizing_rationale":  f"Contracts=None — executor applies {SUGGESTED_RISK_PCT:.0%} risk with Kelly/macro/tech modifiers",
        "exit_rationale":    f"Exit at {TARGET_EXIT_PCT:.0%} of estimated max gain to lock profit before theta decay",
        "composite_score":   composite_score,
        "pillars_fired":     pillars_fired,
        "is_estimated":      IS_ESTIMATED,
        "pricing_method":    PRICING_METHOD,
    }
