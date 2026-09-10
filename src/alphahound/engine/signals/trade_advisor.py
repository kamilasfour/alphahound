"""Trade advisor — converts divergence alerts into structured trade recommendations.

Answers five questions for every alert:
    1. Direction      — long or short?
    2. Conviction     — how strong is the signal? (1-10)
    3. Size           — how much to deploy? (Kelly + D-tier concentration)
    4. Invalidation   — what would prove the signal wrong?
    5. Outlook        — when does this resolve, what's the catalyst, when to exit?

Signal Tier System (D-value driven):
    D 2.0 – 4.0  MONITOR   — logged only, never executed
    D 4.0 – 8.0  STANDARD  — trade underlying stock/ETF, 10% bankroll cap
    D 8.0 – 20.0 HIGH      — route to 3x leveraged ETF equivalent, 20% bankroll cap
    D 20.0+      EXTREME   — route to 3x leveraged ETF, 30% bankroll cap

Leveraged ETF routing:
    When a high/extreme signal fires on a sector or stock, the engine
    substitutes the 3x leveraged ETF in the same direction for max impact.
    e.g. XLF SHORT D=38.9 → FAZ (3x short financials) LONG
         XLK LONG D=12.0  → TQQQ (3x long Nasdaq) LONG
         XLE SHORT D=9.0  → ERY (3x short energy) LONG

Outlook logic:
    - options_flow dominant  → 1-5 days
    - institutional + earnings catalyst → 3-7 days
    - congressional trade    → 10-21 days
    - news vs institutional  → 5-10 days
    - retail vs institutional → 7-21 days
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

TIER_WEIGHTS     = {"A": 2.0, "B": 1.5, "C": 1.0, "D": 0.5}
DEFAULT_BANKROLL = 5_000.0
HALF_KELLY       = 0.5
MIN_POSITION_USD = 25.0

# ---------------------------------------------------------------------------
# D-value tier thresholds and position caps
# ---------------------------------------------------------------------------
D_TIER_STANDARD  = 4.0   # minimum to execute
D_TIER_HIGH      = 8.0   # route to leveraged ETF, 20% cap
D_TIER_EXTREME   = 20.0  # route to leveraged ETF, 30% cap

MAX_POSITION_PCT_STANDARD = 0.10   # 10% of bankroll
MAX_POSITION_PCT_HIGH     = 0.20   # 20% of bankroll
MAX_POSITION_PCT_EXTREME  = 0.30   # 30% of bankroll

# ---------------------------------------------------------------------------
# Leveraged ETF routing map
# Maps (underlying_ticker, direction) -> leveraged_ticker
# Direction: LONG signal -> bull ETF, SHORT signal -> bear ETF (traded as LONG)
# ---------------------------------------------------------------------------
LEVERAGED_ETF_MAP: dict[tuple[str, str], str] = {
    # Financials
    ("XLF",  "SHORT"): "FAZ",    # 3x short financials
    ("XLF",  "LONG"):  "FAS",    # 3x long financials
    # Technology / Nasdaq
    ("XLK",  "SHORT"): "SQQQ",   # 3x short Nasdaq
    ("XLK",  "LONG"):  "TQQQ",   # 3x long Nasdaq
    ("QQQ",  "SHORT"): "SQQQ",
    ("QQQ",  "LONG"):  "TQQQ",
    # S&P 500
    ("SPY",  "SHORT"): "SPXS",   # 3x short S&P
    ("SPY",  "LONG"):  "UPRO",   # 3x long S&P
    # Semiconductors
    ("SMH",  "SHORT"): "SOXS",   # 3x short semis
    ("SMH",  "LONG"):  "SOXL",   # 3x long semis
    ("SOXX", "SHORT"): "SOXS",
    ("SOXX", "LONG"):  "SOXL",
    # Energy
    ("XLE",  "SHORT"): "ERY",    # 3x short energy
    ("XLE",  "LONG"):  "ERX",    # 3x long energy
    # Russell 2000
    ("IWM",  "SHORT"): "TZA",    # 3x short Russell
    ("IWM",  "LONG"):  "TNA",    # 3x long Russell
    # Biotech
    ("XBI",  "SHORT"): "LABD",   # 3x short biotech
    ("XBI",  "LONG"):  "LABU",   # 3x long biotech
    ("IBB",  "SHORT"): "LABD",
    ("IBB",  "LONG"):  "LABU",
    # Gold miners
    ("GDX",  "SHORT"): "DUST",   # 3x short gold miners
    ("GDX",  "LONG"):  "NUGT",   # 3x long gold miners
}


class Direction(str, Enum):
    LONG     = "LONG"
    SHORT    = "SHORT"
    NO_TRADE = "NO_TRADE"


class SignalTier(str, Enum):
    MONITOR  = "MONITOR"   # D 2-4: log only
    STANDARD = "STANDARD"  # D 4-8: trade underlying
    HIGH     = "HIGH"      # D 8-20: route to 3x leveraged ETF
    EXTREME  = "EXTREME"   # D 20+: route to 3x leveraged ETF, max size


def get_signal_tier(d_value: float) -> SignalTier:
    if d_value >= D_TIER_EXTREME:
        return SignalTier.EXTREME
    elif d_value >= D_TIER_HIGH:
        return SignalTier.HIGH
    elif d_value >= D_TIER_STANDARD:
        return SignalTier.STANDARD
    else:
        return SignalTier.MONITOR


def get_max_position_pct(tier: SignalTier) -> float:
    return {
        SignalTier.EXTREME:  MAX_POSITION_PCT_EXTREME,
        SignalTier.HIGH:     MAX_POSITION_PCT_HIGH,
        SignalTier.STANDARD: MAX_POSITION_PCT_STANDARD,
        SignalTier.MONITOR:  0.0,
    }[tier]


def get_leveraged_ticker(ticker: str, direction: Direction) -> str | None:
    """Return the 3x leveraged ETF to trade instead of the underlying.
    Returns None if no routing exists for this ticker/direction pair.
    For SHORT signals, we return the bear ETF and trade it LONG
    (avoids short-selling mechanics entirely).
    """
    return LEVERAGED_ETF_MAP.get((ticker.upper(), direction.value))


@dataclass
class Outlook:
    days_min:        int
    days_max:        int
    resolve_by:      date
    catalyst:        str
    exit_condition:  str
    signal_basis:    str

    def display(self) -> str:
        return (
            f"  Outlook:      {self.days_min}-{self.days_max} days "
            f"(resolve by {self.resolve_by.strftime('%b %d')})\n"
            f"  Catalyst:     {self.catalyst}\n"
            f"  Exit:         {self.exit_condition}\n"
            f"  Basis:        {self.signal_basis}"
        )


@dataclass
class TradeRecommendation:
    ticker:            str
    direction:         Direction
    conviction:        float
    signal_prob:       float
    kelly_fraction:    float
    position_usd:      float
    position_pct:      float
    stop_pct:          float
    stop_price:        float | None
    d_value:           float
    p_value:           float
    components:        dict
    weighted_mean:     float
    price:             float | None
    change_5d_pct:     float | None
    change_vs_spy:     float | None
    narrative:         str
    signal_tier:       SignalTier = SignalTier.STANDARD
    # Leveraged routing: if set, execute_ticker is the 3x ETF, original_ticker is the signal source
    execute_ticker:    str = ""   # actual ticker to trade (may be leveraged ETF)
    original_ticker:   str = ""   # signal source ticker
    is_leveraged:      bool = False
    outlook:           Outlook | None = None
    entity_id:         str = ""
    generated_at:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.execute_ticker:
            self.execute_ticker = self.ticker
        if not self.original_ticker:
            self.original_ticker = self.ticker

    def display(self) -> str:
        lines = [
            "=" * 60,
            "  TRADE RECOMMENDATION -- {}".format(self.ticker),
            "=" * 60,
            "  Signal tier:  {}  (D={:.1f})".format(self.signal_tier.value, self.d_value),
        ]
        if self.is_leveraged:
            lines.append("  ** ROUTING: {} signal -> trade {} (3x leveraged) **".format(
                self.original_ticker, self.execute_ticker))
        lines += [
            "  Direction:    {}".format(self.direction.value),
            "  Conviction:   {:.1f}/10".format(self.conviction),
            "  Signal prob:  {:.1%}".format(self.signal_prob),
            "",
            "  Position:     ${:.0f}  ({:.1%} of bankroll)".format(
                self.position_usd, self.position_pct),
            "  Stop loss:    {:.1%}".format(self.stop_pct),
        ]
        if self.stop_price is not None:
            lines.append("  Stop price:   ${:.2f}".format(self.stop_price))
        lines.append("")
        if self.price is not None:
            lines.append("  Current price: ${:.2f}".format(self.price))
        if self.change_5d_pct is not None:
            spy_str = "  (vs SPY: {:+.1f}%)".format(self.change_vs_spy) if self.change_vs_spy is not None else ""
            lines.append("  5d change:     {:+.1f}%{}".format(self.change_5d_pct, spy_str))
        lines.append("")
        if self.outlook:
            lines.append(self.outlook.display())
            lines.append("")
        lines.append("  D-value: {:.3f}  p-value: {:.4f}".format(self.d_value, self.p_value))
        lines.append("  Components:")
        for sc, polarity in self.components.items():
            if sc == "narrative":
                continue
            bar = "^" if polarity > 0 else "v"
            lines.append("    {} {:<22} {:+.3f}".format(bar, sc, polarity))
        lines.append("")
        lines.append("  Narrative:")
        lines.append("    {}".format(self.narrative))
        lines.append("=" * 60)
        return "\n".join(lines)


def advise(entity_id: str) -> TradeRecommendation | None:
    """Generate a trade recommendation for one entity from its latest alert."""
    alert = _get_latest_alert(entity_id)
    if alert is None:
        return None

    price_ctx = _get_price_context(entity_id)
    bankroll  = _get_bankroll()

    components = {k: v for k, v in (alert["components"] or {}).items() if k != "narrative"}
    narrative  = (alert["components"] or {}).get("narrative", "No narrative available.")

    if not components:
        return None

    weighted_sum = 0.0
    total_weight = 0.0
    source_classes = _get_source_class_tiers()

    for sc, polarity in components.items():
        tier   = source_classes.get(sc, "C")
        weight = TIER_WEIGHTS.get(tier, 1.0)
        weighted_sum += polarity * weight
        total_weight += weight

    weighted_mean = weighted_sum / total_weight if total_weight > 0 else 0.0

    if abs(weighted_mean) < 0.05:
        direction = Direction.NO_TRADE
    elif weighted_mean > 0:
        direction = Direction.LONG
    else:
        direction = Direction.SHORT

    base_p = min(0.90, 0.50 + (alert["d_value"] / 20.0))
    direction_sign = 1 if direction == Direction.LONG else -1
    agreeing = sum(1 for p in components.values() if p * direction_sign > 0.05)
    alignment_bonus = (agreeing / max(len(components), 1)) * 0.10
    signal_prob = min(0.92, base_p + alignment_bonus)

    if direction == Direction.NO_TRADE:
        signal_prob = 0.50

    # Kelly sizing
    b = 1.0
    p = signal_prob
    q = 1.0 - p
    kelly_raw  = (b * p - q) / b if direction != Direction.NO_TRADE else 0.0
    kelly_raw  = max(0.0, kelly_raw)
    kelly_half = kelly_raw * HALF_KELLY

    # Signal tier — drives position cap and routing
    tier = get_signal_tier(alert["d_value"])
    max_pct = get_max_position_pct(tier)

    position_pct = min(kelly_half, max_pct)
    position_usd = bankroll * position_pct

    if position_usd < MIN_POSITION_USD:
        position_usd = 0.0
        position_pct = 0.0

    conviction = min(10.0, round(
        (alert["d_value"] / 5.0) * 5.0 + (signal_prob - 0.50) * 10.0, 1
    ))
    conviction = max(1.0, conviction)

    stop_pct = max(0.05, 1.0 / (alert["d_value"] * 2.0))
    stop_pct = min(0.25, stop_pct)

    price = price_ctx.get("price") if price_ctx else None
    stop_price = None
    if price:
        if direction == Direction.LONG:
            stop_price = round(price * (1.0 - stop_pct), 2)
        elif direction == Direction.SHORT:
            stop_price = round(price * (1.0 + stop_pct), 2)

    # Leveraged ETF routing for HIGH and EXTREME tiers
    original_ticker = alert["canonical_symbol"]
    execute_ticker  = original_ticker
    is_leveraged    = False

    if tier in (SignalTier.HIGH, SignalTier.EXTREME) and direction != Direction.NO_TRADE:
        lev_ticker = get_leveraged_ticker(original_ticker, direction)
        if lev_ticker:
            execute_ticker = lev_ticker
            is_leveraged   = True
            # Leveraged ETFs are always traded LONG (bear ETF = short exposure without shorting)
            log.info(
                "Routing %s %s D=%.1f -> %s (3x leveraged, tier=%s)",
                original_ticker, direction.value, alert["d_value"], lev_ticker, tier.value
            )

    outlook = _build_outlook(
        ticker=original_ticker,
        entity_id=entity_id,
        components=components,
        direction=direction,
        price=price,
        stop_pct=stop_pct,
        stop_price=stop_price,
    )

    return TradeRecommendation(
        ticker         = original_ticker,
        direction      = direction,
        conviction     = conviction,
        signal_prob    = round(signal_prob, 3),
        kelly_fraction = round(kelly_raw, 4),
        position_usd   = round(position_usd, 2),
        position_pct   = round(position_pct, 4),
        stop_pct       = round(stop_pct, 4),
        stop_price     = stop_price,
        d_value        = alert["d_value"],
        p_value        = alert["p_value"],
        components     = components,
        weighted_mean  = round(weighted_mean, 4),
        price          = price,
        change_5d_pct  = price_ctx.get("change_5d_pct") if price_ctx else None,
        change_vs_spy  = price_ctx.get("change_vs_spy") if price_ctx else None,
        narrative      = narrative,
        signal_tier    = tier,
        execute_ticker = execute_ticker,
        original_ticker= original_ticker,
        is_leveraged   = is_leveraged,
        outlook        = outlook,
        entity_id      = entity_id,
    )


def _build_outlook(
    ticker: str,
    entity_id: str,
    components: dict,
    direction: Direction,
    price: float | None,
    stop_pct: float,
    stop_price: float | None,
) -> Outlook | None:
    if direction == Direction.NO_TRADE:
        return None

    today = date.today()

    earnings_date = _get_next_earnings(entity_id)
    if earnings_date and (earnings_date - today).days <= 14:
        days_until = (earnings_date - today).days
        days_min = max(1, days_until - 1)
        days_max = days_until + 1
        resolve_by = earnings_date + timedelta(days=1)
        catalyst = "Earnings {} ({}d away)".format(earnings_date.strftime('%b %d'), days_until)
        if stop_price:
            exit_str = "Close at earnings print. Stop if price {} ${:.2f}".format(
                'below' if direction == Direction.LONG else 'above', stop_price)
        else:
            exit_str = "Close at earnings print. Stop at {:.0%} adverse move".format(stop_pct)
        return Outlook(
            days_min=days_min, days_max=days_max, resolve_by=resolve_by,
            catalyst=catalyst, exit_condition=exit_str,
            signal_basis="Earnings catalyst in {}d".format(days_until),
        )

    has_options = "options_flow" in components and abs(components["options_flow"]) > 0.1
    has_inst    = "institutional_flow" in components and abs(components["institutional_flow"]) > 0.1
    has_news    = "news_wire" in components and abs(components["news_wire"]) > 0.1
    has_retail  = "retail_social" in components and abs(components["retail_social"]) > 0.05

    if has_options and not has_news:
        days_min, days_max = 1, 5
        basis    = "Options flow dominant"
        catalyst = "Options expiry or price catalyst within 1-5 days"
    elif has_news and has_inst:
        inst_val = components.get("institutional_flow", 0)
        news_val = components.get("news_wire", 0)
        if (inst_val > 0) == (news_val > 0):
            days_min, days_max = 3, 7
            basis    = "News + institutions aligned"
            catalyst = "Price follows consensus within 3-7 days"
        else:
            days_min, days_max = 5, 10
            basis    = "News vs institutions divergence"
            catalyst = "Institutional thesis confirms as news fades within 5-10 days"
    elif has_inst and not has_news:
        days_min, days_max = 7, 21
        basis    = "Institutional/congressional flow"
        catalyst = "Public awareness of positioning within 7-21 days"
    elif has_retail and has_inst:
        days_min, days_max = 7, 14
        basis    = "Retail vs institutional divergence"
        catalyst = "Retail catches up to institutional direction within 7-14 days"
    else:
        days_min, days_max = 5, 10
        basis    = "Multi-source divergence"
        catalyst = "Signal resolves as divergence narrows within 5-10 days"

    resolve_by = today + timedelta(days=days_max)

    if stop_price:
        exit_str = "Close D<1.5. Stop {} ${:.2f}. Hard exit by {}".format(
            'below' if direction == Direction.LONG else 'above',
            stop_price, resolve_by.strftime('%b %d'))
    else:
        exit_str = "Close D<1.5. Stop {:.0%} adverse. Hard exit by {}".format(
            stop_pct, resolve_by.strftime('%b %d'))

    return Outlook(
        days_min=days_min, days_max=days_max, resolve_by=resolve_by,
        catalyst=catalyst, exit_condition=exit_str, signal_basis=basis,
    )


def _get_next_earnings(entity_id: str) -> date | None:
    today  = date.today()
    cutoff = today + timedelta(days=30)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT earnings_date FROM earnings_calendar
                    WHERE entity_id = %s
                      AND earnings_date BETWEEN %s AND %s
                      AND beat IS NULL
                    ORDER BY earnings_date ASC LIMIT 1;
                    """,
                    (entity_id, today, cutoff),
                )
                row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def advise_all(module_id: str = "stocks", min_d: float = 2.0) -> list[TradeRecommendation]:
    """Generate recommendations for all current alerts above min_d threshold."""
    entity_ids = _get_alerted_entities(module_id, min_d)
    recommendations = []
    for entity_id in entity_ids:
        rec = advise(entity_id)
        if rec and rec.direction != Direction.NO_TRADE:
            recommendations.append(rec)
    recommendations.sort(key=lambda r: r.conviction, reverse=True)
    return recommendations


