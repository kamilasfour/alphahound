/* ════════════════════════════════════════════════════
   convergence.js — Sprint 11/12
   Multi-Pillar Convergence Engine view
   ════════════════════════════════════════════════════ */

let convergenceData = null;

async function loadConvergence() {
  try {
    const [conv, opts] = await Promise.all([
      fj('/api/convergence'),
      fj('/api/options-positions').catch(() => ({ positions: [] }))
    ]);
    convergenceData = conv;
    renderConvergence();
    renderOptionsPositions(opts.positions || []);
    const supers = (convergenceData.super_signals || []).length;
    const kEl = document.getElementById('k-super');
    if (kEl) kEl.textContent = supers || '0';
  } catch(e) {
    console.error('loadConvergence', e);
    const el = document.getElementById('conv-list');
    if (el) el.innerHTML = '<div class="empty">Error loading convergence signals</div>';
  }
}

function renderConvergence() {
  const el = document.getElementById('conv-list');
  if (!el || !convergenceData) return;
  const { super_signals = [], watching = [], as_of_et, macro_verdict, macro_score } = convergenceData;

  const macroColor = macro_verdict === 'RISK_ON' ? 'var(--g)' : macro_verdict === 'RISK_OFF' ? 'var(--r)' : 'var(--a)';
  const headerHTML = '<div style="padding:12px 16px;border-bottom:1px solid var(--b1);background:var(--s2);display:flex;align-items:center;gap:12px;flex-shrink:0;">'
    + '<span style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--t3)">Macro</span>'
    + '<span style="font-family:var(--mono);font-size:12px;font-weight:800;color:' + macroColor + '">' + (macro_verdict || '\u2014') + '</span>'
    + '<span style="font-family:var(--mono);font-size:11px;color:var(--t3)">' + (macro_score != null ? (macro_score > 0 ? '+' : '') + macro_score.toFixed(3) : '') + '</span>'
    + '<span style="margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--t3)">' + (as_of_et || '') + '</span>'
    + '</div>';

  let superHTML = '';
  if (super_signals.length === 0) {
    superHTML = '<div class="empty" style="padding:24px 16px">'
      + '<div style="font-size:22px;opacity:0.2;margin-bottom:8px">\u25ce</div>'
      + '<div style="font-family:var(--mono);font-size:11px;color:var(--t3)">No super signals right now</div>'
      + '<div style="font-family:var(--sans);font-size:11px;color:var(--t3);margin-top:4px">Need score \u2265 4.0 with 4+ pillars and binary catalyst</div>'
      + '</div>';
  } else {
    superHTML = super_signals.map(function(s, i) { return buildConvergenceCard(s, i, true); }).join('');
  }

  let watchHTML = '';
  if (watching.length > 0) {
    watchHTML = '<div style="padding:8px 16px;border-bottom:1px solid var(--b1);border-top:1px solid var(--b1);background:var(--s2);flex-shrink:0;margin-top:4px;">'
      + '<span style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--t3)">Developing \u2014 ' + watching.length + ' signal' + (watching.length !== 1 ? 's' : '') + ' building</span>'
      + '</div>'
      + watching.map(function(s, i) { return buildConvergenceCard(s, i, false); }).join('');
  }

  el.innerHTML = headerHTML
    + '<div style="padding:8px 16px 6px;border-bottom:1px solid var(--b1);background:var(--s2);flex-shrink:0;">'
    + '<span style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:' + (super_signals.length > 0 ? 'var(--g)' : 'var(--t3)') + '">\ud83d\udea8 Super Signals \u2014 ' + super_signals.length + ' active</span>'
    + '</div>'
    + superHTML + watchHTML;
}

