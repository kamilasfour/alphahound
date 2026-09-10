"""Cross-source divergence metric — PRD v1.2 §A7.1.

What this does:
  For each entity with posts from multiple source classes, compute whether
  those source classes *disagree* about sentiment more than they normally do.

Math (PRD §A7.1):
  1. For each source class c, compute the tier-weighted mean polarity
     over a 24h rolling window:
         s_hat_c = sum(polarity_i * tier_weight_i) / sum(tier_weight_i)

  2. Compute the cross-class standard deviation:
         sigma = stddev({s_hat_c for all classes with data})

  3. Normalise by the entity's historical baseline stddev (90d rolling mean):
         D = sigma / mu_historical(sigma)
     D > 2 means "disagreement is in the top 2.5% of recent history."

  4. Permutation null test (1000 samples):
     Shuffle class labels within the 24h window. If the observed D is not
     in the top 1% of the permuted distribution, suppress as noise.

  5. Write to divergence_events only when D > 2.0 AND p < 0.01
     AND at least 2 source classes have >= MIN_POSTS_PER_CLASS posts.

Sprint 5 change: _write_alert now uses ON CONFLICT DO UPDATE so re-scans
within the same hour update the existing row rather than appending duplicates.

Sprint 6 change: options_flow table is now pulled alongside sentiment_scores.
Each options_flow row contributes a synthetic polarity:
    bullish contract → +min(1.0, unusual_score / 50)
    bearish contract → -min(1.0, unusual_score / 50)
    neutral contract → 0.0
Options flow uses tier A (highest weight) because it represents real money
positioning by sophisticated market participants.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

WINDOW_HOURS = 24
D_THRESHOLD  = 2.0
P_THRESHOLD  = 0.01
N_PERMUTATIONS = 1000
MIN_POSTS_PER_CLASS = 5
MIN_CLASSES = 2

TIER_WEIGHTS = {"A": 2.0, "B": 1.5, "C": 1.0, "D": 0.5}


@dataclass
class DivergenceResult:
    entity_id: str
    canonical_symbol: str
    d_value: float
    p_value: float
    components: dict
    alert: bool


def compute_for_entity(entity_id: str, now: datetime | None = None) -> DivergenceResult | None:
    """Compute divergence for one entity. Returns None if not enough data."""
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=WINDOW_HOURS)
    rows = _pull_sentiment_window(entity_id, window_start)
    if not rows:
        return None
    symbol = rows[0]["canonical_symbol"]
    return _compute(entity_id, symbol, rows)


def scan_and_store(module_id: str = "stocks") -> int:
    """Scan all active entities, compute divergence, store alerts. Returns alert count."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=WINDOW_HOURS)

    entity_ids = _get_active_entities(module_id, window_start)
    if not entity_ids:
        log.info("No active entities for divergence scan.")
        return 0

    alerts = 0
    for entity_id in entity_ids:
        rows = _pull_sentiment_window(entity_id, window_start)
        if not rows:
            continue
        symbol = rows[0]["canonical_symbol"]
        result = _compute(entity_id, symbol, rows)
        if result is None:
            continue
        if result.alert:
            _write_alert(result, now)
            alerts += 1
            log.info(
                "Divergence alert: %s D=%.2f p=%.4f components=%s",
                symbol, result.d_value, result.p_value, result.components,
            )

    log.info("Divergence scan complete: %d alerts from %d entities.", alerts, len(entity_ids))
    return alerts


def _compute(entity_id: str, symbol: str, rows: list[dict]) -> DivergenceResult | None:
    """Core math. Returns DivergenceResult or None if insufficient data."""
    classes: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        sc = row["source_class"]
        classes.setdefault(sc, []).append((row["polarity"], row["tier"]))

    eligible = {
        sc: posts for sc, posts in classes.items()
        if len(posts) >= MIN_POSTS_PER_CLASS
    }
    if len(eligible) < MIN_CLASSES:
        return None

    class_means: dict[str, float] = {}
    for sc, posts in eligible.items():
        weights    = np.array([TIER_WEIGHTS.get(tier, 1.0) for _, tier in posts])
        polarities = np.array([p for p, _ in posts])
        class_means[sc] = float(np.average(polarities, weights=weights))

    means_arr = np.array(list(class_means.values()))
    sigma = float(np.std(means_arr, ddof=0))
    mu_historical = _get_historical_sigma(entity_id) or 0.1
    d_value = sigma / mu_historical if mu_historical > 0 else 0.0
    p_value = _permutation_test(rows, class_means, sigma, n_perms=N_PERMUTATIONS)
    alert = d_value > D_THRESHOLD and p_value < P_THRESHOLD

    return DivergenceResult(
        entity_id=entity_id,
        canonical_symbol=symbol,
        d_value=round(d_value, 4),
        p_value=round(p_value, 4),
        components=class_means,
        alert=alert,
    )


