/* ══ OPTIONS FLOW — Unusual Whales ══
   Every row is clickable and expands to full detail.
   Plain-English explanations for every field.
*/
async function loadFlow() {
  try {
    const d = await fj('/api/options-flow');
    const countEl = document.getElementById('flow-count');
    if (countEl) countEl.textContent = (d.count || 0) + ' unusual sweeps';
    const el = document.getElementById('flow-list');
    if (!el) return;
    if (!d.flow?.length) {
      el.innerHTML = '<div class="empty">No unusual options activity in last 48h</div>';
      return;
    }

    // Summary bar
    const calls   = d.flow.filter(f => f.contract_type === 'call').length;
    const puts    = d.flow.filter(f => f.contract_type === 'put').length;
    const totalPrem = d.flow.reduce((s, f) => s + (f.premium || 0), 0);
    const bullish = calls > puts;
    const bias    = calls === puts ? 'MIXED' : bullish ? 'CALL DOMINANT' : 'PUT DOMINANT';
    const biasCol = calls === puts ? 'var(--a)' : bullish ? 'var(--g)' : 'var(--r)';

    const summaryHtml = `
      <div style="display:flex;align-items:center;gap:16px;padding:12px 16px;background:var(--s2);border-bottom:1px solid var(--b1);flex-wrap:wrap;">
        <div>
          <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">MARKET BIAS</div>
          <div style="font-family:var(--mono);font-size:14px;font-weight:800;color:${biasCol}">${bias}</div>
        </div>
        <div>
          <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">CALLS</div>
          <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--g)">${calls}</div>
        </div>
        <div>
          <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">PUTS</div>
          <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--r)">${puts}</div>
        </div>
        <div>
          <div style="font-family:var(--mono);font-size:9px;color:var(--t3);letter-spacing:0.1em;margin-bottom:2px">TOTAL PREMIUM</div>
          <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--t1)">$${(totalPrem/1000).toFixed(0)}k</div>
        </div>
        <div style="margin-left:auto;font-size:11px;color:var(--t3);max-width:280px;line-height:1.5">
          ${bullish ? 'More call buying than puts — institutions positioning for upside across the market.' : calls === puts ? 'Equal call/put activity — mixed signals, no clear directional bias.' : 'More put buying than calls — institutions hedging or positioning for downside.'}
        </div>
      </div>`;

    el.innerHTML = summaryHtml + d.flow.map((f, i) => buildFlowRow(f, i)).join('');
  } catch(e) { console.error('loadFlow', e); }
}

