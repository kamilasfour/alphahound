"""AlphaHound Dashboard API — v4 with connection pooling + response caching"""
import os, sys
from datetime import datetime, timedelta, timezone, date
from functools import lru_cache
import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv(r"C:\alphahound_project\.env")

ET = ZoneInfo("America/New_York")
PT = ZoneInfo("America/Los_Angeles")  # User's timezone

def now_et() -> datetime:
    """Current time in US Eastern (handles EST/EDT automatically)."""
    return datetime.now(ET)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def fmt_et(dt: datetime) -> str:
    """Format a UTC datetime as Pacific time string for display (user is PT)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    pt = dt.astimezone(PT)
    return pt.strftime("%Y-%m-%d %I:%M %p PT")

sys.path.insert(0, r"C:\alphahound_project\src")

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import psycopg
import psycopg_pool

app = FastAPI(title="AlphaHound Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=r"C:\alphahound_project\dashboard\static"), name="static")

# ── Access gate (single shared code; see dashboard/auth.py) ──────────────────
# Reads DASHBOARD_ACCESS_CODE + DASHBOARD_SESSION_SECRET from .env.
# If unset, the gate is disabled (fails open) so a missing env var can't lock you out.
from dashboard.auth import install_auth
install_auth(app)
DB_URL = os.environ.get("DATABASE_URL", "")

# ── Connection pool (min 2, max 5 connections) ──────────────────────────────
_pool: psycopg_pool.ConnectionPool | None = None

def get_pool() -> psycopg_pool.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg_pool.ConnectionPool(
            DB_URL,
            min_size=2,
            max_size=5,
            max_waiting=30,
            reconnect_timeout=10,
        )
    return _pool

from contextlib import contextmanager

@contextmanager
def get_conn():
    """Borrow a connection from the pool."""
    with get_pool().connection() as conn:
        yield conn

# ── Simple TTL cache ────────────────────────────────────────────────────────
_cache: dict = {}

def cached(key: str, ttl_seconds: int):
    """Returns (hit, value). If hit=False, caller should compute and call cache_set."""
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry["ts"]) < ttl_seconds:
        return True, entry["val"]
    return False, None

def cache_set(key: str, val):
    _cache[key] = {"ts": time.monotonic(), "val": val}

@app.get("/")
def root():
    return FileResponse(r"C:\alphahound_project\dashboard\index.html")

@app.get("/docs")
def platform_docs():
    return FileResponse(r"C:\alphahound_project\docs\platform.html")

# ── Summary ──────────────────────────────────────────────────────────────────

@app.get("/api/summary")
def get_summary():
    hit, val = cached("summary", 60)
    if hit: return val
    now = datetime.now(timezone.utc)
    is_weekend = now.weekday() >= 5
    hours_back = 48 if is_weekend else 6
    since = now - timedelta(hours=hours_back)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT entity_id) FROM divergence_events WHERE time >= %s", (since,))
            alert_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM raw_posts WHERE time >= now() - interval '24 hours'")
            posts_24h = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sentiment_scores WHERE time >= now() - interval '24 hours'")
            scored_24h = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM trade_log WHERE venue = 'signal'")
            signals_logged = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM ingest_runs WHERE started_at >= now() - interval '30 minutes' AND error IS NULL")
            healthy_runs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT entity_id) FROM sentiment_scores WHERE time >= now() - interval '24 hours'")
            entities_active = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM divergence_events WHERE time >= now() - interval '24 hours'")
            alerts_24h = cur.fetchone()[0]
    result = {
        "scored_24h": scored_24h,
        "alert_count": alert_count, "posts_24h": posts_24h,
        "signals_logged": signals_logged, "healthy_runs": healthy_runs,
        "entities_active": entities_active, "alerts_24h": alerts_24h,
        "engine_status": "live" if healthy_runs > 0 else "stale",
        "as_of": now.isoformat(),
        "as_of_et": fmt_et(now),
        "market_open": 9 <= now_et().hour < 16 and now_et().weekday() < 5,
    }
    cache_set("summary", result)
    return result

# ── Macro context ────────────────────────────────────────────────────────────

@app.get("/api/macro")
def get_macro():
    hit, val = cached("macro", 120)
    if hit: return val
    try:
        from alphahound.engine.signals.macro_context import get_macro_context
        m = get_macro_context()
        result = {
            "verdict":       m.verdict.value,
            "score":         m.score,
            "size_modifier": m.size_modifier,
            "reason":        m.reason,
            "signals":       m.signals,
            "contributors":  m.contributors,
        }
    except Exception as e:
        result = {"verdict": "NO_DATA", "score": 0, "reason": str(e), "signals": {}}
    cache_set("macro", result)
    return result


@app.get("/api/global-markets")
def get_global_markets():
    hit, val = cached("global_markets", 300)
    if hit: return val
    try:
        from alphahound.engine.global_markets import fetch_global_markets
        summary = fetch_global_markets()
        result = {
            "overall_verdict":  summary.overall_verdict,
            "asia_verdict":     summary.asia_verdict,
            "europe_verdict":   summary.europe_verdict,
            "futures_verdict":  summary.futures_verdict,
            "size_modifier":    summary.size_modifier,
            "asia_avg_chg":     summary.asia_avg_chg,
            "europe_avg_chg":   summary.europe_avg_chg,
            "futures_avg_chg":  summary.futures_avg_chg,
            "narrative":        summary.narrative,
            "generated_at":     summary.generated_at.isoformat(),
            "indices": [
                {
                    "ticker":     s.ticker,
                    "name":       s.name,
                    "region":     s.region,
                    "market":     s.market,
                    "price":      s.price,
                    "change_pct": s.change_pct,
                    "direction":  s.direction,
                    "severity":   s.severity,
                    "is_open":    s.is_open,
                }
                for s in summary.snapshots
                if s.error is None and s.price is not None
            ],
        }
    except Exception as exc:
        result = {"error": str(exc), "overall_verdict": "UNKNOWN", "indices": []}
    cache_set("global_markets", result)
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_signal(components: dict) -> str:
    """Classify signal type from components."""
    has_options  = abs(components.get("options_flow", 0)) > 0.1
    has_news     = abs(components.get("news_wire", 0)) > 0.1
    has_inst     = abs(components.get("institutional_flow", 0)) > 0.1
    has_retail   = abs(components.get("retail_social", 0)) > 0.05

    if has_options and not has_news:
        return "options_led"
    elif has_news and has_inst:
        inst_v = components.get("institutional_flow", 0)
        news_v = components.get("news_wire", 0)
        if (inst_v > 0) != (news_v > 0):
            return "news_vs_institutional"
        return "confirmed"
    elif has_inst and not has_news:
        return "congress"
    elif has_retail and has_inst:
        return "retail_vs_institutional"
    return "multi_source"

def _build_alert(r, tier_weights) -> dict:
    sym, d_val, p_val, t, components, price, chg1d, chg5d, vs_spy, entity_id = r
    comps = dict(components) if components else {}
    narrative = comps.pop("narrative", "")
    ws = sum(float(comps.get(k, 0)) * tier_weights.get(k, 1.0) for k in comps)
    tw = sum(tier_weights.get(k, 1.0) for k in comps if k in comps)
    wm = ws / tw if tw > 0 else 0
    direction = "LONG" if wm > 0.05 else ("SHORT" if wm < -0.05 else "WATCH")
    base_p = min(0.90, 0.50 + (d_val / 20.0))
    conviction = round(min(10.0, (d_val / 5.0) * 5.0 + (base_p - 0.50) * 10.0), 1)
    stop_pct = round(max(5.0, min(25.0, 100 / (d_val * 2))), 1)
    comps_clean = {k: round(float(v), 4) for k, v in comps.items()}
    signal_type = _classify_signal(comps_clean)

    # --- Signal tier + leveraged ETF routing (matches trade_advisor logic) ---
    from alphahound.engine.signals.trade_advisor import (
        get_signal_tier, get_max_position_pct, get_leveraged_ticker,
        SignalTier, Direction, _get_bankroll
    )
    bankroll   = _get_bankroll()
    tier       = get_signal_tier(d_val)
    max_pct    = get_max_position_pct(tier)
    kelly_raw  = max(0.0, (base_p * 2) - 1) * 0.5  # simplified half-kelly
    pos_pct    = min(kelly_raw, max_pct)
    pos_usd    = int(bankroll * pos_pct)

    dir_enum       = Direction.LONG if direction == "LONG" else (Direction.SHORT if direction == "SHORT" else Direction.NO_TRADE)
    lev_ticker     = get_leveraged_ticker(sym, dir_enum) if tier in (SignalTier.HIGH, SignalTier.EXTREME) else None
    execute_ticker = lev_ticker or sym
    is_leveraged   = lev_ticker is not None
    # -------------------------------------------------------------------------

    outlook = _get_outlook(str(entity_id), sym, comps_clean, direction, price, stop_pct)

    return {
        "ticker": sym, "d_value": round(d_val, 3), "p_value": round(p_val, 4),
        "time": t.isoformat(), "time_et": fmt_et(t),
        "direction": direction, "conviction": conviction,
        "position_usd": pos_usd, "stop_pct": stop_pct,
        "weighted_mean": round(wm, 4), "signal_type": signal_type,
        "components": comps_clean, "narrative": narrative,
        "price": price, "change_1d_pct": chg1d,
        "change_5d_pct": chg5d, "change_vs_spy": vs_spy,
        "entity_id": str(entity_id), "outlook": outlook,
        # New fields for tier/leveraged routing
        "signal_tier":    tier.value,
        "execute_ticker": execute_ticker,
        "is_leveraged":   is_leveraged,
        "bankroll":       bankroll,
        "will_execute":   d_val >= 4.0,
    }

def _get_outlook(entity_id, ticker, components, direction, price, stop_pct):
    try:
        from alphahound.engine.signals.trade_advisor import _build_outlook, Direction
        dir_enum = Direction.LONG if direction=="LONG" else (Direction.SHORT if direction=="SHORT" else Direction.NO_TRADE)
        outlook = _build_outlook(
            ticker=ticker, entity_id=entity_id, components=components,
            direction=dir_enum, price=price,
            stop_pct=stop_pct/100.0 if stop_pct > 1 else stop_pct, stop_price=None,
        )
        if outlook:
            return {
                "days_min": outlook.days_min, "days_max": outlook.days_max,
                "resolve_by": outlook.resolve_by.isoformat(),
                "catalyst": outlook.catalyst,
                "exit_condition": outlook.exit_condition,
                "signal_basis": outlook.signal_basis,
            }
    except Exception:
        pass
    return None

TIER_WEIGHTS = {"institutional_flow": 1.5, "options_flow": 2.0,
                "news_wire": 1.0, "retail_social": 1.0, "analyst_curated": 1.5}

# ── Active alerts (default: execution threshold D>=4.0) ─────────────────────

@app.get("/api/alerts")
def get_alerts(show_all: bool = False):
    now = now_utc()
    et  = now_et()
    # Market hours: 9:30am - 4:00pm ET Mon-Fri
    is_weekend     = et.weekday() >= 5
    market_open    = et.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close   = et.replace(hour=16, minute=0,  second=0, microsecond=0)
    is_market_hours = not is_weekend and market_open <= et <= market_close
    # After close or pre-market: show full day. During market hours: last 4h.
    # Weekends: last 48h so Friday signals still visible.
    if is_weekend:
        hours_back = 48
    elif is_market_hours:
        hours_back = 4
    else:
        hours_back = 24  # pre-market or after-hours -- show full day
    since = now - timedelta(hours=hours_back)
    # D>=4.0 by default (execution only). show_all=true drops to D>=2.0.
    min_d = 2.0 if show_all else 4.0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (de.entity_id)
                    e.canonical_symbol, de.d_value, de.p_value, de.time, de.components,
                    ps.price, ps.change_1d_pct, ps.change_5d_pct, ps.change_vs_spy, de.entity_id
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct, change_5d_pct, change_vs_spy
                    FROM price_snapshots WHERE entity_id = de.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                WHERE de.time >= %s
                  AND de.d_value >= %s
                ORDER BY de.entity_id, de.d_value DESC
            """, (since, min_d))
            rows = cur.fetchall()

    alerts = [_build_alert(r, TIER_WEIGHTS) for r in rows]
    alerts.sort(key=lambda x: x["d_value"], reverse=True)
    return {
        "alerts":    alerts,
        "count":     len(alerts),
        "as_of":     now.isoformat(),
        "as_of_et":  fmt_et(now),
        "show_all":  show_all,
        "min_d":     min_d,
        "market_hours": is_market_hours,
        "hours_back":   hours_back,
    }

