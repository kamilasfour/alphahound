/* ══ TRADE LOG — Options trades + Signal History (Sprint 12) ══ */

async function loadTradeLog() {
  await loadOptionsTab();
}

/* ── Tab switching ── */
function switchTradeTab(tab) {
  ['opts','hist'].forEach(function(t) {
    var btn = document.getElementById('tt-' + t);
    var pnl = document.getElementById('tp-' + t);
    if (btn) btn.classList.toggle('tt-active', t === tab);
    if (pnl) pnl.style.display = t === tab ? 'flex' : 'none';
  });
  if (tab === 'opts') loadOptionsTab();
  if (tab === 'hist') loadHistoryTab();
}

/* ── Options trades tab ── */
async function loadOptionsTab() {
  try {
    const d = await fj('/api/options-trades');

    const pl  = d.total_pnl || 0;
    const tot = document.getElementById('tl-total');
    if (tot) {
      tot.textContent = (pl >= 0 ? '+$' : '-$') + Math.abs(pl).toFixed(0);
      tot.style.color = pl > 0 ? 'var(--g)' : pl < 0 ? 'var(--r)' : 'var(--t1)';
    }
    const setStat = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    setStat('tl-wins',   d.wins   || 0);
    setStat('tl-losses', d.losses || 0);
    setStat('tl-open',   d.open   || 0);

    const badge = document.getElementById('tradelog-badge');
    if (badge) badge.textContent = (d.count || 0) + ' options trades';

    const el = document.getElementById('tl-opts-list');
    if (!el) return;

    if (!d.trades || d.trades.length === 0) {
      el.innerHTML = '<div class="empty" style="padding:32px 16px">'
        + '<div style="font-size:28px;margin-bottom:10px;opacity:0.2">&#9135;</div>'
        + '<div style="font-family:var(--mono);font-size:12px;color:var(--t3)">No options trades placed yet</div>'
        + '<div style="font-size:12px;color:var(--t3);margin-top:6px">Trades appear here when the engine executes during market hours</div>'
        + '</div>';
      return;
    }

    const structNames = {
      BULL_CALL_SPREAD:'Bull Call Spread', BEAR_PUT_SPREAD:'Bear Put Spread',
      LONG_STRANGLE:'Long Strangle', LONG_CALL:'Long Call', LONG_PUT:'Long Put',
    };

    el.innerHTML = d.trades.map(function(t) {
      const dirClass   = t.direction === 'LONG' ? 'dp-long' : t.direction === 'SHORT' ? 'dp-short' : 'dp-watch';
      const structName = structNames[t.structure_type] || (t.structure_type||'').replace(/_/g,' ');
      var stBg, stColor, stLabel;
      if      (t.status === 'closed' && t.pnl > 0)  { stBg='var(--gd)'; stColor='var(--g)'; stLabel='WIN'; }
      else if (t.status === 'closed' && t.pnl <= 0)  { stBg='var(--rd)'; stColor='var(--r)'; stLabel='LOSS'; }
      else if (t.status === 'placed')                 { stBg='var(--bd)'; stColor='var(--b)'; stLabel='OPEN'; }
      else if (t.status === 'dry_run')                { stBg='var(--pd)'; stColor='var(--p)'; stLabel='DRY RUN'; }
      else                                            { stBg='var(--s3)'; stColor='var(--t3)'; stLabel=t.status||'—'; }
      var plStr='—', plColor='var(--t3)';
      if (t.pnl != null) {
        plColor = t.pnl > 0 ? 'var(--g)' : t.pnl < 0 ? 'var(--r)' : 'var(--t3)';
        plStr   = (t.pnl >= 0 ? '+$' : '-$') + Math.abs(t.pnl).toFixed(0);
      }
      var catStr = '';
      if (t.catalyst_type && t.catalyst_date) {
        var days = Math.round((new Date(t.catalyst_date) - new Date().setHours(0,0,0,0)) / 86400000);
        catStr = t.catalyst_type + ' ' + (days >= 0 ? days + 'd' : 'passed');
      }
      return '<div class="tl-row" style="display:flex;align-items:center;gap:10px;padding:11px 16px;border-bottom:1px solid var(--b1);flex-wrap:wrap;">'
        + '<span style="font-family:var(--mono);font-size:15px;font-weight:700;color:var(--t1);min-width:52px">' + t.ticker + '</span>'
        + '<span class="dir-pill ' + dirClass + '" style="font-size:9px">' + t.direction + '</span>'
        + '<span style="font-family:var(--mono);font-size:11px;color:var(--t2)">' + structName + '</span>'
        + (catStr ? '<span style="font-family:var(--mono);font-size:10px;color:var(--a);background:var(--ad);border:1px solid var(--ab);padding:2px 7px;border-radius:3px">' + catStr + '</span>' : '')
        + '<span style="font-family:var(--mono);font-size:11px;color:var(--t3)">' + (t.contracts||1) + ' contract' + ((t.contracts||1) !== 1 ? 's' : '') + '</span>'
        + '<span style="font-family:var(--mono);font-size:11px;color:var(--t2)">~$' + (t.estimated_debit||0).toFixed(0) + ' debit</span>'
        + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-left:auto">' + (t.time_et||'') + '</span>'
        + '<span style="font-family:var(--mono);font-size:11px;font-weight:700;color:' + plColor + '">' + plStr + '</span>'
        + '<span style="font-family:var(--mono);font-size:10px;font-weight:700;background:' + stBg + ';color:' + stColor + ';padding:2px 8px;border-radius:3px">' + stLabel + '</span>'
        + '</div>';
    }).join('');
  } catch(e) {
    console.error('loadOptionsTab', e);
  }
}

