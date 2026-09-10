/* ══ POSITIONS ══ */
async function loadPositions() {
  try {
    const d = await fj('/api/positions');

    document.getElementById('p-equity').textContent = d.equity != null ? '$'+Number(d.equity).toLocaleString('en-US',{maximumFractionDigits:0}) : '—';
    document.getElementById('p-cash').textContent   = d.cash   != null ? (d.cash<0?'-':'')+'$'+Math.abs(d.cash).toFixed(0) : '—';
    document.getElementById('p-bp').textContent     = d.buying_power != null ? '$'+Math.abs(d.buying_power).toFixed(0) : '—';

    const dot = document.getElementById('mkt-dot'), lbl = document.getElementById('mkt-label');
    if (d.market_open) {
      dot.style.cssText = 'background:var(--g);box-shadow:0 0 4px var(--g);';
      lbl.style.color = 'var(--g)'; lbl.textContent = 'Market OPEN';
    } else {
      dot.style.cssText = 'background:var(--t3);';
      lbl.style.color = 'var(--t3)'; lbl.textContent = 'Market CLOSED — last close prices';
    }

    // Group individual option legs by underlying ticker into spread cards
    const spreads = {};
    (d.positions || []).forEach(p => {
      const u = p.underlying || p.ticker;
      if (!spreads[u]) spreads[u] = { underlying: u, legs: [], conv: p };
      spreads[u].legs.push(p);
    });
    const spreadList = Object.values(spreads);
    const totalPL    = spreadList.reduce((s,sp) => s + sp.legs.reduce((a,l) => a+(l.unrealized_pl||0), 0), 0);

    document.getElementById('k-positions').textContent = spreadList.length || 0;
    const plEl = document.getElementById('k-pl');
    plEl.textContent = (totalPL >= 0 ? '+$' : '-$') + Math.abs(totalPL).toFixed(0);
    plEl.style.color = totalPL > 0 ? 'var(--g)' : totalPL < 0 ? 'var(--r)' : 'var(--t1)';
    document.getElementById('k-pl-sub').textContent = spreadList.length > 0 ? spreadList.length+' open' : 'no positions';

    const tplRow = document.getElementById('tpl-row'), tplVal = document.getElementById('tpl-val');
    if (spreadList.length > 0) {
      tplRow.style.display = 'flex';
      tplVal.textContent = fPL(totalPL);
      tplVal.style.color = totalPL > 0 ? 'var(--g)' : totalPL < 0 ? 'var(--r)' : 'var(--t1)';
    } else { tplRow.style.display = 'none'; }

    const el = document.getElementById('pos-list');
    if (d.error) { el.innerHTML = '<div class="empty">Error: '+d.error+'</div>'; return; }
    if (!spreadList.length) {
      el.innerHTML = '<div class="pos-empty"><div class="pe-icon">📊</div><div class="pe-text">No open positions<br>'+(d.market_open?'Market OPEN':'Market CLOSED')+'</div></div>';
      return;
    }
    el.innerHTML = spreadList.map(sp => _renderSpread(sp)).join('');
    el.querySelectorAll('.pos-expand-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const detail = btn.closest('.pos-card').querySelector('.pos-signal-detail');
        const isOpen = detail.style.display !== 'none';
        detail.style.display = isOpen ? 'none' : 'block';
        btn.textContent = isOpen ? 'WHY WE ENTERED ▼' : 'COLLAPSE ▲';
      });
    });
  } catch(e) { console.error('loadPositions', e); }
}

