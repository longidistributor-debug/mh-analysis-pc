from pathlib import Path
import re

p = Path('chrome_host.go')
s = p.read_text(encoding='utf-8')

# Remove both historical forms used by the browser-window finders:
#   multiline: if vis == 0 {\n return 1 \n}
#   inline:    if vis == 0 { return 1 }
patterns = [
    re.compile(
        r'\s*vis,\s*_,\s*_\s*:=\s*chIsWindowVisible\.Call\(hwnd\)\s*\n'
        r'\s*if\s+vis\s*==\s*0\s*\{\s*\n'
        r'\s*return\s+1\s*\n'
        r'\s*\}\s*\n'
    ),
    re.compile(
        r'\s*vis,\s*_,\s*_\s*:=\s*chIsWindowVisible\.Call\(hwnd\)\s*\n'
        r'\s*if\s+vis\s*==\s*0\s*\{\s*return\s+1\s*\}\s*\n'
    ),
]
count = 0
for pattern in patterns:
    s, n = pattern.subn('\n', s)
    count += n

# Hard fallback: delete any remaining visibility-assignment + one-line/multiline
# zero-visible return block without touching other IsWindowVisible uses.
s, n = re.subn(
    r'\s*vis,\s*_,\s*_\s*:=\s*chIsWindowVisible\.Call\(hwnd\)\s*\n'
    r'\s*if\s+vis\s*==\s*0\s*\{[\s\S]*?return\s+1[\s\S]*?\}\s*\n',
    '\n', s,
)
count += n

if 'vis, _, _ := chIsWindowVisible.Call(hwnd)' in s:
    raise SystemExit('visibility gate remains after cleanup')
print(f'Removed {count} visibility gate(s)')
p.write_text(s, encoding='utf-8', newline='\n')