/* ── Signal history tab (convergence signals) ── */
async function loadHistoryTab() {
  const days = (document.getElementById('h-days-tl') || {}).value || 7;
  const el   = document.getElementById('tl-hist-list');
  if (!el) return;
  el.innerHTML = '<div class="loading">Loading signal history…</div>';
  try {
    const d = await fj('/api/convergence/history?days_back=' + days);
    const signals = d.signals || [];
    if (!signals.length) {
      el.innerHTML = '<div class="empty">No convergence signals in this period</div>';
      return;
    }
    el.innerHTML = signals.map(function(s) {
      const dirClass = s.direction==='LONG'?'dp-long':s.direction==='SHORT'?'dp-short':'dp-watch';
      const sc       = s.composite_score >= 4.0 ? 'var(--g)' : s.composite_score >= 3.0 ? 'var(--a)' : 'var(--t2)';
      const superTag = s.super_signal
        ? '<span style="font-family:var(--mono);font-size:9px;background:rgba(0,229,160,0.15);color:var(--g);border:1px solid rgba(0,229,160,0.3);padding:1px 6px;border-radius:3px">SUPER</span>'
        : '';
      const catStr = s.catalyst_type ? s.catalyst_type + (s.catalyst_date ? ' \u00b7 ' + s.days_to_catalyst + 'd' : '') : '';
      return '<div style="display:flex;align-items:center;gap:8px;padding:9px 16px;border-bottom:1px solid var(--b1);flex-wrap:wrap;">'
        + '<span style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--t1);min-width:52px">' + s.ticker + '</span>'
        + '<span class="dir-pill ' + dirClass + '" style="font-size:9px">' + s.direction + '</span>'
        + superTag
        + (catStr ? '<span style="font-family:var(--mono);font-size:10px;color:var(--a)">' + catStr + '</span>' : '')
        + '<span style="font-family:var(--mono);font-size:12px;font-weight:700;color:' + sc + ';margin-left:4px">' + s.composite_score.toFixed(2) + '</span>'
        + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3)">' + s.pillars_fired + ' pillars</span>'
        + '<span style="font-family:var(--mono);font-size:10px;color:var(--t3);margin-left:auto">' + (s.time_et||'') + '</span>'
        + '</div>';
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="empty">Error loading history</div>';
  }
}

/* ── Keep loadHistory for backward compat (called by loadAll) ── */
async function loadHistory() {
  // no-op: history is now embedded in the trades view
}
