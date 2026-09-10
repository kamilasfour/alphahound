"""patch — rewrites OptionsOrderResult with status having a default value"""
import re, sys

path = r'C:\alphahound_project\src\alphahound\engine\execution\options_executor.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

old = '''@dataclass
class OptionsOrderResult:
    status:         str      # "placed", "skipped", "error", "dry_run"
    ticker:         str
    structure_type: str'''

new = '''@dataclass
class OptionsOrderResult:
    ticker:         str
    structure_type: str
    status:         str = "pending"  # "placed", "skipped", "error", "dry_run", "pending"'''

if old not in src:
    print("ERROR: old text not found — check manually")
    sys.exit(1)

src = src.replace(old, new, 1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(src)
print("OK: OptionsOrderResult patched — status now has default 'pending'")
