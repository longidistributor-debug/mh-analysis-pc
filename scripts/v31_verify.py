from pathlib import Path
import re

# V31 release parity hotfix: retained V30 patch leaves updater/license at an older
# compiled version. Force the actual binary identity to V.31 BEFORE verification/build.
for path, pattern, replacement in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.31"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.31"'),
]:
    p=Path(path); s=p.read_text(encoding='utf-8-sig')
    s2,n=re.subn(pattern,replacement,s,count=1)
    if n != 1: raise SystemExit(f'{path}: could not enforce V.31 compiled version')
    p.write_text(s2,encoding='utf-8')

def need(path,*parts):
    s=Path(path).read_text(encoding='utf-8-sig')
    for p in parts:
        if p not in s: raise SystemExit(f'{path}: missing {p!r}')
    return s

# Hard release invariant: updater + license + visible UI must all identify the same release.
need('updater.go','const mhPublicVersionV001 = "V.31"')
need('license_auth.go','const licAppVersion = "V.31"','MachineGuid')
idx=need('web/index.html','V.31 (Late - CH Shaukat Ali)','/v31.css','/v31.js','MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved.')
if 'V.31 Late - CH Shaukat Ali' in idx: raise SystemExit('footer/version memorial formatting regressed')
rec=need('web/records.html','V.31 (Late - CH Shaukat Ali)','/v31.css','/v31.js')
auth=need('web/auth.css','V31 login single-scroll/no-overlap','position:static!important')
css=need('web/v31.css','.rsiCanvasWrap','border-radius:0 0 12px 12px','user-select:none')
js=need('web/v31.js','/api/open-support-external','PrintScreen','contextmenu')
wv=need('webview2_host.go','SetWindowDisplayAffinity','chWDAExcludeFromCaptureV31','V31: keep the current MH view visible','V31: never blank the host while MT5 is starting','chEnsureMT5Terminal')
main=need('main.go','/api/open-support-external','https://wa.me/923434824609','registerRecordsRoutes','registerMT5PrefillRoutes','registerRecordsV2Routes','registerEASignalBridgeRoutes')
app=need('web/app.js','SAME SIGNAL STILL ACTIVE','NO NEW SIGNAL','sendUniqueSignalToEAV30')
if 'lot:0.02' not in app.replace(' ',''): raise SystemExit('web/app.js: EA unique-signal 0.02 lot handoff missing')
need('ea_signal_bridge.go','/api/mt5/ea/send')
if 'AUTO CYCLE (HAMMAD & SOMI)' in idx: raise SystemExit('old AUTO CYCLE label still visible in MH header')
if 'AUTO CYCLE (HAMMAD & SOMI)' in rec: raise SystemExit('old AUTO CYCLE label still visible in Records')
print('V31 regression guards passed, including strict updater/license/UI version parity; update loop cannot recur from version mismatch')
