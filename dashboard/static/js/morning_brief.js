/* ══════════════════════════════════════════════════════════════
   morning_brief.js — Morning Brief modal
   Pulls /api/alerts, /api/macro, /api/global-markets in parallel
   ══════════════════════════════════════════════════════════════ */

/* ── Open / close ───────────────────────────────────────────── */
function openMorningBrief() {
  const modal = document.getElementById('brief-modal');
  const body  = document.getElementById('brief-body');
  if (!modal) return;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';

  body.innerHTML = `
    <div class="brief-loading">
      <div class="loading" style="padding:60px 20px">PULLING SIGNALS · MACRO · GLOBAL MARKETS…</div>
    </div>`;

  Promise.all([
    fj('/api/assessment'),
    fj('/api/alerts?show_all=true'),
    fj('/api/macro'),
    fj('/api/global-markets'),
  ]).then(([assessmentResp, alertsResp, macroResp, globalResp]) => {
    body.innerHTML = _briefContent(assessmentResp, alertsResp, macroResp, globalResp);
  }).catch(err => {
    body.innerHTML = `<div style="padding:40px 20px;text-align:center;font-family:var(--mono);font-size:12px;color:var(--r)">Failed to load: ${err.message}</div>`;
  });
}

function closeMorningBrief() {
  const modal = document.getElementById('brief-modal');
  if (modal) modal.classList.remove('open');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMorningBrief(); });
document.addEventListener('click',   e => { if (e.target.id === 'brief-modal') closeMorningBrief(); });

/* ── Top-level builder ──────────────────────────────────────── */
function _briefContent(assessmentResp, alertsResp, macro, global) {
  const now = new Date().toLocaleString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
    timeZone: 'America/New_York',
  });
  return `
    <div class="brief-dateline">${now} ET</div>
    ${_briefAssessment(assessmentResp)}
    ${_briefMacro(macro)}
    ${_briefGlobal(global)}
    ${_briefAlerts(alertsResp.alerts || [])}
  `;
}