function buildConvergenceCard(s, idx, isSuper) {
  var dirColor   = s.direction === 'LONG' ? 'var(--g)' : s.direction === 'SHORT' ? 'var(--r)' : 'var(--a)';
  var dirClass   = s.direction === 'LONG' ? 'dp-long' : s.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
  var scoreColor = s.composite_score >= 4.0 ? 'var(--g)' : s.composite_score >= 3.0 ? 'var(--a)' : 'var(--t2)';
  var cardBorder = isSuper ? 'background:rgba(16,185,129,0.03);border-left:2px solid var(--g);' : '';

  var pillars    = (s.pillar_breakdown && s.pillar_breakdown.pillars) ? s.pillar_breakdown.pillars : [];
  var pillarHTML = pillars.length ? buildPillarGrid(pillars) : '';
  var structHTML = s.recommended_structure ? buildStructureBadge(s) : '';

  var catHTML = '';
  if (s.catalyst_type) {
    catHTML = '<span style="font-family:var(--mono);font-size:10px;color:var(--a);background:var(--ab);border:1px solid var(--ad);padding:2px 7px;border-radius:4px;">'
      + s.catalyst_type + (s.catalyst_date ? ' \u00b7 ' + daysUntil(s.catalyst_date) + 'd' : '')
      + '</span>';
  }

  // Non-executable warning
  var execWarning = '';
  if (isSuper && s.executable === false) {
    execWarning = '<div style="margin-top:8px;padding:8px 10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:5px;font-size:11px;color:var(--a);line-height:1.5;">'
      + '\u26a0 Cannot execute: ' + (s.skip_reason || 'Chain limitation') + '. Signal is valid but no tradeable contracts available at this price level.'
      + '</div>';
  }

  var narrHTML = s.narrative
    ? '<div style="font-family:var(--sans);font-size:12px;color:var(--t2);line-height:1.6;margin-top:10px;padding:9px 11px;background:rgba(139,92,246,0.04);border:1px solid rgba(139,92,246,0.12);border-left:2px solid var(--p);border-radius:6px;">' + s.narrative + '</div>'
    : '';

  var btnLabel   = s.structure ? '\u29e1 View Structure Plan' : '\u29e1 Get Structure Plan';
  var btnOnclick = s.structure
    ? 'showStructureFromData(\'' + s.ticker + '\', \'' + encodeURIComponent(JSON.stringify(s.structure)) + '\')'
    : 'runStructure(\'' + s.ticker + '\')';
  var footerBtn  = isSuper && s.executable !== false
    ? '<button onclick="' + btnOnclick + '" style="margin-left:auto;font-family:var(--mono);font-size:10px;font-weight:700;padding:4px 10px;background:var(--pb);border:1px solid var(--pd);color:var(--p);border-radius:4px;cursor:pointer;">' + btnLabel + '</button>'
    : '';

  return '<div style="border-bottom:1px solid var(--b1);padding:14px 16px;' + cardBorder + '">'
    + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
    + '<span style="font-family:var(--mono);font-size:20px;font-weight:700;color:var(--t1);">' + s.ticker + '</span>'
    + '<span class="dir-pill ' + dirClass + '">' + s.direction + '</span>'
    + (isSuper ? '<span style="font-family:var(--mono);font-size:9px;font-weight:800;letter-spacing:0.1em;padding:2px 7px;border-radius:4px;background:rgba(16,185,129,0.15);color:var(--g);border:1px solid rgba(16,185,129,0.3)">SUPER SIGNAL</span>' : '')
    + catHTML
    + '<div style="margin-left:auto;text-align:right;">'
    + '<div style="font-family:var(--mono);font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:var(--t3);margin-bottom:2px;">Conv. Score</div>'
    + '<div style="font-family:var(--mono);font-size:18px;font-weight:800;color:' + scoreColor + ';line-height:1;">' + s.composite_score.toFixed(2) + '</div>'
    + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);">' + s.pillars_fired + ' pillars</div>'
    + '</div></div>'
    + pillarHTML + structHTML + narrHTML + execWarning
    + '<div style="margin-top:8px;display:flex;align-items:center;gap:8px;">'
    + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3);">' + (s.time_et || '') + '</span>'
    + footerBtn
    + '</div></div>';
}

