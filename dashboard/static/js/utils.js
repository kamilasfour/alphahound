/* ══ STATE ══ */
let allAlerts = [], activeDir = null, techCache = {};
let macroData = null, hmData = null, secData = null, uniData = null;
const loaded = {};
const seenTickers = new Set(JSON.parse(localStorage.getItem('ah_seen') || '[]'));

/* ══ FORMATTERS ══ */
const fK    = n => n == null ? '—' : n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'k' : String(n);
const fP    = n => n == null ? '—' : (n > 0 ? '+' : '') + n.toFixed(1) + '%';
const fPL   = n => n == null ? '—' : (n >= 0 ? '+$' : '-$') + Math.abs(n).toFixed(2);
const fPrem = n => { if (!n) return '—'; if (n >= 1e6) return '$'+(n/1e6).toFixed(1)+'M'; if (n >= 1e3) return '$'+(n/1e3).toFixed(0)+'k'; return '$'+Math.round(n); };
const tAgo  = iso => { if (!iso) return '—'; const m = Math.round((Date.now()-new Date(iso))/60e3); if (m < 2) return 'now'; if (m < 60) return m+'m'; return Math.round(m/60)+'h'; };
const fDate  = iso => new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false});
const fShort = iso => new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric'});

/* ══ FETCH HELPER ══ */
async function fj(p) {
  const r = await fetch(API + p);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

/* ══ COLOUR HELPERS ══ */
const chgColor = v => v == null ? 'var(--t3)' : v > 1.5 ? 'var(--g)' : v < -1.5 ? 'var(--r)' : v > 0 ? '#4aab80' : '#c06070';
const hmColor  = v => { if (v == null) return 'rgba(255,255,255,0.03)'; const a = Math.min(0.42, Math.abs(v)/5); return v > 0 ? `rgba(0,201,141,${a})` : `rgba(255,77,106,${a})`; };

/* ══ SEEN-TICKER TRACKING ══ */
function markSeen(t) { seenTickers.add(t); localStorage.setItem('ah_seen', JSON.stringify([...seenTickers])); }

/* ══ CLOCK ══ */
// Clock is handled by updateETClock() in main.js — no-op here
