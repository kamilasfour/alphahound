/* ═══════════════════════════════════════════════════════════════
   alerts.js — Legacy divergence alerts (kept for reference)
   Primary signals are now in convergence.js
   ═══════════════════════════════════════════════════════════════ */

/* ── Tech Gate ─────────────────────────────────────────────────── */
async function loadTechGate(ticker, direction, elId) {
  const key = ticker + '_' + direction;
  if (techCache[key]) { renderTechGate(techCache[key], elId); return; }
  try {
    const d = await fj('/api/tech-check-direction?ticker=' + ticker + '&direction=' + direction);
    techCache[key] = d;
    renderTechGate(d, elId);
  } catch (e) {
    const el = document.getElementById(elId);
    if (el) el.innerHTML = '<span class="tg-label" style="font-style:italic;opacity:.5">Tech check unavailable</span>';
  }
}

function renderTechGate(d, elId) {
  const el = document.getElementById(elId); if (!el) return;
  const vC = { CONFIRM: 'tv-confirm', WEAK: 'tv-weak', REJECT: 'tv-reject', NO_DATA: 'tv-nodata' }[d.verdict] || 'tv-nodata';
  const sz = d.verdict === 'WEAK' ? '50% size' : d.verdict === 'REJECT' ? 'BLOCKED' : d.verdict === 'NO_DATA' ? 'pass-thru' : 'full size';
  const labs = { macd: 'MACD', rsi: 'RSI', volume: 'VOL', ema_trend: 'EMA', momentum: 'MOM' };
  const chk = Object.entries(d.checks || {}).map(([k, v]) =>
    '<div class="tc-chip ' + (v === true ? 'pass' : v === false ? 'fail' : '') + '">' + (v === true ? '✓' : v === false ? '✗' : '—') + ' ' + (labs[k] || k) + '</div>'
  ).join('');
  const ind = d.indicators || {};
  const inds = [
    ind.macd_line    != null ? '<span class="tg-ind">MACD <span>' + (ind.macd_line > 0 ? '+' : '') + ind.macd_line.toFixed(2) + '</span></span>' : '',
    ind.rsi          != null ? '<span class="tg-ind">RSI <span>' + ind.rsi.toFixed(1) + '</span></span>' : '',
    ind.ema20        != null ? '<span class="tg-ind">EMA20 <span>$' + ind.ema20.toFixed(2) + '</span></span>' : '',
    ind.volume_ratio != null ? '<span class="tg-ind">VOL <span>' + ind.volume_ratio.toFixed(2) + 'x</span></span>' : '',
    ind.momentum_5d  != null ? '<span class="tg-ind">5D <span>' + (ind.momentum_5d > 0 ? '+' : '') + ind.momentum_5d.toFixed(2) + '%</span></span>' : '',
  ].filter(Boolean).join('');
  el.innerHTML = '<div class="tg-top">'
    + '<span class="tg-label">⬡ Tech Gate</span>'
    + '<span class="tg-verdict ' + vC + '">' + d.verdict + '</span>'
    + '<span class="tg-score">' + d.score + '/5</span>'
    + '<span class="tg-size">' + sz + '</span>'
    + '</div>'
    + '<div class="tg-checks">' + (chk || '<span class="tg-label" style="opacity:.5">No data</span>') + '</div>'
    + '<div class="tg-inds">' + inds + '</div>';
}

/* ── Tier config ── */
const TIER_CONFIG = {
  EXTREME:  { label: 'EXTREME',  color: '#ff4444', bg: 'rgba(255,68,68,0.15)',    desc: 'D ≥ 20 — Maximum conviction.' },
  HIGH:     { label: 'HIGH',     color: '#ff9500', bg: 'rgba(255,149,0,0.15)',    desc: 'D 8–20 — High conviction.' },
  STANDARD: { label: 'STANDARD', color: '#30d158', bg: 'rgba(48,209,88,0.12)',   desc: 'D 4–8 — Standard signal.' },
  MONITOR:  { label: 'MONITOR',  color: '#8e8e93', bg: 'rgba(142,142,147,0.10)', desc: 'D 2–4 — Watching only.' },
};

/* ── Alert card renderer ── */
function renderAlerts(alerts) {
  const el = document.getElementById('alert-list');
  if (!el) return;
  if (!alerts || !alerts.length) {
    el.innerHTML = '<div class="empty">No legacy divergence alerts in this period</div>';
    return;
  }
  el.innerHTML = alerts.map(function(a, idx) { return buildAlertCard(a, idx); }).join('');
  alerts.forEach(function(a, idx) {
    if (a.signal_tier !== 'MONITOR') {
      loadTechGate(a.ticker, a.direction, 'tg-' + a.ticker + '-' + idx);
    }
  });
}

