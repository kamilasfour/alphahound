"""Multi-Pillar Convergence Engine — Sprint 11 core scoring brain.

Replaces the divergence-based signal generator with a structured, explainable
convergence system. Every signal is traceable to specific pillars that fired,
with evidence from real data sources.

THE 7 PILLARS
─────────────
P1  Scalability       Liquid options, account-size appropriate
P2  Options Flow      Unusual Whales sweep >4x normal vol, multi-exchange
P3a Congressional     Quiver: committee-member buy in relevant sector
P3b Gov Contract      Quiver / GovConWire: DoD/DARPA/MDA/FDA award
P3c Social Velocity   ApeWisdom/Substack: mention velocity +150% in 7 days
P4  Meta-Convergence  4+ pillars from independent sources = non-linear boost
P5  Prediction Market Kalshi: sector/event odds shifting
P6  Catalyst          Earnings/PDUFA/FOMC within 14–45 days
P7  Quant Momentum    MACD/RSI/EMA alignment + options order flow

SCORING
───────
Each pillar scores 0, 0.5, or 1.0.
Composite = sum(pillar_scores) + non_linear_boost (1.5 if 4+ independent pillars).
Super Signal: composite >= 4.0 AND 4+ independent pillars AND direction != NEUTRAL.

DIRECTION LOGIC
───────────────
P2 only votes if sentiment-classified rows exist (call_vol > 0 or put_vol > 0).
P/C=0.00 with 0B/0Br rows = ambiguous flow = no directional vote.
P7 institutional polarity votes SHORT if negative, LONG if positive.
Tie → NEUTRAL (not actionable for directional structures).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import psycopg

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# ─── Thresholds ───────────────────────────────────────────────────────────────

SUPER_SIGNAL_THRESHOLD = 4.0
MIN_PILLARS_FOR_SUPER  = 4
NON_LINEAR_BOOST       = 1.5
SOCIAL_VELOCITY_MIN    = 1.5
CONGRESSIONAL_MIN_AMT  = 15_000
UNUSUAL_SCORE_MIN      = 10.0
OPTIONS_PCALL_BULLISH  = 0.35
OPTIONS_PCALL_BEARISH  = 0.65
CATALYST_MIN_DAYS      = 7    # was 14
CATALYST_MAX_DAYS      = 60   # was 45


# ─── Data shapes ──────────────────────────────────────────────────────────────

@dataclass
class PillarResult:
    name:     str
    score:    float
    fired:    bool
    evidence: str
    data:     dict = field(default_factory=dict)


@dataclass
class ConvergenceResult:
    entity_id:             str
    ticker:                str
    composite_score:       float
    pillars_fired:         int
    super_signal:          bool
    direction:             str
    catalyst_date:         Optional[date]
    catalyst_type:         Optional[str]
    recommended_structure: Optional[str]
    pillar_results:        list[PillarResult]
    computed_at:           datetime
    narrative:             str
    structure_dict:        Optional[dict] = None   # S11-6: auto-attached by scan_and_store

    def to_db_json(self) -> dict:
        d = {
            "composite_score":       self.composite_score,
            "pillars_fired":         self.pillars_fired,
            "direction":             self.direction,
            "catalyst_date":         self.catalyst_date.isoformat() if self.catalyst_date else None,
            "catalyst_type":         self.catalyst_type,
            "recommended_structure": self.recommended_structure,
            "narrative":             self.narrative,
            "pillars": [
                {"name": p.name, "score": p.score, "fired": p.fired,
                 "evidence": p.evidence, "data": p.data}
                for p in self.pillar_results
            ],
        }
        if self.structure_dict:
            d["structure"] = self.structure_dict
        return d


# ─── Main entry point ─────────────────────────────────────────────────────────

def scan_and_store(module_id: str = "stocks") -> int:
    _ensure_table()
    now     = datetime.now(timezone.utc)
    tickers = _get_active_tickers(module_id)
    if not tickers:
        log.info("Convergence scan: no active tickers.")
        return 0
    log.info("Convergence scan: evaluating %d tickers", len(tickers))
    super_count = 0
    for entity_id, ticker in tickers:
        try:
            result = score_ticker(entity_id, ticker, now=now)
            if result is None:
                continue
            # Auto-attach structure plan to every super signal before writing
            if result.super_signal:
                try:
                    from alphahound.engine.execution.options_structure import recommend_structure
                    from alphahound.engine.execution.alpaca_broker import get_broker
                    try:
                        equity = float(get_broker().get_account().get("equity", 20_000))
                    except Exception:
                        equity = 20_000.0
                    structure = recommend_structure(
                        entity_id       = entity_id,
                        ticker          = ticker,
                        direction       = result.direction,
                        composite_score = result.composite_score,
                        pillars_fired   = result.pillars_fired,
                        catalyst_type   = result.catalyst_type,
                        catalyst_date   = result.catalyst_date,
                        equity          = equity,
                    )
                    if structure:
                        result.structure_dict = structure.to_dict()
                        log.info("Structure attached for %s: %s", ticker, structure.structure_type)
                except Exception as exc:
                    log.debug("Structure auto-attach failed for %s: %s", ticker, exc)
            _write_result(result)
            if result.super_signal:
                super_count += 1
                log.info("SUPER SIGNAL: %s  score=%.2f  pillars=%d  direction=%s  catalyst=%s",
                         ticker, result.composite_score, result.pillars_fired,
                         result.direction, result.catalyst_type or "none")
        except Exception as exc:
            log.warning("Convergence scoring failed for %s: %s", ticker, exc)
    log.info("Convergence scan complete: %d super signals from %d tickers", super_count, len(tickers))
    return super_count


def score_ticker(entity_id: str, ticker: str, now: datetime | None = None) -> ConvergenceResult | None:
    now = now or datetime.now(timezone.utc)

    p1  = _score_p1_scalability(ticker)
    p2  = _score_p2_options_flow(entity_id, ticker, now)
    p3a = _score_p3a_congressional(entity_id, ticker, now)
    p3b = _score_p3b_gov_contract(entity_id, ticker, now)
    p3c = _score_p3c_social_velocity(entity_id, ticker, now)
    p6, catalyst_date, catalyst_type = _score_p6_catalyst_v2(entity_id, ticker)
    p7  = _score_p7_quant_momentum(entity_id, ticker, now)

    pillar_results = [p1, p2, p3a, p3b, p3c, p6, p7]

    p3_fired = max(p3a.score, p3b.score, p3c.score) > 0
    independent_pillars = [p1.score > 0, p2.score > 0, p3_fired, p6.score > 0, p7.score > 0]
    pillars_fired = sum(independent_pillars)

    raw_score = sum(p.score for p in pillar_results)
    boost     = NON_LINEAR_BOOST if pillars_fired >= MIN_PILLARS_FOR_SUPER else 0.0
    composite = round(raw_score + boost, 3)

    p4 = PillarResult(
        name="P4_meta_convergence",
        score=1.0 if boost > 0 else 0.0,
        fired=boost > 0,
        evidence=(
            f"Non-linear boost applied: {pillars_fired} independent pillars fired"
            if boost > 0 else
            f"Only {pillars_fired}/4 independent pillars fired — no boost"
        ),
        data={"independent_pillars_fired": pillars_fired, "boost": boost},
    )
    pillar_results.insert(3, p4)

    direction             = _determine_direction(p2, p3a, p3b, p3c, p7)
    recommended_structure = _recommend_structure(composite, direction, catalyst_type, pillars_fired)
    fired_names           = [p.name for p in pillar_results if p.fired]
    narrative             = _build_narrative(ticker, composite, direction, fired_names, catalyst_type, catalyst_date, pillars_fired)

    # RULE 1: Catalyst required — UNLESS score >= 5.0 with 5+ pillars (very high conviction)
    # High conviction multi-pillar signals are tradeable without a binary event.
    catalyst_fired = p6.score > 0
    high_conviction_no_catalyst = (
        composite >= 5.0
        and pillars_fired >= 4
        and direction != "NEUTRAL"
        and not catalyst_fired
    )

    # RULE 2: P2 options flow must have Unusual Whales sentiment classification.
    p2_confirmed = (
        not p2.fired or
        p2.data.get("bullish_count", 0) > 0 or
        p2.data.get("bearish_count", 0) > 0
    )

    super_signal = (
        composite >= SUPER_SIGNAL_THRESHOLD
        and pillars_fired >= MIN_PILLARS_FOR_SUPER
        and direction != "NEUTRAL"
        and (catalyst_fired or high_conviction_no_catalyst)
        and p2_confirmed
    )

    return ConvergenceResult(
        entity_id=entity_id, ticker=ticker,
        composite_score=composite, pillars_fired=pillars_fired,
        super_signal=super_signal, direction=direction,
        catalyst_date=catalyst_date, catalyst_type=catalyst_type,
        recommended_structure=recommended_structure,
        pillar_results=pillar_results, computed_at=now, narrative=narrative,
    )


# ─── Pillar scorers ───────────────────────────────────────────────────────────

def _score_p1_scalability(ticker: str) -> PillarResult:
    from alphahound.modules.stocks.adapters.massive import WATCHLIST as PRICE_WATCHLIST
    TIER_A = {
        "AAPL","NVDA","TSLA","AMD","AMZN","MSFT","META","GOOGL","GOOG",
        "ARM","PLTR","COIN","MSTR","SOFI","HOOD","GME","NFLX",
        "INTC","AVGO","NOW","QCOM","UBER","SHOP","UNH","MA",
        "ORCL","IBM","CMG","ADBE","PYPL","TSM","MU","SMCI",
        "BAC","F","SNAP","CVX","CAT","IONQ","RGTI","QBTS",
        "NOC","LMT","RTX","VRDN","PANW","CTSH","IT","KLAC","TXN","CVNA",
    }
    if ticker in TIER_A:
        return PillarResult("P1_scalability", 1.0, True,
                            f"{ticker} is in the high-liquidity options-eligible watchlist")
    if ticker in PRICE_WATCHLIST:
        return PillarResult("P1_scalability", 0.5, True,
                            f"{ticker} is in extended watchlist — options may have wider spreads")
    return PillarResult("P1_scalability", 0.0, False,
                        f"{ticker} not in watchlist — liquidity unknown")


def _score_p2_options_flow(entity_id: str, ticker: str, now: datetime) -> PillarResult:
    window_start = now - timedelta(hours=48)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sentiment, unusual_score, contract_type, volume,
                           open_interest, strike, expiry, time
                    FROM options_flow
                    WHERE entity_id = %s AND time >= %s AND unusual_score IS NOT NULL
                    ORDER BY unusual_score DESC LIMIT 20;
                """, (entity_id, window_start))
                rows = cur.fetchall()
    except Exception as exc:
        return PillarResult("P2_options_flow", 0.0, False, f"Query error: {exc}")

    if not rows:
        return PillarResult("P2_options_flow", 0.0, False, "No unusual options activity in last 48h")

    # Filter to rows with non-null unusual_score before computing max
    scored_rows = [r for r in rows if r[1] is not None]
    if not scored_rows:
        return PillarResult("P2_options_flow", 0.0, False, "Options activity present but no unusual_score data")

    call_vol     = sum(r[3] or 0 for r in rows if r[2] == "call")
    put_vol      = sum(r[3] or 0 for r in rows if r[2] == "put")
    total_vol    = call_vol + put_vol
    max_unusual  = max(r[1] for r in rows if r[1])
    bullish_rows = [r for r in rows if r[0] == "bullish"]
    bearish_rows = [r for r in rows if r[0] == "bearish"]
    pc_ratio     = (put_vol / total_vol) if total_vol > 0 else 0.5

    if max_unusual >= UNUSUAL_SCORE_MIN:
        if pc_ratio <= OPTIONS_PCALL_BULLISH and call_vol > 0:
            direction_note = f"call-dominant (P/C={pc_ratio:.2f})"
            score = 1.0 if len(bullish_rows) > 0 else 0.5
        elif pc_ratio >= OPTIONS_PCALL_BEARISH and put_vol > 0:
            direction_note = f"put-dominant (P/C={pc_ratio:.2f})"
            score = 1.0 if len(bearish_rows) > 0 else 0.5
        else:
            direction_note = f"mixed flow (P/C={pc_ratio:.2f})"
            score = 0.5
        top = rows[0]
        evidence = (f"Unusual options activity: max_score={max_unusual:.0f}, "
                    f"{direction_note}, {len(bullish_rows)}B/{len(bearish_rows)}Br rows, "
                    f"top contract: {top[2]} strike={top[5]} exp={top[6]}")
        return PillarResult("P2_options_flow", score, True, evidence,
                            data={"max_unusual_score": max_unusual, "pc_ratio": round(pc_ratio, 3),
                                  "call_vol": call_vol, "put_vol": put_vol,
                                  "bullish_count": len(bullish_rows), "bearish_count": len(bearish_rows)})

    if max_unusual > 0:
        return PillarResult("P2_options_flow", 0.0, False,
                            f"Options activity but unusual_score={max_unusual:.0f} below threshold {UNUSUAL_SCORE_MIN}")
    return PillarResult("P2_options_flow", 0.0, False, "No unusual options sweep detected")


