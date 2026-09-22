from pathlib import Path
import re

p = Path('chrome_host.go')
s = p.read_text(encoding='utf-8')
pattern = re.compile(
    r'\s*vis,\s*_,\s*_\s*:=\s*chIsWindowVisible\.Call\(hwnd\)\s*\n'
    r'\s*if\s+vis\s*==\s*0\s*\{\s*\n'
    r'\s*return\s+1\s*\n'
    r'\s*\}\s*\n'
)
s, count = pattern.subn('\n', s)
if 'vis, _, _ := chIsWindowVisible.Call(hwnd)' in s:
    raise SystemExit('visibility gate remains after cleanup')
if count < 1:
    print('No visibility gate found; already clean')
else:
    print(f'Removed {count} visibility gate(s)')
p.write_text(s, encoding='utf-8', newline='\n')
