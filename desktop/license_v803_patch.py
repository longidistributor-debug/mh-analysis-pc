from pathlib import Path

MARK = "MH_SECURE_LICENSE_V803"

p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
if 'const licAppVersion = "80.3"' not in s:
    old = 'const licAppVersion = "80.2"'
    if old not in s:
        raise SystemExit("license_auth.go V80.2 version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.3"', 1)
p.write_text(s, encoding="utf-8")

print(MARK + " license version applied")
