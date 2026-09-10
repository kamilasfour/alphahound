"""Mention velocity signal — Sprint 2 crude-but-real output.

Rationale (PRD B5.1):
  "mention_volume_velocity" is the highest-weighted scoring component (20%
  base weight). Computing it from just raw_posts row counts is NOT the final
  form — the final version will use FinBERT-scored posts, source-tier-
  weighted aggregation, and regime multipliers. This Sprint 2 version is
  the stripped-down skeleton so we can eyeball whether the pipeline is
  producing sensible numbers.

Formula:
    v(ticker) = (posts_last_1h / baseline_posts_per_hour_7d) - 1

Where:
    baseline_posts_per_hour_7d = (posts in last 7 days) / (7 * 24)

Interpretation:
    v =  0  -> posting at baseline
    v =  1  -> posting 2x baseline (50% signal ~ interesting)
    v >  2  -> posting 3x+ baseline (very interesting, possible news)
    v = -0.5 -> half baseline (quieting down)

We then squash to a 1-10 score for `signal_scores` as:
    signal_1to10 = clamp(5 + v * 1.5, 1, 10)

Confidence for Sprint 2 is a placeholder: a simple function of the 7-day
baseline sample size (more history = more confident).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)


@dataclass
class VelocityResult:
    entity_id: str
    canonical_symbol: str
    posts_1h: int
    posts_7d: int
    baseline_per_hour: float
    velocity: float
    signal_1to10: float
    confidence_1to10: float


def _compute_velocity(posts_1h: int, posts_7d: int) -> tuple[float, float, float]:
    """Return (velocity, signal_1to10, confidence_1to10)."""
    baseline_per_hour = posts_7d / (7 * 24) if posts_7d > 0 else 0.0
    if baseline_per_hour <= 0:
        # Not enough history to compute velocity.
        velocity = 0.0 if posts_1h == 0 else float(posts_1h)  # raw burst
        confidence = 1.0  # very low confidence
    else:
        velocity = (posts_1h / baseline_per_hour) - 1.0
        # More 7d history -> higher confidence, saturating around ~500 posts.
        confidence = min(10.0, 1.0 + (posts_7d / 50.0))
    signal = max(1.0, min(10.0, 5.0 + velocity * 1.5))
    return velocity, signal, confidence


def compute_for_entity(entity_id: str, now: datetime | None = None) -> VelocityResult | None:
    """Compute velocity for one entity. Returns None if entity not found."""
    now = now or datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    seven_days_ago = now - timedelta(days=7)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.canonical_symbol,
                       COUNT(*) FILTER (WHERE r.time >= %s)                AS posts_1h,
                       COUNT(*) FILTER (WHERE r.time >= %s)                AS posts_7d
                FROM entities e
                LEFT JOIN raw_posts r ON r.entity_id = e.entity_id
                WHERE e.entity_id = %s
                GROUP BY e.canonical_symbol;
                """,
                (one_hour_ago, seven_days_ago, entity_id),
            )
            row = cur.fetchone()

    if row is None:
        return None

    symbol, posts_1h, posts_7d = row
    posts_1h = int(posts_1h or 0)
    posts_7d = int(posts_7d or 0)
    velocity, signal, confidence = _compute_velocity(posts_1h, posts_7d)
    baseline = posts_7d / (7 * 24) if posts_7d > 0 else 0.0
    return VelocityResult(
        entity_id=entity_id,
        canonical_symbol=symbol,
        posts_1h=posts_1h,
        posts_7d=posts_7d,
        baseline_per_hour=baseline,
        velocity=velocity,
        signal_1to10=signal,
        confidence_1to10=confidence,
    )


def compute_and_store_all(module_id: str = "stocks", min_posts_7d: int = 10) -> int:
    """Compute velocity for every entity with enough recent activity, store to signal_scores.

    Returns the number of rows written.
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.entity_id, e.canonical_symbol,
                       COUNT(*) FILTER (WHERE r.time >= %s) AS posts_1h,
                       COUNT(*) FILTER (WHERE r.time >= %s) AS posts_7d
                FROM entities e
                JOIN raw_posts r ON r.entity_id = e.entity_id
                WHERE e.module_id = %s
                  AND r.time >= %s
                GROUP BY e.entity_id, e.canonical_symbol
                HAVING COUNT(*) >= %s;
                """,
                (
                    now - timedelta(hours=1),
                    seven_days_ago,
                    module_id,
                    seven_days_ago,
                    min_posts_7d,
                ),
            )
            rows = cur.fetchall()

    if not rows:
        log.info("compute_and_store_all: no entities with >= %d posts in last 7d.", min_posts_7d)
        return 0

    to_insert = []
    for entity_id, symbol, p1h, p7d in rows:
        velocity, signal, confidence = _compute_velocity(int(p1h or 0), int(p7d or 0))
        weights_snapshot = {
            "method": "sprint2_mention_velocity_only",
            "baseline_per_hour": (int(p7d or 0) / (7 * 24)) if p7d else 0.0,
            "velocity": velocity,
            "posts_1h": int(p1h or 0),
            "posts_7d": int(p7d or 0),
        }
        to_insert.append(
            (now, str(entity_id), signal, confidence, "sprint2_velocity_only", psycopg.types.json.Json(weights_snapshot))
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO signal_scores (
                    time, entity_id, signal_1to10, confidence_1to10, regime, weights_snapshot
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, time) DO UPDATE
                    SET signal_1to10 = EXCLUDED.signal_1to10,
                        confidence_1to10 = EXCLUDED.confidence_1to10,
                        regime = EXCLUDED.regime,
                        weights_snapshot = EXCLUDED.weights_snapshot;
                """,
                to_insert,
            )
            inserted = cur.rowcount
        conn.commit()

    log.info("compute_and_store_all: wrote %d velocity signals.", inserted)
    return inserted
