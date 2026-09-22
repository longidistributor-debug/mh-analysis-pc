from pathlib import Path
import re, runpy

# Build exactly on top of V54.10, then repair only the reported regressions.
runpy.run_path('.github/scripts/v5410_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# Persistent local UI cache: random localhost ports change every run, so browser
# localStorage cannot be the cross-restart source of truth for ticker/recent data.
# -----------------------------------------------------------------------------
p=Path('main.go')
s=p.read_text(encoding='utf-8')
old='mux.HandleFunc("/api/public-ticker", publicTickerHandler)'
new='mux.HandleFunc("/api/public-ticker", publicTickerHandlerV5411)\n\tmux.HandleFunc("/api/ui-cache", uiCacheHandlerV5411)'
if old not in s: raise SystemExit('V54.11 public ticker route anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# WhatsApp/navigation: WhatsApp remains fully rendered for background automation,
# but stays at HWND_BOTTOM unless the WhatsApp tab itself is selected. This restores
# Records and MT5 instead of WhatsApp covering every non-analysis view.
# -----------------------------------------------------------------------------
p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8')

if 'wmWhatsAppRefocusV5411' not in s:
    s=s.replace('wmWhatsAppAckV542          = 0x8F56', 'wmWhatsAppAckV542          = 0x8F56\n\twmWhatsAppRefocusV5411     = 0x8F57', 1)

pat=r"func wv2ParkWhatsAppV547\(\) \{.*?\n\}"
repl='''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
\tif w<1 { w=1 }; if h<1 { h=1 }
\tchMoveWindow.Call(wv2WhatsappContainer, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged()
\t// HWND_BOTTOM = 1. Keep the fully-rendered WhatsApp surface behind every active view.
\tchSetWindowPos.Call(wv2WhatsappContainer, 1, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoActivate)
}'''
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.11 WhatsApp park replacement failed')

pat=r"func wv2ShowLocal\(which int\) \{.*?\n\}"
repl='''func wv2ShowLocal(which int) {
\tif wv2Browser == nil { return }
\twv2SetDesiredView(which)
\twv2HideAll()
\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\tswitch which {
\tcase 1:
\t\tchShowWindow.Call(wv2Container,chSWShow); _=wv2Browser.Show()
\t\tchSetWindowPos.Call(wv2Container,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\t\twv2Browser.Resize(); wv2Browser.Focus()
\tcase 2:
\t\twv2WAResolvedTarget = ""
\t\tif wv2Whatsapp != nil {
\t\t\tchMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)
\t\t\tchShowWindow.Call(wv2WhatsappContainer,chSWShow)
\t\t\tchSetWindowPos.Call(wv2WhatsappContainer,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\t\t\t_ = wv2Whatsapp.Show(); wv2Whatsapp.Resize(); _=wv2Whatsapp.NotifyParentWindowPositionChanged(); wv2Whatsapp.Focus()
\t\t}
\tcase 3:
\t\tif wv2Records != nil {
\t\t\tchShowWindow.Call(wv2RecordsContainer,chSWShow); _=wv2Records.Show()
\t\t\tchSetWindowPos.Call(wv2RecordsContainer,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\t\t\twv2Records.Resize(); wv2Records.Focus()
\t\t}
\t}
\twv2Resize()
}'''
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.11 local-view function replacement failed')

# Restore focus to the view the user is actually using after a short background-WA kick.
anchor='func wv2ProcessWhatsAppQueueV36() {'
helper='''func wv2RestoreDesiredFocusV5411() {
\tchViewMu.Lock(); desired:=chDesiredView; chViewMu.Unlock()
\tswitch desired {
\tcase 1:
\t\tif wv2Browser!=nil { wv2Browser.Focus() }
\tcase 2:
\t\tif wv2Whatsapp!=nil { wv2Whatsapp.Focus() }
\tcase 3:
\t\tif wv2Records!=nil { wv2Records.Focus() }
\tcase 4:
\t\tif chMT5Wnd!=0 { chFocusEmbeddedBrowser(chMT5Wnd) }
\t}
}

'''
if anchor not in s: raise SystemExit('V54.11 WA process anchor missing')
s=s.replace(anchor,helper+anchor,1)

old='''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2WAResolvedTarget = ""
\twv2Whatsapp.Navigate(target)'''
new='''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Focus()
\twv2WAResolvedTarget = ""
\twv2Whatsapp.Navigate(target)
\ttime.AfterFunc(140*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })'''
if old not in s: raise SystemExit('V54.11 WA navigate block missing')
s=s.replace(old,new,1)

# Keep focus long enough for WhatsApp Web to process DOM input/click, then return it.
old='''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Eval(script)'''
new='''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Focus()
\twv2Whatsapp.Eval(script)
\ttime.AfterFunc(180*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })'''
if old in s:
    s=s.replace(old,new,1)
elif '\twv2Whatsapp.Eval(script)' in s:
    s=s.replace('\twv2Whatsapp.Eval(script)',new,1)
else:
    raise SystemExit('V54.11 WA eval anchor missing')

# Do not claim sent merely because .click() returned. Confirm the composer cleared.
old="""if(!send)return ack('waiting-send');
send.click();
sessionStorage.setItem(sentKey,'1');
return ack('sent');"""
new="""if(!send)return ack('waiting-send');
try{send.scrollIntoView({block:'center',inline:'center'})}catch(e){}
try{send.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}));send.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}))}catch(e){}
try{send.click()}catch(e){}
setTimeout(()=>{
  const b=document.querySelector('footer [contenteditable=\"true\"][role=\"textbox\"]')||document.querySelector('footer [contenteditable=\"true\"]')||document.querySelector('footer div[role=\"textbox\"]');
  const left=((b&&((b.innerText||b.textContent)||''))||'').trim();
  if(!left){sessionStorage.setItem(sentKey,'1');ack('sent')}else{ack('retry-send')}
},220);
return 'sending';"""
if old not in s: raise SystemExit('V54.11 confirmed-send JS block missing')
s=s.replace(old,new,1)

# Message handler for returning focus to the selected user view.
needle='''\tcase wmWhatsAppAckV542:
\t\twv2WhatsAppAckV542(wp); return 0'''
replacement='''\tcase wmWhatsAppAckV542:
\t\twv2WhatsAppAckV542(wp); return 0
\tcase wmWhatsAppRefocusV5411:
\t\twv2ParkWhatsAppV547(); wv2RestoreDesiredFocusV5411(); return 0'''
if needle not in s: raise SystemExit('V54.11 ACK handler anchor missing')
s=s.replace(needle,replacement,1)

# If MT5 is the selected view, force its child HWND above the bottom parked WA renderer.
old='''\tif chMT5Wnd != 0 { chMoveWindow.Call(chMT5Wnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) }'''
new='''\tif chMT5Wnd != 0 {
\t\tchMoveWindow.Call(chMT5Wnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
\t\tchViewMu.Lock(); desiredMT5:=chDesiredView; chViewMu.Unlock()
\t\tif desiredMT5==4 { chShowWindow.Call(chMT5Wnd,chSWShow); chSetWindowPos.Call(chMT5Wnd,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate) }
\t}'''
if old not in s: raise SystemExit('V54.11 MT5 resize anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# Frontend: exact user template + disk-backed instant ticker/recent values.
# -----------------------------------------------------------------------------
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
pat=r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl="""function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null;
  const isRe=action==='RE-EVALUATE';
  const statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge');
  const reason=isRe?(d?.explanation||status||d?.bestFamily||sig?.setupReason||'Market re-evaluation'):'';
  const lines=[`*MH ANALYSIS SIGNAL*`,`*Status:* ${statusValue}`];
  if(isRe){lines.push('',`*Reason:* ${reason}`,'')}
  else{lines.push('')}
  lines.push(`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,'');
  if(sig){
    const dot=sig.direction==='SELL'?'🔴':'🟢';
    lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);
  }else{
    lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`);
  }
  return lines.join('\\n');
}"""
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.11 exact WhatsApp template replacement failed')

cache_helper="""
function savePersistentUICacheV5411(delta){
  try{fetch('/api/ui-cache',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(delta),cache:'no-store'}).catch(()=>{})}catch(e){}
}
async function loadPersistentUICacheV5411(){
  try{
    const r=await fetch('/api/ui-cache',{cache:'no-store'}); if(!r.ok)return;
    const j=await r.json();
    if(j?.ticker)applyTickerCacheV549(j.ticker);
    if(Array.isArray(j?.recent)){
      recentSession.splice(0,recentSession.length,...j.recent.slice(0,6));
      renderRecentSignals();
    }
  }catch(e){}
}
"""
idx=s.find('function applyTickerCacheV549(')
if idx<0: raise SystemExit('V54.11 ticker helper anchor missing')
s=s[:idx]+cache_helper+s[idx:]

needle="try{localStorage.setItem('mh-public-ticker-stable',JSON.stringify(j));applyTickerCacheV549(j)}catch(e){}"
if needle not in s: raise SystemExit('V54.11 ticker success anchor missing')
s=s.replace(needle,needle+"\n      savePersistentUICacheV5411({ticker:j});",1)

needle="try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(e){}"
if needle not in s: raise SystemExit('V54.11 recent persistence anchor missing')
s=s.replace(needle,needle+"\n  savePersistentUICacheV5411({recent:recentSession});",1)

startup='renderRecentSignals();primeMovingTickerV547();primeTickerV549();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
if startup not in s: raise SystemExit('V54.11 startup anchor missing')
s=s.replace(startup,'loadPersistentUICacheV5411();'+startup,1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# Calendar: keep the original independent widget as a direct eager iframe.
# No FCS/API gate, no local calendar overlay, no delayed JS loader dependency.
# -----------------------------------------------------------------------------
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
widget='<iframe src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>'
widget2='<iframe id="economicCalendarWidgetV5411" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar" loading="eager"></iframe>'
if widget not in s: raise SystemExit('V54.11 original calendar widget anchor missing')
s=s.replace(widget,widget2,1)
if 'rel="preconnect" href="https://widget.mfbcdn.net"' not in s:
    s=s.replace('<link rel="icon" href="/mh-analysis.ico" />','<link rel="icon" href="/mh-analysis.ico" />\n<link rel="preconnect" href="https://widget.mfbcdn.net" />',1)
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('web/runtime-fixes.css')
css=p.read_text(encoding='utf-8')
css+='''\n/* V54.11 direct economic-calendar widget: visible immediately, no API overlay. */\n#economicCalendarWidgetV5411{display:block!important;width:100%!important;height:340px!important;border:0!important;background:#fff!important;transform:none!important;visibility:visible!important;opacity:1!important}.calendarCrop{background:#fff!important;overflow:hidden!important}\n'''
p.write_text(css,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# Version stamps.
# -----------------------------------------------------------------------------
for path,pat,val in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.11"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.11"')]:
 q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
 if n!=1: raise SystemExit('version stamp failed '+path)
 q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.11\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.11</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.10','Version: V.54.11'); p.write_text(z,encoding='utf-8',newline='\n')

# Hard regression guards.
a=Path('web/app.js').read_text(encoding='utf-8'); wa=Path('webview2_host.go').read_text(encoding='utf-8'); html=Path('web/index.html').read_text(encoding='utf-8'); main=Path('main.go').read_text(encoding='utf-8')
checks=[
 ('WA bottom while background', 'chSetWindowPos.Call(wv2WhatsappContainer, 1' in wa),
 ('Records explicit top', 'chSetWindowPos.Call(wv2RecordsContainer,0' in wa),
 ('Main explicit top', 'chSetWindowPos.Call(wv2Container,0' in wa),
 ('WA background focus kick', 'wmWhatsAppRefocusV5411' in wa and 'wv2Whatsapp.Focus()' in wa),
 ('WA confirmed composer clear', "ack('retry-send')" in wa and "return 'sending'" in wa),
 ('exact template status', "statusValue=isRe?'Re-Evaluate'" in a and '`*Status:* ${statusValue}`' in a),
 ('exact template reason', '`*Reason:* ${reason}`' in a),
 ('disk UI cache frontend', '/api/ui-cache' in a and 'loadPersistentUICacheV5411();renderRecentSignals()' in a),
 ('disk UI cache backend', 'uiCacheHandlerV5411' in main and 'publicTickerHandlerV5411' in main),
 ('calendar direct eager widget', 'economicCalendarWidgetV5411' in html and 'loading="eager"' in html),
]
for name,ok in checks:
 if not ok: raise SystemExit('Guard failed: '+name)
