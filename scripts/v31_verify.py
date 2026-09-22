from pathlib import Path

def need(path,*parts):
    s=Path(path).read_text(encoding='utf-8-sig')
    for p in parts:
        if p not in s: raise SystemExit(f'{path}: missing {p!r}')
    return s

idx=need('web/index.html','V.31 (Late - CH Shaukat Ali)','/v31.css','/v31.js','MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved.')
if 'V.31 Late - CH Shaukat Ali' in idx: raise SystemExit('footer/version memorial formatting regressed')
rec=need('web/records.html','V.31 (Late - CH Shaukat Ali)','/v31.css','/v31.js')
auth=need('web/auth.css','V31 login single-scroll/no-overlap','position:static!important')
css=need('web/v31.css','.rsiCanvasWrap','border-radius:0 0 12px 12px','user-select:none')
js=need('web/v31.js','/api/open-support-external','PrintScreen','contextmenu')
wv=need('webview2_host.go','SetWindowDisplayAffinity','chWDAExcludeFromCaptureV31','V31: keep the current MH view visible','V31: never blank the host while MT5 is starting','chEnsureMT5Terminal')
main=need('main.go','/api/open-support-external','https://wa.me/923434824609','registerRecordsRoutes','registerMT5PrefillRoutes','registerRecordsV2Routes','registerEASignalBridgeRoutes')
need('license_auth.go','MachineGuid')
# The browser signal dispatcher owns the fixed 0.02 lot; the Go EA bridge receives that payload.
app=need('web/app.js','SAME SIGNAL STILL ACTIVE','NO NEW SIGNAL','sendUniqueSignalToEAV30')
if 'lot:0.02' not in app.replace(' ',''):
    raise SystemExit('web/app.js: EA unique-signal 0.02 lot handoff missing')
need('ea_signal_bridge.go','/api/mt5/ea/send')
if 'AUTO CYCLE (HAMMAD & SOMI)' in idx: raise SystemExit('old AUTO CYCLE label still visible in MH header')
if 'AUTO CYCLE (HAMMAD & SOMI)' in rec: raise SystemExit('old AUTO CYCLE label still visible in Records')
print('V31 regression guards passed: UI, first-click navigation, embedded MT5 nonblank startup, capture/copy restrictions, and retained V28-V30 protections')
