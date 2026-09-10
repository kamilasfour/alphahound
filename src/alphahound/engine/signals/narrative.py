"""Claude Tier 2 narrative generator — Sprint 5.

Called automatically after divergence-scan writes new alerts.
For each alert without a narrative, calls the Claude API and stores
the 2-sentence explanation back into divergence_events.components.

Cost: ~$0.003/narrative at claude-sonnet-4-6 pricing.
At 9 alerts/day = ~$0.03/day = ~$1/mo. Hard cap at 50 narratives/run.

Design:
  - Reads unnarrated alerts from divergence_events (PK = entity_id + time).
  - Enriches each with: price context (price_snapshots), recent headlines
    (raw_posts, last 24h, news_wire class), congressional trades (institutional_positions),
    component breakdown with direction labels.
  - Calls Claude API with a tight, context-rich prompt.
  - Patches divergence_events.components JSONB in-place using (entity_id, time) PK.
    Uses a 1-second window on time to handle microsecond precision mismatches.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-6"
MAX_TOKENS     = 150
MAX_PER_RUN    = 50
HEADLINE_LIMIT = 6
CONGRESS_LIMIT = 3


def generate_narratives(module_id: str = "stocks") -> int:
    """Find alerts without narratives, generate and store them. Returns count written."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping narrative generation.")
        return 0

    alerts = _get_unnarrated_alerts(module_id, limit=MAX_PER_RUN)
    if not alerts:
        log.info("Narrative: no unnarrated alerts found.")
        return 0

    log.info("Narrative: generating for %d alerts.", len(alerts))
    written = 0

    for alert in alerts:
        try:
            narrative = _generate_one(alert, api_key)
            if narrative:
                rows_updated = _store_narrative(
                    entity_id=alert["entity_id"],
                    alert_time=alert["time"],
                    components=alert["components"],
                    narrative=narrative,
                )
                if rows_updated == 0:
                    log.warning(
                        "Narrative: UPDATE matched 0 rows for %s at %s — skipping to avoid loop.",
                        alert["canonical_symbol"], alert["time"],
                    )
                else:
                    written += 1
                    log.info(
                        "Narrative: %s → %s",
                        alert["canonical_symbol"],
                        narrative[:80] + "…" if len(narrative) > 80 else narrative,
                    )
        except Exception as exc:
            log.warning(
                "Narrative generation failed for %s: %s",
                alert.get("canonical_symbol", "?"), exc,
            )

    log.info("Narrative: wrote %d narratives.", written)
    return written


def _get_unnarrated_alerts(module_id: str, limit: int) -> list[dict]:
    """Fetch recent divergence alerts that don't yet have a narrative.

    Returns the raw time value from the DB so we match it exactly on UPDATE.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    de.entity_id,
                    de.time,
                    e.canonical_symbol,
                    de.d_value,
                    de.p_value,
                    de.components
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                WHERE e.module_id = %s
                  AND (
                      de.components IS NULL
                      OR NOT (de.components ? 'narrative')
                  )
                ORDER BY de.time DESC
                LIMIT %s;
                """,
                (module_id, limit),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _generate_one(alert: dict, api_key: str) -> str | None:
    """Build context-rich prompt, call Claude, return narrative string."""
    ticker     = alert["canonical_symbol"]
    d_value    = alert["d_value"]
    p_value    = alert["p_value"]
    components = alert["components"] or {}
    alert_time = alert["time"]
    entity_id  = alert["entity_id"]

    price_ctx = _get_price_context(entity_id)
    if price_ctx:
        price_block = (
            f"  Price: ${price_ctx['price']:.2f}\n"
            f"  5-day change: {price_ctx['change_5d_pct']:+.1f}% "
            f"(vs SPY: {price_ctx['change_vs_spy']:+.1f}%)"
            if price_ctx.get("change_5d_pct") is not None
            else f"  Price: ${price_ctx['price']:.2f}"
        )
    else:
        price_block = "  Price data not available (ticker not in Massive watchlist yet)"

    comp_lines = []
    for sc, polarity in components.items():
        if sc == "narrative":
            continue
        if polarity > 0.1:
            direction = "bullish"
        elif polarity < -0.1:
            direction = "bearish"
        else:
            direction = "neutral"
        comp_lines.append(f"  {sc}: polarity={polarity:+.3f} ({direction})")
    comp_block = "\n".join(comp_lines) if comp_lines else "  (no components)"

    headlines = _get_recent_headlines(entity_id, alert_time)
    headline_block = (
        "\n".join(f"  • {h}" for h in headlines)
        if headlines else "  (no recent headlines found)"
    )

    congress_trades = _get_congress_trades(entity_id)
    congress_block = (
        "\n".join(f"  • {t}" for t in congress_trades)
        if congress_trades else "  (no recent congressional trades)"
    )

    prompt = f"""You are a concise financial analyst writing a 2-sentence alert summary for a personal trading signal engine.

TICKER: {ticker}
ALERT TIME: {alert_time.strftime('%Y-%m-%d %H:%M UTC')}
DIVERGENCE: D={d_value:.2f} (threshold=2.0), p={p_value:.4f} — sources disagree significantly on sentiment.

SENTIMENT BY SOURCE CLASS:
{comp_block}

PRICE CONTEXT:
{price_block}

RECENT HEADLINES (last 24h):
{headline_block}

CONGRESSIONAL TRADES (recent):
{congress_block}

Write exactly 2 sentences. First sentence: what the divergence shows (which sources are bullish vs bearish and why they disagree). Second sentence: what the price action and news context suggests about direction. Be specific and factual. No filler phrases. Under 70 words total."""

    try:
        response = httpx.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()
    except httpx.HTTPError as exc:
        log.warning("Claude API call failed: %s", exc)
        return None


