from pathlib import Path
import re

def rd(p): return Path(p).read_text(encoding='utf-8-sig')
def wr(p,s): Path(p).write_text(s,encoding='utf-8',newline='\n')
def need(c,m):
    if not c: raise SystemExit(m)

# This script runs ONCE while creating the canonical V34 source tree.
# Release builds must never run V28/V29/V30/V31/V32/V33 patch scripts again.

# ------------------------------------------------------------------
# MT5: remove PowerShell process polling entirely + single-flight embed
# ------------------------------------------------------------------
p='chrome_host.go'; s=rd(p)
# V33 used PowerShell once per enumerated HWND to discover terminal64.exe. That is the
# visible PowerShell loop reported by the user. Use native class/title markers only.
s=re.sub(r'''\n\t\tif !looks && pid!=0 \{\n\t\t\t// PID-based terminal window fallback: compare against the PID of any running terminal64\.exe\.\n\t\t\tout,_:=exec\.Command\("powershell","-NoProfile","-NonInteractive","-Command",fmt\.Sprintf\("\$p=Get-Process -Id %d -ErrorAction SilentlyContinue; if\(\$p\)\{\$p\.ProcessName\}",pid\)\)\.Output\(\)\n\t\t\tpn:=strings\.ToLower\(strings\.TrimSpace\(string\(out\)\)\)\n\t\t\tlooks = pn=="terminal64" \|\| pn=="terminal"\n\t\t\}''','',s,count=1)
# Broaden native window markers used by common MT5 broker builds.
s=s.replace('looks:=strings.Contains(cls,"metaquotes") || strings.Contains(title,"metatrader") || strings.Contains(title,"meta trader")',
'''looks:=strings.Contains(cls,"metaquotes") || strings.Contains(cls,"metatrader") || strings.Contains(title,"metatrader") || strings.Contains(title,"meta trader") || strings.Contains(title,"mt5")''',1)
# Single-flight guard: repeated clicks while terminal is starting must not launch more processes.
if 'chMT5StartingV34' not in s:
    s=s.replace('chStopping    bool','chStopping    bool\n\tchMT5StartingV34 bool',1)
anchor='func chEnsureMT5Terminal() error {'
need(anchor in s,'V34 MT5 ensure anchor missing')
if 'V34_SINGLE_FLIGHT_MT5' not in s:
    s=s.replace(anchor,anchor+'''\n\t// V34_SINGLE_FLIGHT_MT5: one click starts at most one MT5 attach/launch operation.\n\tchMu.Lock()\n\tif chMT5StartingV34 { chMu.Unlock(); return nil }\n\tchMT5StartingV34=true\n\tchMu.Unlock()\n\tdefer func(){ chMu.Lock(); chMT5StartingV34=false; chMu.Unlock() }()''',1)
wr(p,s)

# ------------------------------------------------------------------
# Navigation: one user click, internal deterministic retries only
# ------------------------------------------------------------------
p='webview2_host.go'; s=rd(p)
if 'V34_ONE_CLICK_VIEW' not in s:
    anchor='func wv2ShowLocal(which int) {'
    need(anchor in s,'V34 view anchor missing')
    # After desired view is set, schedule internal repaint/attach retries. User never clicks again.
    target='\twv2SetDesiredView(which)'
    repl='''\twv2SetDesiredView(which)\n\t// V34_ONE_CLICK_VIEW: first user click is authoritative. Retry visibility internally\n\t// while WebView/MT5 child creation settles instead of requiring more user clicks.\n\tfor _,d:=range []time.Duration{80*time.Millisecond,250*time.Millisecond,650*time.Millisecond,1200*time.Millisecond}{\n\t\ttime.AfterFunc(d,func(){ chApplyDesiredBrowserView(); chResizeChildren() })\n\t}'''
    need(target in s,'V34 desired-view anchor missing')
    s=s.replace(target,repl,1)
wr(p,s)

# ------------------------------------------------------------------
# WhatsApp: retry composer injection after navigation; no silent one-shot failure
# ------------------------------------------------------------------
p='main.go'; s=rd(p)
old='''\tmsgJSON,_:=json.Marshal(t.message)\n\ttime.AfterFunc(5*time.Second, func(){\n\t\tscript:=fmt.Sprintf(`(()=>{const msg=%s;const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(!box)return false;box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,msg);box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));return true;})()`,string(msgJSON))\n\t\twvExecute(whatsappCore,script)\n\t\ttime.AfterFunc(700*time.Millisecond,func(){ postMessage(hostHWND,wmWhatsAppClick,0,0) })\n\t})'''
new='''\tmsgJSON,_:=json.Marshal(t.message)\n\t// V34_WA_RETRY: WhatsApp Web load time varies. Retry the exact same queued message\n\t// from Go until the composer is expected to exist; JS guards against duplicate injection.\n\tfor _,delay:=range []time.Duration{3*time.Second,6*time.Second,10*time.Second,15*time.Second}{\n\t\td:=delay\n\t\ttime.AfterFunc(d,func(){\n\t\t\tscript:=fmt.Sprintf(`(()=>{const msg=%s;const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(!box)return false;const mark='mh-v34-'+btoa(unescape(encodeURIComponent(msg))).slice(0,24);if(window[mark])return true;box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,msg);box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));const b=document.querySelector('[data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]');if(b){b.click();window[mark]=true;return true;}box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));window[mark]=true;return true;})()`,string(msgJSON))\n\t\t\twvExecute(whatsappCore,script)\n\t\t})\n\t}'''
need(old in s,'V34 WhatsApp V33 injection anchor missing')
s=s.replace(old,new,1)
wr(p,s)

# ------------------------------------------------------------------
# Signal fan-out: one explicit owner for NEW unique signals.
# Record + EA pending + MT5 visual prefill happen together from the same decision.
# ------------------------------------------------------------------
p='web/app.js'; s=rd(p)
old="if(d.signal&&!d._sameActiveSignal){void captureSignalRecordV30(d);void sendUniqueSignalToEAV30(d);void prepareMT5SignalV796(d,'NEW');} // V30 unique signal fan-out"
new="if(d.signal&&!d._sameActiveSignal){Promise.allSettled([captureSignalRecordV30(d),sendUniqueSignalToEAV30(d),prepareMT5SignalV796(d,'NEW')]).then(()=>{});} // V34_CANONICAL_SIGNAL_FANOUT"
need(old in s,'V34 canonical NEW signal fanout anchor missing')
s=s.replace(old,new,1)
# Keep re-evaluate from creating duplicate pending orders; it still sends its organized WhatsApp status.
# This is deliberate: re-evaluate validates the original trade, it is not a second trade.
wr(p,s)

# Exact V34 parity in canonical source.
for fn,pat,repl in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.34"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.34"')]:
    x=rd(fn); x,n=re.subn(pat,repl,x,count=1); need(n==1,'V34 version anchor missing '+fn); wr(fn,x)
for fn in ['web/index.html','web/records.html']:
    x=rd(fn); x=re.sub(r'V\.\d+(?:\.\d+)? \(Late - CH Shaukat Ali\)','V.34 (Late - CH Shaukat Ali)',x); wr(fn,x)
Path('VERSION').write_text('V.34\n',encoding='ascii')
print('V34 canonical fixes applied once')