def _permutation_test(
    rows: list[dict],
    observed_means: dict[str, float],
    observed_sigma: float,
    n_perms: int = 1000,
) -> float:
    """Permutation null test — returns one-sided p-value."""
    polarities   = np.array([r["polarity"] for r in rows])
    class_labels = [r["source_class"] for r in rows]
    class_sizes  = {sc: sum(1 for c in class_labels if c == sc) for sc in set(class_labels)}
    eligible_classes = {sc for sc, size in class_sizes.items() if size >= MIN_POSTS_PER_CLASS}

    if len(eligible_classes) < MIN_CLASSES:
        return 1.0

    rng = np.random.default_rng(seed=42)
    perm_sigmas = np.zeros(n_perms)

    for i in range(n_perms):
        shuffled = rng.permutation(polarities)
        idx = 0
        perm_means = []
        for sc in sorted(eligible_classes):
            size  = class_sizes[sc]
            chunk = shuffled[idx : idx + size]
            idx  += size
            perm_means.append(float(np.mean(chunk)))
        perm_sigmas[i] = np.std(perm_means, ddof=0)

    return float(np.mean(perm_sigmas >= observed_sigma))


def _get_historical_sigma(entity_id: str) -> float | None:
    """Compute 90d rolling baseline stddev of cross-source divergence for an entity.

    Uses the last 90 days of divergence_events d_values as a proxy for
    historical volatility of disagreement. Falls back to 0.1 if < 10 rows.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT STDDEV(d_value)
                FROM divergence_events
                WHERE entity_id = %s
                  AND time >= now() - interval '90 days'
                HAVING COUNT(*) >= 10;
                """,
                (entity_id,),
            )
            row = cur.fetchone()
    if row and row[0] is not None:
        return max(0.01, float(row[0]))  # floor at 0.01 to avoid div-by-zero
    return None  # falls back to 0.1 in caller


def _pull_sentiment_window(entity_id: str, since: datetime) -> list[dict]:
    """Pull sentiment_scores + options_flow rows for an entity within the window.

    options_flow rows are converted to synthetic sentiment rows:
        bullish → polarity = +min(1.0, unusual_score / 50)
        bearish → polarity = -min(1.0, unusual_score / 50)
        neutral → polarity = 0.0
    Options flow uses tier A (highest weight, real money positioning).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Standard sentiment scores from FinBERT + institutional flow scorer.
            cur.execute(
                """
                SELECT ss.polarity, ss.confidence, ss.source_class, ss.tier,
                       e.canonical_symbol
                FROM sentiment_scores ss
                JOIN entities e ON e.entity_id = ss.entity_id
                WHERE ss.entity_id = %s
                  AND ss.time >= %s
                ORDER BY ss.time ASC;
                """,
                (entity_id, since),
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

            # Options flow — synthetic sentiment from contract direction + size.
            cur.execute(
                """
                SELECT
                    sentiment,
                    unusual_score,
                    e.canonical_symbol
                FROM options_flow of_
                JOIN entities e ON e.entity_id = of_.entity_id
                WHERE of_.entity_id = %s
                  AND of_.time >= %s
                  AND of_.sentiment IN ('bullish', 'bearish')
                  AND of_.unusual_score IS NOT NULL
                  AND of_.unusual_score > 0;
                """,
                (entity_id, since),
            )
            for sentiment, unusual_score, symbol in cur.fetchall():
                raw_polarity = min(1.0, unusual_score / 50.0)
                polarity = raw_polarity if sentiment == "bullish" else -raw_polarity
                rows.append({
                    "polarity":         round(polarity, 4),
                    "confidence":       round(min(1.0, unusual_score / 100.0), 4),
                    "source_class":     "options_flow",
                    "tier":             "A",
                    "canonical_symbol": symbol,
                })

    return rows


def _get_active_entities(module_id: str, since: datetime) -> list[str]:
    """Return entity_ids with sentiment_scores OR options_flow in the window."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ss.entity_id
                FROM sentiment_scores ss
                JOIN entities e ON e.entity_id = ss.entity_id
                WHERE e.module_id = %s
                  AND ss.time >= %s

                UNION

                SELECT DISTINCT of_.entity_id
                FROM options_flow of_
                JOIN entities e ON e.entity_id = of_.entity_id
                WHERE e.module_id = %s
                  AND of_.time >= %s;
                """,
                (module_id, since, module_id, since),
            )
            return [str(row[0]) for row in cur.fetchall()]


def _write_alert(result: DivergenceResult, now: datetime) -> None:
    """Write a divergence alert to divergence_events.

    Uses ON CONFLICT DO UPDATE so re-scans within the same hour
    refresh the existing row instead of creating duplicates.
    Time is truncated to the hour so all scans within the same hour
    land on the same PK row.
    """
    alert_hour = now.replace(minute=0, second=0, microsecond=0)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO divergence_events
                    (time, entity_id, d_value, p_value, components)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (entity_id, time) DO UPDATE
                    SET d_value    = EXCLUDED.d_value,
                        p_value    = EXCLUDED.p_value,
                        components = EXCLUDED.components;
                """,
                (
                    alert_hour,
                    result.entity_id,
                    result.d_value,
                    result.p_value,
                    psycopg_json(result.components),
                ),
            )
        conn.commit()


def psycopg_json(obj):
    import psycopg
    return psycopg.types.json.Json(obj)
