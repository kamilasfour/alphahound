"""Storage layer — talks to Postgres.

Responsibilities:
  - Open a connection pool to the DB (psycopg 3, sync for now).
  - Resolve entity symbols to canonical entity_ids, creating rows when new.
  - Write batches of Posts to raw_posts, deduplicating on (adapter_id, external_id, entity_id).

Design notes:
  - Sync psycopg for Sprint 1 simplicity. Async can come later; ApeWisdom volume is tiny.
  - Uses a module-level connection pool so CLI commands share state.
  - EntityResolver is an in-memory cache on top of the DB; cold lookups hit the DB,
    warm lookups are dict lookups. Safe because the DB is the source of truth.

Sprint 5 change: write_posts now respects post.source_class when set, falling back to
adapter_meta.source_class. This allows multi-class adapters (e.g. Finnhub produces both
retail_social sentiment posts and news_wire article posts from a single adapter).
"""
from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .adapters.models import Post


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the process-wide connection pool (lazy-init)."""
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
                "then load with python-dotenv or set it in your shell."
            )
        _pool = ConnectionPool(dsn, min_size=1, max_size=5, open=True)
    return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    """Borrow a connection from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    """Close the pool (call at process exit)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Entity resolution (PRD A9.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityKey:
    module_id: str
    canonical_symbol: str
    kind: str


class EntityResolver:
    """Resolves (module_id, symbol, kind) -> entity_id UUID.

    Creates a new entity row on first observation. Caches in-process for speed.
    """

    def __init__(self) -> None:
        self._cache: dict[EntityKey, str] = {}

    def resolve(self, module_id: str, symbol: str, kind: str) -> str:
        """Return entity_id for the given symbol, inserting if new."""
        key = EntityKey(module_id=module_id, canonical_symbol=symbol, kind=kind)
        if key in self._cache:
            return self._cache[key]

        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Insert if absent; either way return the row's entity_id.
                cur.execute(
                    """
                    INSERT INTO entities (module_id, canonical_symbol, kind)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (module_id, canonical_symbol, kind) DO UPDATE
                        SET canonical_symbol = EXCLUDED.canonical_symbol
                    RETURNING entity_id;
                    """,
                    (module_id, symbol, kind),
                )
                row = cur.fetchone()
                assert row is not None
                entity_id = str(row["entity_id"])
            conn.commit()

        self._cache[key] = entity_id
        return entity_id


# ---------------------------------------------------------------------------
# Post storage
# ---------------------------------------------------------------------------


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_author(salt: str, author: str) -> str:
    """SHA-256(salt + author) per PRD A9.2. Raw author never stored."""
    return hashlib.sha256(f"{salt}{author}".encode("utf-8")).hexdigest()


@dataclass
class AdapterMeta:
    """Fetched once per ingestion run from source_adapters."""

    adapter_id: str
    module_id: str
    source_class: str
    tier: str


def load_adapter_meta(adapter_id: str) -> AdapterMeta:
    """Fetch adapter registration; raise if not found or disabled."""
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT adapter_id, module_id, source_class, tier, enabled
                FROM source_adapters
                WHERE adapter_id = %s;
                """,
                (adapter_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            f"Adapter '{adapter_id}' is not registered in source_adapters. "
            f"Run schema_4_seed_data.sql or insert the adapter row."
        )
    if not row["enabled"]:
        raise RuntimeError(f"Adapter '{adapter_id}' is registered but disabled.")

    return AdapterMeta(
        adapter_id=row["adapter_id"],
        module_id=row["module_id"],
        source_class=row["source_class"],
        tier=row["tier"],
    )


def _infer_entity_kind(symbol: str) -> str:
    """Infer the entity kind from a canonical symbol's prefix.

    Convention introduced in Sprint 2:
      'CIK:0001067983'  -> 'filer'  (SEC EDGAR filer)
      'AAPL', 'STNG'    -> 'ticker' (default for anything without a prefix)

    Prefix convention keeps entities distinct without needing adapter-side
    metadata. Later sprints may add 'sector' (XL*), 'etf' (VTI, SPY), etc.
    """
    if symbol.startswith("CIK:"):
        return "filer"
    return "ticker"