def _score_p3a_congressional(entity_id: str, ticker: str, now: datetime) -> PillarResult:
    window_start = now - timedelta(days=45)
    HIGH_SIGNAL_COMMITTEES = {
        "intelligence","armed services","defense","health","finance",
        "banking","commerce","energy","judiciary","foreign affairs",
    }
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT filer, shares, filed_at, kind
                    FROM institutional_positions
                    WHERE entity_id = %s AND filed_at >= %s AND kind = 'Congress'
                    ORDER BY filed_at DESC LIMIT 10;
                """, (entity_id, window_start))
                rows = cur.fetchall()
    except Exception as exc:
        return PillarResult("P3a_congressional", 0.0, False, f"Query error: {exc}")

    if not rows:
        return PillarResult("P3a_congressional", 0.0, False, "No congressional trades in last 45 days")

    buys  = [(f, s, d) for f, s, d, k in rows if s and s > 0]
    sells = [(f, s, d) for f, s, d, k in rows if s and s < 0]
    sig_buys = [(f, s, d) for f, s, d in buys if s >= CONGRESSIONAL_MIN_AMT]

    if not sig_buys:
        if sells:
            return PillarResult("P3a_congressional", 0.0, False,
                                f"{len(sells)} congressional sell(s) — bearish but not a buy trigger",
                                data={"sells": len(sells)})
        return PillarResult("P3a_congressional", 0.0, False, "No significant congressional buys")

    top_buyer, top_amount, top_date = sig_buys[0]
    committee_match = any(c in top_buyer.lower() for c in HIGH_SIGNAL_COMMITTEES)
    score = 1.0 if (len(sig_buys) >= 3 or committee_match) else 0.5
    date_str = top_date.strftime("%Y-%m-%d") if top_date else "n/a"
    evidence = (f"Congressional buy: {top_buyer} ${top_amount:,.0f} on {date_str}"
                + (" [committee]" if committee_match else ""))
    return PillarResult("P3a_congressional", score, True, evidence,
                        data={"total_buys": len(sig_buys), "total_sells": len(sells),
                              "top_buyer": top_buyer, "top_amount": top_amount})


def _score_p3b_gov_contract(entity_id: str, ticker: str, now: datetime) -> PillarResult:
    window_start = now - timedelta(days=30)
    CONTRACT_KEYWORDS = [
        "contract","award","dod","darpa","mda","pentagon",
        "defense contract","navy","army","air force","space force","niwc",
        "idiq","task order","government contract",
    ]
    ANCHOR_KEYWORDS = {
        "contract","dod","darpa","mda","pentagon","idiq",
        "task order","defense contract","government contract","niwc",
    }
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT text, time, adapter_id FROM raw_posts
                    WHERE entity_id = %s AND time >= %s
                      AND source_class IN ('institutional_flow','news_wire','analyst_curated')
                    ORDER BY time DESC LIMIT 50;
                """, (entity_id, window_start))
                rows = cur.fetchall()
    except Exception as exc:
        return PillarResult("P3b_gov_contract", 0.0, False, f"Query error: {exc}")

    if not rows:
        return PillarResult("P3b_gov_contract", 0.0, False, "No relevant posts in last 30 days")

    hits = []
    for text, time_, _ in rows:
        tl = (text or "").lower()
        kws = [kw for kw in CONTRACT_KEYWORDS if kw in tl]
        if len(kws) >= 2 and any(kw in tl for kw in ANCHOR_KEYWORDS):
            hits.append((text[:120], time_, kws))

    if not hits:
        return PillarResult("P3b_gov_contract", 0.0, False, "No government contract signals in recent posts")

    score = 1.0 if len(hits) >= 2 else 0.5
    return PillarResult("P3b_gov_contract", score, True,
                        f"{len(hits)} gov contract signal(s): keywords={hits[0][2][:4]}",
                        data={"contract_hits": len(hits), "top_keywords": hits[0][2][:5]})


