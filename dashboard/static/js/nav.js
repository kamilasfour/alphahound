/* ══ NAVIGATION ══ */
function showView(name) {
  VIEWS.forEach(v => {
    document.getElementById('view-'+v).classList.toggle('active', v === name);
    document.getElementById('snav-'+v).classList.toggle('active', v === name);
  });

  // Load fresh data on every navigation
  if (name === 'checkin')  { loadCheckIn(); }
  if (name === 'alerts')   { loadAlerts(); loadSummary(); }
  if (name === 'portfolio') { loadPositions(); }
  if (name === 'tradelog') { loadTradeLog(); }
  if (name === 'map')      { hmData = null;   loaded.map      = false; renderHeatmap();   loaded.map      = true; }
  if (name === 'sectors')  { secData = null;  loaded.sectors  = false; renderSectors();   loaded.sectors  = true; }
  if (name === 'universe') { uniData = null;  loaded.universe = false; renderUniverse();  loaded.universe = true; }
  if (name === 'global')   { hmData = null;   loaded.global   = false; renderGlobal();    loaded.global   = true; }
  if (name === 'macro')    { loadMacro(); }
  if (name === 'history')  { loadHistory(); }
  if (name === 'congress') { loadCongress(); }
  if (name === 'options')  { loadFlow(); }
  if (name === 'health')   { loadHealth(); }
  if (name === 'earnings') { loadEarnings(); }
}