/* ── Assessment section ──────────────────────────────────────── */
function _briefAssessment(resp) {
  const a = resp && resp.latest;
  if (!a) return _briefSection('Engine Assessment', '<div class="brief-empty">Assessment service not yet run</div>');

  const statusCol = a.status === 'GREEN' ? 'var(--g)' : a.status === 'RED' ? 'var(--r)' : 'var(--a)';
  const statusBg  = a.status === 'GREEN' ? 'var(--gb)' : a.status === 'RED' ? 'var(--rb)' : 'var(--ab)';
  const statusBd  = a.status === 'GREEN' ? 'var(--gd)' : a.status === 'RED' ? 'var(--rd)' : 'var(--ad)';

  const findingRows = (a.findings || []).map(f => {
    const isRed    = f.includes('ERROR') || f.includes('BUG') || f.includes('STOP');
    const isYellow = f.includes('STALE') || f.includes('RISK_OFF') || f.includes('SILENT') || f.includes('PENDING');
    const icon     = isRed ? '🔴' : isYellow ? '🟡' : '🟢';
    return `<div style="font-family:var(--mono);font-size:11px;color:var(--t2);padding:3px 0;border-bottom:1px solid var(--b1)">${icon} ${f}</div>`;
  }).join('');

  const actionRows = (a.actions || []).map(ac =>
    `<div style="font-family:var(--mono);font-size:11px;color:var(--a);padding:3px 0">⚠ ${ac}</div>`
  ).join('');

  const whyRows = (a.why_not_trading || []).map(w =>
    `<div style="font-family:var(--mono);font-size:11px;color:var(--t2);padding:3px 0">→ ${w}</div>`
  ).join('');

  const body = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
      <div style="font-family:var(--mono);font-size:13px;font-weight:800;color:${statusCol};background:${statusBg};border:1px solid ${statusBd};padding:4px 12px;border-radius:4px;letter-spacing:0.1em">${a.status}</div>
      <div style="font-family:var(--mono);font-size:11px;color:var(--t3)">${a.as_of_pt}</div>
      <div style="margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--t3)">${a.market_open ? '● MARKET OPEN' : '○ MARKET CLOSED'}</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:8px 10px">
        <div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">SIGNALS</div>
        <div style="font-family:var(--mono);font-size:16px;font-weight:800;color:${a.executable_count > 0 ? 'var(--g)' : 'var(--t1)'}">${a.executable_count}</div>
        <div style="font-family:var(--mono);font-size:10px;color:var(--t3)">executable</div>
      </div>
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:8px 10px">
        <div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">MAX D</div>
        <div style="font-family:var(--mono);font-size:16px;font-weight:800;color:var(--t1)">${(a.max_d || 0).toFixed(2)}</div>
        <div style="font-family:var(--mono);font-size:10px;color:var(--t3)">threshold 4.0</div>
      </div>
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:8px 10px">
        <div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">MACRO</div>
        <div style="font-family:var(--mono);font-size:13px;font-weight:800;color:${a.macro_verdict === 'RISK_ON' ? 'var(--g)' : 'var(--r)'}">${a.macro_verdict}</div>
        <div style="font-family:var(--mono);font-size:10px;color:var(--t3)">size ${(a.size_modifier || 0)}%</div>
      </div>
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:8px 10px">
        <div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">EXECUTED</div>
        <div style="font-family:var(--mono);font-size:16px;font-weight:800;color:var(--t1)">${a.executed_today || 0}</div>
        <div style="font-family:var(--mono);font-size:10px;color:var(--t3)">today</div>
      </div>
    </div>
    ${findingRows ? `<div style="margin-bottom:10px">${findingRows}</div>` : ''}
    ${whyRows ? `<div style="margin:10px 0 6px;font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">WHY NOTHING TRADED</div>${whyRows}` : ''}
    ${actionRows ? `<div style="margin:10px 0 6px;font-family:var(--mono);font-size:9px;font-weight:700;color:var(--a);letter-spacing:0.1em">ACTIONS NEEDED</div>${actionRows}` : ''}
  `;

  return _briefSection('Engine Assessment', body);
}

/* ── Macro section ──────────────────────────────────────────── */
const ETF_ROLES = {
  UVXY:'VIX / Short-term Fear', TLT:'20yr US Treasuries', UUP:'US Dollar Index',
  HYG:'High Yield Credit', EWJ:'Japan', FXI:'China Large-Cap', EWG:'Germany',
  EEM:'Emerging Markets', SPY:'S&P 500', QQQ:'Nasdaq 100',
};

function _briefMacro(m) {
  if (!m || m.verdict === 'NO_DATA') return _briefSection('Macro Environment', '<div class="brief-empty">No macro data available</div>');

  const vColor  = m.verdict === 'RISK_ON' ? 'var(--g)' : m.verdict === 'RISK_OFF' ? 'var(--r)' : 'var(--a)';
  const vBg     = m.verdict === 'RISK_ON' ? 'var(--gb)' : m.verdict === 'RISK_OFF' ? 'var(--rb)' : 'var(--ab)';
  const vBorder = m.verdict === 'RISK_ON' ? 'var(--gd)' : m.verdict === 'RISK_OFF' ? 'var(--rd)' : 'var(--ad)';
  const sizeLabel = m.size_modifier === 0 ? 'LONGs Blocked' : m.size_modifier < 1 ? `${Math.round(m.size_modifier * 100)}% size` : 'Full size';
  const sizeCol   = m.size_modifier === 0 ? 'var(--r)' : m.size_modifier < 1 ? 'var(--a)' : 'var(--g)';

  const sigRows = Object.entries(m.signals || {})
    .sort(([,a],[,b]) => Math.abs(b) - Math.abs(a)).slice(0, 8)
    .map(([ticker, chg]) => {
      const col = chg > 0 ? 'var(--g)' : 'var(--r)';
      return `<div class="brief-sig-row">
        <span class="brief-sig-tick">${ticker}</span>
        <span class="brief-sig-role">${ETF_ROLES[ticker] || ''}</span>
        <span class="brief-sig-chg" style="color:${col}">${chg > 0 ? '+' : ''}${chg.toFixed(2)}%</span>
      </div>`;
    }).join('');

  const body = `
    <div class="brief-macro-grid">
      <div class="brief-verdict-block">
        <div class="brief-micro-label">Verdict</div>
        <div class="brief-verdict-pill" style="color:${vColor};background:${vBg};border-color:${vBorder}">${m.verdict}</div>
        <div style="margin-top:8px;font-family:var(--mono);font-size:11px;font-weight:700;color:${sizeCol}">${sizeLabel}</div>
      </div>
      <div class="brief-mac-stats">
        <div class="brief-kv"><span class="brief-micro-label">Score</span><span class="brief-kv-val">${(m.score || 0).toFixed(3)}</span></div>
        <div class="brief-kv"><span class="brief-micro-label">Size Modifier</span><span class="brief-kv-val" style="color:${sizeCol}">${m.size_modifier}×</span></div>
      </div>
      <div class="brief-sig-table">${sigRows || '<span style="font-size:11px;color:var(--t3)">No signal data</span>'}</div>
    </div>
    ${m.reason ? `<div class="brief-reason">${m.reason}</div>` : ''}`;

  return _briefSection('Macro Environment', body);
}

/* ── Global markets section ─────────────────────────────────── */
function _briefGlobal(g) {
  if (!g || g.error) return _briefSection('Global Markets', '<div class="brief-empty">No global data available</div>');

  const vCol = v => {
    if (!v) return 'var(--t3)';
    const s = v.toUpperCase();
    return s.includes('POSITIVE') || s.includes('BULL') ? 'var(--g)'
         : s.includes('NEGATIVE') || s.includes('BEAR') ? 'var(--r)'
         : 'var(--a)';
  };

  const regionCard = (label, verdict, avg) => `
    <div class="brief-region">
      <div class="brief-micro-label">${label}</div>
      <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:${vCol(verdict)};margin-top:4px">${verdict || '—'}</div>
      ${avg != null ? `<div style="font-family:var(--mono);font-size:11px;color:var(--t2);margin-top:3px">${avg > 0 ? '+' : ''}${avg.toFixed(2)}% avg</div>` : ''}
    </div>`;

  const indices = (g.indices || []).filter(i => i.change_pct != null);
  const sorted  = [...indices].sort((a,b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
  const tiles = sorted.slice(0, 10).map(ix => {
    const col = ix.change_pct > 0 ? 'var(--g)' : ix.change_pct < 0 ? 'var(--r)' : 'var(--t3)';
    const bg  = Math.abs(ix.change_pct) > 1
      ? (ix.change_pct > 0 ? 'rgba(16,185,129,0.08)' : 'rgba(244,63,94,0.08)')
      : 'var(--s3)';
    return `<div style="background:${bg};border:1px solid var(--b1);border-radius:6px;padding:6px 10px;min-width:76px;text-align:center">
      <div style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--t1)">${ix.ticker}</div>
      <div style="font-family:var(--mono);font-size:11px;font-weight:600;color:${col};margin-top:2px;font-variant-numeric:tabular-nums">${ix.change_pct > 0 ? '+' : ''}${ix.change_pct.toFixed(2)}%</div>
    </div>`;
  }).join('');

  const body = `
    <div class="brief-regions">
      ${regionCard('Overall', g.overall_verdict, null)}
      ${regionCard('Asia', g.asia_verdict, g.asia_avg_chg)}
      ${regionCard('Europe', g.europe_verdict, g.europe_avg_chg)}
      ${regionCard('Futures', g.futures_verdict, g.futures_avg_chg)}
    </div>
    ${tiles ? `<div class="brief-index-tiles">${tiles}</div>` : ''}
    ${g.narrative ? `<div class="brief-reason">${g.narrative}</div>` : ''}`;

  return _briefSection('Global Markets', body);
}

/* ── Alerts section ─────────────────────────────────────────── */
const _BRIEF_TIER_COLORS = {
  EXTREME: '#ff4444', HIGH: '#ff9500', STANDARD: 'var(--g)', MONITOR: '#8e8e93',
};

function _briefAlertRow(a) {
  const dc    = a.direction === 'LONG' ? 'dp-long' : a.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
  const tCol  = _BRIEF_TIER_COLORS[a.signal_tier] || 'var(--t2)';
  const dCol  = a.d_value >= 20 ? '#ff4444' : a.d_value >= 8 ? '#ff9500' : a.d_value >= 4 ? 'var(--g)' : 'var(--t2)';
  const narr  = a.narrative
    ? `<div style="font-family:var(--sans);font-size:11px;color:var(--t2);line-height:1.5;margin-top:6px">${a.narrative.split('. ')[0]}.</div>`
    : '';
  const lev   = a.is_leveraged ? `<span style="font-family:var(--mono);font-size:10px;font-weight:700;color:#ff9500">⚡ ${a.execute_ticker}</span>` : '';
  return `
    <div class="brief-alert-row" onclick="closeMorningBrief();showView('alerts')">
      <div class="brief-alert-top">
        <span class="brief-alert-ticker">${a.ticker}</span>
        <span class="dir-pill ${dc}" style="font-size:9px">${a.direction}</span>
        <span style="font-family:var(--mono);font-size:9px;font-weight:800;color:${tCol};letter-spacing:0.1em">${a.signal_tier || 'STD'}</span>
        ${lev}
        <span style="font-family:var(--mono);font-size:13px;font-weight:700;color:${dCol};margin-left:auto;font-variant-numeric:tabular-nums">D ${a.d_value.toFixed(2)}</span>
      </div>
      <div class="brief-alert-sub">
        <span>Conv <strong>${a.conviction}/10</strong></span>
        ${a.position_usd ? `<span>$${a.position_usd.toLocaleString()}</span>` : ''}
        ${a.stop_pct ? `<span>Stop ${a.stop_pct}%</span>` : ''}
        <span style="color:var(--t3)">${a.time_et || tAgo(a.time)}</span>
      </div>
      ${narr}
    </div>`;
}

function _briefAlerts(alerts) {
  if (!alerts.length) return _briefSection('Active Signals', '<div class="brief-empty">No active signals</div>');

  const exec  = alerts.filter(a => a.will_execute);
  const watch = alerts.filter(a => !a.will_execute);

  const execBlock = exec.length ? `
    <div class="brief-sub-label" style="color:var(--g)">
      Execution — ${exec.length} signal${exec.length !== 1 ? 's' : ''} above threshold (D ≥ 4.0)
    </div>
    <div class="brief-alert-list">${exec.map(_briefAlertRow).join('')}</div>` : '';

  const watchBlock = watch.length ? `
    <div class="brief-sub-label" style="margin-top:${exec.length ? 16 : 0}px">
      Monitoring — ${watch.length} below threshold (D 2–4)
    </div>
    <div class="brief-alert-list">${watch.map(_briefAlertRow).join('')}</div>` : '';

  const title = `Active Signals <span style="font-weight:400;color:var(--t3);font-size:11px">${alerts.length} total</span>`;
  return _briefSection(title, execBlock + watchBlock);
}

/* ── Section shell ──────────────────────────────────────────── */
function _briefSection(title, content) {
  return `
    <div class="brief-section">
      <div class="brief-sec-title">${title}</div>
      ${content}
    </div>`;
}
