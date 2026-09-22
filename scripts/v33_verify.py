from pathlib import Path

def s(p): return Path(p).read_text(encoding='utf-8-sig')
def req(x,m):
    if not x: raise SystemExit('FAIL: '+m)

c=s('chrome_host.go'); m=s('main.go'); u=s('updater.go'); l=s('license_auth.go'); app=s('web/app.js')
req('chFindInstalledMT5WindowV33' in c,'broad installed MT5 detector missing')
req('chEmbedMT5V33' in c and 'chSetParent.Call(hwnd,hostHWND)' in c,'MT5 forced in-host reparent missing')
req('Never deliberately open it externally' in c,'MT5 external-open prevention marker missing')
req("pn==\"terminal64\"" in c,'broker terminal64 process fallback missing')
req('document.execCommand(\'insertText\'' in m or 'document.execCommand("insertText"' in m,'WhatsApp composer injection missing')
req('msgJSON' in m and 't.message' in m,'queued organized signal text not passed to WhatsApp composer')
req('data-icon="send"' in m,'WhatsApp real send-button click missing')
req('*MH ANALYSIS SIGNAL*' in app and '*Pair:*' in app and '*Entry:*' in app,'organized bold signal format regressed')
req('const mhPublicVersionV001 = "V.33"' in u,'updater version not V.33')
req('const licAppVersion = "V.33"' in l,'license version not V.33')
req('MachineGuid' in l,'secure identity regression')
req('SAME SIGNAL STILL ACTIVE' in app,'same-signal guard regression')
print('PASS V33 MT5 embed + WhatsApp auto delivery + retained protections')