# ── Historical alerts (all time, filterable) ──────────────────────────────────

@app.get("/api/alerts/history")
def get_alerts_history(
    ticker: str = Query(None),
    direction: str = Query(None),
    min_conviction: float = Query(0.0),
    signal_type: str = Query(None),
    days_back: int = Query(30),
    limit: int = Query(500),
):
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.canonical_symbol, de.d_value, de.p_value, de.time, de.components,
                    ps.price, ps.change_1d_pct, ps.change_5d_pct, ps.change_vs_spy, de.entity_id
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct, change_5d_pct, change_vs_spy
                    FROM price_snapshots WHERE entity_id = de.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                WHERE de.time >= %s
                ORDER BY de.time DESC
                LIMIT %s
            """, (since, limit * 3))  # fetch more, filter in Python
            rows = cur.fetchall()

    alerts = []
    for r in rows:
        a = _build_alert(r, TIER_WEIGHTS)

        # Apply filters
        if ticker and ticker.upper() not in a["ticker"].upper():
            continue
        if direction and a["direction"] != direction.upper():
            continue
        if a["conviction"] < min_conviction:
            continue
        if signal_type and a["signal_type"] != signal_type:
            continue

        alerts.append(a)
        if len(alerts) >= limit:
            break

    return {"alerts": alerts, "count": len(alerts), "days_back": days_back}

# ── Per-ticker signal history ─────────────────────────────────────────────────

@app.get("/api/ticker/{ticker}/history")
def get_ticker_history(ticker: str, days_back: int = Query(30)):
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT de.time, de.d_value, de.p_value, de.components,
                       ps.price, ps.change_1d_pct
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct FROM price_snapshots
                    WHERE entity_id = de.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                WHERE e.canonical_symbol = %s AND e.module_id = 'stocks'
                  AND de.time >= %s
                ORDER BY de.time ASC
            """, (ticker.upper(), since))
            rows = cur.fetchall()

    points = []
    for r in rows:
        t, d_val, p_val, components, price, chg1d = r
        comps = dict(components) if components else {}
        comps.pop("narrative", None)
        ws = sum(float(comps.get(k, 0)) * TIER_WEIGHTS.get(k, 1.0) for k in comps)
        tw = sum(TIER_WEIGHTS.get(k, 1.0) for k in comps if k in comps)
        wm = ws / tw if tw > 0 else 0
        direction = "LONG" if wm > 0.05 else ("SHORT" if wm < -0.05 else "WATCH")
        points.append({
            "time": t.isoformat(), "d_value": round(d_val, 3),
            "direction": direction, "price": price, "change_1d_pct": chg1d,
            "components": {k: round(float(v), 4) for k, v in comps.items()},
        })
    return {"ticker": ticker.upper(), "points": points, "count": len(points)}

# ── Technical gate ───────────────────────────────────────────────────────────

@app.get("/api/tech-check/{ticker}")
def get_tech_check(ticker: str):
    try:
        from alphahound.engine.execution.technical_gate import check as tech_check
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                    (ticker.upper(),)
                )
                row = cur.fetchone()
        if not row:
            return {"verdict": "NO_DATA", "score": 0, "checks": {}, "indicators": {}, "reason": "Ticker not found"}
        result = tech_check(str(row[0]), ticker.upper(), "LONG")  # direction passed from frontend
        return {
            "verdict":    result.verdict.value,
            "score":      result.score,
            "checks":     result.checks,
            "indicators": result.indicators,
            "reason":     result.reason,
            "size_modifier": result.size_modifier,
        }
    except Exception as e:
        return {"verdict": "NO_DATA", "score": 0, "checks": {}, "indicators": {}, "reason": str(e)}


