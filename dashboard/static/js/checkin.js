/* ══ CHECK-IN — Engine Intelligence Report (Sprint 12)
   Built on convergence engine. No divergence D-scores.
   Super signals come from /api/convergence, not /api/alerts.
*/

async function loadCheckIn() {
  const el = document.getElementById('checkin-body');
  if (!el) return;
  el.innerHTML = '<div class="loading">Engine analyzing conditions...</div>';

  async function safe(url) {
    try {
      const ctrl = new AbortController();
      const tid  = setTimeout(() => ctrl.abort(), 8000);
      const res  = await fetch(url, { signal: ctrl.signal });
      clearTimeout(tid);
      return await res.json();
    } catch(e) { return null; }
  }

  try {
    const [macro, convergence, positions, pipeline, execlog, hitrate, gmarkets, assessment] = await Promise.all([
      safe('/api/macro'),
      safe('/api/convergence'),
      safe('/api/positions'),
      safe('/api/pipeline'),
      safe('/api/execution-log'),
      safe('/api/hit-rate'),
      safe('/api/global-markets'),
      safe('/api/assessment/history?hours=24'),
    ]);

    el.innerHTML = _renderCheckIn(macro, convergence, positions, pipeline, execlog, hitrate, gmarkets, assessment);
  } catch(e) {
    console.error('loadCheckIn', e);
    el.innerHTML = '<div class="empty">Error loading report: ' + e.message + '</div>';
  }
}

