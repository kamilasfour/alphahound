/* ══ MACRO ══ */
async function loadMacro() {
  try {
    macroData = await fj('/api/macro');
    const d    = macroData;
    const vCol = {RISK_ON:'var(--g)',NEUTRAL:'var(--a)',RISK_OFF:'var(--r)',NO_DATA:'var(--t3)'};
    const col  = vCol[d.verdict] || 'var(--t2)';

    const kEl = document.getElementById('k-macro');
    kEl.textContent = d.verdict||'—'; kEl.style.color = col;
    document.getElementById('k-macro-sub').textContent = 'score '+(d.score>=0?'+':'')+(d.score||0).toFixed(3);

    const sorted   = Object.entries(d.signals||{}).sort((a,b) => Math.abs(b[1])-Math.abs(a[1]));
    const contribs = d.contributors||{};
    renderMacroView();
  } catch(e) { console.error('loadMacro', e); }
}

function macroRow(t, chg, contrib) {
  const cc      = chg > 0 ? 'var(--g)' : 'var(--r)';
  const kc      = contrib > 0 ? 'var(--g)' : 'var(--r)';
  const bar     = Math.min(100, Math.abs(contrib/2*100));
  const barSide = contrib >= 0 ? 'left:50%' : 'right:50%;left:auto';
  const macroTips = {
    UVXY: 'VIX volatility ETF. Rising = fear increasing. Falling = fear subsiding. Bearish contribution = risk-on signal.',
    TLT:  '20-year US Treasury ETF. Rising = flight to safety (risk-off). Falling = risk appetite returning.',
    UUP:  'US Dollar index ETF. Rising dollar = headwind for equities and emerging markets.',
    HYG:  'High yield (junk) bond ETF. Falling = credit spreads widening = stress signal.',
    EWJ:  'Japan equity ETF — proxy for Asian market health.',
    FXI:  'China large-cap ETF — proxy for Chinese market sentiment.',
    EWG:  'Germany equity ETF — proxy for European market health.',
    EEM:  'Emerging markets ETF. Sensitive to dollar strength and global risk appetite.',
    SPY:  'S&P 500 ETF — US market baseline.',
    QQQ:  'Nasdaq 100 ETF — US tech/growth baseline.',
  };
  const tickerTip = macroTips[t] ? ` data-tooltip="${macroTips[t]}"` : '';
  return `<div class="mac-row">
    <span class="mac-tick"${tickerTip}>${t}</span>
    <span class="mac-role">${ROLE_LABELS[t]||''}</span>
    <span class="mac-chg" style="color:${cc}">${chg>0?'+':''}${chg.toFixed(2)}%</span>
    <div class="mac-bar-wrap"><div class="mac-bar-fill" style="${barSide};width:${bar}%;background:${kc}"></div></div>
    <span class="mac-contrib" style="color:${kc}" data-tooltip="This instrument's weighted contribution to the overall macro score. Positive = pushing toward RISK_ON, Negative = pushing toward RISK_OFF.">${contrib>=0?'+':''}${contrib.toFixed(3)}</span>
  </div>`;
}

function renderMacroView() {
  if (!macroData) { document.getElementById('mv-table').innerHTML = '<div class="loading">LOADING MACRO…</div>'; return; }
  const d    = macroData;
  const vCol = {RISK_ON:'var(--g)',NEUTRAL:'var(--a)',RISK_OFF:'var(--r)',NO_DATA:'var(--t3)'};
  const col  = vCol[d.verdict] || 'var(--t2)';
  const vEl  = document.getElementById('mv-verdict');
  vEl.textContent = d.verdict||'—'; vEl.style.color = col;
  document.getElementById('mv-score').textContent = (d.score>=0?'+':'')+(d.score||0).toFixed(4);
  document.getElementById('mv-size').textContent  = Math.round((d.size_modifier||1)*100)+'%';
  document.getElementById('mv-inst').textContent  = Object.keys(d.signals||{}).length;
  document.getElementById('mv-reason').textContent = d.reason||'—';
  document.getElementById('macro-view-badge').textContent = d.verdict||'—';

  const sorted   = Object.entries(d.signals||{}).sort((a,b) => Math.abs(b[1])-Math.abs(a[1]));
  const contribs = d.contributors||{};
  document.getElementById('mv-table').innerHTML = sorted.length
    ? sorted.map(([t, chg]) => macroRow(t, chg, contribs[t]||0)).join('')
    : '<div class="empty">No macro data yet</div>';

  loaded.macro = true;
}
