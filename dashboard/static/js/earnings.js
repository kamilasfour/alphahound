/* ══ EARNINGS / CATALYST CALENDAR ══ */
async function loadEarnings() {
  try {
    const [earn, conv] = await Promise.all([
      fj('/api/earnings'),
      fj('/api/convergence').catch(() => ({ super_signals: [], watching: [] })),
    ]);

    const countEl = document.getElementById('earn-count');
    if (countEl) countEl.textContent = (earn.count || 0) + ' catalysts';
    const el = document.getElementById('earn-list');
    if (!el) return;
    if (!earn.earnings?.length) {
      el.innerHTML = '<div class="empty">No earnings in next 60 days</div>';
      return;
    }

    // Build a set of tickers that have active signals
    const superTickers = new Set((conv.super_signals || []).map(s => s.ticker));
    const watchTickers = new Set((conv.watching || []).map(s => s.ticker));

    // Group by week
    const today = new Date(); today.setHours(0,0,0,0);
    const groups = {};
    earn.earnings.forEach(e => {
      const days = e.days_until;
      const week = days <= 0 ? 'Today / Past' : days <= 7 ? 'This Week' : days <= 14 ? 'Next Week' : days <= 30 ? 'This Month' : 'Beyond 30 Days';
      if (!groups[week]) groups[week] = [];
      groups[week].push(e);
    });

    const weekOrder = ['Today / Past', 'This Week', 'Next Week', 'This Month', 'Beyond 30 Days'];
    let html = '';
    weekOrder.forEach(week => {
      if (!groups[week]?.length) return;
      html += `<div style="padding:7px 16px;background:var(--s2);border-bottom:1px solid var(--b1);border-top:1px solid var(--b1);font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--t3)">${week}</div>`;
      html += groups[week].map((e, i) => buildEarningsRow(e, superTickers, watchTickers, week + i)).join('');
    });
    el.innerHTML = html;
  } catch(err) { console.error('loadEarnings', err); }
}

