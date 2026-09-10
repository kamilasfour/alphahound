"""Scoring orchestrator — drives FinBERT over unscored raw_posts.

max_posts cap prevents the 15-min scheduler job from hanging on large backlogs.
Backlog clears gradually across cycles at 200 posts/run instead of all at once.

Source class policy:
  retail_social      scored by FinBERT
  news_wire          scored by FinBERT
  analyst_curated    scored by FinBERT (Alpha Vantage + Substack)
  institutional_flow rule-based scorer (score-institutional command)
  price_data         never scored
"""
from __future__ import annotations

import logging
from datetime import datetime

from alphahound.engine.scoring.base import BaseScorer, get_scorer
from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

SCOREABLE_SOURCE_CLASSES = ("news_wire", "analyst_curated", "retail_social")  # news first — highest signal value
PULL_BATCH_SIZE = 2000  # score everything, no arbitrary cap


def score_new_posts(
    scorer: BaseScorer | None = None,
    dry_run: bool = False,
    max_posts: int | None = None,
) -> int:
    """Score unscored posts. max_posts=200 keeps scheduled runs under 5 min."""
    scorer = scorer or get_scorer()
    total_written = 0
    remaining = max_posts

    for source_class in SCOREABLE_SOURCE_CLASSES:
        if remaining is not None and remaining <= 0:
            log.info("max_posts=%d reached — stopping early", max_posts)
            break
        written = _score_source_class(source_class, scorer, dry_run=dry_run, max_posts=remaining)
        total_written += written
        if remaining is not None:
            remaining -= written
        log.info("Scored source_class=%s: wrote %d rows", source_class, written)

    return total_written


def _score_source_class(
    source_class: str,
    scorer: BaseScorer,
    dry_run: bool = False,
    max_posts: int | None = None,
) -> int:
    log.info("Scoring %s (cap=%s)", source_class, max_posts)
    total_written = 0

    while True:
        if max_posts is not None and total_written >= max_posts:
            break

        pull_limit = PULL_BATCH_SIZE
        if max_posts is not None:
            pull_limit = min(PULL_BATCH_SIZE, max_posts - total_written)

        posts = _pull_unscored(source_class, limit=pull_limit)
        if not posts:
            break

        scores = scorer.score_batch([p["text"] for p in posts])

        if not dry_run:
            written = _write_scores(posts, scores, source_class)
            total_written += written
        else:
            log.info("(dry-run) Would write %d scores", len(scores))
            break

        if len(posts) < pull_limit:
            break

    return total_written


def _pull_unscored(source_class, limit):
    """Pull unscored posts using pure NOT EXISTS check.
    No watermark filter -- that was causing posts to be permanently skipped.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rp.post_id, rp.time, rp.entity_id, rp.adapter_id, rp.source_class, rp.tier, rp.text "
                "FROM raw_posts rp "
                "WHERE rp.source_class = %s "
                "AND NOT EXISTS (SELECT 1 FROM sentiment_scores ss WHERE ss.entity_id=rp.entity_id AND ss.source_class=rp.source_class AND ss.time=rp.time) "
                "ORDER BY rp.time ASC LIMIT %s;",
                (source_class, limit),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _write_scores(posts, scores, source_class):
    rows = [(p["time"], p["entity_id"], source_class, float(s.polarity), float(s.confidence), p.get("tier","C"), 1) for p, s in zip(posts, scores)]
    if not rows:
        return 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO sentiment_scores (time,entity_id,source_class,polarity,confidence,tier,post_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (entity_id,source_class,time) DO NOTHING;",
                rows,
            )
            written = cur.rowcount
        conn.commit()
    return written


def _get_watermark(source_class):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_scored_at FROM scoring_watermark WHERE source_class=%s;", (source_class,))
            row = cur.fetchone()
    return row[0] if row else None


def _set_watermark(source_class, ts):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scoring_watermark (source_class,last_scored_at) VALUES (%s,%s) "
                "ON CONFLICT (source_class) DO UPDATE SET last_scored_at=EXCLUDED.last_scored_at, updated_at=now();",
                (source_class, ts),
            )
        conn.commit()


def reset_watermark(source_class):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM scoring_watermark WHERE source_class=%s;", (source_class,))
        conn.commit()
    log.info("Watermark reset for %s", source_class)
