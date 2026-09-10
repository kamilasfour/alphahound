/* AlphaHound first-run walkthrough.
 *
 * Drop-in: add  <script src="/static/js/walkthrough.js?v=1"></script>  near the
 * end of index.html (after the nav/tabs exist in the DOM).
 *
 * Behaviour:
 *   - Auto-opens once per device on first entry after login (the login page sets
 *     sessionStorage 'ah_show_walkthrough'; we persist 'ah_onboarded' in
 *     localStorage so it won't reappear).
 *   - Replay anytime: window.AHWalkthrough.open()  — wire a "?" / "Tour" button
 *     in the header to call it.
 *
 * Two acts:
 *   Act 1 — how the system works (concept).
 *   Act 2 — the dashboard tour (what each tab is for).
 *
 * Content is descriptive only. It reads no data and changes no state.
 */
(function () {
  "use strict";

  var CONCEPT = [
    {
      t: "What AlphaHound does",
      b: "AlphaHound looks for moments when several independent sources of market "
       + "information line up in the same direction on the same stock — and acts "
       + "before that agreement is fully reflected in the price. It trades defined-risk "
       + "options spreads on a paper account, fully automated."
    },
    {
      t: "Convergence, not noise",
      b: "Any single signal is noisy. The edge is in agreement. When congressional "
       + "buying, unusual options sweeps, a government contract award, a social-velocity "
       + "spike, and a known upcoming catalyst all point the same way at once, that "
       + "stacked agreement is the 'super signal' the engine is hunting for."
    },
    {
      t: "The five pillars",
      b: "Each stock is scored on five pillars: Congressional flow, Unusual options "
       + "sweeps, Government contract awards, Social velocity, and Binary catalyst events. "
       + "Each contributes to one composite score. A SUPER SIGNAL needs a high composite "
       + "(>= 5.0) with at least 4 pillars firing and a clear non-neutral direction."
    },
    {
      t: "The macro gate (why it sometimes does nothing)",
      b: "Before any trade, the engine checks the overall market regime. It only opens "
       + "new positions when the read is RISK_ON. If it's NEUTRAL or RISK_OFF, it stands "
       + "down — no matter how good a single signal looks. 'No trade' is a deliberate, "
       + "correct outcome, not a failure."
    },
    {
      t: "Guardrails on every trade",
      b: "Hard rules bound the risk: at most 3 open spreads at once, max 2 contracts per "
       + "spread, an automatic stop-loss, a time-based exit (about 14 days, or 3 days after "
       + "a catalyst), and a portfolio-health halt that stops new entries when existing "
       + "positions are deep underwater."
    },
    {
      t: "Earning the right to go live",
      b: "Everything runs on a paper account until a hit-rate gate is met across enough "
       + "resolved trades. Until that track record exists, no real capital is deployed. "
       + "The dashboard's job is to make every one of these decisions legible to you."
    }
  ];

  var TOUR = [
    { t: "Health & Pipeline",
      b: "Start here. One glance tells you whether ingest, scoring, and the trade loop "
       + "are running, plus a colour verdict (GREEN/YELLOW/RED) and what — if anything — "
       + "needs your attention.",
      sel: ["health","pipeline"] },
    { t: "Convergence / Signals",
      b: "The live super signals and the developing 'watch' list, each with its pillar "
       + "breakdown and direction. This is the engine's current thesis, ticker by ticker.",
      sel: ["convergence","signals"] },
    { t: "Macro",
      b: "The current regime read (RISK_ON / NEUTRAL / RISK_OFF) and the score behind it. "
       + "When the engine isn't trading, this usually tells you why.",
      sel: ["macro"] },
    { t: "Positions",
      b: "Open spreads with live P&L, days held vs. max hold, and which pillars and "
       + "catalyst put each trade on. Empty when flat — which is the default after a reset.",
      sel: ["positions"] },
    { t: "Trades / History",
      b: "Every signal and trade over time, plus the hit-rate panel that gates live "
       + "capital. This is the scorecard the go/no-go decision rests on.",
      sel: ["trades","history","hit"] },
    { t: "Flow, Congress & Earnings",
      b: "The raw pillar inputs — unusual options flow, congressional trades, and the "
       + "earnings/catalyst calendar — each expandable in plain English so you can see "
       + "what the score is built from.",
      sel: ["flow","congress","earnings"] }
  ];

  function onboarded() {
    try { return !!localStorage.getItem("ah_onboarded"); } catch (e) { return false; }
  }
  function markOnboarded() {
    try { localStorage.setItem("ah_onboarded", String(Date.now())); } catch (e) {}
  }
  function pendingFromLogin() {
    try { return sessionStorage.getItem("ah_show_walkthrough") === "1"; } catch (e) { return false; }
  }
  function clearPending() {
    try { sessionStorage.removeItem("ah_show_walkthrough"); } catch (e) {}
  }

  function injectStyles() {
    if (document.getElementById("ahwt-style")) return;
    var css = ""
    + "#ahwt-overlay{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;"
    + "justify-content:center;background:rgba(5,8,13,.78);backdrop-filter:blur(3px);"
    + "font:14.5px/1.6 ui-monospace,'SF Mono',Menlo,Consolas,monospace;color:#e6edf3}"
    + "#ahwt-card{width:min(560px,92vw);background:#111722;border:1px solid #1e2836;"
    + "border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.55);overflow:hidden}"
    + "#ahwt-head{display:flex;align-items:center;gap:10px;padding:18px 22px;border-bottom:1px solid #1e2836}"
    + "#ahwt-head .dot{width:9px;height:9px;border-radius:50%;background:#f5a623;box-shadow:0 0 12px #f5a623}"
    + "#ahwt-head .ph{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#7d8aa0;margin-left:auto}"
    + "#ahwt-body{padding:24px 22px 8px;min-height:150px}"
    + "#ahwt-title{font-size:17px;margin:0 0 12px;color:#ffc234;letter-spacing:.02em}"
    + "#ahwt-text{margin:0;color:#cdd6e2}"
    + "#ahwt-dots{display:flex;gap:6px;padding:10px 22px 4px}"
    + "#ahwt-dots span{width:7px;height:7px;border-radius:50%;background:#27344a;transition:background .2s}"
    + "#ahwt-dots span.on{background:#f5a623}"
    + "#ahwt-foot{display:flex;align-items:center;gap:10px;padding:16px 22px 22px}"
    + "#ahwt-foot .spacer{margin-left:auto}"
    + ".ahwt-btn{padding:10px 18px;border-radius:9px;border:1px solid #27344a;background:#0c1219;"
    + "color:#e6edf3;font:inherit;cursor:pointer;transition:border-color .15s,filter .15s}"
    + ".ahwt-btn:hover{border-color:#3a4a66}"
    + ".ahwt-btn.primary{border:0;background:linear-gradient(180deg,#ffc234,#f5a623);color:#1a1206;font-weight:700}"
    + ".ahwt-btn.ghost{background:transparent;border-color:transparent;color:#7d8aa0}"
    + ".ahwt-btn.ghost:hover{color:#cdd6e2}"
    + ".ahwt-spot{position:relative;z-index:100000;outline:2px solid #f5a623;"
    + "outline-offset:3px;border-radius:6px;box-shadow:0 0 0 4px rgba(245,166,35,.18)}";
    var s = document.createElement("style");
    s.id = "ahwt-style"; s.textContent = css;
    document.head.appendChild(s);
  }

  var spotted = null;
  function clearSpot() {
    if (spotted) { spotted.classList.remove("ahwt-spot"); spotted = null; }
  }
  function spotlight(selectors) {
    clearSpot();
    if (!selectors) return;
    var candidates = Array.prototype.slice.call(
      document.querySelectorAll("nav a, nav button, [role='tab'], .tab, .nav-item, a, button")
    );
    for (var i = 0; i < selectors.length; i++) {
      var key = selectors[i];
      var hit = candidates.find(function (el) {
        var txt = (el.textContent || "").trim().toLowerCase();
        var data = (el.getAttribute("data-tab") || el.getAttribute("href") || "").toLowerCase();
        return txt && (txt.indexOf(key) !== -1 || data.indexOf(key) !== -1);
      });
      if (hit) {
        hit.classList.add("ahwt-spot"); spotted = hit;
        hit.scrollIntoView({ block: "center", behavior: "smooth" });
        return;
      }
    }
  }

  var act = 1;
  var idx = 0;
  function steps() { return act === 1 ? CONCEPT : TOUR; }

  function render() {
    var list = steps();
    var step = list[idx];
    document.getElementById("ahwt-phase").textContent =
      (act === 1 ? "How it works" : "Dashboard tour") + " \u00b7 " + (idx + 1) + "/" + list.length;
    document.getElementById("ahwt-title").textContent = step.t;
    document.getElementById("ahwt-text").textContent = step.b;

    var dots = document.getElementById("ahwt-dots");
    dots.innerHTML = "";
    for (var i = 0; i < list.length; i++) {
      var d = document.createElement("span");
      if (i === idx) d.className = "on";
      dots.appendChild(d);
    }

    var back = document.getElementById("ahwt-back");
    back.style.visibility = (act === 1 && idx === 0) ? "hidden" : "visible";

    var next = document.getElementById("ahwt-next");
    var lastOfTour = (act === 2 && idx === list.length - 1);
    next.textContent = lastOfTour ? "Done"
      : (act === 1 && idx === list.length - 1) ? "Start tour" : "Next";

    if (act === 2) spotlight(step.sel); else clearSpot();
  }

  function next() {
    var list = steps();
    if (idx < list.length - 1) { idx++; return render(); }
    if (act === 1) { act = 2; idx = 0; return render(); }
    close();
  }
  function back() {
    if (idx > 0) { idx--; return render(); }
    if (act === 2) { act = 1; idx = CONCEPT.length - 1; return render(); }
  }

  function open() {
    injectStyles();
    if (document.getElementById("ahwt-overlay")) return;
    act = 1; idx = 0;
    var el = document.createElement("div");
    el.id = "ahwt-overlay";
    el.innerHTML =
      "<div id='ahwt-card' role='dialog' aria-modal='true' aria-label='AlphaHound walkthrough'>"
      + "<div id='ahwt-head'><span class='dot'></span><strong>ALPHAHOUND</strong>"
      + "<span class='ph' id='ahwt-phase'></span></div>"
      + "<div id='ahwt-body'><h2 id='ahwt-title'></h2><p id='ahwt-text'></p></div>"
      + "<div id='ahwt-dots'></div>"
      + "<div id='ahwt-foot'>"
      + "<button class='ahwt-btn ghost' id='ahwt-skip'>Skip</button>"
      + "<div class='spacer'></div>"
      + "<button class='ahwt-btn' id='ahwt-back'>Back</button>"
      + "<button class='ahwt-btn primary' id='ahwt-next'>Next</button>"
      + "</div></div>";
    document.body.appendChild(el);

    document.getElementById("ahwt-next").addEventListener("click", next);
    document.getElementById("ahwt-back").addEventListener("click", back);
    document.getElementById("ahwt-skip").addEventListener("click", close);
    el.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") back();
    });
    el.tabIndex = -1; el.focus();
    render();
  }

  function close() {
    clearSpot();
    var el = document.getElementById("ahwt-overlay");
    if (el) el.remove();
    markOnboarded();
    clearPending();
  }

  window.AHWalkthrough = {
    open: open,
    close: close,
    reset: function () { try { localStorage.removeItem("ah_onboarded"); } catch (e) {} }
  };

  function maybeAutostart() {
    if (pendingFromLogin() || !onboarded()) open();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", maybeAutostart);
  } else {
    maybeAutostart();
  }
})();
