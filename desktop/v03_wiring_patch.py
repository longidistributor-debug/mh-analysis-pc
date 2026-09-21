from pathlib import Path

p=Path('main.go'); s=p.read_text(encoding='utf-8')
anchor='registerLicenseRoutes(mux)'
if anchor not in s: raise SystemExit('license route anchor missing')
if 'licNavNoticeHandler' not in s:
    s=s.replace(anchor, anchor+'\n\tmux.HandleFunc("/api/license/nav-notice", licNavNoticeHandler)',1)
p.write_text(s,encoding='utf-8')

p=Path('updater.go'); s=p.read_text(encoding='utf-8')
# Build V.03 must identify itself as V.03 before any update comparison.
s=s.replace('const mhPublicVersionV001 = "V.02"','const mhPublicVersionV001 = "V.03"')
if 'const mhPublicVersionV001 = "V.03"' not in s:
    raise SystemExit('V.03 updater identity was not applied')
p.write_text(s,encoding='utf-8')
print('PASS V.03 updater identity and login navigation notice route')