function buildPillarGrid(pillars) {
  var rows = pillars.map(function(p) {
    var icon     = p.fired ? '\u2705' : '\u25a1';
    var nameCol  = p.fired ? 'var(--t1)' : 'var(--t3)';
    var scoreCol = p.score >= 1.0 ? 'var(--g)' : p.score >= 0.5 ? 'var(--a)' : 'var(--t3)';
    var evidence = (p.evidence || '').slice(0, 90) + ((p.evidence || '').length > 90 ? '\u2026' : '');
    return '<div style="display:flex;align-items:flex-start;gap:8px;padding:5px 0;border-bottom:1px solid var(--b0);">'
      + '<span style="font-size:11px;flex-shrink:0;width:18px;text-align:center;">' + icon + '</span>'
      + '<span style="font-family:var(--mono);font-size:10px;font-weight:700;color:' + nameCol + ';width:140px;flex-shrink:0;">' + p.name + '</span>'
      + '<span style="font-family:var(--mono);font-size:10px;font-weight:700;color:' + scoreCol + ';width:28px;flex-shrink:0;">[' + p.score.toFixed(1) + ']</span>'
      + '<span style="font-family:var(--sans);font-size:11px;color:var(--t3);flex:1;line-height:1.4;">' + evidence + '</span>'
      + '</div>';
  }).join('');
  return '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:6px;padding:8px 12px;margin-bottom:10px;">' + rows + '</div>';
}

function buildStructureBadge(s) {
  var structNames = { BULL_CALL_SPREAD:'Bull Call Spread', BEAR_PUT_SPREAD:'Bear Put Spread', LONG_STRANGLE:'Long Strangle', LONG_CALL:'Long Call', LONG_PUT:'Long Put' };
  var name     = structNames[s.recommended_structure] || s.recommended_structure;
  var dirColor = s.direction === 'LONG' ? 'var(--g)' : s.direction === 'SHORT' ? 'var(--r)' : 'var(--a)';
  return '<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.18);border-radius:6px;margin-bottom:6px;">'
    + '<span style="font-family:var(--mono);font-size:10px;font-weight:700;color:var(--bl);">OPTIONS</span>'
    + '<span style="font-family:var(--sans);font-size:11px;color:var(--t2);">Recommended structure:</span>'
    + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:' + dirColor + ';">' + name + '</span>'
    + (s.catalyst_type ? '<span style="font-family:var(--mono);font-size:10px;color:var(--t3);">\u00b7 ' + s.catalyst_type + ' catalyst</span>' : '')
    + '<span style="margin-left:auto;font-family:var(--mono);font-size:9px;color:var(--t3);">Estimated \u2014 verify with broker</span>'
    + '</div>';
}

/* ── Structure modal — pre-attached (S11-6) ── */
function showStructureFromData(ticker, encodedData) {
  var s = JSON.parse(decodeURIComponent(encodedData));
  renderStructureModal(ticker, s);
}

async function runStructure(ticker) {
  var modalId = 'struct-modal-' + ticker;
  document.getElementById(modalId) && document.getElementById(modalId).remove();
  var overlay = buildModalShell(modalId, ticker, true);
  document.body.appendChild(overlay);
  try {
    var d = await fj('/api/convergence/structure?ticker=' + ticker);
    var body = document.getElementById(modalId + '-body');
    if (!body) return;
    if (d.error) { body.innerHTML = '<div class="empty">' + d.error + '</div>'; return; }
    if (!d.structure) { body.innerHTML = '<div class="empty">No structure available</div>'; return; }
    body.innerHTML = buildStructureBody(d.structure);
  } catch(e) {
    var b = document.getElementById(modalId + '-body');
    if (b) b.innerHTML = '<div class="empty">Error: ' + e.message + '</div>';
  }
}

function renderStructureModal(ticker, s) {
  var modalId = 'struct-modal-' + ticker;
  document.getElementById(modalId) && document.getElementById(modalId).remove();
  var overlay = buildModalShell(modalId, ticker, false);
  document.body.appendChild(overlay);
  var body = document.getElementById(modalId + '-body');
  if (body) body.innerHTML = buildStructureBody(s);
}

function buildModalShell(modalId, ticker, loading) {
  var overlay = document.createElement('div');
  overlay.id = modalId;
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.82);backdrop-filter:blur(6px);z-index:300;display:flex;align-items:center;justify-content:center;padding:20px;';
  overlay.innerHTML = '<div style="background:var(--s1);border:1px solid var(--b2);border-radius:12px;width:100%;max-width:640px;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--b1);background:var(--s2);flex-shrink:0;">'
    + '<div><div style="font-family:var(--mono);font-size:12px;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;">Structure Plan \u00b7 ' + ticker + '</div>'
    + '<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-top:2px;">ESTIMATED PRICES \u2014 verify against broker before entry</div></div>'
    + '<button onclick="document.getElementById(\'' + modalId + '\').remove()" style="background:none;border:none;color:var(--t3);font-size:16px;cursor:pointer;padding:4px 8px;">\u2715</button>'
    + '</div>'
    + '<div id="' + modalId + '-body" style="overflow-y:auto;flex:1;padding:16px 18px;">'
    + (loading ? '<div class="loading">Building structure plan\u2026</div>' : '')
    + '</div></div>';
  return overlay;
}

