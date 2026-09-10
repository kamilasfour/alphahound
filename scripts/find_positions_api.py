import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
import subprocess
result = subprocess.run(['findstr', '/n', 'def get_positions\|narrative\|d_value\|conviction', 
                       r'C:\alphahound_project\dashboard\api.py'], 
                      capture_output=True, text=True, shell=True)
print(result.stdout[:3000])
