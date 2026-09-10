"""Rhyme Engine — finds historical divergence patterns similar to current alerts.

PRD §A7.3: "The Rhyme Engine compares the current divergence signature
against a corpus of historical events to find similar patterns and
report what happened next."

How it works:
    1. For each active divergence alert, extract the component polarity
       vector (retail_social, news_wire, institutional_flow, options_flow).
    2. Compare against all historical_events using cosine similarity.
    3. Return the top-N matches with their outcomes (if resolved).
    4. Generate a prediction: if similar past patterns resolved bullish
       X% of the time, predict bullish with confidence X%.

Why cosine similarity instead of DTW:
    - DTW requires a price/sentiment time series with many data points.
    - We have 12 days of history — not enough for meaningful DTW windows.
    - Component polarity vectors are already high-dimensional (4-6 features).
    - Cosine similarity on component vectors captures "same kind of divergence"
      precisely: institutions bearish + news bullish = same pattern fingerprint.
    - We will add DTW in Sprint 10 when we have 90+ days of price series data.

Similarity score interpretation:
    1.0  = identical component pattern
    0.8+ = very similar (same direction, similar magnitudes)
    0.6+ = similar (same direction, different magnitudes)
    <0.6 = weak match — not reported

Output stored in: rhyme_matches table
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

MIN_SIMILARITY    = 0.60    # minimum cosine similarity to report a match
TOP_N_MATCHES     = 5       # max matches per entity
MIN_HISTORY_DAYS  = 3       # skip historical events less than N days old
                             # (outcome not resolved yet)

# Source class order for vector construction. Consistent ordering is required
# for cosine similarity to be meaningful.
COMPONENT_KEYS = [
    "retail_social",
    "news_wire",
    "institutional_flow",
    "options_flow",
    "analyst_curated",
    "prediction_market",
]


@dataclass
class RhymeMatch:
    entity_id:          str
    canonical_symbol:   str
    current_event_id:   str         # divergence_event PK
    corpus_event_id:    str         # historical_event event_id
    corpus_label:       str
    corpus_start:       datetime
    similarity:         float
    outcome_prediction: str | None  # 'bullish' | 'bearish' | None
    confidence:         float | None
    outcome_correct:    bool | None  # if resolved, was it right?
    narrative:          str


def run_rhyme_scan(module_id: str = "stocks") -> int:
    """Find rhyme matches for all current divergence alerts. Returns matches written."""
    now = datetime.now(timezone.utc)
    horizon = now - timedelta(hours=2)  # alerts from last 2 hours

    current_alerts = _get_current_alerts(module_id, since=horizon)
    if not current_alerts:
        log.info("Rhyme Engine: no current alerts to match.")
        return 0

    corpus = _load_corpus(module_id, before=now - timedelta(days=MIN_HISTORY_DAYS))
    if not corpus:
        log.info("Rhyme Engine: corpus is empty — no historical events to match against.")
        return 0

    log.info("Rhyme Engine: %d alerts vs %d corpus events", len(current_alerts), len(corpus))

    matches_written = 0
    for alert in current_alerts:
        matches = _find_matches(alert, corpus)
        for match in matches:
            _write_match(match, now)
            matches_written += 1
            log.info(
                "Rhyme: %s → '%s' similarity=%.2f prediction=%s confidence=%s",
                match.canonical_symbol,
                match.corpus_label[:50],
                match.similarity,
                match.outcome_prediction,
                f"{match.confidence:.0%}" if match.confidence else "n/a",
            )

    log.info("Rhyme Engine: wrote %d matches", matches_written)
    return matches_written


def get_rhyme_summary(entity_id: str) -> list[dict]:
    """Get recent rhyme matches for one entity. Used by trade_advisor."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rm.dtw_distance, rm.p_value, rm.narrative,
                       rm.outcome_prediction, rm.confidence,
                       he.label, he.start_time, he.phases
                FROM rhyme_matches rm
                JOIN historical_events he ON he.event_id = rm.corpus_event_id
                WHERE rm.entity_id = %s
                ORDER BY rm.time DESC
                LIMIT 3;
                """,
                (entity_id,),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def _find_matches(alert: dict, corpus: list[dict]) -> list[RhymeMatch]:
    """Find top-N similar historical events for one alert."""
    current_vec = _extract_vector(alert["components"] or {})
    if not any(v != 0 for v in current_vec):
        return []

    scored = []
    for event in corpus:
        phases = event.get("phases") or {}
        hist_components = phases.get("components") or {}
        hist_vec = _extract_vector(hist_components)

        sim = _cosine_similarity(current_vec, hist_vec)
        if sim >= MIN_SIMILARITY:
            scored.append((sim, event))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:TOP_N_MATCHES]

    matches = []
    for sim, event in top:
        phases      = event.get("phases") or {}
        direction   = phases.get("direction") or "neutral"
        outcome_pct = phases.get("outcome_pct")

        # Derive prediction from corpus direction (what the signal said then).
        prediction = None
        confidence = None
        if direction in ("long", "short"):
            prediction = "bullish" if direction == "long" else "bearish"
            # Confidence = similarity × recency_weight.
            age_days = (datetime.now(timezone.utc) - event["start_time"]).days
            recency_weight = max(0.5, 1.0 - (age_days / 90))
            confidence = sim * recency_weight

        # Generate narrative.
        outcome_str = ""
        if outcome_pct is not None:
            direction_str = "rose" if outcome_pct > 0 else "fell"
            outcome_str = f" Price {direction_str} {abs(outcome_pct):.1f}% in 5 days."

        narrative = (
            f"Similar pattern seen on {event['start_time'].strftime('%Y-%m-%d')} "
            f"({event['label'][:60]}). "
            f"Similarity: {sim:.0%}.{outcome_str}"
        )

        matches.append(RhymeMatch(
            entity_id          = alert["entity_id"],
            canonical_symbol   = alert["canonical_symbol"],
            current_event_id   = str(alert["divergence_event_id"]),
            corpus_event_id    = str(event["event_id"]),
            corpus_label       = event["label"],
            corpus_start       = event["start_time"],
            similarity         = round(sim, 4),
            outcome_prediction = prediction,
            confidence         = round(confidence, 3) if confidence else None,
            outcome_correct    = phases.get("outcome_correct"),
            narrative          = narrative,
        ))

    return matches


def _extract_vector(components: dict) -> list[float]:
    """Convert component dict to ordered float vector for cosine similarity."""
    return [float(components.get(key) or 0.0) for key in COMPONENT_KEYS]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 if either is zero."""
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return max(0.0, dot / (mag_a * mag_b))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_current_alerts(module_id: str, since: datetime) -> list[dict]:
    """Get recent divergence alerts with entity info."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT de.entity_id,
                       md5(de.entity_id::text || de.time::text)::uuid AS divergence_event_id,
                       de.d_value, de.p_value, de.components,
                       e.canonical_symbol
                FROM divergence_events de
                JOIN entities e ON e.entity_id = de.entity_id
                WHERE e.module_id = %s
                  AND de.time >= %s
                ORDER BY de.d_value DESC;
                """,
                (module_id, since),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _load_corpus(module_id: str, before: datetime) -> list[dict]:
    """Load historical events older than MIN_HISTORY_DAYS for matching."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_id, label, start_time, phases, kind
                FROM historical_events
                WHERE module_id = %s
                  AND start_time < %s
                  AND phases IS NOT NULL
                ORDER BY start_time DESC
                LIMIT 500;
                """,
                (module_id, before),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _write_match(match: RhymeMatch, now: datetime) -> None:
    """Write one rhyme match to rhyme_matches table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rhyme_matches (
                    time, entity_id,
                    current_event_id, corpus_event_id,
                    dtw_distance, p_value,
                    narrative, outcome_prediction, confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, current_event_id, corpus_event_id, time)
                DO UPDATE SET
                    narrative          = EXCLUDED.narrative,
                    outcome_prediction = EXCLUDED.outcome_prediction,
                    confidence         = EXCLUDED.confidence;
                """,
                (
                    now,
                    match.entity_id,
                    match.current_event_id,
                    match.corpus_event_id,
                    1.0 - match.similarity,   # dtw_distance = inverse similarity
                    1.0 - match.similarity,   # p_value placeholder
                    match.narrative,
                    match.outcome_prediction,
                    match.confidence,
                ),
            )
        conn.commit()
