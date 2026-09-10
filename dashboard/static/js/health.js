/* ══ HEALTH MONITOR ══
   Pulls /api/health and renders a live system status panel.
   Status colors: GREEN=ok, YELLOW=warning, RED=critical, UNKNOWN=grey
*/

const STATUS_ICON  = { GREEN: '✅', YELLOW: '⚠️', RED: '❌', UNKNOWN: '❓' };
const STATUS_COLOR = {
  GREEN:   'var(--g)',
  YELLOW:  'var(--a)',
  RED:     'var(--r)',
  UNKNOWN: 'var(--t3)',
};

async function loadHealth() {
  try {
    const [d, adapters, hitrate] = await Promise.all([
      fj('/api/health'),
      fj('/api/adapters').catch(() => ({ adapters: [] })),
      fj('/api/hit-rate').catch(() => ({ windows: [], signals_logged: 0, signals_resolved: 0 })),
    ]);
    renderHealth(d);
    renderAdapters(adapters);
    renderHitRate(hitrate);
  } catch (e) {
    console.error('loadHealth', e);
    const el = document.getElementById('health-list');
    if (el) el.innerHTML = '<div class="empty">Health data unavailable</div>';
  }
}

function renderHealth(d) {
  const el = document.getElementById('health-list');
  if (!el) return;

  const overall = d.overall || 'UNKNOWN';
  const icon    = STATUS_ICON[overall]  || '❓';
  const color   = STATUS_COLOR[overall] || 'var(--t3)';
  const items   = d.items || [];
  const genAt   = d.generated_at ? new Date(d.generated_at).toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true,
  }) : '—';

  // Update the health KPI in the summary bar
  const kpiEl = document.getElementById('k-health');
  const subEl = document.getElementById('k-health-sub');
  if (kpiEl) {
    kpiEl.textContent = overall;
    kpiEl.style.color = color;
  }
  if (subEl) {
    const redItems  = items.filter(i => i.status === 'RED').map(i => i.name);
    const yellItems = items.filter(i => i.status === 'YELLOW').map(i => i.name);
    if (redItems.length)  subEl.textContent = 'RED: ' + redItems.join(', ');
    else if (yellItems.length) subEl.textContent = 'WARN: ' + yellItems.join(', ');
    else subEl.textContent = 'All systems nominal';
  }

  el.innerHTML = `
    <div class="health-header" style="display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid var(--border)">
      <div style="font-size:28px">${icon}</div>
      <div>
        <div style="font-family:var(--sans);font-size:18px;font-weight:800;color:${color}">${overall}</div>
        <div style="font-size:10px;color:var(--t3);margin-top:2px">Last check: ${genAt} PT</div>
      </div>
      <button class="refresh-btn" style="margin-left:auto" onclick="loadHealth()">↻ Refresh</button>
    </div>
    <div class="health-grid">
      ${items.map(item => buildHealthItem(item)).join('')}
    </div>
  `;
}

function renderAdapters(d) {
  const el = document.getElementById('adp-list');
  if (!el) return;
  const adapters = d.adapters || [];
  const countEl = document.getElementById('adp-count');
  if (countEl) countEl.textContent = adapters.length + ' adapters';
  if (!adapters.length) { el.innerHTML = '<div class="empty">No adapter data</div>'; return; }
  el.innerHTML = adapters.map(a => {
    const ok      = a.status === 'ok';
    const stale   = a.status === 'stale';
    const col     = ok ? 'var(--g)' : stale ? 'var(--a)' : 'var(--r)';
    const icon    = ok ? '\u2713' : stale ? '\u23f0' : '\u2717';
    const wrote0  = a.posts_fetched > 0 && a.posts_written === 0;
    const warnCol = wrote0 ? 'var(--a)' : 'var(--t3)';
    return '<div style="display:flex;align-items:center;gap:10px;padding:7px 12px;border-bottom:1px solid var(--b1);flex-wrap:wrap;">'
      + '<span style="font-size:11px;color:' + col + ';flex-shrink:0">' + icon + '</span>'
      + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:var(--t1);min-width:160px">' + a.adapter_id.replace('stocks.','') + '</span>'
      + '<span style="font-size:11px;color:var(--t2)">' + (a.posts_fetched||0) + ' fetched</span>'
      + '<span style="font-size:11px;color:' + warnCol + '">' + (a.posts_written||0) + ' wrote</span>'
      + (a.duration_s != null ? '<span style="font-size:10px;color:var(--t3);margin-left:auto">' + a.duration_s + 's</span>' : '')
      + (a.error ? '<div style="width:100%;font-size:10px;color:var(--r);margin-top:2px">' + a.error + '</div>' : '')
      + '</div>';
  }).join('');
}