@app.get("/api/tech-check-direction")
def get_tech_check_direction(ticker: str, direction: str = "LONG"):
    try:
        from alphahound.engine.execution.technical_gate import check as tech_check
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                    (ticker.upper(),)
                )
                row = cur.fetchone()
        if not row:
            return {"verdict": "NO_DATA", "score": 0, "checks": {}, "indicators": {}, "reason": "Ticker not found"}
        result = tech_check(str(row[0]), ticker.upper(), direction.upper())
        return {
            "verdict":       result.verdict.value,
            "score":         result.score,
            "checks":        result.checks,
            "indicators":    result.indicators,
            "reason":        result.reason,
            "size_modifier": result.size_modifier,
        }
    except Exception as e:
        return {"verdict": "NO_DATA", "score": 0, "checks": {}, "indicators": {}, "reason": str(e)}


# ── Live Alpaca positions ─────────────────────────────────────────────────────

@app.get("/api/positions")
def get_positions():
    try:
        from alphahound.engine.execution.alpaca_broker import get_broker
        broker = get_broker()
        acct   = broker.get_account()
        positions = broker.get_all_positions()
        market_open = broker.is_market_open()

        # Extract underlying tickers from OCC symbols (e.g. ORCL260717C00250000 -> ORCL)
        import re
        def occ_to_underlying(occ_symbol):
            m = re.match(r'^([A-Z]+)', occ_symbol)
            return m.group(1) if m else occ_symbol

        underlying_tickers = list(set(occ_to_underlying(p.ticker) for p in positions))

        # Get convergence signals for underlying tickers
        conv_map = {}
        if underlying_tickers:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (ticker)
                            ticker, composite_score, direction, catalyst_type,
                            catalyst_date, narrative, pillar_breakdown, pillars_fired
                        FROM convergence_signals
                        WHERE ticker = ANY(%s)
                          AND super_signal = TRUE
                        ORDER BY ticker, time DESC;
                    """, (underlying_tickers,))
                    for row in cur.fetchall():
                        t, score, direction, cat_type, cat_date, narr, bd, pillars = row
                        bd = bd or {}
                        pillars_list = bd.get('pillars', [])
                        conv_map[t] = {
                            'composite_score': score,
                            'direction': direction,
                            'catalyst_type': cat_type,
                            'catalyst_date': cat_date.isoformat() if cat_date else None,
                            'narrative': narr,
                            'pillars_fired': pillars,
                            'pillars': pillars_list,
                        }

        # Get options trade log for entry timing
        otl_map = {}
        if underlying_tickers:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (ticker)
                            ticker, time, estimated_debit, contracts,
                            structure_type, composite_score, legs_json
                        FROM options_trade_log
                        WHERE ticker = ANY(%s)
                          AND status = 'placed'
                        ORDER BY ticker, time DESC;
                    """, (underlying_tickers,))
                    for row in cur.fetchall():
                        t, tm, debit, contracts, struct, score, legs = row
                        otl_map[t] = {
                            'entered_at': fmt_et(tm),
                            'entered_at_raw': tm,
                            'estimated_debit': float(debit) if debit else None,
                            'contracts': contracts,
                            'structure_type': struct,
                        }

        pos_list = []
        for p in positions:
            underlying = occ_to_underlying(p.ticker)
            conv  = conv_map.get(underlying, {})
            otl   = otl_map.get(underlying, {})

            # Build pillar components from convergence data
            pillars      = conv.get('pillars', [])
            components   = {pl['name']: pl['score'] for pl in pillars if pl.get('fired')}

            # Catalyst exit context
            cat_date = conv.get('catalyst_date')
            days_to_cat = None
            if cat_date:
                from datetime import date as _date
                try:
                    days_to_cat = (_date.fromisoformat(cat_date) - _date.today()).days
                except Exception:
                    pass

            pos_list.append({
                'ticker':             p.ticker,
                'underlying':         underlying,
                'side':               p.side,
                'qty':                p.qty,
                'avg_entry':          p.avg_entry,
                'current_price':      p.current_price,
                'unrealized_pl':      round(p.unrealized_pl, 2),
                'unrealized_pl_pct':  round(p.unrealized_pl_pct, 2),
                # Entry context from options_trade_log
                'entered_at':         otl.get('entered_at'),
                'structure_type':     otl.get('structure_type'),
                'estimated_debit':    otl.get('estimated_debit'),
                'position_size_usd':  otl.get('estimated_debit'),
                # Convergence signal data
                'composite_score':    conv.get('composite_score'),
                'pillars_fired':      conv.get('pillars_fired'),
                'direction':          conv.get('direction'),
                'catalyst_type':      conv.get('catalyst_type'),
                'catalyst_date':      cat_date,
                'days_to_catalyst':   days_to_cat,
                'days_held':          (datetime.now(timezone.utc).date() - otl['entered_at_raw'].date()).days if otl.get('entered_at_raw') else None,
                'max_hold_days':      3 + 3 if conv.get('catalyst_type') else 14,
                'narrative':          conv.get('narrative', ''),
                'components':         components,
                # Legacy divergence fields — empty for options positions
                'd_value':            None,
                'signal_tier':        None,
                'conviction':         None,
                'signal_prob':        None,
                'stop_pct':           None,
                'stop_price':         None,
                'stop_hit':           False,
                'outlook':            None,
            })

        total_pl = sum(p["unrealized_pl"] for p in pos_list)

        return {
            "positions":    pos_list,
            "count":        len(pos_list),
            "total_pl":     round(total_pl, 2),
            "equity":       acct["equity"],
            "cash":         acct["cash"],
            "buying_power": acct["buying_power"],
            "market_open":  market_open,
            "as_of":        datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"positions": [], "count": 0, "total_pl": 0, "error": str(e)}


# ── Trade log (updated with Alpaca columns) ────────────────────────────────────

@app.get("/api/trade-log")
def get_trade_log():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (tl.entity_id)
                    e.canonical_symbol, tl.side, tl.size, tl.price,
                    tl.pnl, tl.time, tl.notes,
                    tl.alpaca_order_id, tl.alpaca_status,
                    tl.filled_price, tl.closed_at
                FROM trade_log tl JOIN entities e ON e.entity_id = tl.entity_id
                WHERE tl.venue = 'signal'
                ORDER BY tl.entity_id, tl.time DESC
            """)
            rows = cur.fetchall()
    trades = []
    for r in rows:
        sym, side, size, price, pnl, t, notes, alpaca_id, alpaca_status, filled_price, closed_at = r
        days_open = (datetime.now(timezone.utc) - t.replace(tzinfo=timezone.utc)).days
        outlook = notes.get("outlook") if isinstance(notes, dict) else None
        conviction = notes.get("conviction") if isinstance(notes, dict) else None
        trades.append({
            "ticker":        sym,
            "side":          side,
            "size":          float(size) if size else 0,
            "price":         float(price) if price else None,
            "filled_price":  float(filled_price) if filled_price else None,
            "pnl":           float(pnl) if pnl else None,
            "time":          t.isoformat(),
            "closed_at":     closed_at.isoformat() if closed_at else None,
            "days_open":     days_open,
            "status":        "closed" if closed_at else ("filled" if alpaca_status=="filled" else ("pending" if alpaca_id else "signal_only")),
            "alpaca_order_id": alpaca_id,
            "alpaca_status": alpaca_status,
            "conviction":    conviction,
            "outlook":       outlook,
        })
    total_pnl = sum(t["pnl"] for t in trades if t["pnl"] is not None)
    wins   = sum(1 for t in trades if t["pnl"] and t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] and t["pnl"] < 0)
    open_  = sum(1 for t in trades if t["alpaca_order_id"] and not t["closed_at"])
    return {"trades": trades, "count": len(trades),
            "total_pnl": total_pnl, "wins": wins, "losses": losses, "open": open_}

# ── Options flow ──────────────────────────────────────────────────────────────

@app.get("/api/options-flow")
def get_options_flow():
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.canonical_symbol, of_.contract_type, of_.sentiment,
                       of_.premium, of_.volume, of_.open_interest,
                       of_.volume_oi_ratio, of_.unusual_score, of_.expiry, of_.time
                FROM options_flow of_ JOIN entities e ON e.entity_id = of_.entity_id
                WHERE of_.time >= %s
                ORDER BY of_.unusual_score DESC NULLS LAST, of_.time DESC LIMIT 50
            """, (since,))
            rows = cur.fetchall()
    flow = []
    for r in rows:
        sym, ctype, sentiment, prem, vol, oi, vol_oi, score, expiry, t = r
        flow.append({
            "ticker": sym, "contract_type": ctype or "unknown",
            "sentiment": sentiment or "neutral", "premium": prem,
            "volume_oi_ratio": round(float(vol_oi), 2) if vol_oi else None,
            "unusual_score": round(float(score), 1) if score else None,
            "expiry": expiry.isoformat() if expiry else None,
            "time": t.isoformat(),
        })
    return {"flow": flow, "count": len(flow)}