function buildEarningsRow(e, superTickers, watchTickers, uid) {
  const days       = e.days_until;
  const isSuper    = superTickers.has(e.ticker);
  const isWatching = watchTickers.has(e.ticker);
  const daysCol    = days <= 3 ? 'var(--r)' : days <= 7 ? 'var(--a)' : 'var(--t2)';
  const daysStr    = days === 0 ? 'TODAY' : days < 0 ? Math.abs(days) + 'd ago' : days + 'd';

  const signalTag = isSuper
    ? '<span style="font-family:var(--mono);font-size:9px;font-weight:800;padding:2px 8px;border-radius:3px;background:rgba(0,229,160,0.15);color:var(--g);border:1px solid rgba(0,229,160,0.3)">🚨 SUPER SIGNAL</span>'
    : isWatching
    ? '<span style="font-family:var(--mono);font-size:9px;padding:2px 8px;border-radius:3px;background:var(--ad);color:var(--a);border:1px solid var(--ab)">DEVELOPING</span>'
    : '';

  const epsStr    = e.estimate_eps != null ? '$' + e.estimate_eps.toFixed(2) : '—';
  const actualStr = e.actual_eps  != null ? '$' + e.actual_eps.toFixed(2)  : '—';
  const beatStr   = e.beat === true ? '✅ BEAT' : e.beat === false ? '❌ MISSED' : '';
  const beatCol   = e.beat === true ? 'var(--g)' : e.beat === false ? 'var(--r)' : 'var(--t3)';

  // Options sweet spot indicator
  const sweetSpot = days >= 14 && days <= 45;
  const sweetTag  = sweetSpot
    ? '<span style="font-family:var(--mono);font-size:9px;padding:2px 7px;border-radius:3px;background:var(--bd);color:var(--b);border:1px solid var(--bb)">OPTIONS SWEET SPOT</span>'
    : '';

  return `<div style="border-bottom:1px solid var(--b1);cursor:pointer;" onclick="toggleEarnDetail('${uid}')">
    <!-- Collapsed -->
    <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;flex-wrap:wrap;">
      <span style="font-family:var(--mono);font-size:16px;font-weight:700;color:var(--t1);min-width:52px">${e.ticker}</span>
      <span style="font-size:12px;color:var(--t2)">${e.earnings_date}</span>
      <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:${daysCol}">${daysStr}</span>
      <span style="font-size:11px;color:var(--t3)">${e.fiscal_quarter || ''}</span>
      ${signalTag}
      ${sweetTag}
      <span style="margin-left:auto;font-size:12px;color:var(--t3)">EPS est: <span style="color:var(--t1);font-weight:500">${epsStr}</span></span>
      ${e.actual_eps != null ? `<span style="font-family:var(--mono);font-size:11px;color:${beatCol}">${beatStr} ${actualStr}</span>` : ''}
    </div>
    <!-- Expanded -->
    <div id="earn-detail-${uid}" style="display:none;padding:0 16px 14px;">
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:12px;">
        ${earnCard('Date', e.earnings_date + ' (' + daysStr + ')', days <= 0 ? 'Already reported.' : days <= 7 ? 'Coming up very soon — options IV is likely already inflating.' : sweetSpot ? 'In the options sweet spot (14–45 days). Best time to position with options before IV spikes.' : days > 45 ? 'Too far out for options positioning yet. Watch for it to enter the 14–45 day window.' : 'Approaching the optimal positioning window.')}
        ${earnCard('EPS Estimate', epsStr, e.estimate_eps != null ? 'Analyst consensus expects earnings of ' + epsStr + ' per share. A beat typically causes a gap up; a miss causes a gap down.' : 'No EPS estimate available.')}
        ${e.actual_eps != null ? earnCard('Actual EPS', actualStr, e.beat === true ? 'Beat the estimate by $' + Math.abs(e.actual_eps - e.estimate_eps).toFixed(2) + '. Positive surprise.' : e.beat === false ? 'Missed the estimate by $' + Math.abs(e.actual_eps - e.estimate_eps).toFixed(2) + '. Negative surprise.' : 'Reported.') : ''}
        ${earnCard('Signal status', isSuper ? '🚨 SUPER SIGNAL ACTIVE' : isWatching ? 'DEVELOPING SIGNAL' : 'No signal yet', isSuper ? 'The convergence engine has a super signal on this ticker. Options structure is queued for execution.' : isWatching ? 'Building toward super signal threshold. Missing some pillars.' : 'No convergence signal on this ticker yet. Monitor as earnings approach.')}
        ${sweetSpot ? earnCard('Options timing', 'SWEET SPOT (' + days + 'd)', 'Between 14–45 days before earnings is the ideal window to buy options spreads or strangles. IV has not fully inflated yet, so premium is still reasonable.') : ''}
      </div>
      ${isSuper ? `<div style="padding:10px 12px;background:rgba(0,229,160,0.06);border:1px solid rgba(0,229,160,0.25);border-radius:5px;font-size:12px;color:var(--t1);line-height:1.6">
        <strong>Action:</strong> ${e.ticker} has an active super signal with earnings in ${daysStr}. The convergence engine has already priced the structure and queued the trade for execution at market open. Check the Conv view for the full pillar breakdown.
      </div>` : sweetSpot && !isSuper ? `<div style="padding:10px 12px;background:var(--bd);border:1px solid var(--bb);border-radius:5px;font-size:12px;color:var(--t2);line-height:1.6">
        <strong style="color:var(--t1)">Watch:</strong> ${e.ticker} is in the options sweet spot (${days}d to earnings). If the convergence engine surfaces a signal with 4+ pillars, this becomes a candidate for an options spread trade before IV spikes.
      </div>` : ''}
    </div>
  </div>`;
}

function earnCard(label, val, explain) {
  return `<div style="background:var(--s3);border:1px solid var(--b1);border-radius:6px;padding:10px 12px;">
    <div style="font-family:var(--mono);font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--t3);margin-bottom:4px">${label}</div>
    <div style="font-size:13px;font-weight:600;color:var(--t1);margin-bottom:4px">${val}</div>
    <div style="font-size:11px;color:var(--t3);line-height:1.4">${explain}</div>
  </div>`;
}

function toggleEarnDetail(uid) {
  const el = document.getElementById('earn-detail-' + uid);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}
