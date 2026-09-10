"""
AlphaHound System Status Monitor
Runs every 30 minutes via Windows Task Scheduler.
Reads actual DB state, cross-checks against expected thresholds,
writes status files to docs/status/, flags anomalies to health_checks table.

Usage:
    python scripts/status_monitor.py

Scheduled: AlphaHound-StatusMonitor every 30 min
Output: C:\\alphahound_project\\docs\\status\\*.json
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

from alphahound.engine.storage import get_conn
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pathlib

PT  = ZoneInfo("America/Los_Angeles")
ET  = ZoneInfo("America/New_York")
now = datetime.now(timezone.utc)

STATUS_DIR = pathlib.Path(r"C:\alphahound_project\docs\status")
STATUS_DIR.mkdir(parents=True, exist_ok=True)

# ── Thresholds ────────────────────────────────────────────────
THRESHOLDS = {
    "ingestion": {
        "apewisdom_min_per_cycle":    400,
        "finnhub_min_per_hour":        50,
        "unusual_whales_min_4h":      100,
        "quiver_min_per_day":         500,
        "substack_min_per_day":        20,
        "max_adapter_age_mins":        30,
    },
    "scoring": {
        "max_backlog":               8000,   # warn above 8k
        "critical_backlog":         20000,   # critical above 20k
        "min_scored_per_run":          50,
        "max_score_run_secs":         120,
        "news_wire_score_pct_min":     80,
        "retail_score_pct_min":        80,
    },
    "pipeline": {
        "max_cycle_age_mins":          20,
        "max_ingest_secs":            150,
        "max_divergence_zero_streak":   4,   # 4 cycles = 1 hour
    },
    "signals": {
        "min_signals_market_hours":     1,
        "executable_d_threshold":     4.0,
    }
}


def collect_ingestion_status(cur, now):
    since_1h  = now - timedelta(hours=1)
    since_4h  = now - timedelta(hours=4)
    since_24h = now - timedelta(hours=24)

    # Posts per adapter last 24h
    cur.execute("""
        SELECT adapter_id, COUNT(*) as posts, MAX(time) as latest
        FROM raw_posts WHERE time >= %s
        GROUP BY adapter_id ORDER BY posts DESC;
    """, (since_24h,))
    posts_24h = {r[0]: {"posts": r[1], "latest": r[2].isoformat() if r[2] else None}
                 for r in cur.fetchall()}

    # Last ingest run per adapter
    cur.execute("""
        SELECT DISTINCT ON (adapter_id)
            adapter_id, started_at, finished_at, posts_fetched, posts_written, error
        FROM ingest_runs
        ORDER BY adapter_id, started_at DESC;
    """)
    last_runs = {}
    for adapter_id, started, finished, fetched, written, error in cur.fetchall():
        age_mins = round((now - started.replace(tzinfo=timezone.utc)).total_seconds() / 60, 1)
        dur = round((finished - started).total_seconds(), 1) if finished and started else None
        last_runs[adapter_id] = {
            "age_mins":  age_mins,
            "duration_s": dur,
            "fetched":   fetched or 0,
            "written":   written or 0,
            "error":     error,
            "ok":        not bool(error),
        }

    # Options flow count
    cur.execute("SELECT COUNT(*) FROM options_flow WHERE time >= %s;", (since_4h,))
    options_4h = cur.fetchone()[0]

    # Congressional trades
    cur.execute("SELECT COUNT(*) FROM raw_posts WHERE adapter_id='stocks.quiver' AND time >= %s;", (since_24h,))
    quiver_24h = cur.fetchone()[0]

    # Enabled adapters
    cur.execute("SELECT adapter_id, enabled FROM source_adapters ORDER BY adapter_id;")
    adapter_status = {r[0]: r[1] for r in cur.fetchall()}

    # Problems
    problems = []
    t = THRESHOLDS["ingestion"]

    for adapter_id, enabled in adapter_status.items():
        if not enabled:
            continue  # skip disabled adapters entirely
        if adapter_id == 'stocks.stocktwits':
            continue  # permanently disabled, skip
        run = last_runs.get(adapter_id, {})
        if run.get("error"):
            problems.append({"severity": "RED", "msg": "{} error: {}".format(adapter_id, run["error"][:60])})
        elif run.get("age_mins", 999) > t["max_adapter_age_mins"]:
            # Skip price_data adapters after hours
            et_hour = now.astimezone(ET).hour
            mkt_open = 9 <= et_hour < 16
            source_class = "price_data" if "massive" in adapter_id else ""
            if mkt_open or source_class != "price_data":
                problems.append({"severity": "YELLOW", "msg": "{} last ran {:.0f}m ago".format(
                    adapter_id, run.get("age_mins", 999))})
        if adapter_id == "stocks.quiver" and run.get("fetched", 0) > 0 and run.get("written", 0) == 0:
            problems.append({"severity": "RED", "msg": "quiver: {} fetched, 0 wrote".format(run["fetched"])})

    if quiver_24h == 0:
        problems.append({"severity": "RED", "msg": "0 congressional trades written in 24h"})

    return {
        "as_of":        now.isoformat(),
        "as_of_pt":     now.astimezone(PT).strftime("%Y-%m-%d %I:%M %p PT"),
        "posts_24h":    posts_24h,
        "last_runs":    last_runs,
        "options_4h":   options_4h,
        "quiver_24h":   quiver_24h,
        "adapter_status": adapter_status,
        "problems":     problems,
        "overall":      "RED" if any(p["severity"]=="RED" for p in problems)
                        else "YELLOW" if problems else "GREEN",
    }


def collect_scoring_status(cur, now):
    since_1h  = now - timedelta(hours=1)
    since_24h = now - timedelta(hours=24)

    # Backlog
    cur.execute("""
        SELECT source_class, COUNT(*) as unscored
        FROM raw_posts rp
        WHERE source_class IN ('news_wire','retail_social','analyst_curated')
        AND NOT EXISTS (
            SELECT 1 FROM sentiment_scores ss
            WHERE ss.entity_id=rp.entity_id AND ss.source_class=rp.source_class AND ss.time=rp.time
        )
        AND rp.time >= now() - interval '7 days'
        GROUP BY source_class;
    """)
    backlog = {r[0]: r[1] for r in cur.fetchall()}
    total_backlog = sum(backlog.values())

    # Score runs last 24h
    cur.execute("""
        SELECT started_at, duration_ms/1000 as secs, rows_affected
        FROM pipeline_runs
        WHERE step='score-new' AND status='ok'
        AND started_at >= %s
        ORDER BY started_at DESC LIMIT 20;
    """, (since_24h,))
    score_runs = [{"time": r[0].isoformat(), "secs": round(r[1] or 0, 1), "rows": r[2] or 0}
                  for r in cur.fetchall()]

    # Coverage last 24h
    cur.execute("""
        SELECT rp.source_class,
               COUNT(*) as total,
               SUM(CASE WHEN ss.entity_id IS NOT NULL THEN 1 ELSE 0 END) as scored
        FROM raw_posts rp
        LEFT JOIN sentiment_scores ss
            ON ss.entity_id=rp.entity_id AND ss.source_class=rp.source_class AND ss.time=rp.time
        WHERE rp.source_class IN ('news_wire','retail_social','analyst_curated')
        AND rp.time >= %s
        GROUP BY rp.source_class;
    """, (since_24h,))
    coverage = {}
    for sc, total, scored in cur.fetchall():
        pct = round(scored/total*100) if total > 0 else 0
        coverage[sc] = {"total": total, "scored": scored, "pct": pct}

    # Watermarks
    cur.execute("SELECT source_class, last_scored_at FROM scoring_watermark;")
    watermarks = {}
    for sc, wm in cur.fetchall():
        if wm:
            age_h = round((now - wm.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
            watermarks[sc] = {"last_scored_at": wm.isoformat(), "age_hours": age_h}

    # Problems
    problems = []
    t = THRESHOLDS["scoring"]

    if total_backlog > t["critical_backlog"]:
        problems.append({"severity": "RED", "msg": "Backlog {:,} exceeds critical threshold {:,}".format(
            total_backlog, t["critical_backlog"])})
    elif total_backlog > t["max_backlog"]:
        problems.append({"severity": "YELLOW", "msg": "Backlog {:,} above warning threshold {:,}".format(
            total_backlog, t["max_backlog"])})

    for sc, wm in watermarks.items():
        if wm["age_hours"] > 2:
            problems.append({"severity": "RED", "msg": "Watermark drift: {} last scored {:.1f}h ago — DELETE FROM scoring_watermark".format(
                sc, wm["age_hours"])})

    for sc, cov in coverage.items():
        min_pct = t.get("{}_score_pct_min".format(sc.replace("_social","").replace("_wire","")), 70)
        if cov["total"] > 100 and cov["pct"] < min_pct:
            problems.append({"severity": "YELLOW", "msg": "{} only {}% scored ({}/{})".format(
                sc, cov["pct"], cov["scored"], cov["total"])})

    avg_rows = sum(r["rows"] for r in score_runs[:5]) / max(len(score_runs[:5]), 1)
    if score_runs and avg_rows < t["min_scored_per_run"] and total_backlog > 1000:
        problems.append({"severity": "YELLOW", "msg": "Scoring averaging {:.0f} rows/run with {:,} backlog".format(
            avg_rows, total_backlog)})

    return {
        "as_of":         now.isoformat(),
        "as_of_pt":      now.astimezone(PT).strftime("%Y-%m-%d %I:%M %p PT"),
        "backlog":       backlog,
        "total_backlog": total_backlog,
        "score_runs":    score_runs[:10],
        "coverage_24h":  coverage,
        "watermarks":    watermarks,
        "problems":      problems,
        "overall":       "RED" if any(p["severity"]=="RED" for p in problems)
                         else "YELLOW" if problems else "GREEN",
    }


def collect_pipeline_status(cur, now):
    since_2h = now - timedelta(hours=2)

    # Last run per step
    cur.execute("""
        SELECT DISTINCT ON (step)
            step, status, started_at, duration_ms, rows_affected, error
        FROM pipeline_runs
        WHERE started_at >= %s
        ORDER BY step, started_at DESC;
    """, (since_2h,))
    steps = {}
    for step, status, started, dur, rows, error in cur.fetchall():
        age = round((now - started.replace(tzinfo=timezone.utc)).total_seconds() / 60, 1)
        steps[step] = {
            "status": status,
            "age_mins": age,
            "duration_s": round(dur/1000, 1) if dur else None,
            "rows": rows or 0,
            "error": error,
        }

    # Last full cycle
    cur.execute("""
        SELECT MAX(started_at) FROM pipeline_runs
        WHERE step='health-check' AND status='ok';
    """)
    last_cycle = cur.fetchone()[0]
    cycle_age = round((now - last_cycle.replace(tzinfo=timezone.utc)).total_seconds() / 60, 1) if last_cycle else None

    # Divergence zero streak
    cur.execute("""
        SELECT COUNT(*) FROM pipeline_runs
        WHERE step='divergence-scan' AND status='ok' AND rows_affected=0
        AND started_at >= %s;
    """, (since_2h,))
    div_zero_streak = cur.fetchone()[0]

    # Active signals
    cur.execute("""
        SELECT COUNT(*), MAX(d_value)
        FROM divergence_events
        WHERE time >= now() - interval '4 hours';
    """)
    sig_count, max_d = cur.fetchone()

    # Problems
    problems = []
    t = THRESHOLDS["pipeline"]

    if cycle_age and cycle_age > t["max_cycle_age_mins"]:
        problems.append({"severity": "RED", "msg": "Last pipeline cycle {:.0f}m ago (expected <{}m)".format(
            cycle_age, t["max_cycle_age_mins"])})

    if div_zero_streak >= t["max_divergence_zero_streak"]:
        problems.append({"severity": "YELLOW", "msg": "Divergence scan returned 0 rows {} times in 2h".format(div_zero_streak)})

    for step, data in steps.items():
        if data["error"]:
            problems.append({"severity": "YELLOW", "msg": "{} error: {}".format(step, data["error"][:60])})
        if step == "ingest-all" and data["duration_s"] and data["duration_s"] > t["max_ingest_secs"]:
            problems.append({"severity": "YELLOW", "msg": "ingest-all took {:.0f}s (expected <{}s)".format(
                data["duration_s"], t["max_ingest_secs"])})

    return {
        "as_of":            now.isoformat(),
        "as_of_pt":         now.astimezone(PT).strftime("%Y-%m-%d %I:%M %p PT"),
        "steps":            steps,
        "last_cycle_age_mins": cycle_age,
        "div_zero_streak":  div_zero_streak,
        "active_signals":   sig_count or 0,
        "max_d":            float(max_d) if max_d else 0,
        "problems":         problems,
        "overall":          "RED" if any(p["severity"]=="RED" for p in problems)
                            else "YELLOW" if problems else "GREEN",
    }


def save_status(name, data):
    path = STATUS_DIR / "{}.json".format(name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def print_summary(ingestion, scoring, pipeline):
    def icon(overall):
        return "✅" if overall=="GREEN" else "⚠️ " if overall=="YELLOW" else "❌"

    print()
    print("=" * 60)
    print("  SYSTEM STATUS MONITOR — {}".format(now.astimezone(PT).strftime("%I:%M %p PT")))
    print("=" * 60)
    print()
    print("  {} INGESTION  {}".format(icon(ingestion["overall"]),
          " | ".join(p["msg"] for p in ingestion["problems"]) or "All adapters healthy"))
    print("  {} SCORING    {}".format(icon(scoring["overall"]),
          " | ".join(p["msg"] for p in scoring["problems"]) or "Backlog {:,}, coverage healthy".format(scoring["total_backlog"])))
    print("  {} PIPELINE   {}".format(icon(pipeline["overall"]),
          " | ".join(p["msg"] for p in pipeline["problems"]) or "Cycle {:.0f}m ago, {} signals".format(
              pipeline["last_cycle_age_mins"] or 0, pipeline["active_signals"])))
    print()

    all_problems = (
        [("INGESTION", p) for p in ingestion["problems"]] +
        [("SCORING",   p) for p in scoring["problems"]] +
        [("PIPELINE",  p) for p in pipeline["problems"]]
    )
    if all_problems:
        print("  ISSUES:")
        for area, p in all_problems:
            icon_s = "❌" if p["severity"]=="RED" else "⚠️"
            print("  {} [{}] {}".format(icon_s, area, p["msg"]))
        print()

    print("  Status files:")
    print("    docs/status/ingestion_health.json")
    print("    docs/status/scoring_health.json")
    print("    docs/status/pipeline_health.json")
    print()


if __name__ == "__main__":
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                ingestion = collect_ingestion_status(cur, now)
                scoring   = collect_scoring_status(cur, now)
                pipeline  = collect_pipeline_status(cur, now)

        # Save status files
        save_status("ingestion_health", ingestion)
        save_status("scoring_health",   scoring)
        save_status("pipeline_health",  pipeline)

        # Combined summary
        all_problems = ingestion["problems"] + scoring["problems"] + pipeline["problems"]
        overall = "RED" if any(p["severity"]=="RED" for p in all_problems) \
                  else "YELLOW" if all_problems else "GREEN"

        summary = {
            "as_of":     now.isoformat(),
            "as_of_pt":  now.astimezone(PT).strftime("%Y-%m-%d %I:%M %p PT"),
            "overall":   overall,
            "ingestion": ingestion["overall"],
            "scoring":   scoring["overall"],
            "pipeline":  pipeline["overall"],
            "problems":  all_problems,
            "signals":   pipeline["active_signals"],
            "max_d":     pipeline["max_d"],
            "backlog":   scoring["total_backlog"],
        }
        save_status("system_summary", summary)

        print_summary(ingestion, scoring, pipeline)

        # Save to health_checks table if issues found
        if all_problems:
            import json as _json
            from alphahound.engine.storage import get_conn as _gc
            try:
                with _gc() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO health_checks (generated_at, overall_status, items)
                            VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;
                        """, (now, overall, _json.dumps([{
                            "name":   "{}: {}".format(area, p["msg"][:40]),
                            "status": p["severity"],
                            "value":  p["msg"][:80],
                            "detail": p["msg"],
                        } for area, p in [
                            ("INGESTION", p) for p in ingestion["problems"]
                        ] + [
                            ("SCORING", p) for p in scoring["problems"]
                        ] + [
                            ("PIPELINE", p) for p in pipeline["problems"]
                        ]])))
                    conn.commit()
            except Exception as e:
                print("  (health_checks save failed: {})".format(e))

        sys.exit(0 if overall != "RED" else 1)

    except Exception as e:
        print("STATUS MONITOR FAILED: {}".format(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)