function renderHitRate(d) {
  const el = document.getElementById('hr-grid');
  if (!el) return;
  const countEl = document.getElementById('hr-count');
  const logged   = d.signals_logged   || 0;
  const resolved = d.signals_resolved || 0;
  const windows  = d.windows || [];
  if (countEl) countEl.textContent = resolved + ' resolved';
  if (!resolved && !windows.length) {
    el.innerHTML = '<div style="padding:16px;font-size:12px;color:var(--t2);line-height:1.7">'
      + '<div style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--a);margin-bottom:8px">PENDING</div>'
      + '<div>Need <strong>30 resolved options trades</strong> to validate edge.</div>'
      + '<div style="margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--t3)">' + logged + ' signals logged &nbsp;&middot;&nbsp; ' + resolved + ' resolved</div>'
      + '<div style="margin-top:12px"><div style="background:var(--b1);border-radius:3px;height:6px"><div style="background:var(--a);border-radius:3px;height:100%;width:' + Math.min(100, Math.round(resolved/30*100)) + '%"></div></div>'
      + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:4px">' + resolved + ' / 30 minimum</div></div>'
      + '</div>';
    return;
  }
  el.innerHTML = windows.map(w => {
    const col  = (w.hit_rate_pct||0) >= 60 ? 'var(--g)' : (w.hit_rate_pct||0) >= 50 ? 'var(--a)' : 'var(--r)';
    const verd = (w.hit_rate_pct||0) >= 60 ? 'GO LIVE' : (w.hit_rate_pct||0) >= 55 ? 'CAUTIOUS' : (w.hit_rate_pct||0) >= 45 ? 'EXTEND' : 'STOP';
    return '<div style="padding:12px 16px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:12px">'
      + '<div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">' + w.window_days + 'D WINDOW</div>'
      + '<div style="font-family:var(--mono);font-size:20px;font-weight:800;color:' + col + '">' + (w.hit_rate_pct||0).toFixed(1) + '%</div>'
      + '<div style="font-size:10px;color:var(--t3)">' + (w.total_signals||0) + ' signals</div></div>'
      + '<div style="margin-left:auto;text-align:right"><div style="font-family:var(--mono);font-size:10px;font-weight:700;color:' + col + '">' + verd + '</div>'
      + '<div style="font-size:10px;color:var(--t3)">exp=' + ((w.expectancy||0)*100).toFixed(1) + '%</div></div>'
      + '</div>';
  }).join('');
}

function buildHealthItem(item) {
  const icon  = STATUS_ICON[item.status]  || '❓';
  const color = STATUS_COLOR[item.status] || 'var(--t3)';
  const borderColor = item.status === 'RED' ? 'rgba(248,113,113,0.3)'
    : item.status === 'YELLOW' ? 'rgba(251,191,36,0.3)'
    : item.status === 'GREEN'  ? 'rgba(52,211,153,0.15)'
    : 'var(--border)';
  const bg = item.status === 'RED'    ? 'rgba(248,113,113,0.05)'
    : item.status === 'YELLOW' ? 'rgba(251,191,36,0.04)'
    : 'transparent';

  return `
    <div class="health-item" style="
      display:flex;align-items:flex-start;gap:12px;
      padding:12px 16px;margin-bottom:8px;
      background:${bg};
      border:1px solid ${borderColor};
      border-radius:8px;
    ">
      <span style="font-size:16px;flex-shrink:0;margin-top:1px">${icon}</span>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
          <span style="font-size:12px;font-weight:700;color:var(--t1)">${item.name}</span>
          <span style="font-size:10px;font-weight:700;color:${color};letter-spacing:0.08em">${item.status}</span>
        </div>
        <div style="font-size:11px;color:var(--t2)">${item.value || ''}</div>
        ${item.detail ? `<div style="font-size:10px;color:var(--t3);margin-top:3px">${item.detail}</div>` : ''}
      </div>
    </div>
  `;
}
