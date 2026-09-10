/* ══ CONGRESS ══ */
async function loadCongress() {
  try {
    const d = await fj('/api/congress');
    const countEl = document.getElementById('cong-count');
    if (countEl) countEl.textContent = d.count || d.trades?.length || 0;
    const el = document.getElementById('cong-list');
    if (!el) return;
    if (!d.trades?.length) {
      el.innerHTML = '<div class="empty">No recent congressional trades</div>';
      return;
    }
    el.innerHTML = d.trades.map(t => {
      const buy    = (t.transaction || '').toLowerCase().includes('purchase');
      const txnCol = buy ? 'var(--g)' : 'var(--r)';
      const txnBg  = buy ? 'var(--gd)' : 'var(--rd)';
      const txnBd  = buy ? 'var(--gb)' : 'var(--rb)';
      const pc     = t.party === 'R' ? 'party-r' : t.party === 'D' ? 'party-d' : '';
      const house  = t.house ? ' · ' + t.house : '';

      // Performance stats
      const hasPerfData = t.price_change != null;
      const perfHtml = hasPerfData ? `
        <div style="display:flex;gap:16px;margin-top:8px;padding:8px 10px;background:var(--bg3);border:1px solid var(--border);border-radius:5px;flex-wrap:wrap;">
          <div>
            <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">TICKER SINCE TRADE</div>
            <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:${(t.price_change||0)>=0?'var(--g)':'var(--r)'}">${(t.price_change||0)>=0?'+':''}${t.price_change}%</div>
          </div>
          <div>
            <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">SPY SINCE TRADE</div>
            <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--t2)">${(t.spy_change||0)>=0?'+':''}${t.spy_change}%</div>
          </div>
          <div>
            <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">EXCESS RETURN</div>
            <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:${(t.excess_return||0)>=0?'var(--g)':'var(--r)'}">${(t.excess_return||0)>=0?'+':''}${t.excess_return}%</div>
          </div>
        </div>` : '';

      const descHtml = t.description
        ? `<div style="font-size:11px;color:var(--t3);margin-top:4px;font-style:italic">${t.description}</div>`
        : '';

      const reportHtml = t.report_date && t.report_date !== t.date
        ? `<span style="font-family:var(--mono);font-size:10px;color:var(--t3)"> · filed ${t.report_date}</span>`
        : '';

      return `<div class="cong-row" style="padding:14px 16px;border-bottom:1px solid var(--b1);">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
          <span style="font-family:var(--mono);font-size:20px;font-weight:700;color:var(--t1)">${t.ticker}</span>
          <span style="font-family:var(--mono);font-size:10px;font-weight:700;padding:3px 10px;border-radius:4px;background:${txnBg};color:${txnCol};border:1px solid ${txnBd}">${(t.transaction||'UNKNOWN').toUpperCase()}</span>
          <span style="font-size:13px;color:var(--t2)">${t.amount}</span>
          <span style="font-size:11px;color:var(--t3)">${t.ticker_type || ''}</span>
          <span style="margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--t3)">${t.date}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <span style="font-size:13px;color:var(--t1);font-weight:500">${t.representative}</span>
          <span class="${pc}" style="font-family:var(--mono);font-size:10px">${t.party ? '(' + t.party + ')' : ''}</span>
          <span style="font-size:11px;color:var(--t3)">${house}</span>
          ${reportHtml}
        </div>
        ${descHtml}
        ${perfHtml}
      </div>`;
    }).join('');
  } catch(e) { console.error('loadCongress', e); }
}