function _renderSpread(sp) {
  const p      = sp.conv;
  const legs   = sp.legs;
  const netPL  = legs.reduce((s,l) => s+(l.unrealized_pl||0), 0);
  const plC    = netPL > 0 ? 'var(--g)' : netPL < 0 ? 'var(--r)' : 'var(--t2)';
  const plSign = netPL >= 0 ? '+' : '';
  const struct = (p.structure_type || 'SPREAD').replace(/_/g,' ');

  const legRows = legs.map(l => {
    const isL    = l.side === 'long';
    const lCol   = isL ? 'var(--g)' : 'var(--r)';
    const lPL    = l.unrealized_pl || 0;
    const lPLCol = lPL >= 0 ? 'var(--g)' : 'var(--r)';
    const m      = l.ticker.match(/([A-Z]+)(\d{6})([CP])(\d{8})$/);
    const strike = m ? (parseInt(m[4])/1000).toFixed(0) : '?';
    const expiry = m ? '20'+m[2].slice(0,2)+'-'+m[2].slice(2,4)+'-'+m[2].slice(4,6) : '';
    const cp     = m && m[3]==='C' ? 'CALL' : 'PUT';
    return '<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--b0);font-family:var(--mono);font-size:11px;">'
      + '<span style="color:'+lCol+';font-weight:700;min-width:36px">'+(isL?'BUY':'SELL')+'</span>'
      + '<span style="color:var(--t1)">'+cp+' $'+strike+'</span>'
      + '<span style="color:var(--t3)">exp '+expiry+'</span>'
      + '<span style="color:var(--t3)">entry $'+(l.avg_entry||0).toFixed(2)+'</span>'
      + '<span style="color:var(--t2)">now $'+(l.current_price||0).toFixed(2)+'</span>'
      + '<span style="margin-left:auto;color:'+lPLCol+';font-weight:700">'+(lPL>=0?'+':'')+'$'+Math.abs(lPL).toFixed(0)+'</span>'
      + '</div>';
  }).join('');

  const score   = p.composite_score;
  const pillars = p.pillars_fired;
  const cat     = p.catalyst_type ? p.catalyst_type+(p.days_to_catalyst!=null?' · '+p.days_to_catalyst+'d':'') : 'none';
  const comps   = p.components || {};

  const compRows = Object.entries(comps).sort((a,b)=>b[1]-a[1]).map(function(kv) {
    var k = kv[0], v = kv[1];
    var col   = v >= 1.0 ? 'var(--g)' : v >= 0.5 ? 'var(--a)' : 'var(--t3)';
    var label = k.replace(/P(\d+[abc]?)_/i,'P$1 ').replace(/_/g,' ');
    return '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--b1)">'
      + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3);min-width:160px">'+label+'</span>'
      + '<div style="flex:1;height:5px;background:var(--b1);border-radius:3px"><div style="height:100%;width:'+(v*100)+'%;background:'+col+';border-radius:3px"></div></div>'
      + '<span style="font-family:var(--mono);font-size:11px;color:'+col+';font-weight:700;min-width:30px;text-align:right">'+v.toFixed(1)+'</span>'
      + '</div>';
  }).join('');

  const narrative = p.narrative
    ? '<div style="margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--t2);font-style:italic;line-height:1.5;padding:8px;background:var(--s3);border-radius:4px;border-left:2px solid var(--a)">'+p.narrative+'</div>'
    : '';

  const metaHtml = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px">'
    + _sigKpi('CONV SCORE', score ? score.toFixed(2) : '—', 'convergence score')
    + _sigKpi('PILLARS', pillars || '—', 'independent signals')
    + _sigKpi('CATALYST', cat, 'binary event')
    + '</div>';

  const catTag = p.catalyst_type
    ? '<span style="font-family:var(--mono);font-size:10px;color:var(--a);background:var(--ad);border:1px solid var(--ab);padding:2px 8px;border-radius:3px">'+p.catalyst_type+(p.days_to_catalyst!=null?' · '+p.days_to_catalyst+'d':'')+'</span>'
    : '';

  return '<div class="pos-card" style="background:var(--s2);border:1px solid var(--b1);border-radius:8px;margin-bottom:10px;overflow:hidden">'
    + '<div style="padding:12px 14px">'
    + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap">'
    + '<span style="font-family:var(--mono);font-size:18px;font-weight:800;color:var(--t1)">'+sp.underlying+'</span>'
    + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;padding:2px 10px;border-radius:3px;background:rgba(16,185,129,0.15);color:var(--g);border:1px solid var(--gd)">LONG</span>'
    + '<span style="font-family:var(--mono);font-size:11px;color:var(--b);background:var(--bd);border:1px solid var(--bb);padding:2px 8px;border-radius:3px">'+struct+'</span>'
    + catTag
    + '<span style="margin-left:auto;font-family:var(--mono);font-size:17px;font-weight:800;color:'+plC+'">'+plSign+'$'+Math.abs(netPL).toFixed(0)+'</span>'
    + '</div>'
    + '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:5px;padding:8px 10px;margin-bottom:10px">'+legRows+'</div>'
    + (p.entered_at ? '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-bottom:8px">Entered '+p.entered_at+(p.days_held != null ? ' &nbsp;·&nbsp; <span style="color:'+(p.days_held >= p.max_hold_days ? 'var(--r)' : p.days_held >= p.max_hold_days*0.7 ? 'var(--a)' : 'var(--t3)')+'">'+p.days_held+'d / '+p.max_hold_days+'d max</span>' : '')+'</div>' : '')
    + '<button class="pos-expand-btn" style="font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.1em;color:var(--a);background:transparent;border:1px solid var(--ad);padding:4px 10px;border-radius:3px;cursor:pointer">WHY WE ENTERED ▼</button>'
    + '</div>'
    + '<div class="pos-signal-detail" style="display:none;padding:0 14px 14px">'
    + '<div style="border-top:1px solid var(--b1);padding-top:12px">'
    + metaHtml + narrative
    + (compRows ? '<div style="margin-top:10px"><div style="font-family:var(--mono);font-size:9px;font-weight:700;color:var(--t3);letter-spacing:0.1em;margin-bottom:6px">PILLARS THAT FIRED</div>'+compRows+'</div>' : '')
    + '</div></div></div>';
}

function _posKpi(label, val) {
  return '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:4px;padding:6px 8px">'
    + '<div style="font-family:var(--mono);font-size:8px;font-weight:700;color:var(--t3);letter-spacing:0.1em">'+label+'</div>'
    + '<div style="font-family:var(--mono);font-size:12px;font-weight:700;color:var(--t1);margin-top:2px">'+val+'</div>'
    + '</div>';
}

function _sigKpi(label, val, sub) {
  return '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:4px;padding:6px 8px">'
    + '<div style="font-family:var(--mono);font-size:8px;font-weight:700;color:var(--t3);letter-spacing:0.1em">'+label+'</div>'
    + '<div style="font-family:var(--mono);font-size:13px;font-weight:800;color:var(--t1);margin-top:2px">'+val+'</div>'
    + '<div style="font-family:var(--mono);font-size:9px;color:var(--t3)">'+(sub||'')+'</div>'
    + '</div>';
}

function _miniBar(v) {
  var pct = Math.min(100, Math.abs(v) * 100);
  var col = v > 0 ? 'var(--g)' : 'var(--r)';
  return '<div style="flex:1;height:6px;background:var(--b1);border-radius:3px;overflow:hidden">'
    + '<div style="height:100%;width:'+pct+'%;background:'+col+';border-radius:3px"></div></div>';
}