def _get_price_context(entity_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT price, change_1d_pct, change_5d_pct, change_vs_spy
                FROM price_snapshots
                WHERE entity_id = %s
                ORDER BY time DESC
                LIMIT 1;
                """,
                (entity_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "price":         row[0],
        "change_1d_pct": row[1],
        "change_5d_pct": row[2],
        "change_vs_spy": row[3],
    }


def _get_recent_headlines(entity_id: str, since: datetime) -> list[str]:
    window_start = since - timedelta(hours=24)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT text
                FROM raw_posts
                WHERE entity_id = %s
                  AND source_class IN ('news_wire', 'analyst_curated')
                  AND time >= %s
                ORDER BY time DESC
                LIMIT %s;
                """,
                (entity_id, window_start, HEADLINE_LIMIT),
            )
            rows = cur.fetchall()
    headlines = []
    for (text,) in rows:
        line = text.split(".")[0].strip()
        if len(line) > 120:
            line = line[:117] + "…"
        if line:
            headlines.append(line)
    return headlines


def _get_congress_trades(entity_id: str) -> list[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT filer, shares, filed_at, kind
                FROM institutional_positions
                WHERE entity_id = %s
                  AND kind = 'Congress'
                ORDER BY filed_at DESC
                LIMIT %s;
                """,
                (entity_id, CONGRESS_LIMIT),
            )
            rows = cur.fetchall()
    trades = []
    for filer, shares, filed_at, kind in rows:
        date_str = filed_at.strftime("%Y-%m-%d") if filed_at else "?"
        amount_str = f"${shares:,}" if shares else "undisclosed amount"
        trades.append(f"{filer} traded {amount_str} on {date_str}")
    return trades


def _store_narrative(
    entity_id: str,
    alert_time: datetime,
    components: dict,
    narrative: str,
) -> int:
    """Patch narrative into divergence_events.components JSONB.

    Uses a 1-second window on time to handle microsecond precision mismatches
    between Python datetime and TimescaleDB timestamptz storage.

    Returns the number of rows updated (0 = match failed, loop guard).
    """
    updated = dict(components or {})
    updated["narrative"] = narrative

    import psycopg as _psycopg

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE divergence_events
                SET components = %s
                WHERE entity_id = %s
                  AND time >= %s::timestamptz - INTERVAL '1 second'
                  AND time <= %s::timestamptz + INTERVAL '1 second';
                """,
                (
                    _psycopg.types.json.Json(updated),
                    entity_id,
                    alert_time,
                    alert_time,
                ),
            )
            rows_updated = cur.rowcount
        conn.commit()

    return rows_updated