function buildStructureBody(s) {
  var structNames = { BULL_CALL_SPREAD:'Bull Call Spread', BEAR_PUT_SPREAD:'Bear Put Spread', LONG_STRANGLE:'Long Strangle', LONG_CALL:'Long Call', LONG_PUT:'Long Put' };
  var dirColor    = s.direction === 'LONG' ? 'var(--g)' : s.direction === 'SHORT' ? 'var(--r)' : 'var(--a)';

  var summaryHTML = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">'
    + card9('Structure', '<span style="color:' + dirColor + '">' + (structNames[s.structure_type] || s.structure_type) + '</span>', s.direction + ' \u00b7 ~$' + (s.current_price ? s.current_price.toFixed(2) : '?'))
    + card9('Expiry', s.expiry || '\u2014', (s.dte || '?') + ' DTE')
    + card9('Score', '<span style="color:var(--g)">' + (s.composite_score ? s.composite_score.toFixed(2) : '\u2014') + '</span>', (s.pillars_fired || '?') + ' pillars')
    + card9('Sizing', 'Executor decides', ((s.suggested_risk_pct || 0.02) * 100).toFixed(0) + '% risk target')
    + '</div>';

  var legsHTML = '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:6px;">Legs (Estimated \u00b7 BS/HV30)</div>'
    + '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:6px;padding:8px 12px;margin-bottom:14px;">';
  (s.legs || []).forEach(function(l) {
    legsHTML += '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--b0);">'
      + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:' + (l.action === 'BUY' ? 'var(--g)' : 'var(--r)') + '">' + l.action + '</span>'
      + '<span style="font-family:var(--mono);font-size:11px;color:var(--t1)">' + l.contract_type + '</span>'
      + '<span style="font-family:var(--mono);font-size:12px;font-weight:700;color:var(--t1)">$' + l.strike + '</span>'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3)">exp ' + l.expiry + ' (' + l.dte + 'DTE)</span>'
      + '<span style="margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--t2)">~$' + (l.estimated_premium ? l.estimated_premium.toFixed(2) : '?') + '/sh</span>'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3)">\u03b4\u2248' + (l.estimated_delta > 0 ? '+' : '') + (l.estimated_delta ? l.estimated_delta.toFixed(2) : '?') + '</span>'
      + '</div>';
  });
  if (!(s.legs && s.legs.length)) legsHTML += '<span style="color:var(--t3);font-size:11px;">No legs available</span>';
  legsHTML += '</div>';

  var econHTML = '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:6px;">Estimated Economics</div>'
    + '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px;">'
    + card9('Debit', '~$' + (s.estimated_debit ? s.estimated_debit.toFixed(2) : '?'), '')
    + card9('Max Loss', '~$' + (s.estimated_max_loss ? s.estimated_max_loss.toFixed(2) : '?'), '')
    + card9('Max Gain', '~$' + (s.estimated_max_gain ? s.estimated_max_gain.toFixed(2) : '?'), '')
    + card9('R/R', '~1:' + (s.estimated_rr ? s.estimated_rr.toFixed(1) : '?'), '')
    + '</div>'
    + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-bottom:12px;">'
    + 'Breakeven' + ((s.estimated_breakevens || []).length > 1 ? 's' : '') + ': '
    + (s.estimated_breakevens || []).map(function(b) { return '~$' + b; }).join(' / ')
    + ' \u00b7 Exit at ~' + (((s.target_exit_pct || 0.5) * 100).toFixed(0)) + '% of max gain'
    + '</div>';

  var warnHTML = (s.warnings || []).map(function(w) {
    return '<div style="padding:7px 10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:5px;font-size:11px;color:var(--a);line-height:1.5;margin-top:6px;">\u26a0 ' + w + '</div>';
  }).join('');

  var catalystHTML = s.catalyst_type
    ? '<div style="margin-top:10px;padding:8px 11px;background:var(--ab);border:1px solid var(--ad);border-radius:6px;font-family:var(--mono);font-size:11px;color:var(--a);">\ud83d\udcc5 ' + s.catalyst_type + ' on ' + s.catalyst_date + ' (' + daysUntil(s.catalyst_date) + 'd away)</div>'
    : '';

  var narrativeHTML = '<div style="margin-top:12px;padding:10px 12px;background:rgba(139,92,246,0.04);border:1px solid rgba(139,92,246,0.12);border-left:2px solid var(--p);border-radius:6px;font-size:12px;color:var(--t2);line-height:1.6;">' + (s.narrative || '') + '</div>';

  return summaryHTML + legsHTML + econHTML + warnHTML + catalystHTML + narrativeHTML;
}

