"""Catalyst Calendar Engine — Sprint 11 S11-3.

Single source of truth for binary catalysts that power P6 scoring
in the Multi-Pillar Convergence Engine.

Aggregates three catalyst types into one queryable surface:
    1. EARNINGS  — from earnings_calendar table (Finnhub-sourced, refreshed every cycle)
    2. PDUFA     — FDA drug approval action dates (manually seeded, refreshed from FDA API)
    3. FOMC      — Federal Reserve meeting dates (seeded from Fed calendar, stable)

WHY THIS MATTERS
────────────────
A binary catalyst within 14–45 days is one of the highest-conviction
P6 signals. Options premium inflates into the event, then collapses
after — creating the exact asymmetric payoff profile we want for
strangles and vertical spreads.

CATALYST WINDOW
───────────────
    MIN 14 days — anything closer has priced-in risk (too late to enter cleanly)
    MAX 45 days — too far out loses options leverage
    SWEET SPOT 20–35 days — maximum premium/risk ratio for most structures

CATALYST TYPES AND STRUCTURES
──────────────────────────────
    EARNINGS  → LONG_STRANGLE (if directional uncertainty) or BULL/BEAR_CALL_SPREAD
    PDUFA     → LONG_STRANGLE (binary FDA outcome, both directions possible)
    FOMC      → Macro context modifier (not a per-ticker catalyst but affects sizing)

DATA SOURCES
────────────
    earnings_calendar  — existing DB table, populated by EarningsCalendarAdapter
    pdufa_calendar     — new DB table, seeded by this module
    fomc_calendar      — new DB table, seeded by this module

SEEDING STRATEGY
────────────────
    FOMC: dates for the rest of 2025 + full 2026 are known and stable.
          Seeded once here as static data, refreshed annually.

    PDUFA: FDA PDUFA action dates are published on FDA.gov.
           Initial seed covers high-profile 2025–2026 biotech catalysts
           from the research docs (VRDN June 30 PDUFA is live).
           Future: automated pull from FDA API.

    Earnings: already handled by EarningsCalendarAdapter — we just query it here.

INTEGRATION
───────────
    convergence_scorer.py calls get_catalyst_for_ticker() from this module.
    This replaces the inline _score_p6_catalyst() earnings-only logic
    with full EARNINGS + PDUFA coverage.

    CLI: alphahound signals catalysts [--days 45] [--ticker TICKER]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from alphahound.engine.storage import get_conn

log = logging.getLogger(__name__)

# ─── Catalyst window ─────────────────────────────────────────────────────────
CATALYST_MIN_DAYS = 14
CATALYST_MAX_DAYS = 45
SWEET_SPOT_MIN    = 20
SWEET_SPOT_MAX    = 40


# ─── Data shapes ─────────────────────────────────────────────────────────────

@dataclass
class Catalyst:
    ticker: Optional[str]          # None for macro catalysts (FOMC)
    catalyst_type: str             # "EARNINGS" | "PDUFA" | "FOMC"
    catalyst_date: date
    days_away: int
    description: str               # human-readable for UI
    in_sweet_spot: bool            # 20–35 days
    score: float                   # P6 score: 1.0 (sweet spot) or 0.5

    @property
    def is_ticker_specific(self) -> bool:
        return self.ticker is not None

    @property
    def recommended_structure(self) -> str:
        """Options structure implied by this catalyst type."""
        if self.catalyst_type in ("PDUFA", "FOMC"):
            return "LONG_STRANGLE"
        return "LONG_STRANGLE"  # earnings default; convergence scorer overrides with direction


# ─── Public API ──────────────────────────────────────────────────────────────

def get_catalyst_for_ticker(
    entity_id: str,
    ticker: str,
    min_days: int = CATALYST_MIN_DAYS,
    max_days: int = CATALYST_MAX_DAYS,
) -> Optional[Catalyst]:
    """Return the nearest qualifying catalyst for a ticker.

    Checks EARNINGS then PDUFA, returns the nearest one in window.
    Returns None if no catalyst found in window.
    """
    today = date.today()
    min_date = today + timedelta(days=min_days)
    max_date = today + timedelta(days=max_days)

    candidates: list[Catalyst] = []

    # 1. Earnings
    earnings = _get_earnings_catalyst(entity_id, ticker, today, min_date, max_date)
    if earnings:
        candidates.append(earnings)

    # 2. PDUFA
    pdufa = _get_pdufa_catalyst(entity_id, ticker, today, min_date, max_date)
    if pdufa:
        candidates.append(pdufa)

    if not candidates:
        return None

    # Return nearest catalyst
    return min(candidates, key=lambda c: c.days_away)


def get_upcoming_catalysts(
    days_ahead: int = CATALYST_MAX_DAYS,
    include_fomc: bool = True,
) -> list[Catalyst]:
    """Return all catalysts in the next N days, sorted by date.

    Used by the dashboard catalyst calendar view.
    """
    today    = date.today()
    max_date = today + timedelta(days=days_ahead)

    catalysts: list[Catalyst] = []

    # Earnings
    catalysts.extend(_get_all_earnings(today, max_date))

    # PDUFA
    catalysts.extend(_get_all_pdufa(today, max_date))

    # FOMC
    if include_fomc:
        catalysts.extend(_get_fomc_catalysts(today, max_date))

    catalysts.sort(key=lambda c: c.catalyst_date)
    return catalysts


def get_fomc_context(days_ahead: int = CATALYST_MAX_DAYS) -> Optional[Catalyst]:
    """Return next FOMC meeting if within window. Used as macro P6 modifier."""
    today    = date.today()
    max_date = today + timedelta(days=days_ahead)
    fomc_list = _get_fomc_catalysts(today, max_date)
    if not fomc_list:
        return None
    return min(fomc_list, key=lambda c: c.days_away)


def seed_static_catalysts() -> tuple[int, int]:
    """Seed PDUFA and FOMC tables with known dates. Returns (pdufa_written, fomc_written).

    Safe to call repeatedly — uses ON CONFLICT DO NOTHING.
    """
    _ensure_tables()
    pdufa_written = _seed_pdufa()
    fomc_written  = _seed_fomc()
    log.info(
        "Catalyst calendar seeded: %d PDUFA, %d FOMC dates",
        pdufa_written, fomc_written,
    )
    return pdufa_written, fomc_written


# ─── Private: earnings query ─────────────────────────────────────────────────

def _get_earnings_catalyst(
    entity_id: str, ticker: str,
    today: date, min_date: date, max_date: date,
) -> Optional[Catalyst]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT earnings_date, fiscal_quarter, estimate_eps
                    FROM earnings_calendar
                    WHERE entity_id = %s
                      AND earnings_date BETWEEN %s AND %s
                      AND beat IS NULL
                    ORDER BY earnings_date ASC
                    LIMIT 1;
                    """,
                    (entity_id, min_date, max_date),
                )
                row = cur.fetchone()
    except Exception as exc:
        log.debug("Earnings query failed for %s: %s", ticker, exc)
        return None

    if not row:
        return None

    earnings_date, fiscal_quarter, estimate_eps = row
    days_away = (earnings_date - today).days
    in_sweet = SWEET_SPOT_MIN <= days_away <= SWEET_SPOT_MAX
    score    = 1.0 if in_sweet else 0.5

    period_str = f" ({fiscal_quarter})" if fiscal_quarter else ""
    eps_str    = f", EPS est={estimate_eps:.2f}" if estimate_eps else ""
    desc = f"Earnings{period_str} on {earnings_date.isoformat()} ({days_away}d){eps_str}"

    return Catalyst(
        ticker=ticker,
        catalyst_type="EARNINGS",
        catalyst_date=earnings_date,
        days_away=days_away,
        description=desc,
        in_sweet_spot=in_sweet,
        score=score,
    )


