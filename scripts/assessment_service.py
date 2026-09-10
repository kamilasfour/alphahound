"""
AlphaHound Assessment Service v3 — Sprint 12
Convergence engine based. No divergence D-scores.
Primary signals: convergence_signals table (super signals)
Output: docs/status/assessment.json + DB assessments table
"""
import sys, os, json, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

PT     = ZoneInfo("America/Los_Angeles")
BASE   = "http://localhost:8080"
STATUS = Path(r"C:\alphahound_project\docs\status")

SILENT = {"stocks.massive_history","stocks.earnings_calendar","stocks.stocktwits",
          "stocks.alpha_vantage","stocks.edgar","stocks.kalshi"}
LOW_WRITE_RATIO_OK = {"stocks.finnhub","stocks.yahoo_finance","stocks.substack",
                      "stocks.unusual_whales","stocks.massive"}

def read_json(filename):
    try: return json.loads((STATUS / filename).read_text())
    except: return {}

def fetch(path):
    try:
        r = requests.get(f"{BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except: return {}

def run_assessment():
    now    = datetime.now(timezone.utc)
    now_pt = now.astimezone(PT)

    summary   = read_json("system_summary.json")
    pipeline  = read_json("pipeline_health.json")
    ingestion = read_json("ingestion_health.json")

    macro     = fetch("/api/macro")
    positions = fetch("/api/positions")

    findings = []
    actions  = []
    status   = "GREEN"

    # ── Pipeline ──────────────────────────────────────────────────────────
    pipe_steps  = pipeline.get("steps", {})
    last_cycle  = pipeline.get("last_cycle_age_mins", 0)
    failed      = [k for k,v in pipe_steps.items() if v.get("status") != "ok"
                   and k not in {"divergence-scan","score-sectors","trade-advice"}]
    stale       = [k for k,v in pipe_steps.items()
                   if v.get("age_mins", 0) > 20
                   and k not in {"massive-history","earnings-calendar","divergence-scan"}]

    if failed:
        status = "RED"
        findings.append(f"PIPELINE ERROR: {', '.join(failed)}")
        actions.append(f"Investigate: {', '.join(failed)}")
    elif stale:
        status = "YELLOW"
        findings.append(f"PIPELINE STALE: {', '.join(stale)}")
    elif last_cycle > 10:
        status = "YELLOW"
        findings.append(f"PIPELINE SLOW: last cycle {last_cycle:.0f}m ago")
    else:
        findings.append(f"PIPELINE: healthy, last cycle {last_cycle:.1f}m ago")

    # ── Adapters ──────────────────────────────────────────────────────────
    last_runs = ingestion.get("last_runs", {})
    for adapter_id, run in last_runs.items():
        if adapter_id in SILENT: continue
        fetched = run.get("fetched", 0)
        written = run.get("written", 0)
        if adapter_id in LOW_WRITE_RATIO_OK: continue
        if fetched > 0 and written == 0:
            status = "RED"
            findings.append(f"ADAPTER BUG: {adapter_id} fetched {fetched} but wrote 0")
            actions.append(f"Fix {adapter_id} write bug")

    # ── Macro ─────────────────────────────────────────────────────────────
    macro_verdict = macro.get("verdict", "UNKNOWN")
    macro_score   = macro.get("score", 0)
    size_mod      = macro.get("size_modifier", 0)

    if macro_verdict == "RISK_OFF":
        findings.append(f"MACRO RISK_OFF (score={macro_score:.3f}): size_modifier={size_mod}% — trades suppressed")
        actions.append("No trades until macro flips RISK_ON")
    else:
        findings.append(f"MACRO {macro_verdict} (score={macro_score:+.3f}, size={size_mod}%)")

    # ── Convergence signals ───────────────────────────────────────────────
    super_signals = []
    watching      = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Super signals last 2 hours
                cur.execute("""
                    SELECT ticker, composite_score, pillars_fired, direction,
                           catalyst_type, catalyst_date, recommended_structure, narrative
                    FROM convergence_signals
                    WHERE super_signal = TRUE AND time >= now() - interval '2 hours'
                    ORDER BY composite_score DESC;
                """)
                cols = [d.name for d in cur.description]
                super_signals = [dict(zip(cols, r)) for r in cur.fetchall()]

                # Developing signals (2.5-3.9)
                cur.execute("""
                    SELECT DISTINCT ON (ticker) ticker, composite_score, pillars_fired, direction
                    FROM convergence_signals
                    WHERE composite_score >= 2.5 AND super_signal = FALSE
                      AND time >= now() - interval '2 hours'
                    ORDER BY ticker, time DESC;
                """)
                cols2 = [d.name for d in cur.description]
                watching = [dict(zip(cols2, r)) for r in cur.fetchall()]
    except Exception as e:
        findings.append(f"CONVERGENCE DB ERROR: {e}")

    if super_signals:
        for s in super_signals:
            days = (s['catalyst_date'] - now.date()).days if s.get('catalyst_date') else None
            cat_str = f" — {s['catalyst_type']} in {days}d" if days else ""
            findings.append(
                f"SUPER SIGNAL: {s['ticker']} {s['direction']} score={s['composite_score']:.2f} "
                f"({s['pillars_fired']} pillars){cat_str}"
            )
    else:
        watch_str = f"{len(watching)} developing" if watching else "0 developing"
        findings.append(f"NO SUPER SIGNALS — {watch_str} signals building")

    # ── Options positions ─────────────────────────────────────────────────
    open_pos  = positions.get("positions", [])
    pnl_total = sum(p.get("unrealized_pnl", 0) or 0 for p in open_pos)
    open_opts = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ticker, structure_type, estimated_debit, contracts
                    FROM options_trade_log
                    WHERE status = 'placed' AND closed_at IS NULL
                    ORDER BY time DESC;
                """)
                cols3 = [d.name for d in cur.description]
                open_opts = [dict(zip(cols3, r)) for r in cur.fetchall()]
    except: pass

    if open_opts:
        findings.append(f"OPTIONS POSITIONS: {len(open_opts)} open — {', '.join(o['ticker'] for o in open_opts)}")
    elif open_pos:
        findings.append(f"POSITIONS: {len(open_pos)} open, P&L ${pnl_total:+.2f}")
    else:
        equity = positions.get("equity", 50000)
        findings.append(f"POSITIONS: None open — ${equity:,.0f} available")

    # ── Build ─────────────────────────────────────────────────────────────
    assessment = {
        "status":           status,
        "as_of_utc":        now.isoformat(),
        "as_of_pt":         now_pt.strftime("%a %b %d %I:%M %p PT"),
        "market_open":      summary.get("market_open", False),
        "engine_status":    "live",
        "macro_verdict":    macro_verdict,
        "macro_score":      round(macro_score, 3),
        "size_modifier":    size_mod,
        "last_cycle_mins":  round(last_cycle, 1),
        "super_signal_count": len(super_signals),
        "watching_count":   len(watching),
        "super_signals":    super_signals,
        "options_positions": open_opts,
        "positions_open":   len(open_opts) or len(open_pos),
        "pnl_unrealized":   round(pnl_total, 2),
        "executed_today":   0,
        "why_not_trading":  (
            ["Macro RISK_OFF: trades suppressed"] if macro_verdict == "RISK_OFF"
            else (["No super signals — convergence threshold not met"] if not super_signals else [])
        ),
        "findings":  findings,
        "actions":   actions,
        "posts_24h": sum(v.get("posts", 0) for v in ingestion.get("posts_24h", {}).values()),
    }

    # ── Write ─────────────────────────────────────────────────────────────
    out = STATUS / "assessment.json"
    out.write_text(json.dumps(assessment, indent=2))

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS assessments (
                        id SERIAL PRIMARY KEY,
                        assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        status TEXT NOT NULL, payload JSONB NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_assessments_time ON assessments(assessed_at DESC);
                    INSERT INTO assessments (assessed_at, status, payload) VALUES (%s, %s, %s);
                """, (now, status, json.dumps(assessment)))
            conn.commit()
    except Exception as e:
        print(f"  DB write failed: {e}")

    # ── Print ──────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  ASSESSMENT v3 — {assessment['as_of_pt']}  [{status}]")
    print(f"{'='*65}")
    print(f"  Macro: {macro_verdict} ({macro_score:+.3f})")
    print(f"  Super signals: {len(super_signals)}  |  Developing: {len(watching)}")
    print(f"  Options positions open: {len(open_opts)}")
    for f in findings:
        icon = "🔴" if "ERROR" in f or "BUG" in f else "🟡" if "STALE" in f or "RISK_OFF" in f else "🟢"
        print(f"    {icon}  {f}")
    if actions:
        print(f"\n  ACTIONS:")
        for a in actions: print(f"    ⚠  {a}")
    print(f"\n  Written → {out}\n{'='*65}\n")
    return assessment

if __name__ == "__main__":
    run_assessment()
