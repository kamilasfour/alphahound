"""
AlphaHound Self-Diagnostic
Runs every pipeline cycle after health-check.
Automatically detects and logs anomalies.
Results saved to health_checks table and visible in dashboard.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone, timedelta
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

RULES = []

def rule(name, severity="YELLOW"):
    """Decorator to register a diagnostic rule."""
    def decorator(fn):
        RULES.append({"name": name, "severity": severity, "fn": fn})
        return fn
    return decorator


# ── Rules ────────────────────────────────────────────────────

@rule("Scoring Watermark Drift", "RED")
def check_watermark_drift(cur, now):
    """Detect if watermarks are drifting into the future or past."""
    cur.execute("SELECT source_class, last_scored_at FROM scoring_watermark;")
    rows = cur.fetchall()
    issues = []
    for sc, wm in rows:
        if not wm:
            continue
        wm = wm.replace(tzinfo=timezone.utc)
        age_hours = (now - wm).total_seconds() / 3600
        if age_hours > 2:
            issues.append("{} watermark is {}h old".format(sc, round(age_hours, 1)))
        if wm > now:
            issues.append("{} watermark is in the FUTURE".format(sc))
    if issues:
        # Auto-fix: delete bad watermarks
        cur.execute("DELETE FROM scoring_watermark;")
        return "AUTO-FIXED: " + " | ".join(issues)
    return None


@rule("Retail Social Not Being Scored", "RED")
def check_retail_scoring(cur, now):
    since_1h = now - timedelta(hours=1)
    cur.execute("""
        SELECT COUNT(*) FROM raw_posts
        WHERE source_class='retail_social' AND time >= %s;
    """, (since_1h,))
    posts_in = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM sentiment_scores
        WHERE source_class='retail_social' AND time >= %s;
    """, (since_1h,))
    scored = cur.fetchone()[0]

    if posts_in > 100 and scored < 10:
        return "{} retail posts ingested but only {} scored in last 1h".format(posts_in, scored)
    return None