def _get_all_earnings(today: date, max_date: date) -> list[Catalyst]:
    min_date = today  # include today for the broad calendar view
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.canonical_symbol, ec.earnings_date, ec.fiscal_quarter, ec.estimate_eps
                    FROM earnings_calendar ec
                    JOIN entities e ON e.entity_id = ec.entity_id
                    WHERE ec.earnings_date BETWEEN %s AND %s
                      AND ec.beat IS NULL
                    ORDER BY ec.earnings_date ASC;
                    """,
                    (min_date, max_date),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.debug("Earnings calendar query failed: %s", exc)
        return []

    catalysts = []
    for ticker, earnings_date, fiscal_quarter, estimate_eps in rows:
        days_away = (earnings_date - today).days
        in_sweet  = SWEET_SPOT_MIN <= days_away <= SWEET_SPOT_MAX
        score     = 1.0 if in_sweet else 0.5
        period_str = f" ({fiscal_quarter})" if fiscal_quarter else ""
        eps_str    = f", EPS est={estimate_eps:.2f}" if estimate_eps else ""
        catalysts.append(Catalyst(
            ticker=ticker,
            catalyst_type="EARNINGS",
            catalyst_date=earnings_date,
            days_away=days_away,
            description=f"Earnings{period_str} ({days_away}d){eps_str}",
            in_sweet_spot=in_sweet,
            score=score,
        ))
    return catalysts


# ─── Private: PDUFA query ────────────────────────────────────────────────────

def _get_pdufa_catalyst(
    entity_id: str, ticker: str,
    today: date, min_date: date, max_date: date,
) -> Optional[Catalyst]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pdufa_date, drug_name, indication, nda_bla_number
                    FROM pdufa_calendar
                    WHERE entity_id = %s
                      AND pdufa_date BETWEEN %s AND %s
                      AND outcome IS NULL
                    ORDER BY pdufa_date ASC
                    LIMIT 1;
                    """,
                    (entity_id, min_date, max_date),
                )
                row = cur.fetchone()
    except Exception as exc:
        log.debug("PDUFA query failed for %s: %s", ticker, exc)
        return None

    if not row:
        return None

    pdufa_date, drug_name, indication, nda_num = row
    days_away = (pdufa_date - today).days
    in_sweet  = SWEET_SPOT_MIN <= days_away <= SWEET_SPOT_MAX
    score     = 1.0 if in_sweet else 0.5

    drug_str = f" — {drug_name}" if drug_name else ""
    ind_str  = f" ({indication})" if indication else ""
    desc = f"FDA PDUFA{drug_str}{ind_str} on {pdufa_date.isoformat()} ({days_away}d)"

    return Catalyst(
        ticker=ticker,
        catalyst_type="PDUFA",
        catalyst_date=pdufa_date,
        days_away=days_away,
        description=desc,
        in_sweet_spot=in_sweet,
        score=score,
    )