# ── Congress ──────────────────────────────────────────────────────────────────

@app.get("/api/congress")
def get_congress():
    hit, val = cached("congress", 300)
    if hit: return val
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (ip.filing_id)
                    e.canonical_symbol,
                    ip.filer,
                    ip.shares,
                    ip.filed_at,
                    ip.kind,
                    rp.raw
                FROM institutional_positions ip
                JOIN entities e ON e.entity_id = ip.entity_id
                LEFT JOIN raw_posts rp ON rp.adapter_id = 'stocks.quiver'
                    AND rp.entity_id = ip.entity_id
                    AND rp.time >= ip.filed_at - interval '1 day'
                    AND rp.time <= ip.filed_at + interval '1 day'
                WHERE ip.kind = 'Congress'
                  AND ip.filed_at >= now() - interval '90 days'
                ORDER BY ip.filing_id, ip.filed_at DESC
                LIMIT 80;
            """)
            rows = cur.fetchall()
    trades = []
    for r in rows:
        sym, filer, shares, filed_at, kind, raw = r
        raw = raw or {}
        txn = raw.get("Transaction", "")
        trades.append({
            "ticker":          sym,
            "representative":  raw.get("Representative") or filer or "Unknown",
            "transaction":     raw.get("Transaction", ""),
            "amount":          raw.get("Range") or raw.get("Amount", ""),
            "party":           raw.get("Party", ""),
            "house":           raw.get("House", ""),
            "date":            raw.get("TransactionDate") or (filed_at.strftime("%Y-%m-%d") if filed_at else ""),
            "report_date":     raw.get("ReportDate", ""),
            "description":     raw.get("Description") or "",
            "ticker_type":     raw.get("TickerType", ""),
            "price_change":    round(float(raw["PriceChange"]), 1) if raw.get("PriceChange") else None,
            "spy_change":      round(float(raw["SPYChange"]), 1) if raw.get("SPYChange") else None,
            "excess_return":   round(float(raw["ExcessReturn"]), 1) if raw.get("ExcessReturn") else None,
        })
    trades.sort(key=lambda x: x.get("date") or "", reverse=True)
    result = {"trades": trades[:60], "count": len(trades)}
    cache_set("congress", result)
    return result

# ── Earnings ──────────────────────────────────────────────────────────────────

@app.get("/api/earnings")
def get_earnings():
    hit, val = cached("earnings", 600)
    if hit: return val
    today = datetime.now(timezone.utc).date()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.canonical_symbol, ec.earnings_date, ec.fiscal_quarter,
                       ec.estimate_eps, ec.actual_eps, ec.beat
                FROM earnings_calendar ec JOIN entities e ON e.entity_id = ec.entity_id
                WHERE ec.earnings_date BETWEEN %s AND %s
                ORDER BY ec.earnings_date ASC
            """, (today, today + timedelta(days=60)))
            rows = cur.fetchall()
    earnings = []
    for r in rows:
        sym, earn_date, quarter, est_eps, actual_eps, beat = r
        earnings.append({
            "ticker": sym, "earnings_date": earn_date.isoformat(),
            "days_until": (earn_date - today).days,
            "fiscal_quarter": quarter, "estimate_eps": est_eps,
            "actual_eps": actual_eps, "beat": beat,
        })
    result = {"earnings": earnings, "count": len(earnings)}
    cache_set("earnings", result)
    return result

# ── Universe ────────────────────────────────────────────────────────────

@app.get("/api/universe")
def get_universe(category: str = Query(None)):
    cache_key = f"universe_{category or 'all'}"
    hit, val = cached(cache_key, 300)
    if hit: return val
    from alphahound.modules.stocks.watchlist.watchlist import (
        CORE_STOCKS, BROAD_ETFS, SECTOR_ETFS, THEMATIC_ETFS,
        COMMODITY_ETFS, INTERNATIONAL_ETFS, MACRO_ETFS
    )
    category_map = {
        "stocks": CORE_STOCKS, "broad": BROAD_ETFS, "sectors": SECTOR_ETFS,
        "thematic": THEMATIC_ETFS, "commodities": COMMODITY_ETFS,
        "international": INTERNATIONAL_ETFS, "macro": MACRO_ETFS,
    }
    tickers = category_map.get(category, None)
    ticker_filter = tickers or []

    with get_conn() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT
                    e.canonical_symbol,
                    ps.price,
                    ps.change_1d_pct,
                    ps.change_5d_pct,
                    ps.change_vs_spy,
                    ps.volume,
                    COALESCE(de.d_value, 0) AS d_value,
                    de.components,
                    de.time AS alert_time,
                    ss.polarity AS sector_polarity,
                    ss.confidence AS sector_confidence
                FROM entities e
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct, change_5d_pct, change_vs_spy, volume
                    FROM price_snapshots WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                LEFT JOIN LATERAL (
                    SELECT d_value, components, time
                    FROM divergence_events WHERE entity_id = e.entity_id
                    ORDER BY time DESC LIMIT 1
                ) de ON true
                LEFT JOIN LATERAL (
                    SELECT polarity, confidence
                    FROM sentiment_scores
                    WHERE entity_id = e.entity_id AND source_class = 'sector_rollup'
                    ORDER BY time DESC LIMIT 1
                ) ss ON true
                WHERE e.module_id = 'stocks' AND e.kind = 'ticker'
            """
            if ticker_filter:
                query += " AND e.canonical_symbol = ANY(%s)"
                cur.execute(query + " ORDER BY e.canonical_symbol", (ticker_filter,))
            else:
                cur.execute(query + " ORDER BY e.canonical_symbol")
            rows = cur.fetchall()

    items = []
    for r in rows:
        sym, price, chg1d, chg5d, vs_spy, vol, d_val, components, alert_time, s_pol, s_conf = r
        comps = dict(components) if components else {}
        comps.pop("narrative", None)
        ws = sum(float(comps.get(k, 0)) * TIER_WEIGHTS.get(k, 1.0) for k in comps)
        tw = sum(TIER_WEIGHTS.get(k, 1.0) for k in comps if k in comps)
        wm = ws / tw if tw > 0 else 0
        direction = "LONG" if wm > 0.05 else ("SHORT" if wm < -0.05 else "NEUTRAL")
        has_alert = d_val > 2.0 and alert_time and (
            datetime.now(timezone.utc) - alert_time.replace(tzinfo=timezone.utc)
        ).total_seconds() < 48 * 3600
        items.append({
            "ticker":           sym,
            "price":            float(price) if price else None,
            "change_1d_pct":    round(float(chg1d), 2) if chg1d else None,
            "change_5d_pct":    round(float(chg5d), 2) if chg5d else None,
            "change_vs_spy":    round(float(vs_spy), 2) if vs_spy else None,
            "volume":           int(vol) if vol else None,
            "d_value":          round(float(d_val), 2) if d_val else 0,
            "direction":        direction if has_alert else "NEUTRAL",
            "has_alert":        has_alert,
            "sentiment":        round(float(s_pol), 4) if s_pol else None,
            "components":       {k: round(float(v), 3) for k, v in comps.items()},
            "alert_time":       alert_time.isoformat() if alert_time else None,
        })
    items.sort(key=lambda x: (not x["has_alert"], -(x["d_value"] or 0)))
    result = {"items": items, "count": len(items), "category": category or "all"}
    cache_set(cache_key, result)
    return result


@app.get("/api/sectors")
def get_sectors():
    hit, val = cached("sectors", 300)
    if hit: return val
    """Sector ETF health — price performance + rollup sentiment + constituent count."""
    from alphahound.modules.stocks.watchlist.watchlist import SECTOR_ETFS, THEMATIC_ETFS, SECTOR_CONSTITUENTS
    all_etfs = list(dict.fromkeys(SECTOR_ETFS + THEMATIC_ETFS))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.canonical_symbol,
                    ps.price, ps.change_1d_pct, ps.change_5d_pct,
                    ss.polarity, ss.confidence, ss.constituent_count, ss.coverage_pct,
                    COALESCE(de.d_value, 0) AS d_value,
                    de.components
                FROM entities e
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct, change_5d_pct
                    FROM price_snapshots WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                LEFT JOIN LATERAL (
                    SELECT polarity, confidence, constituent_count, coverage_pct
                    FROM sector_sentiment WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) ss ON true
                LEFT JOIN LATERAL (
                    SELECT d_value, components FROM divergence_events
                    WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) de ON true
                WHERE e.module_id = 'stocks' AND e.kind = 'ticker'
                  AND e.canonical_symbol = ANY(%s)
                ORDER BY e.canonical_symbol
            """, (all_etfs,))
            rows = cur.fetchall()

    sector_labels = {
        "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
        "XLV": "Health Care", "XLI": "Industrials", "XLB": "Materials",
        "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication",
        "XLY": "Consumer Disc", "XLP": "Consumer Staples",
        "SMH": "Semiconductors", "SOXX": "Semis (iShares)", "XBI": "Biotech",
        "IBB": "Biotech (iShares)", "ARKK": "Innovation", "KWEB": "China Internet",
        "FINX": "Fintech", "GDX": "Gold Miners", "OIH": "Oil Services",
    }

    sectors = []
    for r in rows:
        sym, price, chg1d, chg5d, polarity, confidence, const_count, coverage, d_val, components = r
        comps = dict(components) if components else {}
        comps.pop("narrative", None)
        constituents = SECTOR_CONSTITUENTS.get(sym, [])
        sectors.append({
            "ticker":            sym,
            "label":             sector_labels.get(sym, sym),
            "price":             float(price) if price else None,
            "change_1d_pct":     round(float(chg1d), 2) if chg1d else None,
            "change_5d_pct":     round(float(chg5d), 2) if chg5d else None,
            "sentiment_polarity": round(float(polarity), 4) if polarity else None,
            "sentiment_confidence": round(float(confidence), 4) if confidence else None,
            "constituent_count": const_count,
            "coverage_pct":      round(float(coverage) * 100, 0) if coverage else None,
            "d_value":           round(float(d_val), 2) if d_val else 0,
            "constituents":      constituents[:8],
            "has_alert":         bool(d_val and d_val > 2.0),
        })
    sectors.sort(key=lambda x: (x["change_5d_pct"] or 0), reverse=True)
    result = {"sectors": sectors, "count": len(sectors)}
    cache_set("sectors", result)
    return result


