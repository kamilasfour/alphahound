/* ══ NARRATIVE GENERATORS ══
   Synthesize loaded data into plain-English context for each panel.
   No extra API calls needed. */

function buildHeatmapNarrative(d) {
  const el = document.getElementById('hm-narrative');
  if (!el || !d) return;
  const cats     = ['US Stocks','Sectors','Commodities','International','Macro/Rates'];
  const allItems = cats.flatMap(c => d.categories[c]||[]);
  const withData = allItems.filter(t => t.change_5d_pct != null);
  if (!withData.length) { el.innerHTML = '<div class="intel-headline" style="color:var(--t3)">No price data yet — populates after market open</div>'; return; }
  const pct5   = t => t.change_5d_pct;
  const sorted = [...withData].sort((a,b) => pct5(b)-pct5(a));
  const up     = withData.filter(t => pct5(t) > 0).length;
  const dn     = withData.filter(t => pct5(t) < 0).length;
  const tone   = up > dn*1.5 ? 'bullish' : dn > up*1.5 ? 'bearish' : 'neutral';
  const toneText = tone==='bullish' ? 'broad risk-on tone' : tone==='bearish' ? 'broad risk-off tone' : 'mixed picture';
  const secs      = (d.categories['Sectors']||[]).filter(t => pct5(t) != null).sort((a,b) => pct5(b)-pct5(a));
  const secLeader = secs[0], secLagger = secs[secs.length-1];
  const uvxy      = (d.categories['Macro/Rates']||[]).find(t => t.ticker === 'UVXY');
  const vixNote   = uvxy?.change_5d_pct != null ? (uvxy.change_5d_pct > 5 ? ' VIX spiking — elevated fear.' : uvxy.change_5d_pct < -5 ? ' VIX falling — fear subsiding.' : '') : '';
  const headline  = `${up}/${withData.length} tickers up on the week — ${toneText}.${vixNote}`;
  const detail    = [
    secLeader ? `Leading sector: <strong>${secLeader.ticker}</strong> (${fP(pct5(secLeader))})` : '',
    secLagger ? `Lagging: <strong>${secLagger.ticker}</strong> (${fP(pct5(secLagger))})` : '',
  ].filter(Boolean).join(' · ');
  const chips = [
    ...sorted.slice(0,3).map(t => `<span class="ic ic-g">${t.ticker} ${fP(pct5(t))}</span>`),
    ...sorted.slice(-3).reverse().map(t => `<span class="ic ic-r">${t.ticker} ${fP(pct5(t))}</span>`),
  ].join('');
  el.className = `intel-bar ${tone}`;
  el.innerHTML = `<div class="intel-headline">${headline}</div><div class="intel-detail">${detail}</div><div class="intel-chips">${chips}</div>`;
}

function buildSectorsNarrative(d) {
  const el = document.getElementById('sectors-narrative');
  if (!el || !d?.sectors?.length) return;
  const withChg        = d.sectors.filter(s => s.change_5d_pct != null);
  const sorted         = [...withChg].sort((a,b) => b.change_5d_pct - a.change_5d_pct);
  const leader         = sorted[0], lagger = sorted[sorted.length-1];
  const withAlerts     = d.sectors.filter(s => s.has_alert);
  const withSent       = d.sectors.filter(s => s.sentiment_polarity != null);
  const bullishSectors = withSent.filter(s => s.sentiment_polarity > 0.05);
  const bearishSectors = withSent.filter(s => s.sentiment_polarity < -0.05);
  const avgChg = withChg.length ? (withChg.reduce((s,x) => s+x.change_5d_pct, 0)/withChg.length) : 0;
  const tone   = avgChg > 1 ? 'bullish' : avgChg < -1 ? 'bearish' : 'neutral';
  const headline = (leader && lagger && leader.ticker !== lagger.ticker)
    ? `<strong>${leader.label||leader.ticker}</strong> leads at ${fP(leader.change_5d_pct)}, <strong>${lagger.label||lagger.ticker}</strong> lags at ${fP(lagger.change_5d_pct)}.`
    : `${withChg.length} sectors tracked. Average 5-day: ${fP(avgChg)}.`;
  const details = [];
  if (withAlerts.length) details.push(`${withAlerts.length} sector${withAlerts.length>1?'s':''} with active divergence signal`);
  if (bullishSectors.length > bearishSectors.length) details.push(`Constituent sentiment bullish across ${bullishSectors.length} sectors`);
  else if (bearishSectors.length > bullishSectors.length) details.push(`Constituent sentiment cautious in ${bearishSectors.length} sectors`);
  const chips = [
    ...sorted.slice(0,3).map(s => `<span class="ic ic-g">${s.ticker} ${fP(s.change_5d_pct)}</span>`),
    ...sorted.slice(-3).reverse().map(s => `<span class="ic ic-r">${s.ticker} ${fP(s.change_5d_pct)}</span>`),
    ...withAlerts.map(s => `<span class="ic ic-p">${s.ticker} D${(s.d_value||0).toFixed(1)}</span>`),
  ].join('');
  el.className = `intel-bar ${tone}`;
  el.innerHTML = `<div class="intel-headline">${headline}</div>${details.length?`<div class="intel-detail">${details.join(' · ')}</div>`:''}<div class="intel-chips">${chips}</div>`;
}