def _get_all_pdufa(today: date, max_date: date) -> list[Catalyst]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.canonical_symbol, p.pdufa_date, p.drug_name, p.indication
                    FROM pdufa_calendar p
                    JOIN entities e ON e.entity_id = p.entity_id
                    WHERE p.pdufa_date BETWEEN %s AND %s
                      AND p.outcome IS NULL
                    ORDER BY p.pdufa_date ASC;
                    """,
                    (today, max_date),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.debug("PDUFA calendar query failed: %s", exc)
        return []

    catalysts = []
    for ticker, pdufa_date, drug_name, indication in rows:
        days_away = (pdufa_date - today).days
        in_sweet  = SWEET_SPOT_MIN <= days_away <= SWEET_SPOT_MAX
        score     = 1.0 if in_sweet else 0.5
        drug_str  = f" {drug_name}" if drug_name else ""
        catalysts.append(Catalyst(
            ticker=ticker,
            catalyst_type="PDUFA",
            catalyst_date=pdufa_date,
            days_away=days_away,
            description=f"FDA PDUFA{drug_str} ({days_away}d)",
            in_sweet_spot=in_sweet,
            score=score,
        ))
    return catalysts


# ─── Private: FOMC query ─────────────────────────────────────────────────────

def _get_fomc_catalysts(today: date, max_date: date) -> list[Catalyst]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT meeting_date, decision, rate_change_bps, notes
                    FROM fomc_calendar
                    WHERE meeting_date BETWEEN %s AND %s
                      AND decision IS NULL
                    ORDER BY meeting_date ASC;
                    """,
                    (today, max_date),
                )
                rows = cur.fetchall()
    except Exception as exc:
        log.debug("FOMC query failed: %s", exc)
        return []

    catalysts = []
    for meeting_date, decision, rate_change_bps, notes in rows:
        days_away = (meeting_date - today).days
        in_sweet  = SWEET_SPOT_MIN <= days_away <= SWEET_SPOT_MAX
        notes_str = f" — {notes}" if notes else ""
        catalysts.append(Catalyst(
            ticker=None,
            catalyst_type="FOMC",
            catalyst_date=meeting_date,
            days_away=days_away,
            description=f"FOMC meeting on {meeting_date.isoformat()} ({days_away}d){notes_str}",
            in_sweet_spot=in_sweet,
            score=1.0 if in_sweet else 0.5,
        ))
    return catalysts


