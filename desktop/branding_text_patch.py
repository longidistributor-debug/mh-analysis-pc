from pathlib import Path

APP = Path('web/app.js')
INDEX = Path('web/index.html')

app = APP.read_text(encoding='utf-8')
index = INDEX.read_text(encoding='utf-8')

old_signal = '*MHRLC SIGNAL*'
new_signal = '*MH ANALYSIS SIGNAL*'
old_version = 'v79.6 AUTO CYCLE'
new_version = 'v79.6 AUTO CYCLE (HAMMAD & SOMI)'

if new_signal not in app:
    if old_signal not in app:
        raise SystemExit('Signal title marker not found')
    app = app.replace(old_signal, new_signal)

if new_version not in index:
    if old_version not in index:
        raise SystemExit('Version text marker not found')
    index = index.replace(old_version, new_version)

if old_signal in app:
    raise SystemExit('Old MHRLC SIGNAL text still present')
if old_version in index and new_version not in index:
    raise SystemExit('Old version text still present')

APP.write_text(app, encoding='utf-8')
INDEX.write_text(index, encoding='utf-8')
print('PASS branding text: MH ANALYSIS SIGNAL + v79.6 AUTO CYCLE (HAMMAD & SOMI)')