def write_posts(posts: Iterable[Post], adapter_meta: AdapterMeta, resolver: EntityResolver) -> int:
    """Insert posts into raw_posts. Returns the number of rows written (post-dedup).

    A post with N entity_ids becomes N rows (one per entity). Dedup is on
    (adapter_id, external_id, entity_id, time) — ON CONFLICT DO NOTHING.

    source_class precedence: post.source_class (if set) > adapter_meta.source_class.
    This allows multi-class adapters (e.g. Finnhub) to emit retail_social and
    news_wire posts from the same adapter without corrupting divergence math.
    """
    rows: list[tuple] = []
    for post in posts:
        if not post.entity_ids:
            # Skip posts with no resolved entity — nothing to score.
            continue
        text_hash = _hash_text(post.text)

        # Respect per-post source_class override (Sprint 5).
        effective_source_class = post.source_class or adapter_meta.source_class

        for symbol in post.entity_ids:
            entity_id = resolver.resolve(
                module_id=adapter_meta.module_id,
                symbol=symbol,
                kind=_infer_entity_kind(symbol),
            )
            rows.append((
                post.published_at,
                adapter_meta.adapter_id,
                entity_id,
                effective_source_class,
                adapter_meta.tier,
                post.external_id,
                post.author_hash,
                post.text,
                text_hash,
                psycopg.types.json.Json(post.raw) if post.raw else None,
                post.observed_at,
            ))

    if not rows:
        return 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO raw_posts (
                    time, adapter_id, entity_id, source_class, tier,
                    external_id, author_hash, text, text_hash, raw, observed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (adapter_id, external_id, entity_id, time) DO NOTHING;
                """,
                rows,
            )
            inserted = cur.rowcount
        conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Ingest run tracking (PRD A11 SLOs; Sprint 2)
# ---------------------------------------------------------------------------


def start_ingest_run(adapter_id: str, host: str | None = None, details: dict | None = None) -> str:
    """Insert a new ingest_runs row, return its run_id."""
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO ingest_runs (adapter_id, host, details)
                VALUES (%s, %s, %s)
                RETURNING run_id;
                """,
                (adapter_id, host, psycopg.types.json.Json(details) if details else None),
            )
            row = cur.fetchone()
            assert row is not None
            run_id = str(row["run_id"])
        conn.commit()
    return run_id


def finish_ingest_run(
    run_id: str,
    *,
    posts_fetched: int,
    posts_written: int,
    error: str | None = None,
) -> None:
    """Close out a run with final counts (or an error message)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingest_runs
                SET finished_at = now(),
                    posts_fetched = %s,
                    posts_written = %s,
                    error = %s
                WHERE run_id = %s;
                """,
                (posts_fetched, posts_written, error, run_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Pipeline step tracking
# ---------------------------------------------------------------------------


def start_pipeline_step(step: str, host: str | None = None, details: dict | None = None) -> str:
    """Insert a pipeline_runs row for one scheduler step. Returns run_id."""
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs (step, host, details)
                VALUES (%s, %s, %s)
                RETURNING run_id;
                """,
                (step, host, psycopg.types.json.Json(details) if details else None),
            )
            row = cur.fetchone()
            assert row is not None
            run_id = str(row["run_id"])
        conn.commit()
    return run_id


def finish_pipeline_step(
    run_id: str,
    *,
    status: str = "ok",
    rows_affected: int | None = None,
    error: str | None = None,
    details: dict | None = None,
) -> None:
    """Close out a pipeline step row with result."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs
                SET finished_at   = now(),
                    status        = %s,
                    rows_affected = %s,
                    error         = LEFT(%s, 2000),
                    duration_ms   = EXTRACT(EPOCH FROM (now() - started_at))::int * 1000,
                    details       = COALESCE(%s::jsonb, details)
                WHERE run_id = %s;
                """,
                (
                    status,
                    rows_affected,
                    error,
                    psycopg.types.json.Json(details) if details else None,
                    run_id,
                ),
            )
        conn.commit()
