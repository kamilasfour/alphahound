/* ══ HISTORY ══ */
async function loadHistory() {
  try {
    const days = document.getElementById('h-days').value;
    const d    = await fj('/api/alerts/history?days_back='+days+'&limit=200');
    document.getElementById('h-count').textContent = (d.count||d.alerts?.length||0)+' alerts';
    const el = document.getElementById('hist-list');
    if (!d.alerts?.length) { el.innerHTML = '<div class="empty">No alerts in this period</div>'; return; }
    el.innerHTML = d.alerts.map(a => {
      const dc = a.direction==='LONG'?'dp-long':a.direction==='SHORT'?'dp-short':'dp-watch';
      const dC = a.d_value >= 5 ? 'var(--r)' : a.d_value >= 3.5 ? 'var(--a)' : 'var(--t2)';
      return `<div class="h-row" onclick="jumpToTicker('${a.ticker}')">
        <span class="h-ticker">${a.ticker}</span>
        <span class="dir-pill ${dc}" style="font-size:9px">${a.direction}</span>
        <span class="h-d" style="color:${dC}">${a.d_value.toFixed(2)}</span>
        <span class="h-time">${fShort(a.time)}</span>
        <span class="h-narr">${a.narrative ? a.narrative.slice(0,68)+'…' : '—'}</span>
      </div>`;
    }).join('');
  } catch(e) { console.error('loadHistory', e); }
}

function jumpToTicker(ticker) {
  showView('history');
  document.getElementById('td-search').value = ticker;
  loadTickerDetail();
}

/* ══ BY TICKER ══ */
async function loadTickerDetail() {
  const ticker = (document.getElementById('td-search').value||'').trim().toUpperCase();
  const el     = document.getElementById('ticker-detail');
  if (!ticker) { el.innerHTML = '<div class="empty">Enter a ticker above</div>'; return; }
  el.innerHTML = '<div class="loading">LOADING…</div>';
  try {
    const d = await fj('/api/ticker/'+ticker+'/history?days_back=30');
    if (!d.points?.length) { el.innerHTML = '<div class="empty">No signal history for '+ticker+'</div>'; return; }
    const maxD = Math.max(...d.points.map(p => p.d_value), 0.1);
    const bars = d.points.map((p, i) => {
      const h   = Math.round((p.d_value / maxD) * 46);
      const col = p.direction==='LONG'?'var(--g)':p.direction==='SHORT'?'var(--r)':'var(--a)';
      const lft = (i / (d.points.length||1)) * 100;
      const w   = Math.max(3, 100/(d.points.length||1) * 0.75);
      return `<div class="td-bar" style="left:${lft}%;width:${w}%;height:${h}px;background:${col}"></div>`;
    }).join('');
    const rows = d.points.slice().reverse().map(p => {
      const dC    = p.d_value >= 5 ? 'var(--r)' : p.d_value >= 3.5 ? 'var(--a)' : 'var(--t2)';
      const comps = Object.entries(p.components||{}).map(([k,v]) => `${k.replace(/_/g,' ')} ${v>0?'+':''}${v.toFixed(2)}`).join(' · ');
      return `<div class="td-row"><span class="td-time">${fDate(p.time)}</span><span class="td-d" style="color:${dC}">${p.d_value.toFixed(2)}</span><span class="td-narr">${comps||'—'}</span></div>`;
    }).join('');
    el.innerHTML = `<div style="padding:12px">
      <div class="td-hdr"><span class="td-ticker">${ticker}</span><span class="td-count">${d.count} alerts / 30d</span></div>
      <div class="td-chart">${bars}</div>
      <div>${rows}</div>
    </div>`;
  } catch(e) { el.innerHTML = '<div class="empty">Error loading ticker history</div>'; }
}
