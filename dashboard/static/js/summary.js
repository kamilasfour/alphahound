/* ══ SUMMARY ══ */
async function loadSummary() {
  try {
    const [d, pipeline] = await Promise.all([
      fj('/api/summary'),
      fj('/api/pipeline').catch(() => null),
    ]);

    // Core data KPIs
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setText('k-posts',    fK(d.posts_24h));
    setText('k-universe', d.entities_active ?? '—');

    // Scored / 24h
    const scoredEl = document.getElementById('k-scored');
    if (scoredEl && d.posts_24h) {
      const backlog = pipeline?.backlog ?? 0;
      const scored  = Math.max(0, (d.posts_24h || 0) - backlog);
      scoredEl.textContent = fK(scored);
      const pct = d.posts_24h > 0 ? Math.round(scored / d.posts_24h * 100) : 0;
      const subEl = document.getElementById('k-scored-sub');
      if (subEl) subEl.textContent = pct + '% of posts scored';
    }

    // Engine status
    const live  = d.engine_status === 'live';
    const engEl = document.getElementById('k-eng');
    engEl.textContent = live ? 'LIVE' : 'STALE';
    engEl.style.color = live ? 'var(--g)' : 'var(--r)';
    const runCount = pipeline?.steps?.length ?? d.healthy_runs ?? 0;
    const lastMins = pipeline?.last_cycle_mins;
    document.getElementById('k-eng-sub').textContent =
      lastMins != null ? 'Last cycle ' + lastMins + 'm ago' : (d.healthy_runs || 0) + ' runs / 30m';

    // Market open/closed status
    const mktOpen = d.market_open;
    const lstatEl = document.getElementById('lstatus');
    const pillEl  = document.getElementById('live-pill');
    const dotEl   = document.getElementById('ldot');
    if (lstatEl) {
      lstatEl.textContent = mktOpen ? 'MARKET OPEN' : 'MARKET CLOSED';
      lstatEl.style.color = mktOpen ? 'var(--g)' : 'var(--a)';
    }
    if (pillEl) pillEl.className = 'status-pill ' + (mktOpen ? 'pill-live' : 'pill-stale');
    if (dotEl)  dotEl.className  = 'pill-dot '    + (mktOpen ? 'dot-live'  : 'dot-stale');

  } catch(e) { console.error('loadSummary', e); }
}
