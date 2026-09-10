"""AlphaHound Health Monitor — comprehensive system health checks.

Runs every pipeline cycle. Checks:
- Pipeline step recency (any step overdue?)
- Adapter ingest health (last run, error rate)
- Scoring backlog (unscored posts)
- DB connectivity
- Alpaca account status
- Signal activity (D-values in last 2h)
- Disk / memory (basic)

Writes results to health_checks table for dashboard display.
Also logs warnings for any RED status items.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

Status = Literal["GREEN", "YELLOW", "RED", "UNKNOWN"]

PIPELINE_STEP_MAX_AGE_MINS = 30   # alert if pipeline hasn't run in 30 min
ADAPTER_MAX_AGE_HOURS      = 2    # alert if adapter hasn't ingested in 2h
SCORING_BACKLOG_WARN        = 5000   # warn if >5000 posts unscored
SCORING_BACKLOG_CRIT        = 15000  # critical if >15000 posts unscored


@dataclass
class HealthItem:
    name:    str
    status:  Status
    value:   str
    detail:  str = ""


@dataclass
class HealthReport:
    generated_at: datetime
    overall:      Status
    items:        list[HealthItem] = field(default_factory=list)

    def add(self, item: HealthItem) -> None:
        self.items.append(item)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "overall":      self.overall,
            "items": [
                {
                    "name":   i.name,
                    "status": i.status,
                    "value":  i.value,
                    "detail": i.detail,
                }
                for i in self.items
            ],
        }


def run_health_checks() -> HealthReport:
    now  = datetime.now(timezone.utc)
    report = HealthReport(generated_at=now, overall="GREEN")
    items  = report.items

    # ── 1. DB connectivity ────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        items.append(HealthItem("Database", "GREEN", "Connected"))
    except Exception as exc:
        items.append(HealthItem("Database", "RED", "FAILED", str(exc)))

    # ── 2. Pipeline step recency ──────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT step, status, started_at, error
                    FROM pipeline_runs
                    WHERE started_at >= now() - interval '2 hours'
                    ORDER BY started_at DESC;
                """)
                runs = cur.fetchall()

        if not runs:
            items.append(HealthItem("Pipeline", "RED", "NO RUNS", "No pipeline runs in last 2 hours"))
        else:
            latest_started = runs[0][2]
            # Handle both naive and aware datetimes
            if latest_started.tzinfo is None:
                latest_started = latest_started.replace(tzinfo=timezone.utc)
            mins_ago = int((now - latest_started).total_seconds() / 60)
            errors = [r for r in runs if r[1] == "error" and r[0] != "health-check"]
            if mins_ago > PIPELINE_STEP_MAX_AGE_MINS:
                items.append(HealthItem("Pipeline", "YELLOW",
                    "Last run {}m ago".format(mins_ago),
                    "Expected every 15 min"))
            elif errors:
                items.append(HealthItem("Pipeline", "YELLOW",
                    "{} errors in last 2h".format(len(errors)),
                    "Step: {} -- {}".format(errors[0][0], (errors[0][3] or "")[:60])))
            else:
                items.append(HealthItem("Pipeline", "GREEN",
                    "{}m ago -- all OK".format(mins_ago),
                    "{} steps healthy".format(len(runs))))
    except Exception as exc:
        items.append(HealthItem("Pipeline", "RED", "ERROR", str(exc)))

    # ── 3. Adapter health ─────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sa.adapter_id, sa.enabled,
                           ir.started_at, ir.error, ir.posts_fetched
                    FROM source_adapters sa
                    LEFT JOIN LATERAL (
                        SELECT started_at, error, posts_fetched
                        FROM ingest_runs
                        WHERE adapter_id = sa.adapter_id
                        ORDER BY started_at DESC LIMIT 1
                    ) ir ON true
                    WHERE sa.enabled = true
                    ORDER BY sa.adapter_id;
                """)
                adapters = cur.fetchall()

        stale = []
        errored = []
        for name, enabled, last_run, error, count in adapters:
            if not last_run:
                stale.append(name)
                continue
            hours_ago = (now - last_run.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if error:
                errored.append(name)
            elif hours_ago > ADAPTER_MAX_AGE_HOURS:
                stale.append(name)

        total = len(adapters)
        if errored:
            items.append(HealthItem("Adapters",
                "RED" if len(errored) > 2 else "YELLOW",
                "{}/{} errored".format(len(errored), total),
                ", ".join(errored[:3])))
        elif stale:
            items.append(HealthItem("Adapters", "YELLOW",
                "{}/{} stale".format(len(stale), total),
                ", ".join(stale[:3])))
        else:
            items.append(HealthItem("Adapters", "GREEN",
                "{}/{} healthy".format(total, total)))
    except Exception as exc:
        items.append(HealthItem("Adapters", "RED", "ERROR", str(exc)))

    # ── 4. Scoring backlog ────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source_class, COUNT(*) as unscored
                    FROM raw_posts rp
                    WHERE source_class IN ('news_wire','retail_social','analyst_curated')
                    AND NOT EXISTS (
                        SELECT 1 FROM sentiment_scores ss
                        WHERE ss.entity_id = rp.entity_id
                        AND ss.source_class = rp.source_class
                        AND date_trunc('hour', ss.time) = date_trunc('hour', rp.time)
                    )
                    GROUP BY source_class;
                """)
                backlog = cur.fetchall()

        total_backlog = sum(r[1] for r in backlog)
        detail = " | ".join("{}: {:,}".format(r[0], r[1]) for r in backlog)
        if total_backlog > SCORING_BACKLOG_CRIT:
            items.append(HealthItem("Scoring Backlog", "RED",
                "{:,} unscored".format(total_backlog), detail))
        elif total_backlog > SCORING_BACKLOG_WARN:
            items.append(HealthItem("Scoring Backlog", "YELLOW",
                "{:,} unscored".format(total_backlog), detail))
        else:
            items.append(HealthItem("Scoring Backlog", "GREEN",
                "{:,} unscored".format(total_backlog), detail or "All clear"))
    except Exception as exc:
        items.append(HealthItem("Scoring Backlog", "RED", "ERROR", str(exc)))

    # ── 5. Signal activity ────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*), MAX(d_value), MAX(time)
                    FROM divergence_events
                    WHERE time >= now() - interval '2 hours';
                """)
                sig = cur.fetchone()

        count, max_d, last_sig = sig
        if count == 0:
            hours_since = None
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT MAX(time) FROM divergence_events;")
                    row = cur.fetchone()
            if row and row[0]:
                hours_since = round((now - row[0].replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
            items.append(HealthItem("Signals", "YELLOW",
                "No signals 2h",
                "Last signal {}h ago".format(hours_since) if hours_since else "No signals ever"))
        elif max_d and max_d >= 4.0:
            items.append(HealthItem("Signals", "GREEN",
                "{} signals, max D={:.1f}".format(count, max_d),
                "EXECUTABLE signal present"))
        else:
            items.append(HealthItem("Signals", "GREEN",
                "{} signals, max D={:.1f}".format(count, max_d or 0),
                "All below execution threshold"))
    except Exception as exc:
        items.append(HealthItem("Signals", "RED", "ERROR", str(exc)))

    # ── 6. Alpaca account ─────────────────────────────────────────────────
    try:
        from alphahound.engine.execution.alpaca_broker import get_broker
        broker = get_broker()
        acct   = broker.get_account()
        equity = acct.get("equity", 0)
        items.append(HealthItem("Alpaca Account", "GREEN",
            "Equity ${:,.0f}".format(equity),
            "Status: {}".format(acct.get("status", "?"))))
    except Exception as exc:
        items.append(HealthItem("Alpaca Account", "YELLOW",
            "Unavailable", str(exc)[:60]))

    # ── 7. Bankroll config ────────────────────────────────────────────────
    bankroll = os.environ.get("ALPHAHOUND_BANKROLL", "NOT SET")
    try:
        br_val = float(bankroll)
        items.append(HealthItem("Bankroll Config", "GREEN",
            "${:,.0f}".format(br_val)))
    except Exception:
        items.append(HealthItem("Bankroll Config", "RED",
            "INVALID: {}".format(bankroll)))

    # ── 8. Hit rate status ────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT window_days, hit_rate_pct, total_signals, computed_at
                    FROM hit_rate ORDER BY computed_at DESC LIMIT 1;
                """)
                hr = cur.fetchone()

        if not hr:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT MIN(
                                CASE
                                    WHEN jsonb_typeof(notes) = 'object'
                                    AND notes->>'outlook' IS NOT NULL
                                    THEN (notes->'outlook'->>'resolve_by')
                                    ELSE NULL
                                END
                            )
                            FROM trade_log
                            WHERE venue = 'signal'
                            AND notes IS NOT NULL;
                        """)
                        first_resolve = cur.fetchone()
                detail = "First resolve: {}".format(
                    str(first_resolve[0])[:10] if first_resolve and first_resolve[0] else "May 14-15 (expected)")
            except Exception:
                detail = "First resolve: May 14-15 (expected)"
            items.append(HealthItem("Hit Rate", "YELLOW", "Pending", detail))
        else:
            w, rate, total, computed = hr
            status = "GREEN" if rate >= 55 else "YELLOW" if rate >= 45 else "RED"
            items.append(HealthItem("Hit Rate", status,
                "{:.1f}% ({} signals)".format(rate, total),
                "{}d window, computed {}".format(w, computed.strftime('%b %d'))))
    except Exception as exc:
        items.append(HealthItem("Hit Rate", "RED", "ERROR", str(exc)))

    # ── 9. Portfolio loss alert (CRITICAL) ────────────────────────────────
    try:
        import httpx as _hx, re as _re
        from collections import defaultdict as _dd
        _h = {'APCA-API-KEY-ID': os.environ.get('ALPACA_API_KEY',''), 'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY','')}
        _b = os.environ.get('ALPACA_BASE_URL','https://paper-api.alpaca.markets')
        _rp = _hx.get(f'{_b}/v2/positions', headers=_h, timeout=10)
        _ra = _hx.get(f'{_b}/v2/account',   headers=_h, timeout=10)
        _pos = _rp.json() if _rp.status_code == 200 else []
        _acct = _ra.json() if _ra.status_code == 200 else {}
        _equity = float(_acct.get('equity', 0))
        _start  = float(os.environ.get('STARTING_EQUITY', '20000'))
        _total_pl = _equity - _start
        _pl_pct   = (_total_pl / _start * 100) if _start else 0
        _sp = _dd(list)
        for _p in (_pos if isinstance(_pos, list) else []):
            _m = _re.match(r'^([A-Z]+)\d', _p.get('symbol',''))
            if _m: _sp[_m.group(1)].append(_p)
        _stops, _danger = [], []
        for _t, _legs in _sp.items():
            _e = abs(sum(float(l.get('cost_basis',0)) for l in _legs))
            _c = sum(float(l.get('market_value',0)) for l in _legs)
            if not _e: continue
            _pct = (_c - _e) / _e * 100
            if _pct <= -80: _stops.append(f'{_t}({_pct:.0f}%)')
            elif _pct <= -50: _danger.append(f'{_t}({_pct:.0f}%)')
        if _stops:
            items.append(HealthItem('Portfolio', 'RED',
                f'{len(_stops)} AT STOP LOSS - CLOSE NOW',
                f'{", ".join(_stops)} | P&L ${_total_pl:,.0f} ({_pl_pct:.1f}%)'))
        elif _danger:
            items.append(HealthItem('Portfolio', 'RED',
                f'{len(_danger)} positions >50% down',
                f'{", ".join(_danger)} | P&L ${_total_pl:,.0f} ({_pl_pct:.1f}%)'))
        elif _pl_pct < -10:
            items.append(HealthItem('Portfolio', 'YELLOW',
                f'Account down {_pl_pct:.1f}%',
                f'Equity ${_equity:,.0f} vs ${_start:,.0f} start'))
        else:
            items.append(HealthItem('Portfolio', 'GREEN',
                f'${_equity:,.0f} ({_pl_pct:+.1f}%)', f'{len(_sp)} open spread(s)'))
    except Exception as _exc:
        items.append(HealthItem('Portfolio', 'YELLOW', 'Check failed', str(_exc)[:80]))

    # ── 10. Open positions ────────────────────────────────────────────────
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*), SUM(size)
                    FROM trade_log
                    WHERE alpaca_order_id IS NOT NULL AND closed_at IS NULL;
                """)
                pos = cur.fetchone()
        count, deployed = pos
        deployed = deployed or 0
        items.append(HealthItem("Open Positions", "GREEN",
            "{} positions, ${:,.0f} deployed".format(count or 0, deployed)))
    except Exception as exc:
        items.append(HealthItem("Open Positions", "RED", "ERROR", str(exc)))

    # ── Compute overall ───────────────────────────────────────────────────
    statuses = [i.status for i in items]
    if "RED" in statuses:
        report.overall = "RED"
    elif "YELLOW" in statuses:
        report.overall = "YELLOW"
    else:
        report.overall = "GREEN"

    # Log any issues
    for item in items:
        if item.status == "RED":
            log.error("HEALTH RED: %s — %s %s", item.name, item.value, item.detail)
        elif item.status == "YELLOW":
            log.warning("HEALTH YELLOW: %s — %s %s", item.name, item.value, item.detail)

    return report


def save_health_report(report: HealthReport) -> None:
    """Persist health report to DB for dashboard."""
    import json
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO health_checks (generated_at, overall_status, items)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (
                    report.generated_at,
                    report.overall,
                    json.dumps([{
                        "name": i.name, "status": i.status,
                        "value": i.value, "detail": i.detail
                    } for i in report.items])
                ))
            conn.commit()
    except Exception as exc:
        log.warning("Failed to save health report: %s", exc)


def get_latest_health() -> dict | None:
    """Fetch most recent health report from DB."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT generated_at, overall_status, items
                    FROM health_checks
                    ORDER BY generated_at DESC LIMIT 1;
                """)
                row = cur.fetchone()
        if not row:
            return None
        return {
            "generated_at":  row[0].isoformat(),
            "overall":        row[1],
            "items":          row[2],
        }
    except Exception:
        return None
