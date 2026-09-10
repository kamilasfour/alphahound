import re, sys

path = r'C:\alphahound_project\dashboard\index.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# Bump all ?v= version numbers to v=13 to force cache bust
html = re.sub(r'\?v=\d+', '?v=13', html)

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)

print("All script versions bumped to v=13")

# Show what was changed
matches = re.findall(r'src="[^"]+\?v=13"', html)
for m in matches:
    print("  ", m)