function _renderCheckIn(macro, conv, positions, pipeline, execlog, hitrate, gmarkets, assessment) {
  const now    = new Date().toLocaleString('en-US', { timeZone:'America/Los_Angeles', weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit', hour12:true });
  const et     = new Date().toLocaleString('en-US', { timeZone:'America/New_York', hour:'numeric', minute:'2-digit', hour12:true });
  const etDate = new Date(new Date().toLocaleString('en-US', { timeZone:'America/New_York' }));
  const h = etDate.getHours(), m = etDate.getMinutes(), dow = etDate.getDay();
  const mktOpen = dow >= 1 && dow <= 5 && (h > 9 || (h === 9 && m >= 30)) && h < 16;
  const minsToOpen = !mktOpen && dow >= 1 && dow <= 5 && h < 16 ? Math.max(0, (9*60+30)-(h*60+m)) : 0;

  const superSignals = (conv?.super_signals || []);
  const watching     = (conv?.watching || []);
  const macroVerdict = macro?.verdict || conv?.macro_verdict || 'UNKNOWN';
  const macroScore   = macro?.score   || conv?.macro_score   || 0;
  const openPos      = positions?.positions || [];
  const totalPL      = openPos.reduce((s,p) => s+(p.unrealized_pl||0), 0);
  const riskOff      = macroVerdict === 'RISK_OFF';

  // Determine system state
  var state, stateColor, stateBg, stateDesc;
  if (superSignals.length > 0 && mktOpen && !riskOff) {
    state = 'SIGNALS ACTIVE'; stateColor = 'var(--g)'; stateBg = 'rgba(0,229,160,0.06)';
    const top = superSignals[0];
    stateDesc = superSignals.length + ' super signal' + (superSignals.length > 1 ? 's' : '') +
      ' firing. Top: ' + top.ticker + ' ' + top.direction + ' score=' + top.composite_score.toFixed(2) + '. Execution queued.';
  } else if (superSignals.length > 0 && !mktOpen) {
    state = 'SIGNALS QUEUED'; stateColor = 'var(--a)'; stateBg = 'rgba(255,182,39,0.06)';
    stateDesc = superSignals.length + ' super signal' + (superSignals.length > 1 ? 's' : '') +
      ' ready for market open' + (minsToOpen > 0 ? ' in ' + minsToOpen + 'm' : '') + '. Engine executes automatically.';
  } else if (openPos.length > 0) {
    state = 'POSITIONS RUNNING'; stateColor = '#38bdf8'; stateBg = 'rgba(56,189,248,0.06)';
    stateDesc = openPos.length + ' position' + (openPos.length > 1 ? 's' : '') +
      ' open. P&L: ' + (totalPL >= 0 ? '+' : '') + '$' + Math.abs(totalPL).toFixed(2) + '. Monitor active.';
  } else if (riskOff) {
    state = 'RISK OFF'; stateColor = 'var(--r)'; stateBg = 'rgba(255,77,109,0.06)';
    stateDesc = 'Macro RISK_OFF (score=' + macroScore.toFixed(3) + '). No new options entries until conditions improve.';
  } else if (watching.length > 0) {
    state = 'WATCHING'; stateColor = 'var(--a)'; stateBg = 'rgba(255,182,39,0.05)';
    stateDesc = watching.length + ' ticker' + (watching.length > 1 ? 's' : '') +
      ' building toward super signal threshold. ' + watching.slice(0,3).map(s => s.ticker + ' ' + s.composite_score.toFixed(1)).join(', ');
  } else {
    state = 'QUIET'; stateColor = 'var(--t2)'; stateBg = 'rgba(255,255,255,0.02)';
    stateDesc = 'No convergence above threshold. Engine scanning 1,000+ tickers every 15 minutes. Waiting for catalyst alignment.';
  }

  const mktColor = mktOpen ? 'var(--g)' : 'var(--t3)';
  const mktText  = (mktOpen ? '● MARKET OPEN' : '○ MARKET CLOSED') + (!mktOpen && minsToOpen > 0 ? ' · opens in ' + minsToOpen + 'm' : '');

  return '<div class="ir-wrap">' +

  // Header
  '<div class="ir-header">' +
    '<div><div class="ir-timestamp">' + now + ' <span style="color:var(--t3)">(' + et + ' ET)</span></div>' +
    '<div class="ir-title">Engine Intelligence Report</div></div>' +
    '<div style="display:flex;align-items:center;gap:10px">' +
    '<div class="ir-mkt-pill" style="color:' + mktColor + '">' + mktText + '</div>' +
    '<button class="ir-refresh" onclick="loadCheckIn()">&#8635;</button>' +
    '</div></div>' +

  // Assessment history strip
  _renderAssessmentStrip(assessment) +

  // State banner
  '<div class="ir-state-banner" style="background:' + stateBg + ';border:1px solid ' + stateColor + '30">' +
    '<div class="ir-state-val" style="color:' + stateColor + '">' + state + '</div>' +
    '<div class="ir-state-desc">' + stateDesc + '</div></div>' +

  // Super signals
  _renderConvergenceSection(superSignals, watching, mktOpen, riskOff) +

  // Open positions
  _renderPositionsSection(openPos, totalPL) +

  // Market context
  _renderMarketContext(macro, gmarkets) +

  // Hit rate
  _renderHitRateSection(hitrate) +

  // Pipeline
  _renderPipelineSection(pipeline) +

  // Execution log
  _renderExecLogSection(execlog) +

  '<div style="text-align:right;padding:14px 0 4px;font-size:10px;color:var(--t3)">' +
    'AlphaHound Engine &middot; ' + now + ' &middot; ' +
    '<a href="#" onclick="loadCheckIn();return false" style="color:var(--t3);text-decoration:none">&#8635; Refresh</a>' +
    '</div></div>';
}

// ── Assessment history strip ───────────────────────────────────────────────
function _renderAssessmentStrip(data) {
  const rows    = data?.assessments || [];
  if (!rows.length) return '';
  const latest  = rows[0];
  const latCol  = latest.status === 'GREEN' ? 'var(--g)' : latest.status === 'RED' ? 'var(--r)' : 'var(--a)';
  const latBg   = latest.status === 'GREEN' ? 'var(--gd)' : latest.status === 'RED' ? 'var(--rd)' : 'var(--ad)';
  const latBd   = latest.status === 'GREEN' ? 'var(--gb)' : latest.status === 'RED' ? 'var(--rb)' : 'var(--ab)';

  const kpis = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">' + [
    ['SUPER SIGNALS', latest.super_signal_count || 0, 'convergence signals', (latest.super_signal_count||0) > 0 ? 'var(--g)' : 'var(--t1)'],
    ['OPTIONS OPEN',  (latest.positions_open||0), 'trades placed',       'var(--t1)'],
    ['MACRO',         latest.macro_verdict || '—', 'size ' + (latest.size_modifier||0) + '%', latest.macro_verdict === 'RISK_ON' ? 'var(--g)' : latest.macro_verdict === 'RISK_OFF' ? 'var(--r)' : 'var(--a)'],
    ['LAST CYCLE',    (latest.last_cycle_mins||0).toFixed(1) + 'm', 'ago', 'var(--t1)'],
  ].map(([label, val, sub, col]) =>
    '<div style="background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:8px 10px">' +
    '<div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em">' + label + '</div>' +
    '<div style="font-family:var(--mono);font-size:16px;font-weight:800;color:' + col + ';margin:2px 0">' + val + '</div>' +
    '<div style="font-family:var(--mono);font-size:10px;color:var(--t3)">' + sub + '</div></div>'
  ).join('') + '</div>';

  const findings = (latest.findings || []).map(f => {
    const isRed = f.includes('ERROR') || f.includes('BUG');
    const isYel = f.includes('STALE') || f.includes('RISK_OFF') || f.includes('PENDING') || f.includes('SLOW');
    const col   = isRed ? 'var(--r)' : isYel ? 'var(--a)' : 'var(--t2)';
    const icon  = isRed ? '🔴' : isYel ? '🟡' : '🟢';
    return '<div style="font-family:var(--mono);font-size:11px;color:'+col+';padding:2px 0">' + icon + ' ' + f + '</div>';
  }).join('');

  const actions = (latest.actions || []).length
    ? '<div style="margin-top:8px"><div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--a);letter-spacing:0.1em;margin-bottom:4px">ACTIONS NEEDED</div>' +
      (latest.actions||[]).map(a => '<div style="font-family:var(--mono);font-size:11px;color:var(--a)">&#9888; ' + a + '</div>').join('') + '</div>'
    : '';

  const whyNot = (latest.why_not_trading || []).length
    ? '<div style="margin-top:8px"><div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em;margin-bottom:4px">WHY NOTHING TRADED</div>' +
      (latest.why_not_trading||[]).map(w => '<div style="font-family:var(--mono);font-size:11px;color:var(--t2)">&#8594; ' + w + '</div>').join('') + '</div>'
    : '';

  const dots = rows.length > 1
    ? '<div style="margin-top:12px"><div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em;margin-bottom:6px">24H ASSESSMENT HISTORY (' + rows.length + ' runs)</div>' +
      '<div style="display:flex;flex-wrap:wrap;gap:3px">' +
      rows.slice(0,48).reverse().map(r => {
        const c = r.status==='GREEN'?'#00e5a0':r.status==='RED'?'#ff4d6d':'#ffb627';
        return '<div title="' + (r.as_of_pt||'') + ' · ' + r.status + '" style="width:10px;height:10px;border-radius:50%;background:'+c+';cursor:default"></div>';
      }).join('') + '</div>' +
      '<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:4px">&#9679; GREEN=healthy &nbsp; &#9679; YELLOW=warn &nbsp; &#9679; RED=issue</div>' +
      '</div>'
    : '';

  return '<div class="ir-section">' +
    '<div class="ir-section-title">ENGINE ASSESSMENT' +
    '<span style="font-weight:400;color:var(--t3)"> — ' + (latest.as_of_pt||'') + '</span>' +
    '<span style="font-family:var(--mono);font-size:11px;font-weight:800;color:' + latCol +
    ';background:' + latBg + ';border:1px solid ' + latBd + ';padding:2px 8px;border-radius:3px;margin-left:8px">' + latest.status + '</span>' +
    '</div>' + kpis + findings + whyNot + actions + dots + '</div>';
}

// ── Convergence signals section ────────────────────────────────────────────
function _renderConvergenceSection(superSignals, watching, mktOpen, riskOff) {
  let html = '<div class="ir-section"><div class="ir-section-title">CONVERGENCE SIGNALS' +
    '<span style="font-weight:400;color:var(--t3)"> — ' + superSignals.length + ' super &middot; ' + watching.length + ' developing</span>' +
    '<button onclick="showView(\'convergence\')" style="margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--g);background:var(--gd);border:1px solid var(--gb);padding:3px 10px;border-radius:4px;cursor:pointer">View All &#8594;</button>' +
    '</div>';

  if (superSignals.length === 0 && watching.length === 0) {
    return html +
      '<div class="ir-empty"><div style="font-size:28px;margin-bottom:8px">◎</div>' +
      '<div class="ir-empty-title">Engine is scanning</div>' +
      '<div class="ir-empty-sub">No convergence above threshold (score ≥ 4.0 with 4+ pillars and binary catalyst).<br>1,000+ tickers evaluated every 15 minutes.</div></div></div>';
  }

  if (superSignals.length > 0) {
    html += '<div class="ir-subsection-label" style="color:var(--g)">SUPER SIGNALS — Score ≥ 4.0 · 4+ pillars · catalyst present</div>';
    html += '<div class="ir-signal-grid">' + superSignals.map(s => _renderSuperSignalCard(s, mktOpen, riskOff)).join('') + '</div>';
  }

  if (watching.length > 0) {
    html += '<div class="ir-subsection-label" style="margin-top:' + (superSignals.length > 0 ? '14px' : '0') + '">DEVELOPING — Building toward threshold</div>';
    html += '<div class="ir-watch-list">' + watching.slice(0, 8).map(_renderWatchSignalRow).join('') + '</div>';
  }

  return html + '</div>';
}

function _renderSuperSignalCard(s, mktOpen, riskOff) {
  const dirColor  = s.direction === 'LONG' ? 'var(--g)' : s.direction === 'SHORT' ? 'var(--r)' : 'var(--a)';
  const dirClass  = s.direction === 'LONG' ? 'dp-long' : s.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
  const pillars   = (s.pillar_breakdown?.pillars || []).filter(p => p.fired);
  const catDays   = s.catalyst_date ? Math.round((new Date(s.catalyst_date) - new Date().setHours(0,0,0,0)) / 86400000) : null;
  const catStr    = s.catalyst_type ? (s.catalyst_type + (catDays != null ? ' · ' + catDays + 'd' : '')) : '';
  const execState = s.executable === false ? 'NOT EXECUTABLE' : riskOff ? 'MACRO BLOCKED' : mktOpen ? 'EXECUTING' : 'QUEUED FOR OPEN';
  const execColor = s.executable === false ? 'var(--t3)' : riskOff ? 'var(--r)' : mktOpen ? 'var(--g)' : 'var(--a)';
  const skipNote  = s.executable === false ? '<div style="margin-top:4px;font-size:11px;color:var(--a)">⚠ ' + (s.skip_reason || 'Cannot execute') + '</div>' : '';
  const structNames = { BULL_CALL_SPREAD:'Bull Call Spread', BEAR_PUT_SPREAD:'Bear Put Spread', LONG_STRANGLE:'Long Strangle', LONG_CALL:'Long Call', LONG_PUT:'Long Put' };
  const structName = structNames[s.recommended_structure] || s.recommended_structure || '';

  const pillarsHtml = pillars.map(p =>
    '<div style="display:flex;gap:6px;padding:3px 0;border-bottom:1px solid var(--b0);font-size:11px;">' +
    '<span style="font-family:var(--mono);font-size:9px;color:var(--g);width:16px">✓</span>' +
    '<span style="font-family:var(--mono);font-size:9px;color:var(--t3);width:120px;flex-shrink:0">' + p.name + '</span>' +
    '<span style="color:var(--t2);flex:1;line-height:1.4">' + (p.evidence||'').slice(0,60) + '…</span>' +
    '</div>'
  ).join('');

  return '<div class="ir-signal-card" style="border-color:rgba(0,229,160,0.25)" onclick="showView(\'convergence\')">' +
    '<div class="ir-sc-top">' +
    '<span class="ir-sc-ticker">' + s.ticker + '</span>' +
    '<span class="dir-pill ' + dirClass + '" style="font-size:9px">' + s.direction + '</span>' +
    (catStr ? '<span style="font-family:var(--mono);font-size:10px;color:var(--a);background:var(--ad);border:1px solid var(--ab);padding:2px 8px;border-radius:3px">' + catStr + '</span>' : '') +
    '<span style="font-family:var(--mono);font-size:10px;color:' + execColor + ';margin-left:4px">' + execState + '</span>' +
    '<span style="margin-left:auto;font-family:var(--mono);font-size:18px;font-weight:800;color:var(--g)">' + s.composite_score.toFixed(2) + '</span>' +
    '</div>' +
    (structName ? '<div style="padding:6px 0;font-family:var(--mono);font-size:11px;color:var(--b)">&#8993; ' + structName + ' &nbsp;<span style="color:var(--t3)">Estimated — verify vs broker</span></div>' : '') +
    '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:4px;padding:6px 8px;margin:6px 0">' + pillarsHtml + '</div>' +
    (s.narrative ? '<div style="font-size:12px;color:var(--t2);line-height:1.5;margin-top:6px">' + s.narrative + '</div>' : '') +
    skipNote +
    '</div>';
}

function _renderWatchSignalRow(s) {
  const dc  = s.direction === 'LONG' ? 'var(--g)' : s.direction === 'SHORT' ? 'var(--r)' : 'var(--t2)';
  const pct = Math.min(100, Math.round((s.composite_score - 2.5) / 1.5 * 100));
  return '<div class="ir-watch-row" onclick="showView(\'convergence\')">' +
    '<span class="ir-wr-ticker">' + s.ticker + '</span>' +
    '<span class="ir-wr-dir" style="color:' + dc + '">' + s.direction + '</span>' +
    '<div class="ir-wr-bar"><div class="ir-wr-fill" style="width:' + pct + '%"></div></div>' +
    '<span class="ir-wr-d">score ' + s.composite_score.toFixed(2) + '</span>' +
    '<span class="ir-wr-note">need ' + (4.0 - s.composite_score).toFixed(2) + ' more</span>' +
    '</div>';
}

// ── Positions section ──────────────────────────────────────────────────────
function _renderPositionsSection(openPos, totalPL) {
  if (!openPos || openPos.length === 0) return '';
  const plColor = totalPL >= 0 ? 'var(--g)' : 'var(--r)';
  const plStr   = (totalPL >= 0 ? '+' : '') + '$' + Math.abs(totalPL).toFixed(2);
  return '<div class="ir-section"><div class="ir-section-title">OPEN POSITIONS' +
    '<span style="font-weight:400;color:' + plColor + '"> — Total P&L: ' + plStr + '</span></div>' +
    '<div class="ir-pos-list">' +
    openPos.map(p => {
      const plc = (p.unrealized_pl||0) >= 0 ? 'var(--g)' : 'var(--r)';
      return '<div class="ir-pos-row">' +
        '<span class="ir-pos-ticker">' + (p.symbol||p.ticker) + '</span>' +
        '<span class="ir-pos-side">' + (p.side||'') + '</span>' +
        '<span class="ir-pos-val">$' + Math.round(p.market_value||0).toLocaleString() + '</span>' +
        '<span class="ir-pos-pl" style="color:' + plc + '">' +
        ((p.unrealized_pl||0)>=0?'+':'') + '$' + (p.unrealized_pl||0).toFixed(2) + '</span>' +
        '</div>';
    }).join('') + '</div></div>';
}

// ── Market context ─────────────────────────────────────────────────────────
function _renderMarketContext(macro, g) {
  if (!macro && !g) return '';
  const mv  = macro?.verdict || 'UNKNOWN';
  const mvC = mv==='RISK_ON'?'var(--g)':mv==='RISK_OFF'?'var(--r)':'var(--a)';
  const gv  = g?.overall_verdict || '—';
  const gvC = (gv==='RISK_ON'||gv==='POSITIVE')?'var(--g)':gv==='RISK_OFF'?'var(--r)':'var(--a)';
  const fmt = (v, d) => v != null ? (v>0?'+':'') + v.toFixed(d||2) + '%' : '—';

  const notable = (g?.indices||[]).filter(i => i.change_pct != null && Math.abs(i.change_pct) >= 0.5).sort((a,b)=>Math.abs(b.change_pct)-Math.abs(a.change_pct)).slice(0,5);
  const notableHtml = notable.length ? '<div class="ir-ctx-block"><div class="ir-ctx-label">Notable Moves</div>' +
    notable.map(i => '<div class="ir-idx-row"><span class="ir-idx-name">' + i.name + '</span>' +
    '<span style="color:' + (i.change_pct>0?'var(--g)':'var(--r)') + ';font-family:var(--mono);font-size:11px;font-weight:700">' + fmt(i.change_pct) + '</span></div>').join('') + '</div>' : '';

  return '<div class="ir-section"><div class="ir-section-title">MARKET CONTEXT</div>' +
    '<div class="ir-ctx-grid">' +
    '<div class="ir-ctx-block"><div class="ir-ctx-label">Macro Verdict</div>' +
    '<div class="ir-ctx-big" style="color:' + mvC + '">' + mv + '</div>' +
    '<div class="ir-ctx-sub">Size modifier: ' + Math.round((macro?.size_modifier||0)*100) + '%</div>' +
    '<div class="ir-ctx-sub">' + (macro?.reason||'') + '</div></div>' +
    '<div class="ir-ctx-block"><div class="ir-ctx-label">Global Markets</div>' +
    '<div class="ir-ctx-big" style="color:' + gvC + '">' + gv + '</div>' +
    '<div class="ir-ctx-sub">Asia ' + fmt(g?.asia_avg_chg) + ' · EU ' + fmt(g?.europe_avg_chg) + ' · Futures ' + fmt(g?.futures_avg_chg) + '</div></div>' +
    notableHtml + '</div>' +
    (g?.narrative ? '<div class="ir-narrative">' + g.narrative + '</div>' : '') +
    '</div>';
}

// ── Hit rate ───────────────────────────────────────────────────────────────
function _renderHitRateSection(hr) {
  const windows = hr?.windows || [];
  const best    = windows.find(w => w.window_days === 30) || windows[0];
  const logged  = hr?.signals_logged || 0;
  const resolved = hr?.signals_resolved || 0;
  const pct      = Math.min(100, Math.round(resolved / 30 * 100));

  let inner = '';
  if (best && best.total_signals >= 10) {
    const col  = best.hit_rate_pct >= 60 ? 'var(--g)' : best.hit_rate_pct >= 55 ? 'var(--a)' : 'var(--r)';
    const verd = best.hit_rate_pct >= 60 ? 'GO LIVE — edge confirmed' : best.hit_rate_pct >= 55 ? 'CAUTIOUS GO — start at 25% Kelly' : best.hit_rate_pct >= 45 ? 'EXTEND PAPER — more data needed' : 'STOP — signals not predictive';
    inner = '<div class="ir-hr-big" style="color:' + col + '">' + best.hit_rate_pct.toFixed(1) + '%</div>' +
      '<div class="ir-hr-label">' + best.window_days + '-day window · ' + best.total_signals + ' signals</div>' +
      '<div class="ir-hr-verdict" style="color:' + col + '">' + verd + '</div>';
  } else {
    inner = '<div class="ir-hr-big" style="color:var(--a)">PENDING</div>' +
      '<div class="ir-hr-label">Need 30 resolved options trades to validate edge</div>' +
      '<div style="margin:10px 0 4px"><div class="ir-hr-bar-wrap"><div class="ir-hr-bar-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="ir-hr-bar-label">' + resolved + ' of 30 minimum trades resolved</div></div>' +
      '<div class="ir-hr-label">' + logged + ' signals logged in convergence_signals</div>';
  }

  return '<div class="ir-section"><div class="ir-section-title">HIT RATE — EDGE VALIDATION</div>' +
    '<div class="ir-hr-block">' + inner + '</div></div>';
}

// ── Pipeline ───────────────────────────────────────────────────────────────
function _renderPipelineSection(p) {
  if (!p) return '';
  const steps    = p.steps    || [];
  const adapters = p.adapters || [];
  const cc       = p.cycle_healthy ? 'var(--g)' : 'var(--r)';

  const stepsHtml = steps.map(s => {
    const ic = s.status==='ok' ? 'var(--g)' : 'var(--r)';
    return '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;background:var(--bg2);border:1px solid var(--b1);border-radius:4px">' +
      '<span style="color:' + ic + ';font-size:10px">' + (s.status==='ok'?'✓':'✗') + '</span>' +
      '<span style="font-size:11px;font-weight:700;color:var(--t1);min-width:130px">' + s.step + '</span>' +
      '<span style="font-size:10px;color:var(--t3)">' + (s.duration_s!=null?s.duration_s+'s':'—') + '</span>' +
      '<span style="font-size:9px;color:var(--t3);margin-left:auto">' + s.mins_ago + 'm ago</span>' +
      (s.error?'<span style="color:var(--r);font-size:9px">'+s.error.substring(0,30)+'</span>':'') +
      '</div>';
  }).join('');

  const adaptersHtml = adapters.length === 0 ? '<div style="color:var(--t3);font-size:11px">No runs in last hour</div>'
    : adapters.map(a =>
      '<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;background:var(--bg2);border:1px solid var(--b1);border-radius:4px">' +
      '<span style="font-size:10px">' + (a.ok?'✓':'✗') + '</span>' +
      '<span style="font-size:10px;color:var(--t1);min-width:130px">' + a.adapter_id.replace('stocks.','') + '</span>' +
      '<span style="font-size:10px;color:var(--t2)">' + a.fetched + ' fetched</span>' +
      '<span style="font-size:10px;color:var(--g)">' + a.written + ' wrote</span>' +
      '<span style="font-size:9px;color:var(--t3);margin-left:auto">' + (a.duration_s!=null?a.duration_s+'s':'?') + '</span>' +
      (a.error?'<span style="color:var(--r);font-size:9px">'+a.error.substring(0,30)+'</span>':'') +
      '</div>'
    ).join('');

  return '<div class="ir-section"><div class="ir-section-title">PIPELINE STATUS' +
    '<span style="font-weight:400;color:' + cc + '"> — last cycle ' + (p.last_cycle_mins!=null?p.last_cycle_mins+'m ago':'unknown') + ' · backlog ' + (p.backlog||0).toLocaleString() + '</span></div>' +
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">' +
    '<div><div class="ir-subsection-label">STEPS</div><div style="display:flex;flex-direction:column;gap:3px">' + stepsHtml + '</div></div>' +
    '<div><div class="ir-subsection-label">ADAPTERS</div><div style="display:flex;flex-direction:column;gap:3px">' + adaptersHtml + '</div></div>' +
    '</div></div>';
}

// ── Execution log ──────────────────────────────────────────────────────────
function _renderExecLogSection(e) {
  if (!e?.entries?.length) return '';
  const rows = e.entries.map(entry => {
    const oc   = entry.outcome==='EXECUTED'?'var(--g)':entry.outcome==='BLOCKED'?'var(--r)':entry.outcome==='SIGNAL_ONLY'?'var(--a)':'var(--t3)';
    const icon = entry.outcome==='EXECUTED'?'🟢':entry.outcome==='BLOCKED'?'🔴':'🟡';
    return '<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--bg2);border:1px solid var(--b1);border-radius:6px">' +
      '<span style="font-size:14px">' + icon + '</span>' +
      '<span style="font-family:var(--mono);font-size:13px;font-weight:800;color:var(--t1);min-width:52px">' + entry.ticker + '</span>' +
      '<span style="font-size:10px;font-weight:700;color:' + oc + ';min-width:90px">' + entry.outcome + '</span>' +
      '<span style="font-size:10px;color:var(--t2)">' + (entry.side||'') + (entry.size>0?' $'+Math.round(entry.size).toLocaleString():'') + '</span>' +
      (entry.reason?'<span style="font-size:10px;color:var(--t3);flex:1">'+entry.reason+'</span>':'<span style="flex:1"></span>') +
      '<span style="font-size:9px;color:var(--t3)">' + (entry.time_pt||'') + '</span>' +
      '</div>';
  }).join('');
  return '<div class="ir-section"><div class="ir-section-title">EXECUTION LOG<span style="font-weight:400;color:var(--t3)"> — ' + e.entries.length + ' entries</span></div>' +
    '<div style="display:flex;flex-direction:column;gap:4px">' + rows + '</div></div>';
}
