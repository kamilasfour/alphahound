import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import subprocess
result = subprocess.run(['findstr', '/n', 'Quiver Writing', r'C:\alphahound_project\src\alphahound\engine\diagnostics.py'], capture_output=True, text=True, shell=True)
print("diagnostics.py:", result.stdout)
result2 = subprocess.run(['findstr', '/n', 'Quiver Writing', r'C:\alphahound_project\src\alphahound\engine\health_monitor.py'], capture_output=True, text=True, shell=True)
print("health_monitor.py:", result2.stdout)
