/* ══ JUMP TO TICKER — used by heatmap, universe, global tiles ══ */
function jumpToTicker(ticker) {
  showTickerDetail(ticker);
}

async function showTickerDetail(ticker) {
  const modalId = 'ticker-modal';
  document.getElementById(modalId)?.remove();
  const overlay = document.createElement('div');
  overlay.id = modalId;
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(6px);z-index:300;display:flex;align-items:center;justify-content:center;padding:20px;';
  overlay.innerHTML = '<div style="background:var(--s1);border:1px solid var(--b2);border-radius:12px;width:100%;max-width:720px;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--b1);background:var(--s2);flex-shrink:0;">'
    + '<div><div style="font-family:var(--mono);font-size:13px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;">' + ticker + ' \u00b7 Signal Detail</div>'
    + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:2px">Price, sentiment, options flow, signal history</div></div>'
    + '<button onclick="document.getElementById(\'' + modalId + '\').remove()" style="background:none;border:none;color:var(--t3);font-size:18px;cursor:pointer;padding:4px 8px;">&times;</button>'
    + '</div>'
    + '<div id="' + modalId + '-body" style="overflow-y:auto;flex:1;padding:0;"><div class="loading" style="padding:24px">Loading ' + ticker + '\u2026</div></div>'
    + '</div>';
  document.body.appendChild(overlay);

  try {
    const d    = await fj('/api/lookup/' + ticker);
    const body = document.getElementById(modalId + '-body');
    if (!body) return;
    if (d.error) { body.innerHTML = '<div class="empty" style="padding:24px">' + d.error + '</div>'; return; }

    const ps    = d.price_snapshot || {};
    const p5col = (ps.change_5d_pct||0) > 0 ? 'var(--g)' : (ps.change_5d_pct||0) < 0 ? 'var(--r)' : 'var(--t3)';
    const p1col = (ps.change_1d_pct||0) > 0 ? 'var(--g)' : (ps.change_1d_pct||0) < 0 ? 'var(--r)' : 'var(--t3)';

    // Price strip
    const priceHtml = '<div style="display:flex;gap:16px;padding:12px 18px;background:var(--s2);border-bottom:1px solid var(--b1);flex-wrap:wrap;">'
      + card3('Price', ps.price ? '$' + ps.price.toFixed(2) : '\u2014', 'Last close')
      + card3('1D', ps.change_1d_pct != null ? (ps.change_1d_pct>0?'+':'') + ps.change_1d_pct.toFixed(2)+'%' : '\u2014', 'vs yesterday', p1col)
      + card3('5D', ps.change_5d_pct != null ? (ps.change_5d_pct>0?'+':'') + ps.change_5d_pct.toFixed(2)+'%' : '\u2014', 'vs last week', p5col)
      + card3('vs SPY', ps.change_vs_spy != null ? (ps.change_vs_spy>0?'+':'') + ps.change_vs_spy.toFixed(2)+'%' : '\u2014', '5D excess return', (ps.change_vs_spy||0)>0?'var(--g)':(ps.change_vs_spy||0)<0?'var(--r)':'var(--t3)')
      + '</div>';

    // Sentiment
    const sentHtml = d.sentiment?.length
      ? '<div style="padding:10px 18px 4px;border-bottom:1px solid var(--b1);">'
        + '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:8px">Sentiment (24h)</div>'
        + '<div style="display:flex;gap:8px;flex-wrap:wrap;padding-bottom:10px">'
        + d.sentiment.map(s => {
            const col = (s.avg_polarity||0) > 0.05 ? 'var(--g)' : (s.avg_polarity||0) < -0.05 ? 'var(--r)' : 'var(--t2)';
            return '<div style="background:var(--s3);border:1px solid var(--b1);border-radius:5px;padding:7px 10px;min-width:140px;">'
              + '<div style="font-family:var(--mono);font-size:9px;color:var(--t3);margin-bottom:3px">' + s.source_class.replace(/_/g,' ').toUpperCase() + '</div>'
              + '<div style="font-family:var(--mono);font-size:14px;font-weight:700;color:' + col + '">' + (s.avg_polarity>0?'+':'') + s.avg_polarity.toFixed(3) + '</div>'
              + '<div style="font-size:10px;color:var(--t3)">' + s.count + ' posts</div>'
              + '</div>';
          }).join('')
        + '</div></div>'
      : '';

    // Options flow
    const flowHtml = d.options_flow?.length
      ? '<div style="padding:10px 18px 4px;border-bottom:1px solid var(--b1);">'
        + '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:8px">Options Flow (48h)</div>'
        + d.options_flow.map(f => {
            const isCall = f.contract_type === 'call';
            const col    = isCall ? 'var(--g)' : 'var(--r)';
            const prem   = f.premium ? '$' + (f.premium/1000).toFixed(0)+'k' : '\u2014';
            return '<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--b0);">'
              + '<span style="font-family:var(--mono);font-size:10px;font-weight:700;color:' + col + ';background:' + (isCall?'var(--gd)':'var(--rd)') + ';padding:2px 7px;border-radius:3px">' + f.contract_type.toUpperCase() + '</span>'
              + '<span style="font-size:12px;color:var(--t1);font-weight:500">' + prem + ' premium</span>'
              + '<span style="font-size:11px;color:var(--t3)">vol/OI ' + (f.volume_oi_ratio||0).toFixed(1) + '</span>'
              + '<span style="font-size:11px;color:var(--t3)">exp ' + (f.expiry||'\u2014') + '</span>'
              + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:' + ((f.unusual_score||0)>=80?'var(--r)':(f.unusual_score||0)>=50?'var(--a)':'var(--t3)') + ';margin-left:auto">' + (f.unusual_score||0) + '</span>'
              + '</div>';
          }).join('')
        + '</div></div>'
      : '';

    // Divergence history
    const divHtml = d.divergence_events?.length
      ? '<div style="padding:10px 18px 4px;">'
        + '<div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:8px">Signal History (7d)</div>'
        + d.divergence_events.map(e => {
            const dc = e.direction === 'LONG' ? 'dp-long' : e.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
            const dCol = (e.d_value||0) >= 4 ? 'var(--r)' : (e.d_value||0) >= 2 ? 'var(--a)' : 'var(--t3)';
            return '<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--b0);">'
              + '<span class="dir-pill ' + dc + '" style="font-size:9px">' + e.direction + '</span>'
              + '<span style="font-family:var(--mono);font-size:13px;font-weight:700;color:' + dCol + '">D ' + (e.d_value||0).toFixed(2) + '</span>'
              + '<span style="font-size:11px;color:var(--t3);margin-left:auto">' + (e.time_pt||'') + '</span>'
              + '</div>';
          }).join('')
        + '</div></div>'
      : '<div style="padding:14px 18px;font-size:12px;color:var(--t3)">No divergence signals in last 7 days</div>';

    body.innerHTML = priceHtml + sentHtml + flowHtml + divHtml;
  } catch(e) {
    const body = document.getElementById(modalId + '-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:24px">Error: ' + e.message + '</div>';
  }
}

function card3(label, val, sub, col) {
  return '<div style="flex:1;min-width:80px;">'
    + '<div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:3px">' + label + '</div>'
    + '<div style="font-family:var(--mono);font-size:16px;font-weight:700;color:' + (col||'var(--t1)') + '">' + val + '</div>'
    + '<div style="font-size:10px;color:var(--t3);margin-top:2px">' + (sub||'') + '</div>'
    + '</div>';
}

/* ══ HEATMAP ══ */
async function loadHeatmapData() {
  if (!hmData) hmData = await fj('/api/market-heatmap');
  return hmData;
}

async function renderHeatmap() {
  const el = document.getElementById('hm-wrap');
  try {
    const d    = await loadHeatmapData();
    const cats = ['US Stocks','Sectors','Commodities','International','Macro/Rates'];
    const total = cats.reduce((s,c) => s+(d.categories[c]||[]).length, 0);
    const ku = document.getElementById('k-universe');
    if (ku) ku.textContent = total;
    el.innerHTML = cats.map(cat => {
      const items = d.categories[cat]||[];
      const tiles = items.map(t => {
        const chg = t.change_5d_pct;
        return '<div class="hm-tile" style="background:' + hmColor(chg) + '" title="' + t.ticker + ': ' + (chg!=null?fP(chg):'--') + ' 5d" onclick="jumpToTicker(\'' + t.ticker + '\')">'
          + '<span class="hm-sym">' + t.ticker + '</span>'
          + '<span class="hm-chg" style="color:' + chgColor(chg) + '">' + (chg!=null?fP(chg):'--') + '</span>'
          + '</div>';
      }).join('');
      return '<div class="hm-section"><div class="hm-sec-label">' + cat + '</div><div class="hm-tiles">' + (tiles||'<div class="empty" style="padding:10px;font-size:10px">No data</div>') + '</div></div>';
    }).join('');
    buildHeatmapNarrative(d);
  } catch(e) { el.innerHTML = '<div class="empty">Error loading heatmap</div>'; }
}

/* ══ SECTORS ══ */
async function renderSectors() {
  const el = document.getElementById('sectors-grid');
  try {
    if (!secData) secData = await fj('/api/sectors');
    const d = secData;
    const sb = document.getElementById('sectors-badge');
    if (sb) sb.textContent = (d.sectors?.length||0)+' sectors';
    if (!d.sectors?.length) { el.innerHTML = '<div class="empty">No sector data</div>'; return; }
    el.innerHTML = d.sectors.map(s => {
      const chgC    = (s.change_5d_pct||0) > 0 ? 'var(--g)' : (s.change_5d_pct||0) < 0 ? 'var(--r)' : 'var(--t3)';
      const sentPct = s.sentiment_polarity != null ? Math.min(100, Math.max(0,(s.sentiment_polarity+1)/2*100)) : 50;
      const sentCol = (s.sentiment_polarity||0) > 0.05 ? 'var(--g)' : (s.sentiment_polarity||0) < -0.05 ? 'var(--r)' : 'var(--t3)';
      const badgeH  = s.has_alert ? '<span class="sc-d-badge">D' + (s.d_value||0).toFixed(1) + '</span>' : '';
      const lbl     = (s.label||s.ticker).replace(/'/g, "\\'");
      return '<div class="sc-card" style="cursor:pointer" onclick="showSectorDetail(\'' + s.ticker + '\',\'' + lbl + '\')">'
        + badgeH
        + '<div class="sc-name">' + (s.label||'') + '</div>'
        + '<div class="sc-ticker">' + s.ticker + '</div>'
        + '<div class="sc-price-row">'
        + '<span class="sc-price">' + (s.price ? '$'+s.price.toFixed(2) : '\u2014') + '</span>'
        + '<span class="sc-chg" style="color:' + chgC + '">' + (s.change_5d_pct!=null?fP(s.change_5d_pct):'\u2014') + '</span>'
        + '</div>'
        + '<div class="sc-meta">' + (s.constituent_count?s.constituent_count+' stocks':'') + ' ' + (s.coverage_pct?'('+s.coverage_pct+'% cov)':'') + '</div>'
        + '<div class="sc-sent-bar"><div class="sc-sent-fill" style="width:' + sentPct + '%;background:' + sentCol + '"></div></div>'
        + '</div>';
    }).join('');
    buildSectorsNarrative(d);
  } catch(e) { el.innerHTML = '<div class="empty">Error loading sectors</div>'; }
}

/* ══ UNIVERSE ══ */
async function renderUniverse() {
  const el = document.getElementById('uni-wrap');
  try {
    if (!uniData) uniData = await fj('/api/universe');
    const d       = uniData;
    const itemMap = {};
    (d.items||[]).forEach(i => itemMap[i.ticker] = i);
    const ku = document.getElementById('k-universe');
    if (ku) ku.textContent = d.count || d.items?.length || 0;

    let html = '<table class="uni-table"><thead><tr>'
      + '<th style="text-align:left;padding-left:12px">Ticker</th>'
      + '<th>Price</th><th>1D %</th><th>5D %</th><th>vs SPY</th>'
      + '<th>D-val</th><th>Signal</th><th>Sentiment</th>'
      + '</tr></thead><tbody>';

    for (const [cat, tickers] of Object.entries(UNIVERSE_CATS)) {
      const catItems = tickers.map(t => itemMap[t]).filter(Boolean);
      if (!catItems.length) continue;
      html += '<tr class="uni-cat-row"><td colspan="8" style="padding-left:12px">' + cat + '</td></tr>';
      html += catItems.map(item => {
        const c1 = item.change_1d_pct, c5 = item.change_5d_pct, vs = item.change_vs_spy;
        const dC = (item.d_value||0) >= 4 ? 'var(--r)' : (item.d_value||0) >= 2 ? 'var(--a)' : 'var(--t3)';
        const sigCell = item.has_alert
          ? '<span class="dir-pill ' + (item.direction==='LONG'?'dp-long':'dp-short') + '" style="font-size:9px">' + item.direction + '</span>'
          : '<span style="color:var(--t3)">\u2014</span>';
        const sentCell = item.sentiment != null
          ? '<span style="color:' + (item.sentiment>0.05?'var(--g)':item.sentiment<-0.05?'var(--r)':'var(--t3)') + '">' + (item.sentiment>0?'+':'') + item.sentiment.toFixed(3) + '</span>'
          : '<span style="color:var(--t3)">\u2014</span>';
        return '<tr style="cursor:pointer" onclick="jumpToTicker(\'' + item.ticker + '\')">'
          + '<td style="padding-left:12px">' + item.ticker + '</td>'
          + '<td>' + (item.price ? '$'+item.price.toFixed(2) : '\u2014') + '</td>'
          + '<td style="color:' + chgColor(c1) + '">' + (c1!=null?fP(c1):'\u2014') + '</td>'
          + '<td style="color:' + chgColor(c5) + '">' + (c5!=null?fP(c5):'\u2014') + '</td>'
          + '<td style="color:' + chgColor(vs) + '">' + (vs!=null?fP(vs):'\u2014') + '</td>'
          + '<td style="color:' + dC + '">' + ((item.d_value||0) > 0 ? item.d_value.toFixed(2) : '\u2014') + '</td>'
          + '<td>' + sigCell + '</td>'
          + '<td>' + sentCell + '</td>'
          + '</tr>';
      }).join('');
    }
    html += '</tbody></table>';
    el.innerHTML = html;
    buildUniverseNarrative(d);
  } catch(e) { el.innerHTML = '<div class="empty">Error loading universe</div>'; }
}

/* ══ GLOBAL ══ */
async function renderGlobal() {
  const el = document.getElementById('global-wrap');
  try {
    const d    = await loadHeatmapData();
    const intl  = d.categories['International']||[];
    const macro = d.categories['Macro/Rates']||[];
    const GLOBAL_FULL = {
      EEM:'Emerging Markets', EWJ:'Japan', FXI:'China Large-Cap', EWZ:'Brazil',
      EWG:'Germany', EWU:'UK', EWY:'South Korea', INDA:'India', MCHI:'MSCI China',
      TLT:'20yr US Treasuries', HYG:'High Yield Bonds', LQD:'Investment Grade Bonds',
      UUP:'US Dollar Index', UVXY:'VIX Short-Term', SVXY:'Inverse VIX',
    };
    const mkTiles = (items) => items.map(t => {
      const chg = t.change_5d_pct;
      const tip = GLOBAL_FULL[t.ticker] ? GLOBAL_FULL[t.ticker] + ' \u2014 ' + (chg!=null?fP(chg):'\u2014') + ' 5d' : t.ticker + ': ' + (chg!=null?fP(chg):'\u2014') + ' 5d';
      return '<div class="gt-tile" style="background:' + hmColor(chg) + '" title="' + tip + '" onclick="jumpToTicker(\'' + t.ticker + '\')">'
        + '<span class="gt-sym">' + t.ticker + '</span>'
        + '<span class="gt-label">' + (INTL_LABELS[t.ticker]||'') + '</span>'
        + '<span class="gt-chg" style="color:' + chgColor(chg) + '">' + (chg!=null?fP(chg):'\u2014') + '</span>'
        + '</div>';
    }).join('');
    el.innerHTML = '<div class="global-section">'
      + '<div class="global-sec-title">International ETFs</div>'
      + '<div class="panel-desc" style="padding:6px 0 10px;border:none;background:none">How major international markets are performing this week. Color = magnitude of 5-day move. Click any tile for detail.</div>'
      + '<div class="global-tiles">' + (mkTiles(intl)||'<div class="empty" style="font-size:11px">No data</div>') + '</div>'
      + '</div>'
      + '<div class="global-section">'
      + '<div class="global-sec-title">Macro / Rates</div>'
      + '<div class="panel-desc" style="padding:6px 0 10px;border:none;background:none">Bonds (TLT), dollar (UUP), volatility (UVXY), credit (HYG). These drive AlphaHound\'s RISK_ON/OFF verdict and trade sizing modifier.</div>'
      + '<div class="global-tiles">' + (mkTiles(macro)||'<div class="empty" style="font-size:11px">No data</div>') + '</div>'
      + '</div>';
    buildGlobalNarrative(d);
  } catch(e) { el.innerHTML = '<div class="empty">Error loading global data</div>'; }
}

/* ══ SECTOR DETAIL MODAL ══ */
window.showSectorDetail = async function(ticker, label) {
  const modalId = 'sector-modal';
  document.getElementById(modalId)?.remove();
  const overlay = document.createElement('div');
  overlay.id = modalId;
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(6px);z-index:300;display:flex;align-items:center;justify-content:center;padding:20px;';
  overlay.innerHTML = '<div style="background:var(--s1);border:1px solid var(--b2);border-radius:12px;width:100%;max-width:820px;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;">'
    + '<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--b1);background:var(--s2);flex-shrink:0;">'
    + '<div><div style="font-family:var(--mono);font-size:12px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase;">' + label + ' \u00b7 ' + ticker + '</div>'
    + '<div style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-top:2px">Constituent stocks \u00b7 price, sentiment, signal status</div></div>'
    + '<button onclick="document.getElementById(\'' + modalId + '\').remove()" style="background:none;border:none;color:var(--t3);font-size:18px;cursor:pointer;padding:4px 8px;">&times;</button>'
    + '</div>'
    + '<div id="' + modalId + '-body" style="overflow-y:auto;flex:1;padding:0;"><div class="loading" style="padding:24px">Loading constituents\u2026</div></div>'
    + '</div>';
  document.body.appendChild(overlay);
  try {
    const d    = await fj('/api/sector-detail/' + ticker);
    const body = document.getElementById(modalId + '-body');
    if (!d.constituents?.length) { body.innerHTML = '<div class="empty" style="padding:24px">No constituent data for ' + ticker + '</div>'; return; }
    const bullCount  = d.constituents.filter(c => (c.sentiment||0) > 0.05).length;
    const bearCount  = d.constituents.filter(c => (c.sentiment||0) < -0.05).length;
    const chgItems   = d.constituents.filter(c => c.change_5d_pct != null);
    const avgChg     = chgItems.length ? chgItems.reduce((s,c) => s + c.change_5d_pct, 0) / chgItems.length : 0;
    const summaryCol = avgChg > 0 ? 'var(--g)' : avgChg < 0 ? 'var(--r)' : 'var(--t3)';
    const rows = d.constituents.map(c => {
      const c5   = c.change_5d_pct;
      const col5 = (c5||0) > 0 ? 'var(--g)' : (c5||0) < 0 ? 'var(--r)' : 'var(--t3)';
      const sent = c.sentiment || 0;
      const sCol = sent > 0.05 ? 'var(--g)' : sent < -0.05 ? 'var(--r)' : 'var(--t3)';
      const dir  = c.direction === 'LONG' || c.direction === 'SHORT' ? c.direction : null;
      const sig  = c.has_alert && dir ? '<span class="dir-pill ' + (dir==='LONG'?'dp-long':'dp-short') + '" style="font-size:9px">' + dir + '</span>' : '<span style="color:var(--t3);font-size:11px">\u2014</span>';
      const sentPct = Math.min(100,Math.max(0,(sent+1)/2*100));
      const sentBar = '<div style="width:50px;height:4px;background:var(--b1);border-radius:2px;display:inline-block;vertical-align:middle;margin-left:6px"><div style="height:100%;width:' + sentPct + '%;background:' + sCol + ';border-radius:2px"></div></div>';
      return '<div style="display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid var(--b1);cursor:pointer" onclick="document.getElementById(\'' + modalId + '\').remove();jumpToTicker(\'' + c.ticker + '\')">'
        + '<span style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--t1);min-width:52px">' + c.ticker + '</span>'
        + '<span style="font-family:var(--mono);font-size:13px;color:var(--t2);min-width:80px">' + (c.price ? '$'+c.price.toFixed(2) : '\u2014') + '</span>'
        + '<span style="font-family:var(--mono);font-size:12px;font-weight:700;color:' + col5 + ';min-width:64px">' + (c5 != null ? (c5>0?'+':'')+c5.toFixed(2)+'%' : '\u2014') + '</span>'
        + '<span style="font-size:12px;color:' + sCol + '">' + (sent !== 0 ? (sent>0?'+':'')+sent.toFixed(3) : '0.000') + ' sentiment' + sentBar + '</span>'
        + '<span style="margin-left:auto;display:flex;align-items:center;gap:8px">' + sig + ((c.d_value||0) > 0 ? '<span style="font-family:var(--mono);font-size:11px;color:var(--a)">D' + c.d_value.toFixed(1) + '</span>' : '') + '</span>'
        + '</div>';
    }).join('');
    body.innerHTML = '<div style="display:flex;gap:20px;padding:12px 18px;background:var(--s2);border-bottom:1px solid var(--b1);flex-wrap:wrap;">'
      + '<div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:3px">AVG 5D RETURN</div><div style="font-family:var(--mono);font-size:16px;font-weight:700;color:' + summaryCol + '">' + (avgChg>0?'+':'') + avgChg.toFixed(2) + '%</div></div>'
      + '<div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:3px">NET BULLISH</div><div style="font-family:var(--mono);font-size:16px;font-weight:700;color:var(--g)">' + bullCount + '</div></div>'
      + '<div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:3px">NET BEARISH</div><div style="font-family:var(--mono);font-size:16px;font-weight:700;color:var(--r)">' + bearCount + '</div></div>'
      + '<div><div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:3px">STOCKS</div><div style="font-family:var(--mono);font-size:16px;font-weight:700;color:var(--t1)">' + d.count + '</div></div>'
      + '</div>' + rows;
  } catch(e) {
    const body = document.getElementById(modalId + '-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:24px">Error: ' + e.message + '</div>';
  }
};