@app.get("/api/market-heatmap")
def get_market_heatmap():
    hit, val = cached("market_heatmap", 300)
    if hit: return val
    """Returns price performance across all tracked tickers grouped by category."""
    from alphahound.modules.stocks.watchlist.watchlist import (
        CORE_STOCKS, BROAD_ETFS, SECTOR_ETFS, COMMODITY_ETFS,
        INTERNATIONAL_ETFS, MACRO_ETFS
    )
    categories = {
        "US Stocks": CORE_STOCKS[:20],
        "Sectors": SECTOR_ETFS,
        "Commodities": COMMODITY_ETFS,
        "International": INTERNATIONAL_ETFS,
        "Macro/Rates": MACRO_ETFS,
    }
    all_tickers = [t for tickers in categories.values() for t in tickers]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (e.canonical_symbol)
                    e.canonical_symbol, ps.price, ps.change_1d_pct, ps.change_5d_pct, ps.volume
                FROM entities e
                JOIN price_snapshots ps ON ps.entity_id = e.entity_id
                WHERE e.module_id = 'stocks' AND e.kind = 'ticker'
                  AND e.canonical_symbol = ANY(%s)
                ORDER BY e.canonical_symbol, ps.time DESC
            """, (all_tickers,))
            rows = cur.fetchall()

    price_map = {}
    for sym, price, chg1d, chg5d, vol in rows:
        price_map[sym] = {
            "ticker": sym,
            "price": float(price) if price else None,
            "change_1d_pct": round(float(chg1d), 2) if chg1d else None,
            "change_5d_pct": round(float(chg5d), 2) if chg5d else None,
            "volume": int(vol) if vol else None,
        }

    result = {}
    for cat, tickers in categories.items():
        result[cat] = [price_map.get(t, {"ticker": t, "price": None, "change_1d_pct": None, "change_5d_pct": None}) for t in tickers]

    result = {"categories": result, "as_of": datetime.now(timezone.utc).isoformat()}
    cache_set("market_heatmap", result)
    return result


@app.get("/api/sector-detail/{sector}")
def get_sector_detail(sector: str):
    """Drill into a sector's constituent stocks with individual sentiment + price."""
    from alphahound.modules.stocks.watchlist.watchlist import SECTOR_CONSTITUENTS
    constituents = SECTOR_CONSTITUENTS.get(sector.upper(), [])
    if not constituents:
        return {"sector": sector, "constituents": [], "count": 0}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.canonical_symbol,
                    ps.price, ps.change_1d_pct, ps.change_5d_pct,
                    COALESCE(avg_sent.polarity, 0) AS polarity,
                    COALESCE(de.d_value, 0) AS d_value
                FROM entities e
                LEFT JOIN LATERAL (
                    SELECT price, change_1d_pct, change_5d_pct
                    FROM price_snapshots WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) ps ON true
                LEFT JOIN LATERAL (
                    SELECT AVG(polarity) AS polarity FROM sentiment_scores
                    WHERE entity_id = e.entity_id
                      AND time >= now() - interval '24 hours'
                      AND source_class IN ('news_wire','retail_social','institutional_flow')
                ) avg_sent ON true
                LEFT JOIN LATERAL (
                    SELECT d_value FROM divergence_events
                    WHERE entity_id = e.entity_id ORDER BY time DESC LIMIT 1
                ) de ON true
                WHERE e.module_id = 'stocks' AND e.kind = 'ticker'
                  AND e.canonical_symbol = ANY(%s)
                ORDER BY e.canonical_symbol
            """, (constituents,))
            rows = cur.fetchall()

    items = []
    for sym, price, chg1d, chg5d, polarity, d_val in rows:
        items.append({
            "ticker": sym,
            "price": float(price) if price else None,
            "change_1d_pct": round(float(chg1d), 2) if chg1d else None,
            "change_5d_pct": round(float(chg5d), 2) if chg5d else None,
            "sentiment": round(float(polarity), 4) if polarity else 0,
            "d_value": round(float(d_val), 2) if d_val else 0,
            "has_alert": bool(d_val and d_val > 2.0),
        })
    items.sort(key=lambda x: x["change_5d_pct"] or 0, reverse=True)
    return {"sector": sector.upper(), "constituents": items, "count": len(items)}


# ── Adapters ──────────────────────────────────────────────────────────────────

@app.get("/api/adapters")
def get_adapters():
    hit, val = cached("adapters", 120)
    if hit: return val
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (adapter_id)
                    adapter_id, started_at, finished_at, posts_fetched, posts_written, error
                FROM ingest_runs ORDER BY adapter_id, started_at DESC
            """)
            rows = cur.fetchall()
    now = datetime.now(timezone.utc)
    adapters = []
    for r in rows:
        adapter_id, started, finished, fetched, written, error = r
        mins_ago = round((now - started.replace(tzinfo=timezone.utc)).total_seconds() / 60) if started else None
        dur = round((finished - started).total_seconds(), 1) if finished and started else None
        status = "error" if error else ("ok" if mins_ago is not None and mins_ago < 30 else "stale")
        adapters.append({
            "adapter_id": adapter_id, "started_at": started.isoformat() if started else None,
            "mins_ago": mins_ago, "duration_s": dur,
            "posts_fetched": fetched, "posts_written": written,
            "status": status, "error": (error or "")[:80],
        })
    result = {"adapters": adapters, "count": len(adapters)}
    cache_set("adapters", result)
    return result

