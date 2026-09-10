"""AlphaHound CLI — the `alphahound` command.

Sprint 5: massive, finnhub, alpha_vantage, quiver, divergence-scan with narratives
Sprint 6: unusual_whales, kalshi, score-institutional
Sprint 6.5: trade-advice, kalshi-watch, trade_log logging
Sprint 7: substack, earnings_calendar, earnings CLI command
Sprint 8: rhyme, hit-rate, backtest
Sprint 9: score-new --max-posts to prevent scheduler hangs
"""
from __future__ import annotations

import logging
import os
import socket
from pathlib import Path

import typer
from dotenv import load_dotenv

app = typer.Typer(name="alphahound", help="AlphaHound — multi-industry sentiment intelligence engine.", no_args_is_help=True, add_completion=False)
db_app = typer.Typer(help="Database utilities.")
signals_app = typer.Typer(help="Signal computations.")
app.add_typer(db_app, name="db")
app.add_typer(signals_app, name="signals")


@app.callback()
def _bootstrap() -> None:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            break
    level = os.environ.get("ALPHAHOUND_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    import atexit
    from alphahound.engine.storage import close_pool
    atexit.register(close_pool)


@db_app.command("check")
def db_check() -> None:
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_database(), current_user;")
            row = cur.fetchone()
            version, db, user = row
    typer.echo("✅ Connected")
    typer.echo(f"   Server:   {version.split(',')[0]}")
    typer.echo(f"   Database: {db}")
    typer.echo(f"   User:     {user}")


@db_app.command("tables")
def db_tables() -> None:
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1;")
            tables = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1;")
            hypertables = {r[0] for r in cur.fetchall()}
    typer.echo(f"Tables ({len(tables)}):")
    for t in tables:
        typer.echo(f"  - {t}{'  [hypertable]' if t in hypertables else ''}")


@db_app.command("ingest-runs")
def db_ingest_runs(tail: int = typer.Option(20)) -> None:
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT adapter_id, started_at, finished_at, posts_fetched, posts_written, COALESCE(LEFT(error,80),'') FROM ingest_runs ORDER BY started_at DESC LIMIT %s;", (tail,))
            rows = cur.fetchall()
    if not rows:
        typer.echo("(no runs yet)"); return
    typer.echo(f"{'adapter':<26} {'started':<22} {'dur_s':>6} {'fetch':>6} {'wrote':>6}  error")
    typer.echo("-" * 92)
    for adapter_id, started, finished, fetched, wrote, error in rows:
        dur = (finished - started).total_seconds() if finished else None
        dur_str = f"{dur:>6.2f}" if dur is not None else "   ...".rjust(6)
        typer.echo(f"{adapter_id:<26} {started.strftime('%Y-%m-%d %H:%M:%S'):<22} {dur_str} {fetched:>6} {wrote:>6}  {error}")


@db_app.command("divergence-events")
def db_divergence_events(tail: int = typer.Option(20)) -> None:
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT de.time, e.canonical_symbol, de.d_value, de.p_value, ps.price, ps.change_5d_pct, de.components
                FROM divergence_events de JOIN entities e ON e.entity_id = de.entity_id
                LEFT JOIN LATERAL (SELECT price, change_5d_pct FROM price_snapshots WHERE entity_id = de.entity_id ORDER BY time DESC LIMIT 1) ps ON true
                ORDER BY de.time DESC LIMIT %s;""", (tail,))
            rows = cur.fetchall()
    if not rows:
        typer.echo("(no divergence alerts yet)"); return
    typer.echo(f"{'time':<22} {'ticker':<8} {'D':>6} {'p':>7}  {'price':>7} {'5d%':>6}  narrative")
    typer.echo("-" * 100)
    for time, symbol, d_val, p_val, price, change_5d, components in rows:
        price_str = f"${price:.2f}" if price is not None else "  n/a "
        change_str = f"{change_5d:+.1f}%" if change_5d is not None else "  n/a"
        narrative = ((components or {}).get("narrative","") if isinstance(components, dict) else "")
        typer.echo(f"{time.strftime('%Y-%m-%d %H:%M:%S'):<22} {symbol:<8} {d_val:>6.3f} {p_val:>7.4f}  {price_str:>7} {change_str:>6}  {(narrative[:60]+'…') if len(narrative)>60 else narrative}")


DIRECT_WRITE_CLASSES = {"price_data":("price_snapshots","price snapshot"),"options_flow":("options_flow","options flow contract"),"prediction_market":("kalshi_contracts","prediction market contract")}

def _run_adapter(adapter, meta, resolver, dry_run):
    from datetime import datetime, timezone
    from alphahound.engine.storage import write_posts
    try:
        since = datetime.now(timezone.utc)
        posts = list(adapter.pull(since=since))
        fetched = len(posts)
        if dry_run: return (fetched, 0, None)
        written = write_posts(posts, adapter_meta=meta, resolver=resolver)
        return (fetched, written, None)
    except Exception as exc:
        return (0, 0, f"{type(exc).__name__}: {exc}")


@app.command("ingest")
def ingest(source: str = typer.Option(...,"--source"), max_pages: int = typer.Option(1), watchlist_size: int = typer.Option(20), dry_run: bool = typer.Option(False)) -> None:
    """Run one ingestion batch from a named adapter."""
    from alphahound.engine.storage import EntityResolver, finish_ingest_run, load_adapter_meta, start_ingest_run
    adapter = _build_adapter(source, max_pages=max_pages, watchlist_size=watchlist_size)
    meta = load_adapter_meta(adapter.adapter_id)
    typer.echo(f"Adapter: {meta.adapter_id}  module={meta.module_id}  class={meta.source_class}  tier={meta.tier}")
    resolver = EntityResolver()
    run_id = None if dry_run else start_ingest_run(meta.adapter_id, host=socket.gethostname())
    fetched, written, error = _run_adapter(adapter, meta, resolver, dry_run)
    if not dry_run and run_id is not None:
        finish_ingest_run(run_id, posts_fetched=fetched, posts_written=written, error=error)
    if error:
        typer.echo(f"❌ Error: {error}"); raise typer.Exit(code=1)
    if dry_run:
        typer.echo(f"Fetched {fetched} posts. (dry-run)")
    elif meta.source_class in DIRECT_WRITE_CLASSES:
        table, label = DIRECT_WRITE_CLASSES[meta.source_class]
        from alphahound.engine.storage import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                count = cur.fetchone()[0]
        typer.echo(f"✅ {label.capitalize()}s written. Total rows in {table}: {count}")
    else:
        typer.echo(f"✅ Fetched {fetched}, wrote {written} rows to raw_posts.")


@app.command("ingest-all")
def ingest_all(dry_run: bool = typer.Option(False)) -> None:
    """Run every enabled adapter sequentially."""
    from alphahound.engine.storage import EntityResolver, finish_ingest_run, get_conn, load_adapter_meta, start_ingest_run
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT adapter_id FROM source_adapters WHERE enabled = true ORDER BY adapter_id;")
            adapter_ids = [r[0] for r in cur.fetchall()]
    if not adapter_ids:
        typer.echo("No enabled adapters found."); return
    resolver = EntityResolver()
    failures = 0
    for adapter_id in adapter_ids:
        short_source = adapter_id.split(".", 1)[-1]
        try:
            adapter = _build_adapter(short_source)
        except typer.BadParameter:
            typer.echo(f"⚠ Skipping {adapter_id}"); continue
        meta = load_adapter_meta(adapter_id)
        run_id = None if dry_run else start_ingest_run(meta.adapter_id, host=socket.gethostname())
        fetched, written, error = _run_adapter(adapter, meta, resolver, dry_run)
        if not dry_run and run_id is not None:
            finish_ingest_run(run_id, posts_fetched=fetched, posts_written=written, error=error)
        if error:
            typer.echo(f"❌ {adapter_id}: {error}"); failures += 1
        else:
            typer.echo(f"✅ {adapter_id}: fetched={fetched} wrote={written}")
    if failures: raise typer.Exit(code=1)


def _build_adapter(source: str, *, max_pages: int = 1, watchlist_size: int = 20):
    if source in ("apewisdom","stocks.apewisdom"):
        from alphahound.modules.stocks.adapters.apewisdom import ApeWisdomAdapter; return ApeWisdomAdapter(max_pages=max_pages)
    if source in ("edgar","stocks.edgar"):
        from alphahound.modules.stocks.adapters.edgar import EdgarAdapter; return EdgarAdapter()
    if source in ("yahoo","yahoo_finance","stocks.yahoo_finance"):
        from alphahound.modules.stocks.adapters.yahoo_finance import YahooFinanceAdapter; return YahooFinanceAdapter()
    if source in ("stocktwits","stocks.stocktwits"):
        from alphahound.modules.stocks.adapters.stocktwits import StockTwitsAdapter
        from alphahound.modules.stocks.watchlist.watchlist import CORE_STOCKS, BROAD_ETFS, SECTOR_ETFS
        return StockTwitsAdapter(watchlist=CORE_STOCKS + BROAD_ETFS + SECTOR_ETFS)
    if source in ("massive","stocks.massive"):
        from alphahound.modules.stocks.adapters.massive import MassiveAdapter; return MassiveAdapter()
    if source in ("finnhub","stocks.finnhub"):
        from alphahound.modules.stocks.adapters.finnhub import FinnhubAdapter; return FinnhubAdapter()
    if source in ("alpha_vantage","stocks.alpha_vantage"):
        from alphahound.modules.stocks.adapters.alpha_vantage import AlphaVantageAdapter; return AlphaVantageAdapter()
    if source in ("quiver","stocks.quiver"):
        from alphahound.modules.stocks.adapters.quiver import QuiverAdapter; return QuiverAdapter()
    if source in ("unusual_whales","stocks.unusual_whales"):
        from alphahound.modules.stocks.adapters.unusual_whales import UnusualWhalesAdapter; return UnusualWhalesAdapter()
    if source in ("substack","stocks.substack"):
        from alphahound.modules.stocks.adapters.substack import SubstackAdapter; return SubstackAdapter()
    if source in ("massive_history","stocks.massive_history"):
        from alphahound.modules.stocks.adapters.massive_history import MassiveHistoryAdapter; return MassiveHistoryAdapter()
    if source in ("earnings_calendar","stocks.earnings_calendar"):
        from alphahound.engine.signals.earnings_calendar import EarningsCalendarAdapter; return EarningsCalendarAdapter()
    if source in ("kalshi","stocks.kalshi"):
        from alphahound.modules.stocks.adapters.kalshi import KalshiAdapter; return KalshiAdapter()
    raise typer.BadParameter(f"Unknown adapter '{source}'.")


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------

@signals_app.command("velocity")
def signals_velocity(ticker: str = typer.Option(...)) -> None:
    from alphahound.engine.signals.velocity import compute_for_entity
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';", (ticker.upper(),))
            row = cur.fetchone()
    if row is None:
        typer.echo(f"❓ {ticker} not found."); raise typer.Exit(1)
    result = compute_for_entity(str(row[0]))
    if result is None:
        typer.echo(f"❓ No velocity for {ticker}."); raise typer.Exit(1)
    typer.echo(f"Ticker: {result.canonical_symbol}\n  Posts 1h: {result.posts_1h}\n  Posts 7d: {result.posts_7d}\n  Velocity: {result.velocity:+.2f}\n  Signal: {result.signal_1to10:.2f}/10")


@signals_app.command("compute-all")
def signals_compute_all(min_posts_7d: int = typer.Option(10)) -> None:
    from alphahound.engine.signals.velocity import compute_and_store_all
    n = compute_and_store_all(module_id="stocks", min_posts_7d=min_posts_7d)
    typer.echo(f"✅ Wrote {n} velocity signals.")


@signals_app.command("score-new")
def signals_score_new(
    dry_run: bool = typer.Option(False),
    max_posts: int = typer.Option(0, "--max-posts", help="Max posts to score per run. 0 = unlimited. Use 200 for scheduled runs."),
) -> None:
    """Run FinBERT on unscored posts. Use --max-posts 200 in scheduled jobs to prevent hangs."""
    from alphahound.engine.scoring.orchestrator import score_new_posts
    limit = max_posts if max_posts > 0 else None
    if limit:
        typer.echo(f"Running FinBERT scoring (max {limit} posts)...")
    else:
        typer.echo("Running FinBERT scoring (all unscored posts)...")
    n = score_new_posts(dry_run=dry_run, max_posts=limit)
    typer.echo(f"✅ Wrote {n} sentiment scores." if not dry_run else f"(dry-run) Would write {n}.")


@signals_app.command("score-institutional")
def signals_score_institutional(dry_run: bool = typer.Option(False)) -> None:
    from alphahound.engine.scoring.institutional_flow_scorer import score_institutional_flow
    typer.echo("Running institutional flow scorer...")
    n = score_institutional_flow(dry_run=dry_run)
    typer.echo(f"✅ Wrote {n} scores." if not dry_run else f"(dry-run) Would write {n}.")


@signals_app.command("divergence")
def signals_divergence(ticker: str = typer.Option(...)) -> None:
    from alphahound.engine.signals.divergence import compute_for_entity
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';", (ticker.upper(),))
            row = cur.fetchone()
    if row is None:
        typer.echo(f"❓ {ticker} not found."); raise typer.Exit(1)
    result = compute_for_entity(str(row[0]))
    if result is None:
        typer.echo(f"❓ Not enough data for {ticker}."); raise typer.Exit(0)
    typer.echo(f"{ticker}  {'🚨 ALERT' if result.alert else 'OK'}\n  D={result.d_value:.4f}  p={result.p_value:.4f}")
    for sc, mean in result.components.items():
        typer.echo(f"    {sc:<22} {mean:+.4f}")


@signals_app.command("divergence-scan")
def signals_divergence_scan(no_narratives: bool = typer.Option(False)) -> None:
    from alphahound.engine.signals.divergence import scan_and_store
    from alphahound.engine.signals.narrative import generate_narratives
    n = scan_and_store(module_id="stocks")
    typer.echo(f"✅ Divergence scan complete: {n} alerts written.")
    if no_narratives or not os.environ.get("ANTHROPIC_API_KEY"):
        if not no_narratives: typer.echo("⚠ ANTHROPIC_API_KEY not set — skipping narratives.")
        return
    typer.echo("Generating Claude narratives...")
    narrated = generate_narratives(module_id="stocks")
    typer.echo(f"✅ Narratives generated: {narrated}")


@signals_app.command("trade-advice")
def signals_trade_advice(ticker: str = typer.Option(None,"--ticker"), min_d: float = typer.Option(2.0,"--min-d")) -> None:
    from alphahound.engine.signals.trade_advisor import advise, advise_all, log_recommendation, log_all_recommendations
    from alphahound.engine.storage import get_conn
    if ticker:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';", (ticker.upper(),))
                row = cur.fetchone()
        if row is None:
            typer.echo(f"❓ {ticker} not found."); raise typer.Exit(1)
        rec = advise(str(row[0]))
        if rec is None:
            typer.echo(f"❓ No active alert for {ticker}."); raise typer.Exit(0)
        log_recommendation(rec); typer.echo(rec.display())
    else:
        recs = advise_all(module_id="stocks", min_d=min_d)
        log_all_recommendations(recs)
        if not recs:
            typer.echo(f"No actionable alerts above D={min_d}."); raise typer.Exit(0)
        typer.echo(f"{'='*60}\n  TRADE RECOMMENDATIONS  ({len(recs)} alerts)\n{'='*60}")
        for rec in recs:
            typer.echo(rec.display()); typer.echo("")


@signals_app.command("kalshi-watch")
def signals_kalshi_watch(min_d: float = typer.Option(2.0,"--min-d")) -> None:
    from alphahound.engine.signals.trade_advisor import advise_all, _get_bankroll
    from alphahound.engine.signals.kalshi_watcher import scan_opportunities
    recs = advise_all(module_id="stocks", min_d=min_d)
    if not recs:
        typer.echo(f"No actionable alerts above D={min_d}."); raise typer.Exit(0)
    typer.echo(f"Found {len(recs)} alerts. Scanning Kalshi...")
    opportunities = scan_opportunities(recs, bankroll=_get_bankroll())
    if not opportunities:
        typer.echo("No Kalshi contracts found.\n(Stock contracts open 9:30am-4pm ET)"); return
    typer.echo(f"\n{'='*60}\n  KALSHI OPPORTUNITIES  ({len(opportunities)} found)\n{'='*60}")
    for opp in opportunities:
        typer.echo(opp.display()); typer.echo("")


@signals_app.command("earnings")
def signals_earnings(days: int = typer.Option(14,"--days")) -> None:
    from alphahound.engine.signals.earnings_calendar import get_upcoming_earnings
    upcoming = get_upcoming_earnings(days_ahead=days)
    if not upcoming:
        typer.echo(f"No earnings in next {days} days."); return
    typer.echo(f"{'ticker':<8} {'earnings_date':<14}"); typer.echo("-" * 24)
    for ticker, dt in sorted(upcoming.items(), key=lambda x: x[1]):
        typer.echo(f"{ticker:<8} {dt.strftime('%Y-%m-%d'):<14}")


@signals_app.command("rhyme")
def signals_rhyme(ticker: str = typer.Option(None,"--ticker")) -> None:
    from alphahound.engine.signals.rhyme_engine import run_rhyme_scan, get_rhyme_summary
    from alphahound.engine.storage import get_conn
    if ticker:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';", (ticker.upper(),))
                row = cur.fetchone()
        if row is None:
            typer.echo(f"❓ {ticker} not found."); raise typer.Exit(1)
        matches = get_rhyme_summary(str(row[0]))
        if not matches:
            typer.echo(f"No rhyme matches for {ticker}."); return
        for m in matches:
            typer.echo(f"  {m['narrative']}")
            if m.get("outcome_prediction"):
                typer.echo(f"  → {m['outcome_prediction'].upper()}  confidence={m.get('confidence','n/a')}")
            typer.echo("")
    else:
        typer.echo("Running Rhyme Engine scan...")
        n = run_rhyme_scan(module_id="stocks")
        typer.echo(f"✅ Rhyme scan complete: {n} matches written.")


@signals_app.command("hit-rate")
def signals_hit_rate() -> None:
    from alphahound.engine.signals.hit_rate import compute_hit_rate
    typer.echo("Computing hit rate...")
    results = compute_hit_rate(module_id="stocks")
    if not results:
        typer.echo("No resolved signals yet — check back after May 5."); return
    typer.echo(f"\n{'='*50}\n  SIGNAL HIT RATE\n{'='*50}")
    for window, stats in results.items():
        typer.echo(f"\n  {window}: {stats['correct_signals']}/{stats['total_signals']} = {stats['hit_rate_pct']:.1f}%")
        if stats.get("expectancy") is not None:
            typer.echo(f"    Expectancy: {stats['expectancy']:+.3f}%")


@signals_app.command("execute")
def signals_execute(
    ticker: str = typer.Option(None, "--ticker"),
    min_d:  float = typer.Option(2.0, "--min-d"),
) -> None:
    """Place Alpaca paper orders for current trade recommendations."""
    from alphahound.engine.execution.executor import execute_all, execute_ticker

    if ticker:
        result = execute_ticker(ticker.upper())
        results = [result]
    else:
        results = execute_all(module_id="stocks", min_d=min_d)

    if not results:
        typer.echo("No results."); return

    if results[0].get("status") == "market_closed":
        typer.echo(f"⏸  Market is closed. Next open: {results[0].get('next_open', 'unknown')}"); return

    if results[0].get("status") == "no_alerts":
        typer.echo(f"No actionable alerts above D={min_d}."); return

    typer.echo(f"\n{'='*60}\n  ALPACA PAPER EXECUTION\n{'='*60}")
    placed = skipped = errors = 0
    for r in results:
        status = r.get("status")
        t      = r.get("ticker", "")
        if status == "placed":
            typer.echo(
                f"  ✅ {t:<6}  {r['side']:<11}  ${r['notional']:.0f}"
                f"  conviction={r['conviction']:.1f}  p={r['signal_prob']:.0%}"
                f"  order={r['order_id'][:8]}…"
            )
            placed += 1
        elif status in ("already_open", "already_executed_today"):
            typer.echo(f"  ⏭  {t:<6}  {status}")
            skipped += 1
        elif status == "position_too_small":
            typer.echo(f"  ⏭  {t:<6}  position_too_small (${r.get('position_usd', 0):.0f})")
            skipped += 1
        elif status == "portfolio_cap_reached":
            typer.echo(
                f"  🛑 {t:<6}  PORTFOLIO CAP  deployed={r.get('deployed_pct',0):.1f}%"
                f" >= max={r.get('max_pct',0):.1f}%"
                f"  equity=${r.get('equity',0):.0f}  buying_power=${r.get('buying_power',0):.0f}"
            )
            skipped += 1
        elif status == "tech_rejected":
            typer.echo(
                f"  ❌ {t:<6}  TECH REJECTED  score={r.get('tech_score',0)}/5  {r.get('tech_reason','')[:60]}"
            )
            errors += 1
        elif status == "error":
            typer.echo(f"  ❌ {t:<6}  {r.get('error', 'unknown error')}")
            errors += 1
        else:
            typer.echo(f"  ℹ  {t:<6}  {status}")
            skipped += 1

    typer.echo(f"\n  Placed: {placed}  Skipped: {skipped}  Errors: {errors}")


@signals_app.command("close-positions")
def signals_close_positions(
    ticker: str = typer.Option(None, "--ticker"),
) -> None:
    """Check open paper positions and close those that hit exit criteria."""
    from alphahound.engine.execution.close_positions import close_aged_positions, force_close

    if ticker:
        result = force_close(ticker.upper())
        results = [result]
    else:
        typer.echo("Checking open positions...")
        results = close_aged_positions()

    if not results:
        typer.echo("No open positions."); return

    if results[0].get("status") == "no_open_positions":
        typer.echo("No open paper positions."); return

    typer.echo(f"\n{'='*60}\n  POSITION REVIEW\n{'='*60}")
    closed = holding = 0
    for r in results:
        status = r.get("status")
        t      = r.get("ticker", "")
        if status == "closed":
            pnl     = r.get("pnl", 0) or 0
            pnl_pct = r.get("pnl_pct", 0) or 0
            sign    = "+" if pnl >= 0 else ""
            typer.echo(
                f"  🔒 {t:<6}  CLOSED  pnl={sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)"
                f"  reason={r.get('reason', '')}"
            )
            closed += 1
        elif status == "holding":
            pl      = r.get("unrealized_pl", 0) or 0
            pl_pct  = r.get("unrealized_pct", 0) or 0
            sign    = "+" if pl >= 0 else ""
            typer.echo(f"  📊 {t:<6}  HOLDING  unrealized={sign}${pl:.2f} ({sign}{pl_pct:.1f}%)")
            holding += 1
        elif status == "force_closed":
            typer.echo(f"  🔒 {t:<6}  FORCE CLOSED  order={r.get('close_order_id','')[:8]}…")
            closed += 1
        elif status == "no_position":
            typer.echo(f"  ℹ  {t:<6}  no open position")
        else:
            typer.echo(f"  ℹ  {t:<6}  {status}")

    typer.echo(f"\n  Closed: {closed}  Holding: {holding}")


@signals_app.command("score-sectors")
def signals_score_sectors() -> None:
    """Aggregate constituent stock sentiment into sector/thematic ETF scores."""
    from alphahound.engine.scoring.sector_rollup_scorer import score_all_sectors
    typer.echo("Running sector rollup scorer...")
    written = score_all_sectors()
    typer.echo(f"\u2705 Sector rollup complete: {written} ETF scores written to sentiment_scores.")


@signals_app.command("seed-relationships")
def signals_seed_relationships() -> None:
    """Seed entity_relationships table from SECTOR_CONSTITUENTS map."""
    from alphahound.engine.scoring.sector_rollup_scorer import seed_entity_relationships
    typer.echo("Seeding entity relationships...")
    inserted = seed_entity_relationships()
    typer.echo(f"\u2705 Seeded {inserted} constituent relationships.")


@signals_app.command("macro-check")
def signals_macro_check() -> None:
    """Show current global macro context and risk verdict."""
    from alphahound.engine.signals.macro_context import get_macro_context
    result = get_macro_context()
    verdict_color = {"RISK_ON": "\033[32m", "NEUTRAL": "\033[33m", "RISK_OFF": "\033[31m", "NO_DATA": "\033[90m"}
    reset = "\033[0m"
    col = verdict_color.get(result.verdict.value, "")
    typer.echo(f"\n{'='*55}\n  MACRO CONTEXT\n{'='*55}")
    typer.echo(f"  Verdict:  {col}{result.verdict.value}{reset}")
    typer.echo(f"  Score:    {result.score:+.4f}")
    typer.echo(f"  Modifier: {result.size_modifier:.0%} size")
    typer.echo(f"  Reason:   {result.reason}")
    if result.signals:
        typer.echo(f"\n  Instrument signals (1d change):")
        for ticker, chg in sorted(result.signals.items(), key=lambda x: abs(x[1]), reverse=True):
            contrib = result.contributors.get(ticker, 0)
            arrow = "+" if chg > 0 else "-"
            typer.echo(f"    {arrow} {ticker:<5}  {chg:+.2f}%   contrib={contrib:+.3f}")


@signals_app.command("tech-backfill")
def signals_tech_backfill() -> None:
    """One-time backfill of 60 days of daily OHLCV into price_daily for technical analysis."""
    from alphahound.modules.stocks.adapters.massive_history import MassiveHistoryAdapter
    from alphahound.modules.stocks.adapters.massive import WATCHLIST
    typer.echo(f"Backfilling 60 days of daily OHLCV for {len(WATCHLIST)} tickers...")
    adapter = MassiveHistoryAdapter(backfill=True)
    from datetime import datetime, timezone
    list(adapter.pull(since=datetime.now(timezone.utc)))
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT entity_id) FROM price_daily;")
            total, tickers = cur.fetchone()
    typer.echo(f"\u2705 Backfill complete: {total} daily bars across {tickers} tickers in price_daily.")


@signals_app.command("tech-check")
def signals_tech_check(ticker: str = typer.Option(..., "--ticker")) -> None:
    """Run the technical gate for a single ticker and show indicator values."""
    from alphahound.engine.execution.technical_gate import check as tech_check
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                (ticker.upper(),),
            )
            row = cur.fetchone()
    if row is None:
        typer.echo(f"❓ {ticker} not found."); raise typer.Exit(1)
    result = tech_check(str(row[0]), ticker.upper(), "LONG")
    typer.echo(f"\nTechnical check for {ticker.upper()} (tested as LONG):")
    typer.echo(result.display())


@signals_app.command("health-check")
def signals_health_check() -> None:
    """Run full system health checks + self-diagnostics. Saves to DB."""
    from alphahound.engine.health_monitor import run_health_checks, save_health_report
    from alphahound.engine.diagnostics import run_diagnostics, save_diagnostics

    # Health checks
    report = run_health_checks()
    save_health_report(report)

    # Self-diagnostics — auto-detect and auto-fix issues
    findings = run_diagnostics()
    save_diagnostics(findings)

    overall_icon = {"GREEN": "\u2705", "YELLOW": "\u26a0\ufe0f", "RED": "\u274c"}.get(report.overall, "\u2753")
    typer.echo("\n{}  {}  {}  HEALTH {}\n{}".format("="*50, "SYSTEM HEALTH", overall_icon, report.overall, "="*50))
    for item in report.items:
        icon = {"GREEN": "\u2705", "YELLOW": "\u26a0\ufe0f ", "RED": "\u274c"}.get(item.status, "\u2753")
        detail = "  ({})".format(item.detail) if item.detail else ""
        typer.echo("  {} {:<22} {}{}".format(icon, item.name, item.value, detail))

    if findings:
        typer.echo("\nDIAGNOSTICS:")
        for f in findings:
            icon = "\u274c" if f["severity"] == "RED" else "\u26a0\ufe0f"
            typer.echo("  {} [{}] {}".format(icon, f["rule"], f["message"][:80]))
    else:
        typer.echo("\n\u2705 Diagnostics: all clear")

    typer.echo("")
    # Never exit non-zero -- health-check is informational only


@signals_app.command("backtest")
def signals_backtest() -> None:
    from alphahound.engine.storage import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kind, COUNT(*), COUNT(*) FILTER (WHERE (phases->>'outcome_correct')::boolean=true), AVG((phases->>'outcome_pct')::float) FILTER (WHERE phases->>'outcome_pct' IS NOT NULL), MIN(start_time), MAX(start_time) FROM historical_events WHERE module_id='stocks' GROUP BY kind;")
            rows = cur.fetchall()
    if not rows:
        typer.echo("No historical events found."); return
    typer.echo(f"\n{'='*60}\n  BACKTEST SUMMARY\n{'='*60}")
    for kind, total, correct, avg_pct, min_t, max_t in rows:
        typer.echo(f"  {kind:<20} {correct or 0}/{total}  avg={avg_pct:+.1f}%  {min_t.strftime('%Y-%m-%d') if min_t else 'n/a'} → {max_t.strftime('%Y-%m-%d') if max_t else 'n/a'}")


@signals_app.command("catalysts")
def signals_catalysts(
    days: int = typer.Option(45, "--days", help="Look-ahead window in days"),
    ticker: str = typer.Option(None, "--ticker", help="Filter to one ticker"),
    seed: bool = typer.Option(False, "--seed", help="Seed PDUFA and FOMC static data first"),
) -> None:
    """Show upcoming binary catalysts (EARNINGS + PDUFA + FOMC). Sprint 11 S11-3."""
    from alphahound.engine.signals.catalyst_calendar import (
        get_upcoming_catalysts, get_catalyst_for_ticker,
        seed_static_catalysts, format_catalyst_table,
    )
    from alphahound.engine.storage import get_conn

    if seed:
        typer.echo("Seeding static catalyst data (PDUFA + FOMC)...")
        pdufa_n, fomc_n = seed_static_catalysts()
        typer.echo(f"\u2705 Seeded {pdufa_n} PDUFA dates, {fomc_n} FOMC dates.")

    if ticker:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                    (ticker.upper(),),
                )
                row = cur.fetchone()
        if row is None:
            typer.echo(f"\u2753 {ticker} not found."); raise typer.Exit(1)
        catalyst = get_catalyst_for_ticker(str(row[0]), ticker.upper(), max_days=days)
        if catalyst is None:
            typer.echo(f"No catalyst for {ticker} in next {days} days.")
        else:
            sweet = " \u2605 SWEET SPOT" if catalyst.in_sweet_spot else ""
            typer.echo(f"  {catalyst.ticker:<8} {catalyst.catalyst_type:<10} {catalyst.catalyst_date}  {catalyst.days_away}d{sweet}")
            typer.echo(f"  {catalyst.description}")
    else:
        catalysts = get_upcoming_catalysts(days_ahead=days)
        if not catalysts:
            typer.echo(f"No catalysts in next {days} days."); return
        typer.echo(f"\nCatalysts in next {days} days ({len(catalysts)} total):")
        typer.echo(format_catalyst_table(catalysts))


@signals_app.command("structure")
def signals_structure(
    ticker: str = typer.Option(..., "--ticker"),
    equity: float = typer.Option(20000.0, "--equity", help="Account equity for sizing"),
) -> None:
    """Recommend an options structure for a ticker's current convergence signal. S11-4."""
    from alphahound.engine.scoring.convergence_scorer import score_ticker
    from alphahound.engine.execution.options_structure import recommend_structure
    from alphahound.engine.storage import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                (ticker.upper(),),
            )
            row = cur.fetchone()
    if row is None:
        typer.echo(f"\u2753 {ticker} not found."); raise typer.Exit(1)

    entity_id = str(row[0])
    result = score_ticker(entity_id, ticker.upper())
    if result is None:
        typer.echo(f"\u2753 No convergence data for {ticker}."); raise typer.Exit(0)

    typer.echo(f"Convergence: {result.ticker} score={result.composite_score:.2f} "
               f"pillars={result.pillars_fired} {result.direction}")

    if result.direction == "NEUTRAL" and result.catalyst_type != "PDUFA":
        typer.echo("No structure: direction is NEUTRAL — signal not actionable."); raise typer.Exit(0)

    structure = recommend_structure(
        entity_id=entity_id,
        ticker=ticker.upper(),
        direction=result.direction,
        composite_score=result.composite_score,
        pillars_fired=result.pillars_fired,
        catalyst_type=result.catalyst_type,
        catalyst_date=result.catalyst_date,
        equity=equity,
    )
    if structure is None:
        typer.echo("\u26a0  No price data available — run tech-backfill first."); raise typer.Exit(0)

    typer.echo(structure.display())