function buildUniverseNarrative(d) {
  const el = document.getElementById('universe-narrative');
  if (!el || !d?.items?.length) return;
  const items           = d.items;
  const withAlerts      = items.filter(i => i.has_alert);
  const longs           = withAlerts.filter(i => i.direction === 'LONG');
  const shorts          = withAlerts.filter(i => i.direction === 'SHORT');
  const outperformers   = items.filter(i => (i.change_vs_spy||0) > 3 && i.change_5d_pct != null);
  const underperformers = items.filter(i => (i.change_vs_spy||0) < -3 && i.change_5d_pct != null);
  const withSent = items.filter(i => i.sentiment != null);
  const bullish  = withSent.filter(i => i.sentiment > 0.05).length;
  const bearish  = withSent.filter(i => i.sentiment < -0.05).length;
  const tone     = longs.length > shorts.length*1.5 ? 'bullish' : shorts.length > longs.length*1.5 ? 'bearish' : 'neutral';
  const headline = withAlerts.length
    ? `${withAlerts.length} active signal${withAlerts.length>1?'s':''}: ${longs.length} LONG, ${shorts.length} SHORT across ${items.length} tracked tickers.`
    : `${items.length} tickers tracked. No active divergence signals currently.`;
  const details = [];
  if (outperformers.length)   details.push(`${outperformers.length} tickers outpacing SPY by >3%`);
  if (underperformers.length) details.push(`${underperformers.length} lagging SPY by >3%`);
  if (withSent.length) details.push(`Sentiment: ${bullish} bullish, ${bearish} bearish, ${withSent.length-bullish-bearish} neutral`);
  const alertChips = withAlerts.slice(0,6).map(i =>
    `<span class="ic ${i.direction==='LONG'?'ic-g':'ic-r'}">${i.ticker} D${(i.d_value||0).toFixed(1)}</span>`
  ).join('');
  el.className = `intel-bar ${tone}`;
  el.innerHTML = `<div class="intel-headline">${headline}</div>${details.length?`<div class="intel-detail">${details.join(' · ')}</div>`:''}<div class="intel-chips">${alertChips}</div>`;
}

function buildGlobalNarrative(d) {
  const el = document.getElementById('global-narrative');
  if (!el || !d) return;
  const intl  = (d.categories['International']||[]).filter(t => t.change_5d_pct != null);
  const rates = (d.categories['Macro/Rates']||[]).filter(t => t.change_5d_pct != null);
  const intlUp   = intl.filter(t => t.change_5d_pct > 0).length;
  const intlDn   = intl.filter(t => t.change_5d_pct < 0).length;
  const intlTone = intlUp > intlDn ? 'constructive' : intlDn > intlUp ? 'risk-off' : 'mixed';
  const tlt  = rates.find(t => t.ticker === 'TLT');
  const uup  = rates.find(t => t.ticker === 'UUP');
  const hyg  = rates.find(t => t.ticker === 'HYG');
  const uvxy = rates.find(t => t.ticker === 'UVXY');
  const rateSignals = [];
  if (tlt?.change_5d_pct > 1)    rateSignals.push('bonds rallying (flight to safety)');
  else if (tlt?.change_5d_pct < -1) rateSignals.push('bonds selling (risk appetite improving)');
  if (uup?.change_5d_pct > 1)    rateSignals.push('dollar strengthening (headwind for equities/EM)');
  else if (uup?.change_5d_pct < -1) rateSignals.push('dollar weakening (tailwind for EM/commodities)');
  if (uvxy?.change_5d_pct > 5)   rateSignals.push('VIX elevated (fear in market)');
  if (hyg?.change_5d_pct < -1)   rateSignals.push('credit spreads widening (stress signal)');
  const tone = intlTone==='constructive' && !rateSignals.some(s => s.includes('safety')||s.includes('fear')) ? 'bullish'
    : intlTone==='risk-off' || rateSignals.length > 1 ? 'bearish' : 'neutral';
  const headline = `Global markets ${intlTone} — ${intlUp}/${intl.length} international ETFs positive on the week.`;
  const detail   = rateSignals.length ? rateSignals.join('; ')+'.' : 'No major macro stress signals.';
  const topIntl  = [...intl].sort((a,b) => b.change_5d_pct - a.change_5d_pct);
  const chips = [
    ...topIntl.slice(0,2).map(t => `<span class="ic ic-g">${t.ticker} ${fP(t.change_5d_pct)}</span>`),
    ...topIntl.slice(-2).reverse().map(t => `<span class="ic ic-r">${t.ticker} ${fP(t.change_5d_pct)}</span>`),
    ...rateSignals.slice(0,2).map(s => `<span class="ic ic-a">${s.split(' ')[0]}</span>`),
  ].join('');
  el.className = `intel-bar ${tone}`;
  el.innerHTML = `<div class="intel-headline">${headline}</div><div class="intel-detail">${detail}</div><div class="intel-chips">${chips}</div>`;
}