# ── Hit rate ──────────────────────────────────────────────────────────────────

@app.get("/api/hit-rate")
def get_hit_rate():
    hit, val = cached("hit_rate", 300)
    if hit: return val
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT window_days, hit_rate_pct, total_signals, correct_signals, expectancy, computed_at
                FROM hit_rate ORDER BY computed_at DESC, window_days ASC LIMIT 9
            """)
            rows = cur.fetchall()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM trade_log WHERE venue = 'signal'")
            logged = cur.fetchone()[0]
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM trade_log WHERE pnl IS NOT NULL")
            resolved = cur.fetchone()[0]
    windows = [{
        "window_days": r[0], "hit_rate_pct": r[1], "total_signals": r[2],
        "correct_signals": r[3], "expectancy": r[4],
        "computed_at": r[5].isoformat() if r[5] else None
    } for r in rows]
    result = {"windows": windows, "signals_logged": logged, "signals_resolved": resolved}
    cache_set("hit_rate", result)
    return result


# ── Health Monitor ─────────────────────────────────────────────────────────

@app.get("/api/health")
def get_health():
    """Latest system health report. Serves cached DB version if <20min old."""
    hit, val = cached("health", 60)
    if hit: return val
    from alphahound.engine.health_monitor import get_latest_health, run_health_checks, save_health_report
    cached_report = get_latest_health()
    if cached_report:
        try:
            generated = datetime.fromisoformat(
                cached_report["generated_at"].replace("Z", "+00:00"))
            age_mins = (datetime.now(timezone.utc) - generated).total_seconds() / 60
            if age_mins <= 20:
                cache_set("health", cached_report)
                return cached_report
        except Exception:
            pass
    report = run_health_checks()
    save_health_report(report)
    result = report.to_dict()
    cache_set("health", result)
    return result


# ── Pipeline Status ─────────────────────────────────────────────────────────

@app.get("/api/pipeline")
def get_pipeline():
    """Full pipeline status — every step, timing, rows, errors."""
    hit, val = cached("pipeline", 30)
    if hit: return val
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Last run of each step
            cur.execute("""
                SELECT DISTINCT ON (step)
                    step, status, started_at, duration_ms, rows_affected, error
                FROM pipeline_runs
                WHERE started_at >= now() - interval '2 hours'
                ORDER BY step, started_at DESC;
            """)
            steps = cur.fetchall()

            # Last full cycle time
            cur.execute("""
                SELECT MAX(started_at) FROM pipeline_runs
                WHERE step = 'health-check' AND status = 'ok'
                AND started_at >= now() - interval '2 hours';
            """)
            last_cycle = cur.fetchone()[0]

            # Ingest adapter status
            cur.execute("""
                SELECT DISTINCT ON (adapter_id)
                    adapter_id, started_at, finished_at, posts_fetched, posts_written, error
                FROM ingest_runs
                WHERE started_at >= now() - interval '1 hour'
                ORDER BY adapter_id, started_at DESC;
            """)
            adapters = cur.fetchall()

            # Scoring backlog -- fast approximation using counts
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM raw_posts WHERE time >= now() - interval '24 hours') -
                    (SELECT COUNT(*) FROM sentiment_scores WHERE time >= now() - interval '24 hours')
                    AS backlog;
            """)
            backlog = max(0, cur.fetchone()[0] or 0)

    step_list = []
    for step, status, started, dur_ms, rows, error in steps:
        mins_ago = int((now - started.replace(tzinfo=timezone.utc)).total_seconds() / 60)
        step_list.append({
            "step":      step,
            "status":    status,
            "mins_ago":  mins_ago,
            "duration_s": round(dur_ms/1000, 1) if dur_ms else None,
            "rows":      rows or 0,
            "error":     (error or "")[:100],
            "time_pt":   fmt_et(started),
        })

    adapter_list = []
    for adapter_id, started, finished, fetched, written, error in adapters:
        dur = round((finished - started).total_seconds(), 1) if finished and started else None
        adapter_list.append({
            "adapter_id": adapter_id,
            "duration_s": dur,
            "fetched":    fetched or 0,
            "written":    written or 0,
            "error":      (error or "")[:80],
            "ok":         not bool(error),
        })

    mins_since_cycle = int((now - last_cycle.replace(tzinfo=timezone.utc)).total_seconds() / 60) if last_cycle else None

    # Scoring mode
    scoring_mode = "CATCHUP" if backlog > 3000 else "NORMAL"

    result = {
        "steps":            step_list,
        "adapters":         adapter_list,
        "backlog":          backlog,
        "scoring_mode":     scoring_mode,
        "last_cycle_mins":  mins_since_cycle,
        "last_cycle_pt":    fmt_et(last_cycle) if last_cycle else None,
        "cycle_healthy":    mins_since_cycle is not None and mins_since_cycle < 20,
    }
    cache_set("pipeline", result)
    return result


# ── Execution log ──────────────────────────────────────────────────────────────

