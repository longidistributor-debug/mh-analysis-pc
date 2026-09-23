from pathlib import Path

APP = Path('web/app.js')
INDEX = Path('web/index.html')

app = APP.read_text(encoding='utf-8')
index = INDEX.read_text(encoding='utf-8')

old_signal = '*MHRLC SIGNAL*'
new_signal = '*MH ANALYSIS SIGNAL*'
old_version = 'v79.6 AUTO CYCLE'
new_version = 'v79.6 AUTO CYCLE (HAMMAD & SOMI)'

# Idempotent: current V.01 sources may already have newer branding/version markup.
if old_signal in app and new_signal not in app:
    app = app.replace(old_signal, new_signal)

if old_version in index and new_version not in index:
    index = index.replace(old_version, new_version)

if old_signal in app:
    raise SystemExit('Old MHRLC SIGNAL text still present')

APP.write_text(app, encoding='utf-8')
INDEX.write_text(index, encoding='utf-8')
print('PASS branding text: retained current branding; upgraded legacy markers when present')