def log_recommendation(rec: TradeRecommendation) -> bool:
    """Write a trade recommendation to trade_log -- once per entity per day."""
    if not rec.entity_id:
        return False

    side_map = {Direction.LONG: "buy", Direction.SHORT: "short"}
    side = side_map.get(rec.direction)
    if side is None:
        return False

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM trade_log WHERE entity_id = %s AND venue = 'signal' AND time >= %s LIMIT 1;",
                    (rec.entity_id, today_start),
                )
                if cur.fetchone():
                    log.debug("trade_log: skipping %s -- already logged today", rec.ticker)
                    return False
    except Exception:
        pass

    notes_data = {
        "conviction":     rec.conviction,
        "signal_prob":    rec.signal_prob,
        "d_value":        rec.d_value,
        "signal_tier":    rec.signal_tier.value,
        "execute_ticker": rec.execute_ticker,
        "is_leveraged":   rec.is_leveraged,
        "weighted_mean":  rec.weighted_mean,
        "stop_pct":       rec.stop_pct,
        "stop_price":     rec.stop_price,
        "components":     rec.components,
        "narrative":      rec.narrative[:200],
    }

    if rec.outlook:
        notes_data["outlook"] = {
            "days_min":       rec.outlook.days_min,
            "days_max":       rec.outlook.days_max,
            "resolve_by":     rec.outlook.resolve_by.isoformat(),
            "catalyst":       rec.outlook.catalyst,
            "exit_condition": rec.outlook.exit_condition,
            "signal_basis":   rec.outlook.signal_basis,
        }

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trade_log
                        (time, module_id, entity_id, side, size, price, venue, pnl, notes)
                    VALUES (%s, 'stocks', %s, %s, %s, %s, 'signal', NULL, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (
                        rec.generated_at,
                        rec.entity_id,
                        side,
                        rec.position_usd,
                        rec.price,
                        json.dumps(notes_data),
                    ),
                )
            conn.commit()
        return True
    except Exception as exc:
        log.warning("trade_log write failed for %s: %s", rec.ticker, exc)
        return False


