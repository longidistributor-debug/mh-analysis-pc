from pathlib import Path

def s(p): return Path(p).read_text(encoding='utf-8-sig')
def req(x,m):
    if not x: raise SystemExit('FAIL: '+m)

auth=s('web/auth.css'); aj=s('web/auth.js'); w=s('webview2_host.go'); c=s('chrome_host.go'); u=s('updater.go'); l=s('license_auth.go'); idx=s('web/index.html'); rec=s('web/records.html')
req('flex-direction:column!important' in auth,'login overlay is not single-column')
req('MH_V32_EXTERNAL_SUPPORT' in aj and '/api/open-support-external' in aj,'login support is not forced external')
req('V32: create/attach before returning so one click is enough' in w,'WhatsApp first-click deterministic load missing')
req('V32: Records must be attached and visible on the first click' in w,'Records first-click deterministic load missing')
req('no startup prewarm race' in w,'aux prewarm race not removed')
req('chSignalLinkBtn' in w and 'which == 2' in w,'Signal Link same-click visibility missing')
req('chFindExistingMT5WindowV32' in c and 'metatrader 5' in c.lower(),'existing MT5 detection missing')
req('chAttachBrowser(existing)' in c,'existing MT5 is not re-parented')
req('wnd = chFindExistingMT5WindowV32()' in c,'broker handoff MT5 fallback missing')
req('V.32' in u and 'V.32' in l,'compiled updater/license version parity missing')
req('V.32 (Late - CH Shaukat Ali)' in idx and 'V.32 (Late - CH Shaukat Ali)' in rec,'V32 UI version labels missing')
# Retained protections from earlier releases.
req('MachineGuid' in l,'secure device identity regression')
req('SetWindowDisplayAffinity' in w,'capture exclusion regression')
req('SAME SIGNAL STILL ACTIVE' in s('web/app.js'),'same-signal guard regression')
req('registerEASignalBridgeRoutes' in s('main.go'),'EA bridge regression')
print('PASS V32 requested fixes + retained regression guards')
