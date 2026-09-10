

# ── Assessment endpoints ─────────────────────────────────────────────────────

@app.get("/api/assessment")
def get_assessment(limit: int = Query(default=1, ge=1, le=100)):
    """Latest assessment(s) from the assessment service."""
    hit, val = cached("assessment", 30)
    if hit and limit == 1:
        return val

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'assessments'
                )
            """)
            exists = cur.fetchone()[0]
            if not exists:
                return {"latest": None, "history": [], "message": "Assessment service not yet run"}

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
        return {
            "id":          id_,
            "assessed_at": fmt_et(ts),
            "status":      status,
            **payload,
        }

    result = {
        "latest":  fmt_row(rows[0]),
        "history": [fmt_row(r) for r in rows],
        "count":   len(rows),
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
                       (payload->>'executable_count')::int as executable_count,
                       (payload->>'monitoring_count')::int as monitoring_count,
                       (payload->>'executed_today')::int   as executed_today,
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
        "executed_today", "why_not_trading", "findings", "actions"
    ]
    return {
        "assessments": [dict(zip(cols, r)) for r in rows],
        "hours":       hours,
        "count":       len(rows),
    }
