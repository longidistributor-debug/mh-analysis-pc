from pathlib import Path
import sys,re

def t(p): return Path(p).read_text(encoding='utf-8-sig')
def req(c,m):
    if not c:
        print('FAIL:',m); sys.exit(1)

def has(p,x): return x in t(p)

# Version + requested branding
req(has('updater.go','const mhPublicVersionV001 = "V.30"'),'public updater version is not V.30')
req(has('license_auth.go','const licAppVersion = "V.30"'),'license app version is not V.30')
idx=t('web/index.html'); rec=t('web/records.html'); auth=t('web/auth.js'); app=t('web/app.js')
req('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ' in idx,'exact Arabic Bismillah missing')
req('Late - CH Shaukat Ali' in idx and 'Late - CH Shaukat Ali' in rec,'memorial text missing from MH Analysis or Records')
req('Icons Assistant: Sinha Creates' in auth,'Sinha Creates credit missing')
req(auth.find('Icons Assistant: Sinha Creates') < auth.find('Admin Layout Credit: Ruhi Mughal'),'Sinha credit is not before Ruhi Mughal')
req('/v30.css' in idx and '/v30.css' in rec,'V30 responsive CSS not loaded')

# No known visible mojibake may ship again.
for p,s in [('web/index.html',idx),('web/records.html',rec)]:
    for bad in ['Ã','Â','â€”','â€¢','â†','â—','ðŸ','Ø¨Ù']:
        req(bad not in s,f'{p} still contains mojibake token {bad!r}')

# V28 identity fixes retained.
lic=t('license_auth.go')
req('MachineGuid' in lic,'MachineGuid identity source lost')
req('license-device-v1.bin' in lic,'secure device identity file logic lost')
req('licDeviceIdentityMu' in lic or 'licDevice' in lic,'device identity synchronization/self-heal markers lost')

# V29 navigation + Signal Link retained.
wv=t('webview2_host.go'); native=t('native_settings.go'); chrome=t('chrome_host.go')
req('Signal Link' in wv and 'chIDSignalLink' in wv and 'chIDSignalLink' in native,'WhatsApp Signal Link native control lost')
req('chEnsureMT5Terminal' in wv,'MT5 embed path lost from WebView2 host')
req('do not blank MH Analysis while MT5 is still starting' in wv,'V30 MT5 nonblank launch guard missing')

# Duplicate prevention and single fan-out ownership.
records=t('records_mt5_local.go'); v03=t('web/v03.js')
req('MH_SAME_SIGNAL_GUARD_V30' in records and '/api/records-v2/duplicate' in records,'server semantic duplicate guard missing')
req('SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL' in app,'same-signal UI state missing')
req('sendUniqueSignalToEAV30' in app,'EA automatic pending handoff missing')
req("postJSON('/api/records-v2/capture'" not in v03 and "postJSON('/api/mt5/prepare'" not in v03,'legacy V27 DOM double fan-out still active')

# EA bridge is actually reachable and uses fixed 0.02 handoff.
main=t('main.go'); ea=t('ea_signal_bridge.go')
req('registerEASignalBridgeRoutes(mux)' in main,'EA signal bridge routes are not registered')
req('/api/mt5/ea/send' in ea,'EA send route implementation missing')
req('lot:0.02' in app.replace(' ',''),'EA unique-signal lot 0.02 handoff missing')

# WhatsApp Signal Link must accept full group/chat URL, not digits-only.
req('chat.whatsapp.com' in main and 'waTask{target: target, message: q.Message}' in main,'full WhatsApp group/chat Signal Link handling missing')
req('func chSendWhatsAppViaCDP(target, message string)' in chrome,'WhatsApp CDP message composer path missing')
req('execCommand(\'insertText\'' in chrome and 'data-icon=\\"send\\"' in chrome,'WhatsApp composer/send automation missing')
req('*MH ANALYSIS SIGNAL*' in app and '*Pair:*' in app and '*Entry:*' in app,'organized bold WhatsApp message format lost')

# Native MT5 visual queue remains, but final placement is single EA path to avoid duplicates.
mt5=t('mt5_prefill.go')
req('READY - EA HANDLES AUTO PENDING' in mt5,'native MT5 visual queue single-path marker missing')
req("'PENDING ORDER SUBMITTED'" not in mt5,'native UI auto-submit still present and could duplicate EA pending')

# Fixed 15-minute clock + persistent analysis logic must remain.
req('FIXED_PHASE_MS=15*60*1000' in app,'fixed 15-minute cycle lost')
req('lastDecision = new Map()' in app,'analysis persistence state lost')

print('PASS V30 no-regression guards')
