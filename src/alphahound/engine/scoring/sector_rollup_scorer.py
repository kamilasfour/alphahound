"""Sector rollup scorer — Sprint 9.7.

Aggregates individual stock sentiment into sector/thematic ETF sentiment.

How it works:
    1. For each sector ETF (XLK, XLF, etc), pull its constituent stocks
       from entity_relationships table.
    2. For each constituent, get the latest 24h weighted average sentiment
       from sentiment_scores.
    3. Aggregate constituent sentiments (weighted by ETF weight if available,
       equal weight otherwise).
    4. Write aggregated score to sector_sentiment table.
    5. The divergence engine reads sector_sentiment as an additional
       source_class ('sector_rollup') alongside options_flow.

Why this matters:
    Without this, XLK has no sentiment signal. With this, XLK inherits
    the collective sentiment of AAPL + NVDA + MSFT + AVGO etc. If that
    collective sentiment diverges from XLK options flow → real sector signal.

Coverage:
    We report coverage_pct = % of ETF weight represented by constituents
    with data. Signals with coverage < 30% are suppressed (too thin).

Called by:
    alphahound signals score-sectors   (new CLI command)
    ingest_all.ps1 after score-new
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alphahound.engine.storage import get_conn
from alphahound.modules.stocks.watchlist.watchlist import SECTOR_CONSTITUENTS, SECTOR_ETFS, THEMATIC_ETFS

log = logging.getLogger(__name__)

WINDOW_HOURS    = 24
MIN_COVERAGE    = 0.30   # suppress sector signal if < 30% of constituents have data
MIN_CONSTITUENTS = 2     # need at least 2 constituents with data


def score_all_sectors() -> int:
    """Compute and store sector rollup sentiment for all sector/thematic ETFs.

    Returns number of sector scores written.
    """
    now = datetime.now(timezone.utc)
    all_etfs = list(dict.fromkeys(SECTOR_ETFS + THEMATIC_ETFS))
    written = 0

    for etf_ticker in all_etfs:
        constituents = SECTOR_CONSTITUENTS.get(etf_ticker, [])
        if not constituents:
            # Pure price ETF (GLD, TLT etc) — no constituent rollup possible
            continue

        try:
            result = _compute_sector_sentiment(etf_ticker, constituents, now)
            if result:
                _write_sector_sentiment(result, now)
                written += 1
                log.info(
                    "Sector rollup: %s polarity=%.4f confidence=%.4f "
                    "constituents=%d coverage=%.0f%%",
                    etf_ticker, result["polarity"], result["confidence"],
                    result["constituent_count"], result["coverage_pct"] * 100,
                )
        except Exception as exc:
            log.warning("Sector rollup failed for %s: %s", etf_ticker, exc)

    log.info("Sector rollup complete: %d ETF scores written", written)
    return written


def _compute_sector_sentiment(
    etf_ticker: str,
    constituents: list[str],
    now: datetime,
) -> dict | None:
    """Aggregate constituent sentiment into a sector score."""
    window_start = now - timedelta(hours=WINDOW_HOURS)

    # Get ETF entity_id
    etf_entity_id = _get_entity_id(etf_ticker)
    if not etf_entity_id:
        log.debug("Sector rollup: no entity for %s — skipping", etf_ticker)
        return None

    # Fetch constituent sentiments
    constituent_scores = []
    for ticker in constituents:
        entity_id = _get_entity_id(ticker)
        if not entity_id:
            continue
        score = _get_constituent_sentiment(entity_id, window_start)
        if score is not None:
            constituent_scores.append({
                "ticker":    ticker,
                "entity_id": entity_id,
                "polarity":  score["polarity"],
                "confidence": score["confidence"],
                "post_count": score["post_count"],
            })

    if len(constituent_scores) < MIN_CONSTITUENTS:
        log.debug(
            "Sector rollup: %s only %d constituents with data (need %d)",
            etf_ticker, len(constituent_scores), MIN_CONSTITUENTS,
        )
        return None

    coverage_pct = len(constituent_scores) / len(constituents)
    if coverage_pct < MIN_COVERAGE:
        log.debug(
            "Sector rollup: %s coverage %.0f%% < %.0f%% minimum",
            etf_ticker, coverage_pct * 100, MIN_COVERAGE * 100,
        )
        return None

    # Equal-weighted average (use ETF weights from entity_relationships if available)
    weights = _get_constituent_weights(etf_entity_id, [s["entity_id"] for s in constituent_scores])

    total_weight = 0.0
    weighted_polarity = 0.0
    weighted_confidence = 0.0

    for s in constituent_scores:
        w = weights.get(s["entity_id"], 1.0 / len(constituent_scores))
        weighted_polarity   += s["polarity"]   * w
        weighted_confidence += s["confidence"] * w
        total_weight += w

    if total_weight > 0:
        agg_polarity    = weighted_polarity   / total_weight
        agg_confidence  = weighted_confidence / total_weight
    else:
        agg_polarity   = 0.0
        agg_confidence = 0.0

    return {
        "etf_ticker":        etf_ticker,
        "entity_id":         etf_entity_id,
        "polarity":          round(agg_polarity, 6),
        "confidence":        round(agg_confidence, 6),
        "constituent_count": len(constituent_scores),
        "coverage_pct":      round(coverage_pct, 4),
        "contributors":      [s["ticker"] for s in constituent_scores],
    }


def _write_sector_sentiment(result: dict, now: datetime) -> None:
    """Write sector rollup score to sector_sentiment table."""
    # Also write to sentiment_scores so the divergence engine picks it up
    # as a source_class='sector_rollup' signal
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. sector_sentiment (detailed record)
            cur.execute(
                """
                INSERT INTO sector_sentiment
                    (time, entity_id, source_class, polarity, confidence,
                     constituent_count, coverage_pct)
                VALUES (%s, %s, 'sector_rollup', %s, %s, %s, %s)
                ON CONFLICT (entity_id, time) DO UPDATE
                    SET polarity          = EXCLUDED.polarity,
                        confidence        = EXCLUDED.confidence,
                        constituent_count = EXCLUDED.constituent_count,
                        coverage_pct      = EXCLUDED.coverage_pct;
                """,
                (
                    now.replace(minute=0, second=0, microsecond=0),  # hour-bucketed
                    result["entity_id"],
                    result["polarity"],
                    result["confidence"],
                    result["constituent_count"],
                    result["coverage_pct"],
                ),
            )

            # 2. sentiment_scores so divergence engine can read it
            cur.execute(
                """
                INSERT INTO sentiment_scores
                    (time, entity_id, source_class, polarity, confidence, tier, post_count)
                VALUES (%s, %s, 'sector_rollup', %s, %s, 'B', %s)
                ON CONFLICT (entity_id, source_class, time) DO UPDATE
                    SET polarity    = EXCLUDED.polarity,
                        confidence  = EXCLUDED.confidence,
                        post_count  = EXCLUDED.post_count;
                """,
                (
                    now.replace(minute=0, second=0, microsecond=0),
                    result["entity_id"],
                    result["polarity"],
                    result["confidence"],
                    result["constituent_count"],
                ),
            )
        conn.commit()


def _get_constituent_sentiment(
    entity_id: str,
    since: datetime,
) -> dict | None:
    """Get aggregated sentiment for a single constituent stock."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        SUM(polarity * confidence) / NULLIF(SUM(confidence), 0) AS weighted_polarity,
                        AVG(confidence) AS avg_confidence,
                        COUNT(*) AS post_count
                    FROM sentiment_scores
                    WHERE entity_id = %s
                      AND time >= %s
                      AND source_class IN ('news_wire', 'retail_social', 'institutional_flow')
                    """,
                    (entity_id, since),
                )
                row = cur.fetchone()
        if row and row[0] is not None:
            return {
                "polarity":   float(row[0]),
                "confidence": float(row[1]) if row[1] else 0.5,
                "post_count": int(row[2]),
            }
        return None
    except Exception as exc:
        log.warning("_get_constituent_sentiment(%s) failed: %s", entity_id, exc)
        return None


def _get_entity_id(ticker: str) -> str | None:
    """Look up entity_id for a ticker symbol."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities "
                    "WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker' LIMIT 1;",
                    (ticker,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


def _get_constituent_weights(
    parent_entity_id: str,
    child_entity_ids: list[str],
) -> dict[str, float]:
    """Get ETF constituent weights from entity_relationships. Equal weight if not set."""
    if not child_entity_ids:
        return {}
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT child_entity_id, weight
                    FROM entity_relationships
                    WHERE parent_entity_id = %s
                      AND child_entity_id = ANY(%s)
                      AND weight IS NOT NULL;
                    """,
                    (parent_entity_id, child_entity_ids),
                )
                rows = cur.fetchall()
        if rows:
            return {str(r[0]): float(r[1]) for r in rows}
        # Fall back to equal weighting
        equal = 1.0 / len(child_entity_ids)
        return {eid: equal for eid in child_entity_ids}
    except Exception:
        equal = 1.0 / len(child_entity_ids) if child_entity_ids else 1.0
        return {eid: equal for eid in child_entity_ids}


def seed_entity_relationships() -> int:
    """Seed entity_relationships from SECTOR_CONSTITUENTS map.

    Safe to re-run — uses ON CONFLICT DO NOTHING.
    Returns rows inserted.
    """
    inserted = 0
    for etf_ticker, constituents in SECTOR_CONSTITUENTS.items():
        if not constituents:
            continue
        parent_id = _get_entity_id(etf_ticker)
        if not parent_id:
            log.debug("seed_entity_relationships: no entity for ETF %s — skipping", etf_ticker)
            continue
        equal_weight = round(1.0 / len(constituents), 6)
        for constituent in constituents:
            child_id = _get_entity_id(constituent)
            if not child_id:
                continue
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO entity_relationships
                                (child_entity_id, parent_entity_id, relationship_type, weight)
                            VALUES (%s, %s, 'constituent_of', %s)
                            ON CONFLICT (child_entity_id, parent_entity_id, relationship_type)
                            DO NOTHING;
                            """,
                            (child_id, parent_id, equal_weight),
                        )
                    conn.commit()
                inserted += 1
            except Exception as exc:
                log.warning("seed_entity_relationships: %s->%s failed: %s", constituent, etf_ticker, exc)

    log.info("seed_entity_relationships: %d relationships inserted", inserted)
    return inserted