def _score_p3c_social_velocity(entity_id: str, ticker: str, now: datetime) -> PillarResult:
    window_7d  = now - timedelta(days=7)
    window_24h = now - timedelta(hours=24)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE time >= %s AND source_class IN ('retail_social','analyst_curated')) AS posts_24h,
                        COUNT(*) FILTER (WHERE time >= %s AND source_class IN ('retail_social','analyst_curated')) AS posts_7d
                    FROM raw_posts WHERE entity_id = %s;
                """, (window_24h, window_7d, entity_id))
                row = cur.fetchone()
    except Exception as exc:
        return PillarResult("P3c_social_velocity", 0.0, False, f"Query error: {exc}")

    if not row or not row[1]:
        return PillarResult("P3c_social_velocity", 0.0, False, "No social posts in last 7 days")

    posts_24h = int(row[0] or 0)
    posts_7d  = int(row[1] or 0)
    baseline  = posts_7d / 7.0

    if baseline <= 0:
        if posts_24h > 5:
            return PillarResult("P3c_social_velocity", 0.5, True,
                                f"New social activity: {posts_24h} posts today (no baseline)")
        return PillarResult("P3c_social_velocity", 0.0, False, "Insufficient social post history")

    velocity = (posts_24h / baseline) - 1.0

    if velocity >= SOCIAL_VELOCITY_MIN:
        return PillarResult("P3c_social_velocity", 1.0, True,
                            f"Social velocity +{velocity:.0%}: {posts_24h}/24h vs baseline {baseline:.1f}/day",
                            data={"posts_24h": posts_24h, "posts_7d": posts_7d,
                                  "baseline_per_day": round(baseline, 1), "velocity": round(velocity, 3)})
    if velocity >= 0.5:
        return PillarResult("P3c_social_velocity", 0.5, True,
                            f"Moderate velocity +{velocity:.0%}: {posts_24h}/24h vs baseline {baseline:.1f}/day",
                            data={"posts_24h": posts_24h, "posts_7d": posts_7d,
                                  "baseline_per_day": round(baseline, 1), "velocity": round(velocity, 3)})
    if velocity >= 0.0:
        return PillarResult("P3c_social_velocity", 0.0, False,
                            f"Velocity below threshold (+{velocity:.0%}): {posts_24h}/24h vs {baseline:.1f}/day — need +150%")
    return PillarResult("P3c_social_velocity", 0.0, False,
                        f"Velocity declining ({velocity:+.0%}): {posts_24h}/24h vs baseline {baseline:.1f}/day")


def _score_p6_catalyst_v2(entity_id: str, ticker: str) -> tuple[PillarResult, Optional[date], Optional[str]]:
    try:
        from alphahound.engine.signals.catalyst_calendar import get_catalyst_for_ticker
        catalyst = get_catalyst_for_ticker(entity_id, ticker,
                                           min_days=CATALYST_MIN_DAYS, max_days=CATALYST_MAX_DAYS)
    except Exception as exc:
        return PillarResult("P6_catalyst", 0.0, False, f"Catalyst lookup error: {exc}"), None, None

    if catalyst is None:
        return (PillarResult("P6_catalyst", 0.0, False,
                             f"No EARNINGS/PDUFA catalyst in {CATALYST_MIN_DAYS}-{CATALYST_MAX_DAYS} day window"),
                None, None)

    sweet_note = " [sweet spot]" if catalyst.in_sweet_spot else ""
    evidence   = f"{catalyst.description}{sweet_note}"
    return (PillarResult("P6_catalyst", catalyst.score, True, evidence,
                         data={"catalyst_type": catalyst.catalyst_type,
                               "catalyst_date": catalyst.catalyst_date.isoformat(),
                               "days_away": catalyst.days_away,
                               "in_sweet_spot": catalyst.in_sweet_spot}),
            catalyst.catalyst_date, catalyst.catalyst_type)


def _score_p7_quant_momentum(entity_id: str, ticker: str, now: datetime) -> PillarResult:
    window_start = now - timedelta(hours=72)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT AVG(polarity), COUNT(*), MAX(time)
                    FROM sentiment_scores
                    WHERE entity_id = %s AND time >= %s AND source_class = 'institutional_flow';
                """, (entity_id, window_start))
                flow_row = cur.fetchone()
                cur.execute("""
                    SELECT price, change_1d_pct, change_5d_pct, volume
                    FROM price_snapshots WHERE entity_id = %s ORDER BY time DESC LIMIT 1;
                """, (entity_id,))
                price_row = cur.fetchone()
    except Exception as exc:
        return PillarResult("P7_quant_momentum", 0.0, False, f"Query error: {exc}")

    if not flow_row or not flow_row[1]:
        return PillarResult("P7_quant_momentum", 0.0, False,
                            "Insufficient institutional flow data for momentum signal")

    avg_polarity = float(flow_row[0] or 0)
    flow_count   = int(flow_row[1] or 0)

    if price_row:
        price  = float(price_row[0] or 0)
        chg_5d = float(price_row[2] or 0)

        if avg_polarity > 0.1 and chg_5d > 0:
            return PillarResult("P7_quant_momentum", 1.0, True,
                                f"Bullish alignment: inst_flow={avg_polarity:+.3f} ({flow_count} trades), price 5d={chg_5d:+.1f}%",
                                data={"avg_polarity": round(avg_polarity, 4), "flow_count": flow_count,
                                      "price": price, "chg_5d": chg_5d})
        if avg_polarity < -0.1 and chg_5d < 0:
            return PillarResult("P7_quant_momentum", 1.0, True,
                                f"Bearish alignment: inst_flow={avg_polarity:+.3f} ({flow_count} trades), price 5d={chg_5d:+.1f}%",
                                data={"avg_polarity": round(avg_polarity, 4), "flow_count": flow_count,
                                      "price": price, "chg_5d": chg_5d})
        if abs(avg_polarity) > 0.1:
            return PillarResult("P7_quant_momentum", 0.5, True,
                                f"Partial momentum: inst_flow={avg_polarity:+.3f} but price 5d={chg_5d:+.1f}% doesn't confirm direction",
                                data={"avg_polarity": round(avg_polarity, 4), "flow_count": flow_count,
                                      "price": price, "chg_5d": chg_5d})
        return PillarResult("P7_quant_momentum", 0.0, False,
                            f"No momentum signal: inst_flow={avg_polarity:+.3f}, price 5d={chg_5d:+.1f}%")

    if abs(avg_polarity) > 0.2:
        return PillarResult("P7_quant_momentum", 0.5, True,
                            f"Institutional flow signal (no price data): polarity={avg_polarity:+.3f} ({flow_count} trades)",
                            data={"avg_polarity": round(avg_polarity, 4), "flow_count": flow_count})
    return PillarResult("P7_quant_momentum", 0.0, False,
                        f"Weak institutional flow: polarity={avg_polarity:+.3f} ({flow_count} trades)")


