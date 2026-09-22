from pathlib import Path
import re, runpy

# Build from the verified V54.7 runtime, then touch only the four reported regressions.
runpy.run_path('.github/scripts/v547_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) Restore the original seamless ticker loop. Do not manipulate track layout
# from JS; the original CSS two-copy marquee already loops continuously.
# -----------------------------------------------------------------------------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')
pat = r"function primeMovingTickerV547\(\)\{.*?\n\}"
repl = '''function primeMovingTickerV547(){
  try{
    const bar=document.querySelector('.movingTicker');
    if(bar){bar.style.visibility='visible';bar.style.opacity='1'}
  }catch(e){}
}'''
s, n = re.subn(pat, repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('ticker prime replacement failed')

# -----------------------------------------------------------------------------
# 2) Exact WhatsApp template: labels bold, values normal. Re-evaluation uses
# Status: Re-Evaluate and a separate Reason line before Pair.
# -----------------------------------------------------------------------------
pat = r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl = r'''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null;
  const isRe=action==='RE-EVALUATE';
  const statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge');
  const reason=isRe?(d?.explanation||status||d?.bestFamily||sig?.setupReason||'Market re-evaluation'):'';
  const lines=[`*MH ANALYSIS SIGNAL*`,`*Status:* ${statusValue}`];
  if(isRe){lines.push('',`*Reason:* ${reason}`)}
  lines.push('',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,'');
  if(sig){
    const dot=sig.direction==='SELL'?'🔴':'🟢';
    lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);
  }else{
    lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`);
  }
  return lines.join('\\n');
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('WhatsApp exact template replacement failed')

# Calendar should show cache instantly; network gets enough time to actually succeed.
s = s.replace("const kill=setTimeout(()=>ctl.abort(),1500);", "const kill=setTimeout(()=>ctl.abort(),3200);", 1)
s = s.replace("setTimeout(loadEconomicCalendarV545,900)", "setTimeout(loadEconomicCalendarV545,1500)", 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 2) WhatsApp background navigation/send: keep the SAME logged-in WebView alive
# inside the parent (2x2 bottom-right, not off-screen), focus it only while the
# queue is being processed, then return focus to MH Analysis after confirmed send.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')
old = '''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tx:=int32(r.R-r.L)+32
\ty:=int32(r.B-r.T)+32
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(y), 2, 2, 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
}'''
new = '''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tx:=int32(r.R-r.L)-3
\ty:=int32(r.B-r.T)-3
\tif x<0 { x=0 }; if y<int32(barH) { y=int32(barH) }
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(y), 2, 2, 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
}'''
if old not in s:
    raise SystemExit('V54.7 parked WhatsApp function missing')
s = s.replace(old, new, 1)

anchor = '''\tif wv2WAResolvedTarget == target {
\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, token, 0)
\t} else {
\t\twv2Whatsapp.Navigate(target)
\t}'''
replacement = '''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Focus()
\tif wv2WAResolvedTarget == target {
\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, token, 0)
\t} else {
\t\twv2Whatsapp.Navigate(target)
\t}'''
if anchor not in s:
    raise SystemExit('WhatsApp resolved-target navigation anchor missing')
s = s.replace(anchor, replacement, 1)

s = s.replace('\twv2Whatsapp.Eval(script)', '\twv2ParkWhatsAppV547()\n\t_ = wv2Whatsapp.Show()\n\twv2Whatsapp.Focus()\n\twv2Whatsapp.Eval(script)', 1)

ack_anchor = '''\tif wv2WALastAckStatus == "sent" {
\t\twv2WAResolvedTarget = wv2WAActiveTarget
\t\twv2FinishWhatsAppV54(token)'''
ack_new = '''\tif wv2WALastAckStatus == "sent" {
\t\twv2WAResolvedTarget = wv2WAActiveTarget
\t\twv2FinishWhatsAppV54(token)
\t\tchViewMu.Lock(); desired:=chDesiredView; chViewMu.Unlock()
\t\tif desired == 1 && wv2Browser != nil { wv2Browser.Focus() }'''
if ack_anchor not in s:
    raise SystemExit('WhatsApp sent ACK anchor missing')
s = s.replace(ack_anchor, ack_new, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 3) Calendar backend: keep the fast concurrent design, but stop timing out so
# aggressively that the feed returns temporary unavailable. Cached data is still
# rendered first by the frontend.
# -----------------------------------------------------------------------------
p = Path('calendar3d.go')
s = p.read_text(encoding='utf-8')
s = s.replace('Timeout: 900 * time.Millisecond', 'Timeout: 2500 * time.Millisecond', 1)
s = s.replace('1050*time.Millisecond', '2800*time.Millisecond', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 4) MT5: immediately and repeatedly hide any standalone terminal window while
# waiting for child embedding. Reduce the exposure window from 20ms to 2ms.
# -----------------------------------------------------------------------------
p = Path('mt5_embed_v36.go')
s = p.read_text(encoding='utf-8')
s = s.replace('time.Sleep(20*time.Millisecond)', 'time.Sleep(2*time.Millisecond)', 1)
s = s.replace('time.Sleep(60*time.Millisecond)', 'time.Sleep(2*time.Millisecond)', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# V54.8 stamps.
for path, pat, val in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.8"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.8"'),
]:
    q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
    if n!=1: raise SystemExit('version stamp failed '+path)
    q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.8\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.8</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.7','Version: V.54.8'); p.write_text(z,encoding='utf-8',newline='\n')

# Hard regression guards.
a=Path('web/app.js').read_text(encoding='utf-8')
wa=Path('webview2_host.go').read_text(encoding='utf-8')
mt=Path('mt5_embed_v36.go').read_text(encoding='utf-8')
checks=[
    ('ticker original CSS owns movement', "querySelectorAll('.cleanTickerTrack').forEach" not in a),
    ('new status exact', "statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge')" in a),
    ('reeval reason separate', '`*Reason:* ${reason}`' in a),
    ('labels bold values normal', '`*Pair:* ${symbol}`' in a and '`*Signal:* ${dot} ${sig.direction}`' in a),
    ('WA parked inside client', 'int32(r.R-r.L)-3' in wa and 'wv2Whatsapp.Focus()' in wa),
    ('calendar reliable budget', '2500 * time.Millisecond' in Path('calendar3d.go').read_text(encoding='utf-8')),
    ('MT5 fast hide poll', 'time.Sleep(2*time.Millisecond)' in mt),
]
for name, ok in checks:
    if not ok: raise SystemExit('Guard failed: '+name)