@app.get("/api/execution-log")
def get_execution_log():
    """Why did the executor fire or skip each signal today."""
    hit, val = cached("exec_log", 30)
    if hit: return val
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.canonical_symbol, tl.side, tl.size, tl.venue,
                    tl.alpaca_status, tl.alpaca_order_id,
                    tl.notes, tl.time
                FROM trade_log tl
                JOIN entities e ON e.entity_id = tl.entity_id
                WHERE tl.time >= now() - interval '24 hours'
                ORDER BY tl.time DESC LIMIT 50;
            """)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]

    entries = []
    for row in rows:
        d = dict(zip(cols, row))
        notes = d.get("notes") or {}
        # Determine what happened
        venue   = d.get("venue") or ""
        alpaca  = d.get("alpaca_order_id")
        status  = d.get("alpaca_status") or ""
        if alpaca and status in ("filled", "accepted", "pending_new"):
            outcome = "EXECUTED"
        elif venue in ("blocked", "rejected"):
            outcome = "BLOCKED"
        elif venue == "signal" and not alpaca:
            outcome = "SIGNAL_ONLY"
        else:
            outcome = venue.upper() if venue else "UNKNOWN"

        reason = ""
        if isinstance(notes, dict):
            reason = notes.get("block_reason") or notes.get("skip_reason") or notes.get("reason") or ""
            if not reason and notes.get("tech_gate"):
                tg = notes["tech_gate"]
                reason = "Tech gate: {}/{} — {}".format(
                    tg.get("score","?"), 5, tg.get("verdict","?"))

        entries.append({
            "ticker":   d["canonical_symbol"],
            "side":     d.get("side"),
            "size":     float(d.get("size") or 0),
            "outcome":  outcome,
            "reason":   reason[:120],
            "status":   status,
            "time_pt":  fmt_et(d["time"]),
        })

    result = {"entries": entries, "count": len(entries)}
    cache_set("exec_log", result)
    return result


# ── Ticker Lookup ─────────────────────────────────────────────────────────

@app.get("/api/lookup/{ticker}")
def lookup_ticker(ticker: str):
    """Full signal detail for any ticker."""
    ticker = ticker.upper().strip()
    PT = ZoneInfo("America/Los_Angeles")
    now = datetime.now(timezone.utc)

    def fmt_pt(dt):
        if not dt: return None
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(PT).strftime("%b %d %I:%M %p PT")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Entity lookup
            cur.execute(
                "SELECT entity_id FROM entities WHERE canonical_symbol=%s AND module_id='stocks' LIMIT 1;",
                (ticker,)
            )
            row = cur.fetchone()
            if not row:
                return {"error": "{} not found in watchlist".format(ticker)}
            entity_id = row[0]

            # Price snapshot
            cur.execute("""
                SELECT price, change_1d_pct, change_5d_pct, change_vs_spy, time
                FROM price_snapshots WHERE entity_id=%s ORDER BY time DESC LIMIT 1
            """, (entity_id,))
            pr = cur.fetchone()
            price_snapshot = None
            if pr:
                price_snapshot = {
                    "price": float(pr[0]) if pr[0] else None,
                    "change_1d_pct": float(pr[1]) if pr[1] else None,
                    "change_5d_pct": float(pr[2]) if pr[2] else None,
                    "change_vs_spy": float(pr[3]) if pr[3] else None,
                    "time_pt": fmt_pt(pr[4]),
                }

            # Divergence events last 7 days
            cur.execute("""
                SELECT d_value, p_value, components, time
                FROM divergence_events WHERE entity_id=%s
                AND time >= now() - interval '7 days'
                ORDER BY time DESC LIMIT 10
            """, (entity_id,))
            div_rows = cur.fetchall()
            divergence_events = []
            for d_val, p_val, comps, t in div_rows:
                c = dict(comps) if comps else {}
                c.pop("narrative", None)
                ws = sum(float(v) for v in c.values() if isinstance(v, (int,float)))
                direction = "LONG" if ws > 0.05 else "SHORT" if ws < -0.05 else "WATCH"
                divergence_events.append({
                    "d_value": round(float(d_val), 3),
                    "p_value": round(float(p_val), 4),
                    "direction": direction,
                    "components": {k: round(float(v), 4) for k,v in c.items() if isinstance(v,(int,float))},
                    "time_pt": fmt_pt(t),
                })

            # Sentiment last 24h
            cur.execute("""
                SELECT source_class, AVG(polarity), AVG(confidence), COUNT(*)
                FROM sentiment_scores WHERE entity_id=%s
                AND time >= now() - interval '24 hours'
                GROUP BY source_class ORDER BY AVG(polarity) DESC
            """, (entity_id,))
            sentiment = [{
                "source_class": r[0],
                "avg_polarity": round(float(r[1]), 4) if r[1] else 0,
                "avg_confidence": round(float(r[2]), 4) if r[2] else 0,
                "count": r[3],
            } for r in cur.fetchall()]

            # Options flow last 48h
            cur.execute("""
                SELECT contract_type, sentiment, premium, unusual_score, expiry, time
                FROM options_flow WHERE entity_id=%s
                AND time >= now() - interval '48 hours'
                ORDER BY time DESC LIMIT 5
            """, (entity_id,))
            options_flow = [{
                "contract_type": r[0], "sentiment": r[1],
                "premium": float(r[2]) if r[2] else None,
                "unusual_score": float(r[3]) if r[3] else None,
                "expiry": r[4].isoformat() if r[4] else None,
                "time_et": fmt_et(r[5]) if r[5] else None,
            } for r in cur.fetchall()]

            # Rhyme matches — optional table
            try:
                cur.execute("""
                    SELECT event_name, similarity, prediction, confidence
                    FROM rhyme_matches WHERE entity_id=%s
                    ORDER BY similarity DESC LIMIT 3
                """, (entity_id,))
                rhyme_matches = [{
                    "event_name": r[0], "similarity": round(float(r[1]),3) if r[1] else 0,
                    "prediction": r[2], "confidence": round(float(r[3]),3) if r[3] else None,
                } for r in cur.fetchall()]
            except Exception:
                rhyme_matches = []

            # Trade history
            cur.execute("""
                SELECT side, size, price, alpaca_status, pnl, time, closed_at
                FROM trade_log WHERE entity_id=%s
                ORDER BY time DESC LIMIT 5
            """, (entity_id,))
            trades = [{
                "side": r[0], "size": float(r[1]) if r[1] else 0,
                "price": float(r[2]) if r[2] else None,
                "alpaca_status": r[3],
                "pnl": round(float(r[4]), 2) if r[4] is not None else None,
                "time_pt": fmt_pt(r[5]),
                "closed": r[6] is not None,
            } for r in cur.fetchall()]

    return {
        "ticker":           ticker,
        "entity_id":        str(entity_id),
        "price_snapshot":   price_snapshot,
        "divergence_events": divergence_events,
        "sentiment":        sentiment,
        "options_flow":     options_flow,
        "rhyme_matches":    rhyme_matches,
        "trades":           trades,
        "as_of_pt":         fmt_pt(now),
    }


@app.get("/api/options-trades")
def get_options_trades():
    """Options trade log from options_trade_log table. Sprint 12."""
    hit, val = cached("options_trades", 30)
    if hit: return val
    try:
        from alphahound.engine.execution.options_executor import _ensure_options_log_table
        _ensure_options_log_table()
    except Exception:
        pass
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, ticker, structure_type, direction, contracts,
                       estimated_debit, catalyst_type, catalyst_date,
                       composite_score, time, legs_json, status,
                       closed_at, pnl, notes, order_ids
                FROM options_trade_log
                ORDER BY time DESC
                LIMIT 200;
            """)
            cols   = [d.name for d in cur.description]
            rows   = [dict(zip(cols, r)) for r in cur.fetchall()]
    trades = []
    for r in rows:
        debit  = float(r.get("estimated_debit") or 0)
        pnl    = float(r.get("pnl") or 0) if r.get("pnl") is not None else None
        status = r.get("status", "placed")
        trades.append({
            "id":             r["id"],
            "ticker":         r["ticker"],
            "structure_type": r["structure_type"],
            "direction":      r.get("direction", "NEUTRAL"),
            "contracts":      r.get("contracts") or 1,
            "estimated_debit": round(debit, 2),
            "catalyst_type":  r.get("catalyst_type"),
            "catalyst_date":  r["catalyst_date"].isoformat() if r.get("catalyst_date") else None,
            "composite_score": float(r.get("composite_score") or 0),
            "time":           r["time"].isoformat(),
            "time_et":        fmt_et(r["time"]),
            "closed_at":      r["closed_at"].isoformat() if r.get("closed_at") else None,
            "pnl":            round(pnl, 2) if pnl is not None else None,
            "status":         status,
            "notes":          r.get("notes") or "",
        })
    total_pnl = sum(t["pnl"] for t in trades if t["pnl"] is not None)
    wins      = sum(1 for t in trades if t["pnl"] and t["pnl"] > 0)
    losses    = sum(1 for t in trades if t["pnl"] and t["pnl"] < 0)
    open_     = sum(1 for t in trades if t["status"] == "placed" and not t["closed_at"])
    result    = {
        "trades":    trades,
        "count":     len(trades),
        "total_pnl": round(total_pnl, 2),
        "wins":      wins,
        "losses":    losses,
        "open":      open_,
    }
    cache_set("options_trades", result)
    return result


def get_options_positions():
    """Current open options positions with live P&L from Alpaca. Sprint 12."""
    hit, val = cached("options_positions", 60)
    if hit: return val
    try:
        from alphahound.engine.execution.options_monitor import get_open_positions_summary
        result = {"positions": get_open_positions_summary(), "as_of": now_utc().isoformat(), "as_of_et": fmt_et(now_utc())}
    except Exception as e:
        result = {"positions": [], "error": str(e), "as_of": now_utc().isoformat(), "as_of_et": fmt_et(now_utc())}
    cache_set("options_positions", result)
    return result


# ── Convergence Engine (Sprint 11) ──────────────────────────────────────────