# ─── Direction resolver ───────────────────────────────────────────────────────

def _determine_direction(p2: PillarResult, p3a: PillarResult, p3b: PillarResult,
                         p3c: PillarResult, p7: PillarResult) -> str:
    votes_long  = 0
    votes_short = 0

    # P2 — only vote direction when UW has classified rows as bullish/bearish.
    # Raw call/put volume without sentiment classification is not directionally reliable.
    if p2.fired:
        pc            = p2.data.get("pc_ratio", 0.5)
        bullish_count = p2.data.get("bullish_count", 0)
        bearish_count = p2.data.get("bearish_count", 0)
        if bullish_count > 0 or bearish_count > 0:
            if pc <= OPTIONS_PCALL_BULLISH:
                votes_long  += 2
            elif pc >= OPTIONS_PCALL_BEARISH:
                votes_short += 2
        # 0 sentiment rows = flow present but unclassified = no directional vote

    # P3a — congressional buys
    if p3a.fired and p3a.data.get("total_buys", 0) > p3a.data.get("total_sells", 0):
        votes_long += 1

    # P3b — gov contract = bullish
    if p3b.fired:
        votes_long += 1

    # P7 — institutional flow polarity
    if p7.fired:
        polarity = p7.data.get("avg_polarity", 0)
        if polarity > 0.1:
            votes_long  += 1
        elif polarity < -0.1:
            votes_short += 1

    if votes_long > votes_short:
        return "LONG"
    if votes_short > votes_long:
        return "SHORT"
    return "NEUTRAL"


