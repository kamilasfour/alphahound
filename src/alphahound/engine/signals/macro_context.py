"""Macro context filter — Sprint 9.6.

Reads global market signals and produces a RISK_ON / RISK_OFF / NEUTRAL verdict
that gates execution decisions.

Checks (weighted):
    1. VIX proxy (UVXY)     — high volatility = risk-off
    2. Treasury (TLT)       — rising bonds = risk-off (flight to safety)
    3. Dollar (UUP)         — rising dollar = risk-off for equities
    4. High yield (HYG)     — falling HYG = credit stress = risk-off
    5. Asia (EWJ + FXI)     — Asian markets down = US likely to follow
    6. Europe (EWG)         — European markets down = global risk-off
    7. Emerging markets     — EEM falling = broad risk-off

Verdict:
    RISK_ON   — macro supports LONG execution (score > +0.15)
    NEUTRAL   — no strong macro signal (score between -0.15 and +0.15)
    RISK_OFF  — macro suggests caution (score < -0.15)

Size modifiers:
    RISK_ON   -> 1.0x (full size)
    NEUTRAL   -> 0.75x (reduced size)
    RISK_OFF  -> 0.0x for LONGs (blocked), 1.0x for SHORTs (confirmed)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# Macro instruments and their role
# direction_weight > 0 means RISING = RISK_ON
# direction_weight < 0 means RISING = RISK_OFF
MACRO_INSTRUMENTS = {
    "UVXY": ("volatility",   -2.0),  # rising VIX = risk-off (heavy weight)
    "TLT":  ("bonds",        -1.0),  # rising bonds = flight to safety = risk-off
    "UUP":  ("dollar",       -1.0),  # rising dollar = risk-off for equities
    "HYG":  ("credit",       +1.5),  # rising HYG = healthy credit = risk-on
    "EWJ":  ("asia_japan",   +1.0),  # Japan up = Asia constructive
    "FXI":  ("china",        +0.8),  # China up = EM risk-on
    "EWG":  ("europe",       +1.0),  # Germany up = Europe constructive
    "EEM":  ("emerging",     +1.0),  # EM up = global risk appetite
    "SPY":  ("us_market",    +1.5),  # US market itself (heavy weight)
    "QQQ":  ("us_tech",      +1.0),  # Tech specifically
}

RISK_ON_THRESHOLD  =  0.20   # raised from 0.15 — need clearer green light
RISK_OFF_THRESHOLD = -0.10   # lowered from -0.15 — trip faster on bad macro
NEUTRAL_BLOCKS_NEW = True    # NEUTRAL also blocks new LONGs (only RISK_ON allows them)


class MacroVerdict(str, Enum):
    RISK_ON  = "RISK_ON"
    NEUTRAL  = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    NO_DATA  = "NO_DATA"


@dataclass
class MacroContext:
    verdict:       MacroVerdict
    score:         float
    signals:       dict
    contributors:  dict
    size_modifier: float
    reason:        str

    def display(self) -> str:
        lines = [
            f"  Macro Context: {self.verdict.value}  (score={self.score:+.3f})",
            f"  Size modifier: {self.size_modifier:.0%}",
            "  Signals:",
        ]
        for ticker, chg in sorted(self.signals.items(), key=lambda x: abs(x[1]), reverse=True):
            contrib = self.contributors.get(ticker, 0)
            arrow = "UP" if chg > 0 else "DN"
            lines.append(f"    {arrow} {ticker:<5}  {chg:+.2f}%  (contrib {contrib:+.3f})")
        lines.append(f"  Reason: {self.reason}")
        return "\n".join(lines)


def get_macro_context() -> MacroContext:
    """Compute current macro context from price_snapshots."""
    changes = _get_1d_changes(list(MACRO_INSTRUMENTS.keys()))

    if len(changes) < 3:
        log.info("MacroContext: insufficient data (%d instruments)", len(changes))
        return MacroContext(
            verdict=MacroVerdict.NO_DATA,
            score=0.0,
            signals={},
            contributors={},
            size_modifier=1.0,
            reason=f"Only {len(changes)} macro instruments available — passing through",
        )

    total_weight = 0.0
    weighted_sum = 0.0
    contributors = {}

    for ticker, (role, weight) in MACRO_INSTRUMENTS.items():
        if ticker not in changes:
            continue
        chg = changes[ticker]
        normalized = max(-1.0, min(1.0, chg / 2.0))
        contribution = normalized * weight
        contributors[ticker] = round(contribution, 4)
        weighted_sum += contribution
        total_weight += abs(weight)

    score = weighted_sum / total_weight if total_weight > 0 else 0.0

    if score >= RISK_ON_THRESHOLD:
        verdict       = MacroVerdict.RISK_ON
        size_modifier = 1.0
        reason        = f"Global macro supportive (score={score:+.3f}) — full size execution"
    elif score <= RISK_OFF_THRESHOLD:
        verdict       = MacroVerdict.RISK_OFF
        size_modifier = 0.0
        reason        = _build_risk_off_reason(changes, score)
    else:
        verdict       = MacroVerdict.NEUTRAL
        size_modifier = 0.0  # NEUTRAL now BLOCKS new entries — was 0.75
        reason        = f"Macro NEUTRAL (score={score:+.3f}) — no new LONG entries until RISK_ON confirmed"

    # Additional check: SPY 5-day trend override
    # If SPY is down >2% over 5 days, force RISK_OFF regardless of score
    spy_5d = _get_5d_change('SPY')
    if spy_5d is not None and spy_5d < -2.0 and verdict != MacroVerdict.RISK_OFF:
        verdict       = MacroVerdict.RISK_OFF
        size_modifier = 0.0
        reason        = f"SPY 5-day trend: {spy_5d:+.1f}% — sustained downtrend forces RISK_OFF. LONGs blocked."

    log.info("MacroContext: %s  score=%+.3f  instruments=%d", verdict.value, score, len(changes))

    return MacroContext(
        verdict=verdict,
        score=round(score, 4),
        signals={k: round(v, 4) for k, v in changes.items()},
        contributors=contributors,
        size_modifier=size_modifier,
        reason=reason,
    )


def _build_risk_off_reason(changes: dict, score: float) -> str:
    culprits = []
    if changes.get("UVXY", 0) > 2:
        culprits.append(f"VIX spiking (+{changes['UVXY']:.1f}%)")
    if changes.get("TLT", 0) > 1:
        culprits.append(f"bonds rallying (+{changes['TLT']:.1f}%, flight to safety)")
    if changes.get("HYG", 0) < -1:
        culprits.append(f"credit stress (HYG {changes['HYG']:.1f}%)")
    if changes.get("EWJ", 0) < -1 or changes.get("FXI", 0) < -1:
        culprits.append("Asian markets down")
    if changes.get("EWG", 0) < -1:
        culprits.append("European markets down")
    if changes.get("SPY", 0) < -1:
        culprits.append(f"US market down ({changes['SPY']:.1f}%)")
    reason_parts = ", ".join(culprits) if culprits else "broad risk-off conditions"
    return f"RISK_OFF (score={score:+.3f}): {reason_parts} — LONGs blocked"


def _get_5d_change(ticker: str) -> float | None:
    """Get 5-day price change % for a ticker from price_snapshots."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT change_5d_pct FROM price_snapshots ps
                    JOIN entities e ON e.entity_id = ps.entity_id
                    WHERE e.canonical_symbol = %s AND e.module_id = 'stocks'
                    ORDER BY ps.time DESC LIMIT 1;
                """, (ticker,))
                row = cur.fetchone()
                return float(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def _get_1d_changes(tickers: list) -> dict:
    """Fetch 1-day change % for each ticker from price_daily (last 2 bars)."""
    if not tickers:
        return {}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sym, close_today, close_prev,
                           CASE WHEN close_prev > 0
                                THEN (close_today - close_prev) / close_prev * 100
                                ELSE NULL END AS chg_pct
                    FROM (
                        SELECT
                            e.canonical_symbol AS sym,
                            FIRST_VALUE(pd.close) OVER (PARTITION BY pd.entity_id ORDER BY pd.date DESC) AS close_today,
                            NTH_VALUE(pd.close, 2)  OVER (PARTITION BY pd.entity_id ORDER BY pd.date DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close_prev,
                            ROW_NUMBER() OVER (PARTITION BY pd.entity_id ORDER BY pd.date DESC) AS rn
                        FROM price_daily pd
                        JOIN entities e ON e.entity_id = pd.entity_id
                        WHERE e.canonical_symbol = ANY(%s)
                          AND e.module_id = 'stocks'
                    ) sub
                    WHERE rn = 1
                      AND close_prev IS NOT NULL;
                    """,
                    (tickers,),
                )
                rows = cur.fetchall()
        return {sym: round(float(chg), 4) for sym, _, _, chg in rows if chg is not None}
    except Exception as exc:
        log.warning("_get_1d_changes failed: %s", exc)
        return {}


_cache: MacroContext | None = None
_cache_time: datetime | None = None
CACHE_TTL = timedelta(minutes=15)


def get_macro_context_cached() -> MacroContext:
    """Return cached macro context, refreshing if stale."""
    global _cache, _cache_time
    now = datetime.now(timezone.utc)
    if _cache is None or _cache_time is None or (now - _cache_time) > CACHE_TTL:
        _cache = get_macro_context()
        _cache_time = now
    return _cache