@signals_app.command("options-monitor")
def signals_options_monitor(
    close:   bool = typer.Option(False, "--close",   help="Submit closing orders for positions that hit targets"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would close without submitting orders"),
) -> None:
    """Monitor open options positions and optionally auto-close at gain/loss targets. Sprint 12."""
    from alphahound.engine.execution.options_monitor import monitor_positions

    if dry_run:
        typer.echo("[DRY RUN] Checking positions — no orders will be placed.")

    positions = monitor_positions(close=close, dry_run=dry_run)

    if not positions:
        typer.echo("No open options positions found in options_trade_log.")
        return

    to_close = [p for p in positions if p.should_close]
    holding  = [p for p in positions if not p.should_close]

    typer.echo(f"\n{'='*65}\n  OPEN OPTIONS POSITIONS ({len(positions)})\n{'='*65}")

    if to_close:
        typer.echo(f"\n  \U0001f6a8 CLOSE TARGETS ({len(to_close)}):")
        for p in to_close:
            typer.echo(p.display())

    if holding:
        typer.echo(f"\n  \U0001f4cb HOLDING ({len(holding)}):")
        for p in holding:
            typer.echo(p.display())

    typer.echo(f"\n  Target gain: +{50:.0f}%  |  Stop loss: -80%  |  Close before expiry: 5 DTE")

    if close:
        typer.echo(f"\n\u2705 Submitted close orders for {len(to_close)} position(s).")
    elif dry_run:
        typer.echo(f"\n\U0001f50d Would close {len(to_close)} position(s). Run with --close to execute.")
    elif to_close:
        typer.echo(f"\n\u26a0  {len(to_close)} position(s) hit close targets. Run with --close to execute.")


@signals_app.command("options-execute")
def signals_options_execute(
    ticker:  str  = typer.Option(None,  "--ticker",  help="Execute for one ticker only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be placed without sending orders"),
) -> None:
    """Execute options trades for current super signals. Sprint 11 S11-7."""
    from alphahound.engine.execution.options_executor import execute_options_all, execute_options_ticker

    if dry_run:
        typer.echo("[DRY RUN] Simulating options execution — no orders will be placed.")

    if ticker:
        result = execute_options_ticker(ticker.upper(), dry_run=dry_run)
        results = [result]
    else:
        results = execute_options_all(dry_run=dry_run)

    typer.echo(f"\n{'='*65}\n  OPTIONS EXECUTION  {'[DRY RUN]' if dry_run else ''}\n{'='*65}")
    placed = skipped = errors = dry = 0
    for r in results:
        typer.echo(r.display())
        if r.status == 'placed':    placed  += 1
        elif r.status == 'skipped': skipped += 1
        elif r.status == 'error':   errors  += 1
        elif r.status == 'dry_run': dry     += 1
    typer.echo(f"\n  {'Placed' if not dry_run else 'Would place'}: {placed + dry}  Skipped: {skipped}  Errors: {errors}")


@signals_app.command("options-status")
def signals_options_status(days: int = typer.Option(7, "--days")) -> None:
    """Show recent options trades from options_trade_log."""
    from alphahound.engine.storage import get_conn
    from alphahound.engine.execution.options_executor import _ensure_options_log_table
    _ensure_options_log_table()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT time, ticker, structure_type, direction, contracts,
                       estimated_debit, catalyst_type, catalyst_date,
                       composite_score, status, pnl
                FROM options_trade_log
                WHERE time >= now() - interval '%s days'
                ORDER BY time DESC;
            """, (days,))
            rows = cur.fetchall()
    if not rows:
        typer.echo(f"No options trades in last {days} days."); return
    typer.echo(f"\n{'='*80}\n  OPTIONS TRADE LOG  (last {days} days)\n{'='*80}")
    typer.echo(f"  {'time':<20} {'ticker':<6} {'structure':<22} {'dir':<6} {'qty':>4} {'debit':>8} {'catalyst':<12} {'score':>6} {'pnl':>8}")
    typer.echo("  " + "-"*78)
    for row in rows:
        time_, ticker_, struct_, dir_, qty_, debit_, cat_, cat_date_, score_, status_, pnl_ = row
        pnl_str   = f"+${pnl_:.0f}" if pnl_ and pnl_ > 0 else (f"-${abs(pnl_):.0f}" if pnl_ else "—")
        debit_str = f"${debit_:.0f}" if debit_ else "—"
        cat_str   = f"{cat_} {cat_date_}" if cat_ else "—"
        typer.echo(f"  {time_.strftime('%Y-%m-%d %H:%M'):<20} {ticker_:<6} {struct_:<22} {dir_:<6} {str(qty_):>4} {debit_str:>8} {cat_str:<12} {score_:>6.2f} {pnl_str:>8}")


@signals_app.command("seed-catalysts")
def signals_seed_catalysts() -> None:
    """Seed static PDUFA and FOMC calendar data. Run once after deploy."""
    from alphahound.engine.signals.catalyst_calendar import seed_static_catalysts
    typer.echo("Seeding PDUFA and FOMC calendar...")
    pdufa_n, fomc_n = seed_static_catalysts()
    typer.echo(f"\u2705 Seeded {pdufa_n} PDUFA dates, {fomc_n} FOMC dates.")


@signals_app.command("convergence-scan")
def signals_convergence_scan(
    ticker: str = typer.Option(None, "--ticker", help="Score a single ticker instead of all active"),
) -> None:
    """Run Multi-Pillar Convergence Engine. Sprint 11 replacement for divergence-scan."""
    from alphahound.engine.scoring.convergence_scorer import scan_and_store, score_ticker, get_super_signals
    from alphahound.engine.storage import get_conn

    if ticker:
        # Single ticker mode — score live, don't read from cache
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM entities WHERE module_id='stocks' AND canonical_symbol=%s AND kind='ticker';",
                    (ticker.upper(),),
                )
                row = cur.fetchone()
        if row is None:
            typer.echo(f"\u2753 {ticker} not found."); raise typer.Exit(1)
        entity_id = str(row[0])
        result = score_ticker(entity_id, ticker.upper())
        if result is None:
            typer.echo(f"\u2753 No data for {ticker}."); raise typer.Exit(0)
        # Sanity check — result must match the requested ticker
        if result.ticker.upper() != ticker.upper():
            typer.echo(f"\u26a0 Entity mismatch: asked for {ticker}, got {result.ticker}. DB entity_id={entity_id}")
            raise typer.Exit(1)
        typer.echo(f"\n{'='*60}")
        typer.echo(f"  {result.ticker}  score={result.composite_score:.2f}  pillars={result.pillars_fired}  {result.direction}  {'\U0001f6a8 SUPER SIGNAL' if result.super_signal else ''}")
        typer.echo(f"  {result.narrative}")
        if result.recommended_structure:
            typer.echo(f"  Structure: {result.recommended_structure}")
        if result.catalyst_date:
            typer.echo(f"  Catalyst: {result.catalyst_type} on {result.catalyst_date}")
        typer.echo(f"{'='*60}")
        for p in result.pillar_results:
            icon = "\u2705" if p.fired else "\u25a1"
            score_str = f"{p.score:.1f}"
            typer.echo(f"  {icon} {p.name:<28} [{score_str}]  {p.evidence[:70]}")
    else:
        # Full scan mode
        typer.echo("Running Multi-Pillar Convergence Engine...")
        n = scan_and_store(module_id="stocks")
        typer.echo(f"\u2705 Convergence scan complete: {n} super signal(s) found.")
        if n > 0:
            signals = get_super_signals(hours_back=1)
            typer.echo(f"\n{'='*60}\n  SUPER SIGNALS ({len(signals)})\n{'='*60}")
            for s in signals:
                typer.echo(
                    f"  \U0001f6a8 {s['ticker']:<6}  score={s['composite_score']:.2f}  "
                    f"pillars={s['pillars_fired']}  {s['direction']}  "
                    f"{s.get('recommended_structure','')}"
                )
                typer.echo(f"     {s.get('narrative','')[:80]}")


if __name__ == "__main__":
    app()