# ─── Structure recommender ────────────────────────────────────────────────────

def _recommend_structure(composite: float, direction: str,
                         catalyst_type: Optional[str], pillars_fired: int) -> Optional[str]:
    if composite < SUPER_SIGNAL_THRESHOLD or direction == "NEUTRAL":
        return None
    if pillars_fired >= 5:
        return "LONG_CALL" if direction == "LONG" else "LONG_PUT"
    if catalyst_type == "PDUFA":
        return "LONG_STRANGLE"
    if direction == "LONG":
        return "BULL_CALL_SPREAD"
    if direction == "SHORT":
        return "BEAR_PUT_SPREAD"
    return None


# ─── Narrative ───────────────────────────────────────────────────────────────

def _build_narrative(ticker: str, composite: float, direction: str,
                     fired_names: list[str], catalyst_type: Optional[str],
                     catalyst_date: Optional[date], pillars_fired: int = 0) -> str:
    if composite < 2.0:
        return f"{ticker}: weak signal ({composite:.1f}), monitoring only."

    pillar_count  = len(fired_names)
    catalyst_str  = ""
    if catalyst_date:
        days = (catalyst_date - date.today()).days
        catalyst_str = f" with {catalyst_type or 'catalyst'} in {days}d"

    structure_hints = {
        "LONG_STRANGLE":    "strangle opportunity",
        "BULL_CALL_SPREAD": "bull call spread opportunity",
        "BEAR_PUT_SPREAD":  "bear put spread opportunity",
    }
    rec_str = ""
    if composite >= SUPER_SIGNAL_THRESHOLD:
        rec = _recommend_structure(composite, direction, catalyst_type, pillars_fired)
        if rec:
            rec_str = f" → {structure_hints.get(rec, rec)}"

    direction_str = {"LONG": "bullish", "SHORT": "bearish", "NEUTRAL": "mixed"}.get(direction, direction)
    return (f"{ticker}: {pillar_count} pillar(s) fire {direction_str} "
            f"(score={composite:.2f}){catalyst_str}{rec_str}.")