function buildAlertCard(a, idx) {
  const tier    = a.signal_tier || 'STANDARD';
  const tierCfg = TIER_CONFIG[tier] || TIER_CONFIG.STANDARD;
  const dc      = a.direction === 'LONG' ? 'dp-long' : a.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
  const dCol    = a.d_value >= 20 ? '#ff4444' : a.d_value >= 8 ? '#ff9500' : a.d_value >= 4 ? 'var(--g)' : 'var(--t2)';
  const pct     = Math.min(100, (a.d_value / 40) * 100);
  const techId  = 'tg-' + a.ticker + '-' + idx;
  const isMonitor = tier === 'MONITOR';
  const opacity = isMonitor ? 'opacity:0.65;' : '';

  const chips = Object.entries(a.components || {}).map(function(kv) {
    const k = kv[0], v = kv[1];
    const p2 = Math.min(50, Math.abs(v) * 50);
    const col = v > 0 ? 'var(--g)' : 'var(--r)';
    return '<div class="comp"><span class="comp-name">' + k.replace(/_/g,' ') + '</span>'
      + '<div class="comp-bar">' + (v > 0 ? '<div class="cbar-pos" style="width:' + p2 + '%"></div>' : '<div class="cbar-neg" style="width:' + p2 + '%"></div>') + '</div>'
      + '<span class="comp-val" style="color:' + col + '">' + (v > 0 ? '+' : '') + v.toFixed(3) + '</span></div>';
  }).join('');

  const narrHTML = a.narrative
    ? '<div class="narr"><div class="narr-label">⬡ AI ASSESSMENT</div><div class="narr-text">' + a.narrative + '</div></div>'
    : '';

  const techHTML = isMonitor
    ? '<div style="color:#8e8e93;font-size:10px;padding:4px 0;font-style:italic">Tech gate skipped</div>'
    : '<div class="comps-label" style="margin-top:2px">Technical Gate</div><div class="tech-gate" id="' + techId + '"><span class="tg-label" style="opacity:.5">Loading…</span></div>';

  const priceChg = a.price
    ? '<span class="a-ms">·</span><span class="a-mi" style="color:' + ((a.change_5d_pct||0) > 0 ? 'var(--g)' : 'var(--r)') + '">' + a.price.toFixed(2) + ' (' + fP(a.change_5d_pct) + ' 5d)</span>'
    : '';

  return '<div class="acard" style="' + opacity + '" id="acard-' + a.ticker + '-' + idx + '">'
    + '<div class="acard-hdr" onclick="toggleAlertCard(this.closest(\'.acard\'))">'
    + '<span class="a-ticker">' + a.ticker + '</span>'
    + '<span class="dir-pill ' + dc + '">' + a.direction + '</span>'
    + '<span class="tier-badge" style="background:' + tierCfg.bg + ';color:' + tierCfg.color + ';border:1px solid ' + tierCfg.color + '40;padding:2px 7px;border-radius:4px;font-size:9px;font-weight:800">' + tierCfg.label + '</span>'
    + '<span class="sig-type">' + (TYPE_LABELS[a.signal_type] || a.signal_type || '—') + '</span>'
    + '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;margin-left:auto">'
    + '<span style="font-family:var(--mono);font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:var(--t3)">Divergence Score</span>'
    + '<div class="d-row" style="margin-left:0"><div class="d-bar-wrap"><div class="d-bar-fill" style="width:' + pct + '%;background:' + tierCfg.color + '"></div></div>'
    + '<span class="d-num" style="color:' + dCol + '">D ' + a.d_value.toFixed(2) + '</span></div></div>'
    + '<span class="acard-chevron">▾</span></div>'
    + '<div class="acard-body"><div class="acard-left">'
    + '<div class="a-meta"><span class="a-mi">Conv <strong>' + (a.conviction||0) + '/10</strong></span><span class="a-ms">·</span>'
    + '<span class="a-mi">Stop ' + (a.stop_pct||0) + '%</span>' + priceChg
    + '<span class="a-ms">·</span><span class="a-mi" style="color:var(--t3)">' + (a.time_et || tAgo(a.time)) + '</span></div>'
    + '<div><div class="comps-label">Signal Sources</div><div class="comps">' + chips + '</div></div>'
    + techHTML + '</div>'
    + '<div class="acard-right">' + narrHTML + '</div></div></div>';
}

function toggleAlertCard(card) {
  if (!card) return;
  card.classList.toggle('expanded');
}

/* ── Filters ── */
function applyFilters() {
  const tickerEl = document.getElementById('f-ticker');
  const typeEl   = document.getElementById('f-type');
  const countEl  = document.getElementById('f-count');
  const ticker   = tickerEl ? tickerEl.value.toUpperCase() : '';
  const type     = typeEl   ? typeEl.value : '';

  const filtered = (allAlerts || []).filter(function(a) {
    if (ticker && !a.ticker.includes(ticker)) return false;
    if (activeDir && a.direction !== activeDir) return false;
    if (type && a.signal_type !== type) return false;
    return true;
  });

  if (countEl) countEl.textContent = filtered.length + ' alerts';
  renderAlerts(filtered);
}

function toggleDir(dir) {
  activeDir = activeDir === dir ? null : dir;
  ['LONG', 'SHORT', 'WATCH'].forEach(function(d) {
    const btn = document.getElementById('f-' + d.toLowerCase());
    if (btn) btn.className = 'f-btn' + (activeDir === d ? ' ' + (d === 'LONG' ? 'long-on' : d === 'SHORT' ? 'short-on' : 'active') : '');
  });
  applyFilters();
}

async function loadAlerts() {
  try {
    const showAll = window._showAllAlerts || false;
    const d = await fj('/api/alerts' + (showAll ? '?show_all=true' : ''));
    allAlerts = d.alerts || [];

    // Safely update any elements that may or may not exist
    const kAlerts = document.getElementById('k-alerts');
    if (kAlerts) kAlerts.textContent = d.count || allAlerts.length;

    const toggleBtn = document.getElementById('f-show-all');
    if (toggleBtn) {
      toggleBtn.textContent = showAll ? '▾ Execution only' : '▾ Show all signals';
      toggleBtn.style.opacity = showAll ? '1' : '0.6';
    }

    applyFilters();
  } catch(e) { console.error('loadAlerts', e); }
}

function toggleShowAll() {
  window._showAllAlerts = !window._showAllAlerts;
  loadAlerts();
}
