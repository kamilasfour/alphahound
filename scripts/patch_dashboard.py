"""
Patch script: fix dashboard for Sprint 12 convergence system.
Run: python scripts\patch_dashboard.py
"""
import sys, re

html_path = r'C:\alphahound_project\dashboard\index.html'
css_path  = r'C:\alphahound_project\dashboard\static\css\dashboard.css'

print("Patching dashboard HTML and CSS for convergence system...")

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. Replace KPI strip ────────────────────────────────────────────────────
kpi_start = html.find('<!-- \u2550\u2550\u2550\u2550 KPI STRIP \u2550\u2550\u2550\u2550 -->')
kpi_end   = html.find('<!-- \u2550\u2550\u2550\u2550 BODY \u2550\u2550\u2550\u2550 -->')
if kpi_start == -1: print("WARN: KPI strip start not found")
if kpi_end   == -1: print("WARN: BODY marker not found")

if kpi_start != -1 and kpi_end != -1:
    new_kpi = '''<!-- \u2550\u2550\u2550\u2550 KPI STRIP \u2550\u2550\u2550\u2550 -->
<div class="kpi-strip">
  <div class="kpi"><div class="kpi-label">Tickers Watched</div><div class="kpi-val" id="k-universe">&mdash;</div><div class="kpi-sub">Active in engine</div></div>
  <div class="kpi"><div class="kpi-label">Posts / 24h</div><div class="kpi-val" id="k-posts">&mdash;</div><div class="kpi-sub" id="k-posts-sub">Raw data ingested</div></div>
  <div class="kpi"><div class="kpi-label">Scored / 24h</div><div class="kpi-val" id="k-scored">&mdash;</div><div class="kpi-sub" id="k-scored-sub">FinBERT scored</div></div>
  <div class="kpi"><div class="kpi-label">Super Signals</div><div class="kpi-val" id="k-super" style="color:var(--g)">&mdash;</div><div class="kpi-sub">Score &ge;4.0 &middot; catalyst required</div></div>
  <div class="kpi"><div class="kpi-label">Open Positions</div><div class="kpi-val" id="k-positions">&mdash;</div><div class="kpi-sub" id="k-pos-sub">Options trades live</div></div>
  <div class="kpi"><div class="kpi-label">P&amp;L</div><div class="kpi-val" id="k-pl">&mdash;</div><div class="kpi-sub" id="k-pl-sub">Unrealized</div></div>
  <div class="kpi"><div class="kpi-label">Macro</div><div class="kpi-val" id="k-macro" style="font-size:13px;padding-top:4px">&mdash;</div><div class="kpi-sub" id="k-macro-sub">Risk environment</div></div>
  <div class="kpi"><div class="kpi-label">Engine</div><div class="kpi-val" id="k-eng" style="font-size:13px;padding-top:4px">&mdash;</div><div class="kpi-sub" id="k-eng-sub">Pipeline status</div></div>
</div>

'''
    html = html[:kpi_start] + new_kpi + html[kpi_end:]
    print("OK: KPI strip replaced (8 cells)")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

# ── 2. Fix CSS grid columns ─────────────────────────────────────────────────
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

css_new = re.sub(
    r'(\.kpi-strip\s*\{[^}]*?grid-template-columns:\s*)repeat\(\d+,\s*1fr\)',
    r'\g<1>repeat(8, 1fr)',
    css, flags=re.DOTALL
)
if css_new != css:
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_new)
    print("OK: CSS grid set to 8 columns")
else:
    print("NOTE: CSS grid unchanged (check kpi-strip rule manually)")

print("\nDone. Hard-refresh dashboard (Ctrl+Shift+R).")
