import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import subprocess
result = subprocess.run(
    [r'C:\alphahound_project\.venv\Scripts\python.exe',
     r'C:\alphahound_project\.venv\Scripts\alphahound.exe',
     'signals', 'options-monitor', '--close'],
    capture_output=True, text=True,
    cwd=r'C:\alphahound_project'
)
print(result.stdout)
print(result.stderr[-2000:] if result.stderr else '')
