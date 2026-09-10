-- ============================================================
-- AlphaHound schema — chunk 2 of 4
-- Core hypertables (raw_posts, sentiment, signals, divergence, rhyme)
-- Run AFTER chunk 1. Safe to re-run.
-- ============================================================

-- raw_posts: every ingested post, one row per (post, entity).
CREATE TABLE IF NOT EXISTS raw_posts (
    time            TIMESTAMPTZ NOT NULL,
    post_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    adapter_id      TEXT NOT NULL REFERENCES source_adapters(adapter_id),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    source_class    TEXT NOT NULL,
    tier            TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    author_hash     TEXT,
    text            TEXT NOT NULL,
    text_hash       TEXT NOT NULL,
    raw             JSONB,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, time)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_posts_dedup
    ON raw_posts (adapter_id, external_id, entity_id, time);
CREATE INDEX IF NOT EXISTS idx_raw_posts_entity_time
    ON raw_posts (entity_id, time DESC);
SELECT create_hypertable(
    'raw_posts', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- sentiment_scores: FinBERT polarity per (entity, source_class) per tick.
CREATE TABLE IF NOT EXISTS sentiment_scores (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    source_class    TEXT NOT NULL,
    polarity        DOUBLE PRECISION NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL,
    tier            TEXT NOT NULL,
    post_count      INTEGER NOT NULL,
    PRIMARY KEY (entity_id, source_class, time)
);
CREATE INDEX IF NOT EXISTS idx_sentiment_entity_time
    ON sentiment_scores (entity_id, time DESC);
SELECT create_hypertable(
    'sentiment_scores', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- signal_scores: final 1–10 signal with confidence and the weight snapshot used.
CREATE TABLE IF NOT EXISTS signal_scores (
    time                TIMESTAMPTZ NOT NULL,
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    signal_1to10        DOUBLE PRECISION NOT NULL CHECK (signal_1to10 BETWEEN 0 AND 10),
    confidence_1to10    DOUBLE PRECISION NOT NULL CHECK (confidence_1to10 BETWEEN 0 AND 10),
    regime              TEXT,
    weights_snapshot    JSONB NOT NULL,
    PRIMARY KEY (entity_id, time)
);
SELECT create_hypertable(
    'signal_scores', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- divergence_events: PRD §A7.1.
CREATE TABLE IF NOT EXISTS divergence_events (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    d_value         DOUBLE PRECISION NOT NULL,
    p_value         DOUBLE PRECISION NOT NULL,
    components      JSONB NOT NULL,
    PRIMARY KEY (entity_id, time)
);
SELECT create_hypertable(
    'divergence_events', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- rhyme_matches: PRD §A7.3.
CREATE TABLE IF NOT EXISTS rhyme_matches (
    time                TIMESTAMPTZ NOT NULL,
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    current_event_id    UUID NOT NULL,
    corpus_event_id     UUID NOT NULL,
    dtw_distance        DOUBLE PRECISION NOT NULL,
    p_value             DOUBLE PRECISION NOT NULL,
    phase_position      JSONB,
    PRIMARY KEY (entity_id, current_event_id, corpus_event_id, time)
);
SELECT create_hypertable(
    'rhyme_matches', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);