# ─── DB helpers ──────────────────────────────────────────────────────────────

def _get_active_tickers(module_id: str) -> list[tuple[str, str]]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT e.entity_id, e.canonical_symbol
                    FROM entities e
                    WHERE e.module_id = %s AND e.kind = 'ticker'
                      AND EXISTS (
                          SELECT 1 FROM raw_posts rp
                          WHERE rp.entity_id = e.entity_id AND rp.time >= %s
                      )
                    ORDER BY e.canonical_symbol;
                """, (module_id, since))
                return [(str(r[0]), r[1]) for r in cur.fetchall()]
    except Exception as exc:
        log.error("_get_active_tickers failed: %s", exc)
        return []


def _write_result(result: ConvergenceResult) -> None:
    # Use actual timestamp, not rounded-to-hour (rounding was causing freshness check failures)
    ts      = result.computed_at
    payload = result.to_db_json()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO convergence_signals
                    (time, entity_id, ticker, composite_score, pillars_fired,
                     super_signal, direction, catalyst_date, catalyst_type,
                     recommended_structure, narrative, pillar_breakdown)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (entity_id, time) DO UPDATE
                    SET composite_score       = EXCLUDED.composite_score,
                        pillars_fired         = EXCLUDED.pillars_fired,
                        super_signal          = EXCLUDED.super_signal,
                        direction             = EXCLUDED.direction,
                        catalyst_date         = EXCLUDED.catalyst_date,
                        catalyst_type         = EXCLUDED.catalyst_type,
                        recommended_structure = EXCLUDED.recommended_structure,
                        narrative             = EXCLUDED.narrative,
                        pillar_breakdown      = EXCLUDED.pillar_breakdown;
            """, (ts, result.entity_id, result.ticker, result.composite_score,
                  result.pillars_fired, result.super_signal, result.direction,
                  result.catalyst_date, result.catalyst_type, result.recommended_structure,
                  result.narrative, psycopg.types.json.Json(payload)))
        conn.commit()