function card9(label, val, sub) {
  return '<div style="flex:1;min-width:100px;background:var(--s3);border:1px solid var(--b1);border-radius:8px;padding:12px;">'
    + '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:4px;">' + label + '</div>'
    + '<div style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--t1);">' + val + '</div>'
    + (sub ? '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:2px;">' + sub + '</div>' : '')
    + '</div>';
}

function daysUntil(dateStr) {
  if (!dateStr) return '?';
  var today = new Date(); today.setHours(0,0,0,0);
  return Math.round((new Date(dateStr) - today) / 86400000);
}

/* ── Options positions panel (Sprint 12) ── */
function renderOptionsPositions(positions) {
  var el = document.getElementById('opts-positions');
  if (!el) return;
  if (!positions || positions.length === 0) {
    el.innerHTML = '<div style="padding:14px 18px;font-family:var(--mono);font-size:11px;color:var(--t3);">No open options positions</div>';
    return;
  }
  var rows = positions.map(function(p) {
    var plColor  = p.unrealized_pl >= 0 ? 'var(--g)' : 'var(--r)';
    var plAbs    = Math.abs(p.unrealized_pl || 0).toFixed(0);
    var plStr    = (p.unrealized_pl >= 0 ? '+' : '-') + '$' + plAbs;
    var pctStr   = (p.unrealized_pl_pct >= 0 ? '+' : '') + (p.unrealized_pl_pct || 0).toFixed(1) + '%';
    var border   = p.should_close ? 'border-left:3px solid var(--r);' : '';
    var closeTag = p.should_close
      ? '<span style="font-family:var(--mono);font-size:9px;background:rgba(255,77,109,0.15);color:var(--r);border:1px solid rgba(255,77,109,0.3);padding:2px 8px;border-radius:3px;">CLOSE TARGET</span>'
      : '';
    var catStr    = p.catalyst_type ? p.catalyst_type + (p.catalyst_date ? ' \u00b7 ' + daysUntil(p.catalyst_date) + 'd' : '') : '';
    var structStr = (p.structure_type || '').replace(/_/g, ' ');
    return '<div style="padding:12px 18px;border-bottom:1px solid var(--b1);' + border + 'display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
      + '<span style="font-family:var(--mono);font-size:17px;font-weight:700;color:var(--t1);">' + p.ticker + '</span>'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--t2);">' + structStr + '</span>'
      + (catStr ? '<span style="font-family:var(--mono);font-size:10px;color:var(--a);background:var(--ab);border:1px solid var(--ad);padding:2px 7px;border-radius:3px;">' + catStr + '</span>' : '')
      + closeTag
      + '<div style="margin-left:auto;text-align:right;">'
      + '<div style="font-family:var(--mono);font-size:18px;font-weight:700;color:' + plColor + ';line-height:1;">' + plStr + '</div>'
      + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:2px;">' + pctStr + ' &nbsp;\u00b7&nbsp; ' + (p.dte || '?') + 'DTE</div>'
      + '</div>'
      + (p.close_reason ? '<div style="width:100%;font-family:var(--mono);font-size:11px;color:var(--r);margin-top:4px;">\u2192 ' + p.close_reason + '</div>' : '')
      + '</div>';
  }).join('');
  el.innerHTML = rows;
}