@app.get("/api/convergence")
def get_convergence():
    """Latest convergence signals from the Multi-Pillar Convergence Engine."""
    hit, val = cached("convergence", 60)
    if hit: return val

    try:
        from alphahound.engine.scoring.convergence_scorer import get_super_signals, get_ticker_score
        from alphahound.engine.signals.macro_context import get_macro_context

        super_rows = get_super_signals(hours_back=24)
        macro = get_macro_context()

        # Known non-executable tickers (chain too short for current price)
        NON_EXECUTABLE = {'MU'}  # MU chain maxes at $890, price ~$1035

        def fmt_signal(row):
            bd = row.get("pillar_breakdown") or {}
            ticker = row["ticker"]
            executable = ticker not in NON_EXECUTABLE
            return {
                "ticker":                ticker,
                "composite_score":       row["composite_score"],
                "pillars_fired":         row["pillars_fired"],
                "super_signal":          True,
                "direction":             row["direction"],
                "catalyst_date":         row["catalyst_date"].isoformat() if row.get("catalyst_date") else None,
                "catalyst_type":         row.get("catalyst_type"),
                "recommended_structure": row.get("recommended_structure"),
                "narrative":             row.get("narrative"),
                "time_et":               fmt_et(row["time"]) if row.get("time") else None,
                "pillar_breakdown":      bd,
                "structure":             bd.get("structure"),
                "executable":            executable,
                "skip_reason":           "Options chain too short for current price ($1035 > $890 max listed strike)" if not executable else None,
            }

        # Developing signals (score 2.5-3.9) from last convergence scan
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (ticker)
                        time, ticker, composite_score, pillars_fired, super_signal,
                        direction, catalyst_date, catalyst_type,
                        recommended_structure, narrative, pillar_breakdown
                    FROM convergence_signals
                    WHERE time >= now() - interval '4 hours'
                      AND composite_score >= 2.5
                      AND super_signal = FALSE
                    ORDER BY ticker, time DESC;
                """
                )
                cols = [d.name for d in cur.description]
                watch_rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        watching = []
        for row in sorted(watch_rows, key=lambda r: r["composite_score"], reverse=True)[:10]:
            bd = row.get("pillar_breakdown") or {}
            watching.append({
                "ticker":           row["ticker"],
                "composite_score":  row["composite_score"],
                "pillars_fired":    row["pillars_fired"],
                "super_signal":     False,
                "direction":        row["direction"],
                "catalyst_date":    row["catalyst_date"].isoformat() if row.get("catalyst_date") else None,
                "catalyst_type":    row.get("catalyst_type"),
                "narrative":        row.get("narrative"),
                "time_et":          fmt_et(row["time"]) if row.get("time") else None,
                "pillar_breakdown": bd,
            })

        result = {
            "super_signals": [fmt_signal(r) for r in super_rows],
            "watching":      watching,
            "macro_verdict": macro.verdict.value,
            "macro_score":   macro.score,
            "as_of":         now_utc().isoformat(),
            "as_of_et":      fmt_et(now_utc()),
        }
    except Exception as e:
        result = {
            "super_signals": [], "watching": [],
            "macro_verdict": "UNKNOWN", "macro_score": 0,
            "error": str(e),
            "as_of": now_utc().isoformat(), "as_of_et": fmt_et(now_utc()),
        }
    cache_set("convergence", result)
    return result


@app.get("/api/convergence/history")
def get_convergence_history(days_back: int = Query(default=7, ge=1, le=90)):
    """Convergence signal history for the Trades / History tab."""
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (ticker, date_trunc('hour', time))
                        time, ticker, composite_score, pillars_fired,
                        super_signal, direction, catalyst_date, catalyst_type,
                        recommended_structure, narrative
                    FROM convergence_signals
                    WHERE time >= %s
                    ORDER BY ticker, date_trunc('hour', time) DESC, time DESC;
                """, (since,))
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        today = datetime.now(timezone.utc).date()
        signals = []
        for r in sorted(rows, key=lambda x: x['time'], reverse=True):
            cat_date = r.get('catalyst_date')
            days_to  = (cat_date - today).days if cat_date else None
            signals.append({
                'ticker':           r['ticker'],
                'composite_score':  r['composite_score'],
                'pillars_fired':    r['pillars_fired'],
                'super_signal':     r['super_signal'],
                'direction':        r['direction'],
                'catalyst_type':    r.get('catalyst_type'),
                'catalyst_date':    cat_date.isoformat() if cat_date else None,
                'days_to_catalyst': days_to,
                'recommended_structure': r.get('recommended_structure'),
                'narrative':        r.get('narrative'),
                'time_et':          fmt_et(r['time']),
            })
        return {'signals': signals, 'count': len(signals), 'days_back': days_back}
    except Exception as e:
        return {'signals': [], 'error': str(e), 'days_back': days_back}


@app.get("/api/convergence/structure")
def get_convergence_structure(ticker: str = Query(...)):
    """Get the options structure plan for a ticker's current convergence signal."""
    ticker = ticker.upper().strip()
    try:
        from alphahound.engine.scoring.convergence_scorer import score_ticker
        from alphahound.engine.execution.options_structure import recommend_structure

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                    (ticker,)
                )
                row = cur.fetchone()
        if not row:
            return {"error": f"{ticker} not found"}

        entity_id = str(row[0])
        result    = score_ticker(entity_id, ticker)
        if result is None:
            return {"error": f"No convergence data for {ticker}"}

        from alphahound.engine.execution.alpaca_broker import get_broker
        try:
            equity = float(get_broker().get_account().get("equity", 20000))
        except Exception:
            equity = 20000.0

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

        return {
            "ticker":    ticker,
            "score":     result.composite_score,
            "direction": result.direction,
            "structure": structure.to_dict() if structure else None,
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


# ── Assessment endpoints ─────────────────────────────────────────────────────

@app.get("/api/assessment")
def get_assessment(limit: int = Query(default=1, ge=1, le=100)):
    """Latest assessment from the assessment service. Reads from JSON file for speed, DB for history."""
    import json as _json
    from pathlib import Path as _Path
    assessment_file = _Path(r"C:\alphahound_project\docs\status\assessment.json")
    hit, val = cached("assessment", 30)
    if hit and limit == 1:
        return val

    # Fast path: read from assessment.json file
    if limit == 1 and assessment_file.exists():
        try:
            data = _json.loads(assessment_file.read_text())
            result = {"latest": data, "history": [data], "count": 1, "source": "file"}
            cache_set("assessment", result)
            return result
        except Exception:
            pass  # fall through to DB

    # DB path: history or file missing
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'assessments'
                )
            """)
            exists = cur.fetchone()[0]
            if not exists:
                return {"latest": None, "history": [], "message": "Assessment service not yet run. Run: .venv\\Scripts\\python.exe scripts\\assessment_service.py"}

            cur.execute("""
                SELECT id, assessed_at, status, payload
                FROM assessments
                ORDER BY assessed_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()

    if not rows:
        return {"latest": None, "history": [], "message": "No assessments yet"}

    def fmt_row(row):
        id_, ts, status, payload = row
        return {"id": id_, "assessed_at": fmt_et(ts), "status": status, **payload}

    result = {
        "latest":  fmt_row(rows[0]),
        "history": [fmt_row(r) for r in rows],
        "count":   len(rows),
        "source":  "db",
    }
    cache_set("assessment", result)
    return result


@app.get("/api/assessment/history")
def get_assessment_history(hours: int = Query(default=24, ge=1, le=168)):
    """Assessment history for the last N hours."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'assessments'
                )
            """)
            if not cur.fetchone()[0]:
                return {"assessments": [], "message": "Assessment service not yet run"}

            cur.execute("""
                SELECT id, assessed_at, status,
                       payload->>'as_of_pt'         as as_of_pt,
                       payload->>'macro_verdict'     as macro_verdict,
                       payload->>'engine_status'     as engine_status,
                       (payload->>'executable_count')::int  as executable_count,
                       (payload->>'monitoring_count')::int  as monitoring_count,
                       (payload->>'executed_today')::int    as executed_today,
                       (payload->>'max_d')::float           as max_d,
                       (payload->>'size_modifier')::float   as size_modifier,
                       payload->'why_not_trading'    as why_not_trading,
                       payload->'findings'           as findings,
                       payload->'actions'            as actions
                FROM assessments
                WHERE assessed_at >= now() - (%s || ' hours')::interval
                ORDER BY assessed_at DESC
            """, (str(hours),))
            rows = cur.fetchall()

    cols = [
        "id", "assessed_at", "status", "as_of_pt", "macro_verdict",
        "engine_status", "executable_count", "monitoring_count",
        "executed_today", "max_d", "size_modifier",
        "why_not_trading", "findings", "actions"
    ]
    return {
        "assessments": [dict(zip(cols, r)) for r in rows],
        "hours":       hours,
        "count":       len(rows),
    }
