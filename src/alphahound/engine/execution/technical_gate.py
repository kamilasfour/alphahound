"""Technical confirmation gate — Sprint 9.5.

Validates a sentiment signal against chart technicals before execution.
Called by executor.py as a pre-execution filter.

Checks (each pass/fail):
    1. MACD       — line vs signal line direction matches trade direction
    2. RSI        — not overbought (LONG) or oversold (SHORT)
    3. Volume     — current day volume above 20-day average
    4. EMA trend  — price above/below 20-day EMA matches direction
    5. Momentum   — 5-day return sign matches direction

Scoring:
    5/5 or 4/5 → CONFIRM  (execute full size)
    3/5        → WEAK     (execute at 50% size)
    2/5 or less → REJECT  (skip trade)

MACD parameters: fast=12, slow=26, signal=9 (standard)
RSI period: 14
EMA period: 20
Volume period: 20
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# Indicator parameters
MACD_FAST    = 12
MACD_SLOW    = 26
MACD_SIGNAL  = 9
RSI_PERIOD   = 14
EMA_PERIOD   = 20
VOL_PERIOD   = 20

# RSI thresholds
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# Scoring thresholds
CONFIRM_THRESHOLD = 4   # 4+ checks pass → CONFIRM
WEAK_THRESHOLD    = 3   # 3 checks pass → WEAK (50% size)
                        # <3 → REJECT


class TechVerdict(str, Enum):
    CONFIRM = "CONFIRM"   # chart agrees — execute full size
    WEAK    = "WEAK"      # chart neutral — execute 50% size
    REJECT  = "REJECT"    # chart disagrees — skip trade
    NO_DATA = "NO_DATA"   # insufficient history — execute full size (don't block)


@dataclass
class TechCheckResult:
    verdict:       TechVerdict
    score:         int                        # checks passed out of 5
    checks:        dict[str, bool | None]     # individual check results
    indicators:    dict[str, float | None]    # computed indicator values
    size_modifier: float                      # 1.0 = full, 0.5 = half, 0.0 = skip
    reason:        str                        # human-readable summary

    def display(self) -> str:
        lines = [
            f"  Technical Gate: {self.verdict.value}  ({self.score}/5 checks passed)",
            f"  Size modifier:  {self.size_modifier:.0%}",
        ]
        ind = self.indicators
        lines.append(f"  Indicators:")
        if ind.get("macd_line") is not None:
            lines.append(f"    MACD line={ind['macd_line']:+.4f}  signal={ind['macd_signal']:+.4f}  hist={ind['macd_hist']:+.4f}")
        if ind.get("rsi") is not None:
            lines.append(f"    RSI={ind['rsi']:.1f}")
        if ind.get("ema20") is not None:
            lines.append(f"    EMA20={ind['ema20']:.2f}  price={ind['price']:.2f}")
        if ind.get("volume_ratio") is not None:
            lines.append(f"    Volume ratio={ind['volume_ratio']:.2f}x avg")
        if ind.get("momentum_5d") is not None:
            lines.append(f"    5d momentum={ind['momentum_5d']:+.2f}%")
        lines.append(f"  Checks: " + "  ".join(
            f"{'✅' if v else '❌' if v is False else '—'} {k}"
            for k, v in self.checks.items()
        ))
        lines.append(f"  Reason: {self.reason}")
        return "\n".join(lines)


def check(entity_id: str, ticker: str, direction: str) -> TechCheckResult:
    """Run technical gate for a ticker.

    Args:
        entity_id: UUID of the entity
        ticker:    Stock symbol e.g. 'AAPL'
        direction: 'LONG' or 'SHORT'

    Returns:
        TechCheckResult with verdict, score, and indicator values.
    """
    is_long = direction.upper() == "LONG"

    # Need at least MACD_SLOW + MACD_SIGNAL + buffer = 40 bars
    bars = _get_daily_bars(entity_id, limit=60)

    if len(bars) < MACD_SLOW + MACD_SIGNAL:
        log.info("TechGate %s: only %d bars — NO_DATA, passing through", ticker, len(bars))
        return TechCheckResult(
            verdict=TechVerdict.NO_DATA,
            score=0,
            checks={},
            indicators={},
            size_modifier=1.0,
            reason=f"Only {len(bars)} daily bars available (need {MACD_SLOW + MACD_SIGNAL}). Passing through.",
        )

    closes  = [b["close"]  for b in bars]
    volumes = [b["volume"] for b in bars if b["volume"] is not None]
    price   = closes[-1]

    # --- Compute indicators ---
    macd_line, macd_sig, macd_hist = _macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    rsi_val                        = _rsi(closes, RSI_PERIOD)
    ema20                          = _ema(closes, EMA_PERIOD)
    vol_ratio                      = _volume_ratio(volumes, VOL_PERIOD)
    momentum_5d                    = _momentum(closes, 5)

    indicators = {
        "macd_line":    round(macd_line, 6)  if macd_line  is not None else None,
        "macd_signal":  round(macd_sig, 6)   if macd_sig   is not None else None,
        "macd_hist":    round(macd_hist, 6)  if macd_hist  is not None else None,
        "rsi":          round(rsi_val, 2)    if rsi_val    is not None else None,
        "ema20":        round(ema20, 4)      if ema20      is not None else None,
        "price":        round(price, 4),
        "volume_ratio": round(vol_ratio, 3)  if vol_ratio  is not None else None,
        "momentum_5d":  round(momentum_5d, 4) if momentum_5d is not None else None,
    }

    # --- Run checks ---
    checks: dict[str, bool | None] = {}

    # 1. MACD
    if macd_line is not None and macd_sig is not None:
        if is_long:
            checks["macd"] = macd_line > macd_sig   # MACD above signal = bullish
        else:
            checks["macd"] = macd_line < macd_sig   # MACD below signal = bearish
    else:
        checks["macd"] = None

    # 2. RSI
    if rsi_val is not None:
        if is_long:
            checks["rsi"] = rsi_val < RSI_OVERBOUGHT   # not overbought
        else:
            checks["rsi"] = rsi_val > RSI_OVERSOLD     # not oversold
    else:
        checks["rsi"] = None

    # 3. Volume -- only check during market hours with fresh data
    # After-hours volume ratios are meaningless (partial day data)
    from datetime import datetime, timezone
    et_hour = datetime.now(timezone.utc).hour - 5  # rough ET
    market_hours = 9 <= et_hour < 16
    if vol_ratio is not None and market_hours:
        checks["volume"] = vol_ratio >= 1.0
    else:
        checks["volume"] = None  # skip volume check outside market hours

    # 4. EMA trend
    if ema20 is not None:
        if is_long:
            checks["ema_trend"] = price > ema20   # price above EMA = uptrend
        else:
            checks["ema_trend"] = price < ema20   # price below EMA = downtrend
    else:
        checks["ema_trend"] = None

    # 5. Momentum
    if momentum_5d is not None:
        if is_long:
            checks["momentum"] = momentum_5d > 0
        else:
            checks["momentum"] = momentum_5d < 0
    else:
        checks["momentum"] = None

    # --- Score (only count definitive pass/fail, not None) ---
    score   = sum(1 for v in checks.values() if v is True)
    checked = sum(1 for v in checks.values() if v is not None)

    # Adjust threshold if we have fewer than 5 checks with data
    if checked < 5:
        confirm_thresh = max(2, CONFIRM_THRESHOLD - (5 - checked))
        weak_thresh    = max(1, WEAK_THRESHOLD    - (5 - checked))
    else:
        confirm_thresh = CONFIRM_THRESHOLD
        weak_thresh    = WEAK_THRESHOLD

    # --- Verdict ---
    if score >= confirm_thresh:
        verdict       = TechVerdict.CONFIRM
        size_modifier = 1.0
        reason        = f"{score}/{checked} technical checks pass — chart confirms signal"
    elif score >= weak_thresh:
        verdict       = TechVerdict.WEAK
        size_modifier = 0.5
        reason        = f"{score}/{checked} checks pass — chart neutral, executing at 50% size"
    else:
        verdict       = TechVerdict.REJECT
        size_modifier = 0.0
        failing = [k for k, v in checks.items() if v is False]
        reason  = f"{score}/{checked} checks pass — chart contradicts signal. Failing: {', '.join(failing)}"

    log.info(
        "TechGate %s (%s): %s score=%d/%d  MACD=%s RSI=%s EMA=%s VOL=%s MOM=%s",
        ticker, direction, verdict.value, score, checked,
        "✅" if checks.get("macd") else "❌" if checks.get("macd") is False else "—",
        "✅" if checks.get("rsi")  else "❌" if checks.get("rsi")  is False else "—",
        "✅" if checks.get("ema_trend") else "❌" if checks.get("ema_trend") is False else "—",
        "✅" if checks.get("volume")    else "❌" if checks.get("volume")    is False else "—",
        "✅" if checks.get("momentum")  else "❌" if checks.get("momentum")  is False else "—",
    )

    return TechCheckResult(
        verdict=verdict,
        score=score,
        checks=checks,
        indicators=indicators,
        size_modifier=size_modifier,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Indicator calculations (pure Python, no external dependencies)
# ---------------------------------------------------------------------------

def _ema(values: list[float], period: int) -> float | None:
    """Exponential moving average over the last `period` values."""
    if len(values) < period:
        return None
    k   = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _macd(
    closes: list[float],
    fast: int,
    slow: int,
    signal: int,
) -> tuple[float | None, float | None, float | None]:
    """Compute MACD line, signal line, and histogram.

    Returns (macd_line, signal_line, histogram) or (None, None, None).
    """
    if len(closes) < slow + signal:
        return None, None, None

    # Build EMA series for fast and slow
    def ema_series(values: list[float], period: int) -> list[float]:
        k    = 2.0 / (period + 1)
        ema  = sum(values[:period]) / period
        series = [ema]
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
            series.append(ema)
        return series

    fast_series = ema_series(closes, fast)
    slow_series = ema_series(closes, slow)

    # Align: slow_series starts at index (slow-1), fast_series at (fast-1)
    # MACD = fast_ema - slow_ema, aligned to the slow series length
    offset      = slow - fast
    macd_series = [f - s for f, s in zip(fast_series[offset:], slow_series)]

    if len(macd_series) < signal:
        return None, None, None

    # Signal line = EMA(macd_series, signal)
    sig_k      = 2.0 / (signal + 1)
    signal_val = sum(macd_series[:signal]) / signal
    for v in macd_series[signal:]:
        signal_val = v * sig_k + signal_val * (1 - sig_k)

    macd_val = macd_series[-1]
    hist_val = macd_val - signal_val

    return macd_val, signal_val, hist_val


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder's RSI."""
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs  = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _volume_ratio(volumes: list[float], period: int = 20) -> float | None:
    """Current volume / average volume over last `period` days."""
    if len(volumes) < period + 1:
        return None
    avg     = sum(volumes[-period - 1:-1]) / period
    current = volumes[-1]
    if avg == 0:
        return None
    return current / avg


def _momentum(closes: list[float], period: int = 5) -> float | None:
    """% change over last `period` bars."""
    if len(closes) < period + 1:
        return None
    start = closes[-(period + 1)]
    end   = closes[-1]
    if start == 0:
        return None
    return (end - start) / start * 100


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_daily_bars(entity_id: str, limit: int = 60) -> list[dict]:
    """Fetch the most recent `limit` daily bars from price_daily, oldest first."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date, open, high, low, close, volume
                    FROM price_daily
                    WHERE entity_id = %s
                    ORDER BY date DESC
                    LIMIT %s;
                    """,
                    (entity_id, limit),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.warning("_get_daily_bars(%s) failed: %s", entity_id, exc)
        return []

    # Reverse to chronological order (oldest first for indicator math)
    return [
        {"date": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]}
        for r in reversed(rows)
    ]
