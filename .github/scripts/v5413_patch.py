from pathlib import Path
import re, runpy

# Build on V54.12, then hard-fix the runtime paths that were still failing on a real PC.
runpy.run_path('.github/scripts/v5412_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) WHATSAPP: keep the logged-in WebView fully sized but clipped to a 1px edge.
#    This keeps WhatsApp rendered for background automation without ever covering
#    MH Analysis / Records / MH MT5.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')

pat = r"func wv2ParkWhatsAppV547\(\) \{.*?\n\}"
repl = '''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
\tif w<1 { w=1 }; if h<1 { h=1 }
\tx:=w-1; if x<0 { x=0 }
\t// Full desktop-size renderer, but only a 1px clipped edge stays inside the host.
\t// This prevents the WhatsApp surface from ever appearing under MH MT5.
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged()
\tchSetWindowPos.Call(wv2WhatsappContainer, 1, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), chSWPNoActivate)
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.13 WhatsApp park replacement failed')

# Replace the whole sender JS with idempotent composer replacement + confirmed send.
# Every retry first normalizes the composer to EXACTLY one organized message, then
# clicks Send. It is not marked sent until the composer actually clears.
fn_start = s.index('func wv2EvalWhatsAppV54(token uintptr)')
start = s.index('\tscript := fmt.Sprintf(`(()=>{', fn_start)
end = s.index('\twv2ParkWhatsAppV547()', start)
new_script = r'''\tscript := fmt.Sprintf(`(()=>{
const msg=%s,isGroup=%s,token=%d;
const ack=(st)=>{try{window.external.invoke('MHWA|'+token+'|'+st)}catch(e){};return st};
const sentKey='mh-v5413-sent-'+token;
if(sessionStorage.getItem(sentKey)==='1')return ack('sent');
const host=(location.hostname||'').toLowerCase();
try{window.open=(u)=>{if(u)location.assign(String(u));return window}}catch(e){}
if(isGroup&&host!=='web.whatsapp.com'){
  const nodes=[...document.querySelectorAll('a,button,[role="button"]')];
  const preferred=nodes.find(el=>{
    const txt=((el.innerText||el.textContent||'')+' '+(el.getAttribute('aria-label')||'')).toLowerCase();
    const href=(el.href||el.getAttribute('href')||'').toLowerCase();
    return /continue to chat|open chat|use whatsapp web|whatsapp web|continue|join chat/.test(txt)||href.includes('web.whatsapp.com');
  });
  if(preferred){
    const a=preferred.tagName==='A'?preferred:preferred.closest('a');
    const href=(a&&a.href)||preferred.href||preferred.getAttribute('href');
    if(a){a.target='_self';a.removeAttribute('target')}
    if(preferred.removeAttribute)preferred.removeAttribute('target');
    ack('opening-group-same-view');
    if(href&&/^https?:/i.test(href)){location.assign(href);return 'opening-group-same-view'}
    preferred.click();return 'opening-group-same-view';
  }
  return ack('waiting-group-link');
}
if(host!=='web.whatsapp.com')return ack('waiting-whatsapp');
const getBox=()=>document.querySelector('footer [contenteditable="true"][role="textbox"]')||document.querySelector('footer [contenteditable="true"]')||document.querySelector('footer div[role="textbox"]');
const box=getBox();
if(!box)return ack('waiting-chat');
const norm=(v)=>String(v||'').replace(/\r/g,'').trim();
box.focus();
if(norm(box.innerText||box.textContent)!==norm(msg)){
  // Clear ONLY the WhatsApp composer, never the whole document selection.
  try{
    const sel=window.getSelection(),range=document.createRange();
    range.selectNodeContents(box);sel.removeAllRanges();sel.addRange(range);
    document.execCommand('delete',false,null);sel.removeAllRanges();
  }catch(e){}
  try{box.innerHTML=''}catch(e){try{box.textContent=''}catch(_){}}
  try{box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward',data:null}))}catch(e){box.dispatchEvent(new Event('input',{bubbles:true}))}
  let inserted=false;
  try{inserted=document.execCommand('insertText',false,msg)}catch(e){}
  if(!inserted){box.textContent=msg}
  try{box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}))}catch(e){box.dispatchEvent(new Event('input',{bubbles:true}))}
}
const send=document.querySelector('footer [data-icon="send"]')?.closest('button,[role="button"]')||document.querySelector('button[aria-label="Send"]')||document.querySelector('[aria-label="Send"][role="button"]')||document.querySelector('[data-testid="compose-btn-send"]');
if(!send)return ack('waiting-send');
try{send.scrollIntoView({block:'center',inline:'center'})}catch(e){}
try{send.focus()}catch(e){}
try{send.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,pointerType:'mouse',isPrimary:true}))}catch(e){}
try{send.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window}))}catch(e){}
try{send.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window}))}catch(e){}
try{send.click()}catch(e){}
setTimeout(()=>{
  const b=getBox();
  const left=norm(b&&((b.innerText||b.textContent)||''));
  if(!left){sessionStorage.setItem(sentKey,'1');ack('sent');return}
  // Final automatic Enter fallback while the hidden WhatsApp view still owns focus.
  try{
    b.focus();
    b.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
    b.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
    b.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
  }catch(e){}
  setTimeout(()=>{
    const b2=getBox();
    const left2=norm(b2&&((b2.innerText||b2.textContent)||''));
    if(!left2){sessionStorage.setItem(sentKey,'1');ack('sent')}else{ack('retry-send')}
  },260);
},360);
return 'sending';
})()`, string(msgJSON), string(groupJSON), token)
'''
new_script = new_script.replace(r'\t','\t')
s = s[:start] + new_script + s[end:]

# Keep WhatsApp focused until the composer confirms it actually sent. The V54.11
# 180ms focus return was early enough to make the message sit unsent in the composer.
s = s.replace('\twv2Whatsapp.Eval(script)\n\ttime.AfterFunc(180*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })',
              '\twv2Whatsapp.Eval(script)', 1)

# Retry immediately on a confirmed unsent composer, and return focus only after send.
pat = r"func wv2WhatsAppAckV542\(token uintptr\) \{.*?\n\}"
repl = '''func wv2WhatsAppAckV542(token uintptr) {
\tif token == 0 || token != wv2WAActiveToken || token != wv2WALastAckToken { return }
\tswitch wv2WALastAckStatus {
\tcase "sent":
\t\twv2WAResolvedTarget = wv2WAActiveTarget
\t\twv2FinishWhatsAppV54(token)
\t\ttime.AfterFunc(90*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })
\tcase "retry-send":
\t\ttime.AfterFunc(120*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
\t}
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.13 WhatsApp ACK replacement failed')

# MH MT5: explicitly sweep every external MT5 top-level window before/after activation.
s = s.replace('func wv2ActivateMT5V5412() {\n\twv2SetDesiredView(4)',
              'func wv2ActivateMT5V5412() {\n\tv546HideAllMT5TopLevel()\n\twv2SetDesiredView(4)', 1)
s = s.replace('\tchFocusEmbeddedBrowser(chMT5Wnd)\n}',
              '\tchFocusEmbeddedBrowser(chMT5Wnd)\n\tv546HideAllMT5TopLevel()\n}', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 2) RECENT SIGNALS: the record store is the source of truth. Load it immediately
#    at startup, then keep the UI cache only as a fallback.
# -----------------------------------------------------------------------------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')

pat = r"function renderRecentSignals\(\)\{.*?\n\}"
repl = '''function renderRecentSignals(){
  const previous=recentSession.slice(0,5);
  $('#recentSignals').className='recentList';
  $('#recentSignals').innerHTML=previous.length?previous.map(x=>`<div class="recentRow"><span>${x.time}</span><span class="recentTf">${x.timeframe||'—'}</span><b class="${x.label==='BUY'?'good':x.label==='SELL'?'bad':'warn'}">${x.label}</b><span>${Math.round(Number(x.score)||0)}/100</span></div>`).join(''):'No recent signals yet.';
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.13 recent renderer replacement failed')

recent_loader = '''
async function loadRecentSignalsV5413(){
  try{
    const r=await fetch('/api/records-v2',{cache:'no-store'});if(!r.ok)throw new Error('records unavailable');
    const j=await r.json();
    const rows=(Array.isArray(j?.records)?j.records:[]).slice().sort((a,b)=>Number(b?.created_at||0)-Number(a?.created_at||0)).slice(0,6).map(x=>{
      const ts=Number(x?.created_at||0)*1000;
      const t=String(x?.local_time||'').trim()||(ts?new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'—');
      const label=String(x?.direction||'').trim().toUpperCase()||'NO EDGE';
      return {time:t,timeframe:String(x?.timeframe||'—'),label,score:Math.round(Number(x?.score)||0),state:String(x?.status||''),key:String(x?.signal_id||x?.id||`${ts}|${label}`)};
    });
    if(rows.length){
      recentSession.splice(0,recentSession.length,...rows);
      try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(e){}
      savePersistentUICacheV5411({recent:recentSession});
    }
    renderRecentSignals();
    return rows.length;
  }catch(e){renderRecentSignals();return 0}
}
'''
idx = s.find('function renderRecentSignals(){')
if idx < 0:
    raise SystemExit('V54.13 recent loader insertion anchor missing')
s = s[:idx] + recent_loader + s[idx:]

startup = 'await loadPersistentUICacheV5411();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
startup2 = 'await loadPersistentUICacheV5411();await loadRecentSignalsV5413();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
if startup not in s:
    raise SystemExit('V54.13 startup anchor missing')
s = s.replace(startup, startup2, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 3) MOVING TICKER: if there is no usable disk cache, warm it BEFORE the native
#    window appears. Once MH Analysis is visible the ticker therefore has values.
# -----------------------------------------------------------------------------
p = Path('main.go')
s = p.read_text(encoding='utf-8')
helper = '''func warmStartupTickerV5413() {
\tc := loadUICacheV5411()
\tif len(c.Ticker) >= 5 { return }
\tdone := make(chan struct{})
\tgo func(){ _ = refreshTickerV5411(); close(done) }()
\tselect {
\tcase <-done:
\tcase <-time.After(1600 * time.Millisecond):
\t}
}

'''
anchor = 'func main() {\n\tloadSettings()'
if anchor not in s:
    raise SystemExit('V54.13 main startup anchor missing')
s = s.replace('func main() {\n', helper + 'func main() {\n', 1)
s = s.replace('\tloadSettings()\n', '\tloadSettings()\n\twarmStartupTickerV5413()\n', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 4) ECONOMIC CALENDAR: use the user's Myfxbook iframe directly. Hide/crop the
#    top date/app/settings toolbar and make the whole widget non-clickable.
# -----------------------------------------------------------------------------
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
old = '<div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>'
new = '<iframe id="economicCalendarWidgetV5413" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=0,1,2,3&countries=Australia,Belgium,Canada,China,France,Germany,Italy,Japan,Mexico,New%20Zealand,South%20Africa,Spain,Switzerland,United%20Kingdom,United%20States" title="Economic Calendar" loading="eager" tabindex="-1" aria-label="Economic Calendar"></iframe>'
if old not in s:
    raise SystemExit('V54.13 calendar local element anchor missing')
s = s.replace(old, new, 1)
if 'rel="preconnect" href="https://widget.mfbcdn.net"' not in s:
    s = s.replace('<link rel="icon" href="/mh-analysis.ico" />','<link rel="icon" href="/mh-analysis.ico" />\n<link rel="preconnect" href="https://widget.mfbcdn.net" crossorigin />',1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/runtime-fixes.css')
css = p.read_text(encoding='utf-8')
css += '''\n/* V54.13 Myfxbook calendar: eager display, toolbar cropped, all clicks disabled. */\n.calendarCrop{position:relative!important;overflow:hidden!important;background:#fff!important}.calendarCrop #economicCalendarWidgetV5413{display:block!important;border:0!important;width:100%!important;height:calc(100% + 42px)!important;min-height:300px!important;transform:translateY(-40px)!important;visibility:visible!important;opacity:1!important;pointer-events:none!important;user-select:none!important;background:#fff!important}.calendarCrop .economicCalendarLocal{display:none!important}\n'''
p.write_text(css, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# Version stamps.
# -----------------------------------------------------------------------------
for path, pat, val in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.13"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.13"'),
]:
    q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
    if n!=1: raise SystemExit('V54.13 version stamp failed '+path)
    q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.13\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.13</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.12','Version: V.54.13'); p.write_text(z,encoding='utf-8',newline='\n')

# Hard regression guards: fail CI instead of publishing these problems again.
a=Path('web/app.js').read_text(encoding='utf-8')
wa=Path('webview2_host.go').read_text(encoding='utf-8')
html=Path('web/index.html').read_text(encoding='utf-8')
css=Path('web/runtime-fixes.css').read_text(encoding='utf-8')
main=Path('main.go').read_text(encoding='utf-8')
checks=[
 ('WA only clipped edge', 'x:=w-1' in wa and 'only a 1px clipped edge' in wa),
 ('WA exact composer clear', "range.selectNodeContents(box)" in wa and "box.innerHTML=''" in wa),
 ('WA confirmed composer clear', "ack('retry-send')" in wa and "sessionStorage.setItem(sentKey,'1');ack('sent')" in wa),
 ('WA no early 180ms refocus', '180*time.Millisecond' not in wa),
 ('WA retry ack', 'case "retry-send"' in wa),
 ('recent records source', "fetch('/api/records-v2'" in a and 'loadRecentSignalsV5413' in a),
 ('recent latest five', 'recentSession.slice(0,5)' in a),
 ('ticker startup warm', 'warmStartupTickerV5413()' in main and 'refreshTickerV5411()' in main),
 ('calendar exact countries', 'impacts=0,1,2,3&countries=Australia,Belgium,Canada,China,France,Germany,Italy,Japan,Mexico,New%20Zealand,South%20Africa,Spain,Switzerland,United%20Kingdom,United%20States' in html),
 ('calendar toolbar crop', 'translateY(-40px)' in css),
 ('calendar non clickable', 'pointer-events:none' in css),
 ('MH MT5 external sweep', 'func wv2ActivateMT5V5412()' in wa and 'v546HideAllMT5TopLevel()' in wa),
]
for name,ok in checks:
    if not ok: raise SystemExit('Guard failed: '+name)
