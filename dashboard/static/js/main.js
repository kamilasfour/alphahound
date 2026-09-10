/* ══ MASTER LOAD ══ */
async function loadAll() {
  hmData = null; secData = null; uniData = null; macroData = null;
  Object.keys(loaded).forEach(k => delete loaded[k]);

  // Wrap every loader so one failure never kills the rest
  const safe = (fn, name) => fn().catch(e => console.warn('loadAll: ' + name + ' failed:', e.message));

  await Promise.all([
    safe(loadSummary,    'summary'),
    safe(loadAlerts,     'alerts'),
    safe(loadPositions,  'positions'),
    safe(loadTradeLog,   'tradelog'),
    safe(loadCongress,   'congress'),
    safe(loadFlow,       'flow'),
    safe(loadHealth,     'health'),
    safe(loadMacro,      'macro'),
    safe(loadEarnings,   'earnings'),
    safe(loadConvergence,'convergence'),
  ]);

  try {
    const active = VIEWS.find(v => {
      const el = document.getElementById('view-' + v);
      return el && el.classList.contains('active');
    });
    if (active) showView(active);
  } catch(e) {
    console.error('loadAll showView', e);
  }
}

/* ── Clock ── */
function updateETClock() {
  const el = document.getElementById('et-time');
  if (!el) return;
  const now = new Date();
  const pt = now.toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    weekday: 'short', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true,
  });
  const et = now.toLocaleString('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric', minute: '2-digit', hour12: true,
  });
  const etDate = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const h = etDate.getHours(), m = etDate.getMinutes(), dow = etDate.getDay();
  const mktOpen = dow >= 1 && dow <= 5 && (h > 9 || (h === 9 && m >= 30)) && h < 16;
  el.innerHTML = '<span style="color:' + (mktOpen ? 'var(--g)' : 'var(--t3)') + '">'
    + (mktOpen ? '&#9679; OPEN' : '&#9675; CLOSED') + '</span>&nbsp;&nbsp;'
    + pt + '&nbsp;<span style="color:var(--t3);font-size:9px">(' + et + ' ET)</span>';
}

setInterval(updateETClock, 1000);
updateETClock();

/* ── Initial load ── */
loadCheckIn();
loadAll();