function buildFlowRow(f, idx) {
  const isCall    = f.contract_type === 'call';
  const typeCol   = isCall ? 'var(--g)' : 'var(--r)';
  const typeBg    = isCall ? 'var(--gd)' : 'var(--rd)';
  const typeBd    = isCall ? 'var(--gb)' : 'var(--rb)';
  const score     = f.unusual_score || 0;
  const scoreCol  = score >= 80 ? 'var(--r)' : score >= 50 ? 'var(--a)' : 'var(--t2)';
  const prem      = f.premium ? '$' + (f.premium >= 1000000 ? (f.premium/1000000).toFixed(1)+'M' : (f.premium/1000).toFixed(0)+'k') : '—';
  const volOI     = f.volume_oi_ratio ? f.volume_oi_ratio.toFixed(2) : '—';
  const expiry    = f.expiry || '—';
  const daysToExp = f.expiry ? Math.round((new Date(f.expiry) - new Date().setHours(0,0,0,0)) / 86400000) : null;
  const expStr    = daysToExp != null ? expiry + ' (' + daysToExp + 'd)' : expiry;

  // What this sweep means in plain English
  const volOINum = f.volume_oi_ratio || 0;
  let volOIExplain = '';
  if      (volOINum > 100) volOIExplain = 'Extremely unusual — volume is ' + volOINum.toFixed(0) + 'x open interest. Someone made a very large, aggressive bet.';
  else if (volOINum > 20)  volOIExplain = 'Very unusual — volume is ' + volOINum.toFixed(0) + 'x open interest. Large directional bet, likely institutional.';
  else if (volOINum > 5)   volOIExplain = 'Notable — volume is ' + volOINum.toFixed(0) + 'x open interest. Above-average positioning activity.';
  else                     volOIExplain = 'Moderate activity — vol/OI ratio of ' + volOINum.toFixed(1) + '.';

  const scoreExplain = score >= 80
    ? 'Score ' + score + '/100 — maximum unusualness. This is in the top tier of all sweeps tracked by Unusual Whales.'
    : score >= 50
    ? 'Score ' + score + '/100 — highly unusual sweep worth watching.'
    : 'Score ' + score + '/100 — elevated but not extreme activity.';

  const direction = isCall ? 'BULLISH — buyer expects ' + f.ticker + ' price to go UP' : 'BEARISH — buyer expects ' + f.ticker + ' price to go DOWN';
  const dirCol    = isCall ? 'var(--g)' : 'var(--r)';

  return `<div class="flow-row" id="flow-${idx}" style="border-bottom:1px solid var(--b1);cursor:pointer;" onclick="toggleFlowDetail(${idx})">
    <!-- Collapsed row -->
    <div style="display:flex;align-items:center;gap:10px;padding:11px 16px;">
      <span style="font-family:var(--mono);font-size:15px;font-weight:700;color:var(--t1);min-width:52px">${f.ticker}</span>
      <span style="font-family:var(--mono);font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;background:${typeBg};color:${typeCol};border:1px solid ${typeBd}">${f.contract_type.toUpperCase()}</span>
      <span style="font-family:var(--mono);font-size:14px;font-weight:700;color:var(--t1)">${prem}</span>
      <span style="font-size:12px;color:var(--t3)">vol/OI ${volOI}</span>
      <span style="font-size:11px;color:var(--t3)">exp ${expStr}</span>
      <span style="margin-left:auto;font-family:var(--mono);font-size:12px;font-weight:700;color:${scoreCol}">${score}</span>
    </div>
    <!-- Expanded detail -->
    <div id="flow-detail-${idx}" style="display:none;padding:0 16px 14px;">
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:12px;">
        ${flowCard('What this is', (f.contract_type==='call'?'CALL option':'PUT option') + ' on ' + f.ticker, 'A ' + (isCall?'call':'put') + ' option gives the buyer the right to ' + (isCall?'buy':'sell') + ' ' + f.ticker + ' at a specific price before expiry.')}
        ${flowCard('Direction signal', direction, 'Based on ' + (isCall?'call':'put') + ' buying. ' + (isCall?'Bullish bets increase when institutions expect upward price movement.':'Bearish bets increase when institutions expect downward price movement or are hedging.'))}
        ${flowCard('Premium paid', prem, 'Total dollar value of the options contracts purchased. Larger premiums = higher conviction bet.')}
        ${flowCard('Vol/OI ratio', volOI, volOIExplain)}
        ${flowCard('Expiry', expStr, 'The contracts expire on this date. ' + (daysToExp != null && daysToExp <= 7 ? 'Very short-dated — aggressive near-term bet.' : daysToExp != null && daysToExp <= 30 ? 'Short-dated — positioned for a move within the next month.' : 'Medium-dated — positioned for a move over coming weeks.'))}
        ${flowCard('Unusual score', score + '/100', scoreExplain)}
      </div>
      <div style="padding:10px 12px;background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.15);border-left:2px solid var(--p);border-radius:5px;font-size:12px;color:var(--t2);line-height:1.6">
        <strong style="color:var(--t1)">Plain English:</strong> Someone paid ${prem} to open a ${f.contract_type.toUpperCase()} position on ${f.ticker} expiring ${expStr}. The vol/OI ratio of ${volOI} means trading volume was ${volOINum.toFixed(0)}x the existing open interest — strongly suggesting this was a new, aggressive position rather than routine hedging. This is <span style="color:${dirCol};font-weight:600">${direction.split('—')[0].trim()}</span>.
      </div>
    </div>
  </div>`;
}

function flowCard(label, val, explain) {
  return `<div style="background:var(--s3);border:1px solid var(--b1);border-radius:6px;padding:10px 12px;">
    <div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:4px">${label}</div>
    <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--t1);margin-bottom:4px">${val}</div>
    <div style="font-size:11px;color:var(--t3);line-height:1.4">${explain}</div>
  </div>`;
}

function toggleFlowDetail(idx) {
  const el = document.getElementById('flow-detail-' + idx);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}