def log_all_recommendations(recs: list[TradeRecommendation]) -> int:
    written = 0
    for rec in recs:
        if log_recommendation(rec):
            written += 1
    if written:
        log.info("trade_log: wrote %d signal recommendations", written)
    return written


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_latest_alert(entity_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT de.entity_id, de.time, de.d_value, de.p_value,
                       de.components, e.canonical_symbol
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                WHERE de.entity_id = %s
                ORDER BY de.time DESC LIMIT 1;
                """,
                (entity_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(["entity_id","time","d_value","p_value","components","canonical_symbol"], row))


def _get_alerted_entities(module_id: str, min_d: float) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (de.entity_id) de.entity_id
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                WHERE e.module_id = %s AND de.d_value >= %s AND de.time >= %s
                ORDER BY de.entity_id, de.time DESC;
                """,
                (module_id, min_d, since),
            )
            return [str(row[0]) for row in cur.fetchall()]


def _get_price_context(entity_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT price, change_1d_pct, change_5d_pct, change_vs_spy "
                "FROM price_snapshots WHERE entity_id = %s ORDER BY time DESC LIMIT 1;",
                (entity_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "price":          row[0],
        "change_1d_pct":  row[1],
        "change_5d_pct":  row[2],
        "change_vs_spy":  row[3],
    }


def _get_source_class_tiers() -> dict[str, str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT source_class, tier FROM source_adapters;")
            rows = cur.fetchall()
    tier_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
    result: dict[str, str] = {}
    for source_class, tier in rows:
        if source_class not in result or tier_rank.get(tier, 0) > tier_rank.get(result[source_class], 0):
            result[source_class] = tier
    return result


def _get_bankroll() -> float:
    try:
        return float(os.environ.get("ALPHAHOUND_BANKROLL", DEFAULT_BANKROLL))
    except (ValueError, TypeError):
        return DEFAULT_BANKROLL
