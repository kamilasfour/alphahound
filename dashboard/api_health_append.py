
# ── Health Monitor ────────────────────────────────────────────────────────────

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