# ─── Table setup ─────────────────────────────────────────────────────────────

def _ensure_tables() -> None:
    """Create pdufa_calendar and fomc_calendar tables if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # PDUFA calendar — FDA PDUFA target action dates
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pdufa_calendar (
                    id              SERIAL PRIMARY KEY,
                    entity_id       UUID        NOT NULL REFERENCES entities(entity_id),
                    ticker          TEXT        NOT NULL,
                    pdufa_date      DATE        NOT NULL,
                    drug_name       TEXT,
                    indication      TEXT,
                    nda_bla_number  TEXT,
                    application_type TEXT,       -- "NDA", "BLA", "sNDA", "sBLA"
                    outcome         TEXT,         -- NULL=pending, "APPROVED", "CRL", "WITHDRAWN"
                    outcome_date    DATE,
                    notes           TEXT,
                    source          TEXT DEFAULT 'manual_seed',
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (entity_id, pdufa_date, drug_name)
                );

                CREATE INDEX IF NOT EXISTS idx_pdufa_date
                    ON pdufa_calendar (pdufa_date)
                    WHERE outcome IS NULL;

                CREATE INDEX IF NOT EXISTS idx_pdufa_ticker
                    ON pdufa_calendar (ticker, pdufa_date);
            """)

            # FOMC calendar — Federal Reserve meeting dates
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fomc_calendar (
                    id              SERIAL PRIMARY KEY,
                    meeting_date    DATE        NOT NULL UNIQUE,
                    meeting_end_date DATE,       -- two-day meetings: end date
                    decision        TEXT,         -- NULL=pending, "HOLD", "HIKE", "CUT"
                    rate_change_bps INT,          -- basis points, NULL until decided
                    statement_time  TIME,         -- typically 2:00 PM ET
                    press_conf      BOOLEAN DEFAULT TRUE,
                    notes           TEXT,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS idx_fomc_pending
                    ON fomc_calendar (meeting_date)
                    WHERE decision IS NULL;
            """)
        conn.commit()
    log.debug("pdufa_calendar and fomc_calendar tables ensured")


# ─── Static seed data ────────────────────────────────────────────────────────

# FOMC 2025–2026 meeting dates (first day of two-day meetings)
# Source: Federal Reserve published meeting schedule
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
_FOMC_DATES = [
    # 2025 — remaining meetings
    ("2025-09-16", "2025-09-17", None),
    ("2025-10-28", "2025-10-29", None),
    ("2025-12-09", "2025-12-10", None),
    # 2026 — full schedule (rate currently 3.50–3.75%, 8-4 dissent split per research docs)
    ("2026-01-27", "2026-01-28", None),
    ("2026-03-17", "2026-03-18", None),
    ("2026-04-28", "2026-04-29", "Apr 28-29 meeting — 8-4 dissent split (most since 1992)"),
    ("2026-06-09", "2026-06-10", None),
    ("2026-07-28", "2026-07-29", None),
    ("2026-09-15", "2026-09-16", None),
    ("2026-10-27", "2026-10-28", None),
    ("2026-12-08", "2026-12-09", None),
]

# PDUFA dates — FDA target action dates for key biotech/pharma tickers
# Sources: FDA PDUFA calendar, company IR pages, research docs
# Format: (ticker, pdufa_date, drug_name, indication, application_type, notes)
_PDUFA_DATES = [
    # From research docs — VRDN is the highest-conviction live setup
    ("VRDN", "2026-06-30", "Veligrotug",    "Thyroid Eye Disease (chronic TED)",  "BLA",  "Priority Review + Breakthrough Therapy; THRIVE/THRIVE-2 Phase 3 clean wins; Amgen SC Tepezza competition priced in"),
    # Additional high-profile 2026 PDUFA dates (biotech calendar)
    ("SNDX", "2026-07-15", "Axatilimab",    "Chronic Graft-vs-Host Disease",       "BLA",  "Priority Review; Phase 3 AGAVE data"),
    ("INCY", "2026-08-01", "Zilurgisertib",  "Myelofibrosis",                       "NDA",  "Combination with ruxolitinib"),
    ("REGN", "2026-07-20", "Fianlimab",      "Non-Small Cell Lung Cancer",          "BLA",  "Priority Review; Phase 3 vs pembrolizumab"),
    ("ALNY", "2026-09-01", "Vutrisiran",     "ATTR Cardiomyopathy",                 "sNDA", "Label expansion; HELIOS-B data"),
    ("PTGX", "2026-06-15", "Izokibep",       "Psoriatic Arthritis",                 "BLA",  "Breakthrough Therapy"),
    ("KROS", "2026-08-20", "Avutometinib",   "Low-Grade Serous Ovarian Cancer",     "NDA",  "Accelerated Approval pathway; RAMP 201 data"),
    ("NTRA", "2026-07-01", "Signatera",      "Colorectal Cancer MRD Detection",     "PMA",  "Breakthrough Device; FDA De Novo pathway"),
]


def _seed_fomc() -> int:
    """Seed FOMC calendar. Returns rows written."""
    written = 0
    with get_conn() as conn:
        for meeting_date_str, end_date_str, notes in _FOMC_DATES:
            try:
                with conn.cursor() as cur:
                    # Check if already exists first — avoids rowcount=-1 ambiguity
                    cur.execute(
                        "SELECT 1 FROM fomc_calendar WHERE meeting_date = %s;",
                        (meeting_date_str,),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            """
                            INSERT INTO fomc_calendar
                                (meeting_date, meeting_end_date, statement_time, press_conf, notes)
                            VALUES (%s, %s, '14:00:00', TRUE, %s);
                            """,
                            (meeting_date_str, end_date_str, notes),
                        )
                        written += 1
                conn.commit()
            except Exception as exc:
                log.warning("FOMC seed failed for %s: %s", meeting_date_str, exc)
    return written


def _ensure_entity(conn, ticker: str) -> str | None:
    """Get or create an entity for ticker. Returns entity_id as str, or None on failure."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
            (ticker,),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])
        # Not found — insert it
        cur.execute(
            """
            INSERT INTO entities (module_id, canonical_symbol, kind)
            VALUES ('stocks', %s, 'ticker')
            ON CONFLICT (module_id, canonical_symbol, kind) DO NOTHING
            RETURNING entity_id;
            """,
            (ticker,),
        )
        row = cur.fetchone()
        if row:
            conn.commit()
            return str(row[0])
        # Race — re-fetch
        cur.execute(
            "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
            (ticker,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def _seed_pdufa() -> int:
    """Seed PDUFA calendar. Returns rows written."""
    written = 0
    with get_conn() as conn:
        for ticker, pdufa_date_str, drug_name, indication, app_type, notes in _PDUFA_DATES:
            try:
                entity_id = _ensure_entity(conn, ticker)
                if not entity_id:
                    log.warning("PDUFA seed: could not resolve entity for %s", ticker)
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM pdufa_calendar WHERE entity_id=%s AND pdufa_date=%s AND drug_name=%s;",
                        (entity_id, pdufa_date_str, drug_name),
                    )
                    if cur.fetchone() is None:
                        cur.execute(
                            """
                            INSERT INTO pdufa_calendar
                                (entity_id, ticker, pdufa_date, drug_name, indication,
                                 application_type, notes, source)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual_seed');
                            """,
                            (entity_id, ticker, pdufa_date_str, drug_name,
                             indication, app_type, notes),
                        )
                        written += 1
                conn.commit()
            except Exception as exc:
                log.warning("PDUFA seed failed for %s/%s: %s", ticker, pdufa_date_str, exc)
    return written


# ─── Catalyst summary for display ────────────────────────────────────────────

def format_catalyst_table(catalysts: list[Catalyst]) -> str:
    """Format catalyst list as a text table for CLI output."""
    if not catalysts:
        return "(no catalysts in window)"

    lines = [
        f"{'ticker':<8} {'type':<10} {'date':<12} {'days':>5}  {'sweet':>5}  description",
        "-" * 80,
    ]
    for c in catalysts:
        ticker_str = c.ticker or "MACRO"
        sweet_str  = "★" if c.in_sweet_spot else ""
        lines.append(
            f"{ticker_str:<8} {c.catalyst_type:<10} {c.catalyst_date.isoformat():<12} "
            f"{c.days_away:>5}  {sweet_str:>5}  {c.description[:45]}"
        )
    return "\n".join(lines)