@rule("Divergence Scan Returning Zero", "RED")
def check_divergence_zero(cur, now):
    since_1h = now - timedelta(hours=1)
    cur.execute("""
        SELECT COUNT(*) FROM pipeline_runs
        WHERE step='divergence-scan' AND status='ok'
        AND rows_affected = 0
        AND started_at >= %s;
    """, (since_1h,))
    zero_runs = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM pipeline_runs
        WHERE step='divergence-scan' AND status='ok'
        AND started_at >= %s;
    """, (since_1h,))
    total_runs = cur.fetchone()[0]

    if total_runs >= 2 and zero_runs == total_runs:
        # Check if we have scored data to work with
        cur.execute("""
            SELECT COUNT(*) FROM sentiment_scores
            WHERE time >= %s;
        """, (since_1h,))
        scored = cur.fetchone()[0]
        return "divergence-scan returned 0 rows in ALL {} runs last 1h (scored posts available: {})".format(
            total_runs, scored)
    return None


@rule("Adapter Fetching Zero Posts", "YELLOW")
def check_adapter_zero(cur, now):
    since_1h = now - timedelta(hours=1)
    cur.execute("""
        SELECT DISTINCT ON (adapter_id) adapter_id, posts_fetched, error
        FROM ingest_runs
        WHERE started_at >= %s
        ORDER BY adapter_id, started_at DESC;
    """, (since_1h,))
    runs = cur.fetchall()

    # Check if it's market hours
    et_hour = now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).hour
    mkt_open = 9 <= et_hour < 16

    issues = []
    for adapter_id, fetched, error in runs:
        if error:
            issues.append("{}: {}".format(adapter_id, error[:40]))
        elif fetched == 0 and mkt_open and adapter_id in (
            'stocks.unusual_whales', 'stocks.finnhub', 'stocks.apewisdom'
        ):
            issues.append("{}: 0 fetched during market hours".format(adapter_id))
    return " | ".join(issues) if issues else None


@rule("High Scoring Backlog", "YELLOW")
def check_backlog(cur, now):
    cur.execute("""
        SELECT COUNT(*) FROM raw_posts rp
        WHERE source_class IN ('news_wire','retail_social','analyst_curated')
        AND NOT EXISTS (
            SELECT 1 FROM sentiment_scores ss
            WHERE ss.entity_id=rp.entity_id
            AND ss.source_class=rp.source_class
            AND ss.time=rp.time
        )
        AND rp.time >= now() - interval '7 days';
    """)
    backlog = cur.fetchone()[0]
    if backlog > 10000:
        return "{:,} posts unscored — scoring falling behind".format(backlog)
    return None


# Quiver Writing Zero Posts rule removed — false positive.
# Quiver dedup works correctly: all trades already in DB, 0 writes is expected.


@rule("Pipeline Step Overdue", "YELLOW")
def check_pipeline_overdue(cur, now):
    cur.execute("""
        SELECT MAX(started_at) FROM pipeline_runs
        WHERE step='health-check' AND status='ok';
    """)
    last = cur.fetchone()[0]
    if not last:
        return "No successful pipeline cycle found"
    age_mins = (now - last.replace(tzinfo=timezone.utc)).total_seconds() / 60
    if age_mins > 20:
        return "Last pipeline cycle was {:.0f} minutes ago (expected every 15m)".format(age_mins)
    return None


@rule("Score-New Cap Hit Every Run", "YELLOW")
def check_scoring_cap(cur, now):
    since_2h = now - timedelta(hours=2)
    cur.execute("""
        SELECT COUNT(*), AVG(rows_affected) FROM pipeline_runs
        WHERE step='score-new' AND status='ok'
        AND rows_affected >= 2000
        AND started_at >= %s;
    """, (since_2h,))
    row = cur.fetchone()
    if row and row[0] >= 3:
        return "score-new hitting 2000 cap {} times in 2h — backlog not clearing".format(row[0])
    return None


# ── Runner ───────────────────────────────────────────────────

def run_diagnostics() -> list[dict]:
    now = datetime.now(timezone.utc)
    findings = []

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                for rule_def in RULES:
                    try:
                        result = rule_def["fn"](cur, now)
                        if result:
                            findings.append({
                                "rule":     rule_def["name"],
                                "severity": rule_def["severity"],
                                "message":  result,
                                "time":     now.isoformat(),
                            })
                            if rule_def["severity"] == "RED":
                                log.error("DIAGNOSTIC RED: %s — %s", rule_def["name"], result)
                            else:
                                log.warning("DIAGNOSTIC YELLOW: %s — %s", rule_def["name"], result)
                    except Exception as exc:
                        log.warning("Diagnostic rule %s failed: %s", rule_def["name"], exc)
            conn.commit()
    except Exception as exc:
        log.error("Diagnostics failed: %s", exc)

    if not findings:
        log.info("Diagnostics: all clear")

    return findings


def save_diagnostics(findings: list[dict]) -> None:
    """Append diagnostic findings to health_checks table."""
    if not findings:
        return
    import json
    now = datetime.now(timezone.utc)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO health_checks (generated_at, overall_status, items)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (
                    now,
                    "RED" if any(f["severity"] == "RED" for f in findings) else "YELLOW",
                    json.dumps([{
                        "name":   f["rule"],
                        "status": f["severity"],
                        "value":  f["message"][:80],
                        "detail": f["message"],
                    } for f in findings])
                ))
            conn.commit()
    except Exception as exc:
        log.warning("Failed to save diagnostics: %s", exc)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    findings = run_diagnostics()

    if not findings:
        print("\n✅ All diagnostics clear — system healthy\n")
    else:
        print("\n{'='*55}")
        print("  DIAGNOSTIC FINDINGS")
        print("{'='*55}")
        for f in findings:
            icon = "❌" if f["severity"] == "RED" else "⚠️"
            print("\n{} [{}] {}".format(icon, f["rule"], f["message"]))
        print()

    save_diagnostics(findings)