def _ensure_table() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS convergence_signals (
                    time                  TIMESTAMPTZ NOT NULL,
                    entity_id             UUID        NOT NULL,
                    ticker                TEXT        NOT NULL,
                    composite_score       FLOAT       NOT NULL DEFAULT 0,
                    pillars_fired         INT         NOT NULL DEFAULT 0,
                    super_signal          BOOLEAN     NOT NULL DEFAULT FALSE,
                    direction             TEXT        NOT NULL DEFAULT 'NEUTRAL',
                    catalyst_date         DATE,
                    catalyst_type         TEXT,
                    recommended_structure TEXT,
                    narrative             TEXT,
                    pillar_breakdown      JSONB,
                    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (entity_id, time)
                );
                CREATE INDEX IF NOT EXISTS idx_convergence_super
                    ON convergence_signals (time DESC) WHERE super_signal = TRUE;
                CREATE INDEX IF NOT EXISTS idx_convergence_ticker
                    ON convergence_signals (ticker, time DESC);
            """)
        conn.commit()
    log.debug("convergence_signals table ensured")


def get_super_signals(hours_back: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (ticker)
                        time, ticker, composite_score, pillars_fired,
                        direction, catalyst_date, catalyst_type,
                        recommended_structure, narrative, pillar_breakdown
                    FROM convergence_signals
                    WHERE super_signal = TRUE AND time >= %s
                    ORDER BY ticker, time DESC;
                """, (since,))
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        # Sort by composite score descending after dedup
        rows.sort(key=lambda r: r["composite_score"], reverse=True)
        return rows
    except Exception as exc:
        log.error("get_super_signals failed: %s", exc)
        return []


def get_ticker_score(ticker: str) -> Optional[dict]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT time, ticker, composite_score, pillars_fired,
                           super_signal, direction, catalyst_date, catalyst_type,
                           recommended_structure, narrative, pillar_breakdown
                    FROM convergence_signals WHERE ticker = %s ORDER BY time DESC LIMIT 1;
                """, (ticker.upper(),))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [d.name for d in cur.description]
                return dict(zip(cols, row))
    except Exception as exc:
        log.error("get_ticker_score failed for %s: %s", ticker, exc)
        return None
