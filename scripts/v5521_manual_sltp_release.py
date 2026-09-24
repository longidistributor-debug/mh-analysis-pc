from pathlib import Path

# V.55.21 is an application release marker paired with EA v1.30.
# Trading analysis logic is intentionally unchanged. The EA-side change keeps
# TP1/partial/BE+2 automation active while respecting a user's stronger manual
# SL and any live manually-moved TP.

Path('VERSION').write_text('V.55.21\n', encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    p=Path(name)
    s=p.read_text(encoding='utf-8')
    s=s.replace('V.55.20','V.55.21')
    p.write_text(s,encoding='utf-8')
