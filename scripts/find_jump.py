import subprocess
result = subprocess.run(['findstr', '/s', '/r', 'jumpToTicker', r'C:\alphahound_project\dashboard\static\js\*.js'], capture_output=True, text=True, shell=True)
print(result.stdout)
print(result.stderr)
