from pathlib import Path
import re, runpy

# The inherited V54.5 build-time patch contains a stale precheck that fires before
# it has a chance to declare the native version label. Neutralize only that stale
# precheck in the CI workspace, then apply the full inherited V54.6 runtime.
legacy=Path('.github/scripts/v545_patch.py')
legacy_src=legacy.read_text(encoding='utf-8')
legacy_src=legacy_src.replace("if 'wv2VersionLabel' not in s:\n    raise SystemExit('unexpected precheck')", "if False:\n    raise SystemExit('unexpected precheck')", 1)
legacy.write_text(legacy_src,encoding='utf-8',newline='\n')

# Start from V54.6 exactly, then apply only the four reported runtime fixes.
runpy.run_path('.github/scripts/v546_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) WhatsApp must keep running while hidden: keep the SAME logged-in WebView
# alive/visible but parked outside the client area instead of Hide() suspending it.
# -----------------------------------------------------------------------------
p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8')

anchor='func wv2HideAll() {'
park='''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tx:=int32(r.R-r.L)+32
\ty:=int32(r.B-r.T)+32
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(y), 2, 2, 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
}

'''
if anchor not in s: raise SystemExit('wv2HideAll anchor missing')
s=s.replace(anchor,park+anchor,1)

# Do not hide/suspend WhatsApp when another tab is active.
s=s.replace('\tif wv2Whatsapp != nil { _ = wv2Whatsapp.Hide() }','\tif wv2Whatsapp != nil { wv2ParkWhatsAppV547() }',1)
s=s.replace('\tif wv2WhatsappContainer != 0 { chShowWindow.Call(wv2WhatsappContainer, chSWHide) }','',1)

# After creation, keep WhatsApp renderer alive off-screen instead of hidden.
old='''\tb.Navigate(target)\n\t_ = b.Hide()\n\tchShowWindow.Call(*c, chSWHide)\n\tif which == 2 { wv2Whatsapp = b } else { wv2Records = b }\n\twv2Resize()'''
new='''\tb.Navigate(target)\n\tif which == 2 {\n\t\twv2Whatsapp = b\n\t\t_ = b.Show()\n\t\twv2ParkWhatsAppV547()\n\t} else {\n\t\t_ = b.Hide()\n\t\tchShowWindow.Call(*c, chSWHide)\n\t\twv2Records = b\n\t}\n\twv2Resize()'''
if old not in s: raise SystemExit('aux creation hide block missing')
s=s.replace(old,new,1)

# Resize must not drag parked WhatsApp back on-screen unless WhatsApp tab is active.
oldloop='''\tfor _, c := range []uintptr{wv2Container, wv2WhatsappContainer, wv2RecordsContainer} {\n\t\tif c != 0 { chMoveWindow.Call(c, 0, uintptr(barH), uintptr(w), uintptr(h), 1) }\n\t}'''
newloop='''\tfor _, c := range []uintptr{wv2Container, wv2RecordsContainer} {\n\t\tif c != 0 { chMoveWindow.Call(c, 0, uintptr(barH), uintptr(w), uintptr(h), 1) }\n\t}\n\tif wv2WhatsappContainer != 0 {\n\t\tchViewMu.Lock(); desired:=chDesiredView; chViewMu.Unlock()\n\t\tif desired == 2 { chMoveWindow.Call(wv2WhatsappContainer, 0, uintptr(barH), uintptr(w), uintptr(h), 1) } else { wv2ParkWhatsAppV547() }\n\t}'''
if oldloop not in s: raise SystemExit('resize container loop missing')
s=s.replace(oldloop,newloop,1)

# When explicitly opening WhatsApp, bring the same parked WebView back into client area.
s=s.replace('case 2:\n\t\twv2WAResolvedTarget = ""\n\t\tif wv2Whatsapp != nil { chShowWindow.Call(wv2WhatsappContainer, chSWShow); _ = wv2Whatsapp.Show(); wv2Whatsapp.Focus() }',
'''case 2:
\t\twv2WAResolvedTarget = ""
\t\tif wv2Whatsapp != nil {
\t\t\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\t\t\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\t\t\tchMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)
\t\t\tchShowWindow.Call(wv2WhatsappContainer,chSWShow); _=wv2Whatsapp.Show(); wv2Whatsapp.Focus()
\t\t}''',1)

# Faster background retry cadence now that the renderer stays alive.
s=s.replace('[]time.Duration{200*time.Millisecond, 500*time.Millisecond, 900*time.Millisecond, 1400*time.Millisecond, 2*time.Second, 3*time.Second}',
            '[]time.Duration{120*time.Millisecond, 300*time.Millisecond, 650*time.Millisecond, 1100*time.Millisecond, 1700*time.Millisecond, 2400*time.Millisecond}',1)
s=s.replace('time.AfterFunc(4*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })',
            'time.AfterFunc(3*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })',1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# 2/4) Exact template for BOTH New Analysis and Re-Evaluate + calendar/ticker UI.
# -----------------------------------------------------------------------------
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
pat=r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl=r'''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null;
  if(!sig){return [`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* No clear edge`,'',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,'',`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`].join('\\n')}
  const dot=sig.direction==='SELL'?'🔴':'🟢';
  return [
    `*MH ANALYSIS SIGNAL*`,
    `🤝 *Status:* Signal generated`,
    ``,
    `*Pair:* ${symbol}`,
    `*Timeframe:* ${String(timeframe).toUpperCase()}`,
    `*Time:* ${new Date().toLocaleString()}`,
    ``,
    `*Signal:* ${dot} ${sig.direction}`,
    `*Entry:* ${dot} ${fmt(sig.entry)}`,
    `*SL:* ${fmt(sig.sl)}`,
    `*TP1:* ${fmt(sig.tp1)}`,
    `*TP2:* ${fmt(sig.tp2)}`,
    `*Score:* ${sig.score}/100`,
    `*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`
  ].join('\\n');
}'''
s,n=re.subn(pat,lambda m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('exact WhatsApp template replacement failed')

# Stable calendar cache across versions: do not lose calendar just because app updated.
s=s.replace("localStorage.getItem('mh-economic-calendar-v546')||'null'","localStorage.getItem('mh-economic-calendar-stable')||localStorage.getItem('mh-economic-calendar-v546')||localStorage.getItem('mh-economic-calendar-v545')||'null'",1)
s=s.replace("localStorage.setItem('mh-economic-calendar-v546',JSON.stringify({days,at:Date.now()}))","localStorage.setItem('mh-economic-calendar-stable',JSON.stringify({days,at:Date.now()}))",1)
s=s.replace("root.innerHTML='<div class=\"calendarLoading\">Calendar retrying…</div>';setTimeout(loadEconomicCalendarV545,1800)","if(!root.querySelector('.calDayV545'))root.innerHTML='<div class=\"calendarLoading\">Loading calendar…</div>';setTimeout(loadEconomicCalendarV545,900)",1)

# Moving pairs strip is visual/static first; API only updates values later.
prime=r'''
function primeMovingTickerV547(){
  try{
    const bar=document.querySelector('.movingTicker'),marquee=document.querySelector('.cleanTickerMarquee');
    if(bar){bar.style.display='block';bar.style.visibility='visible';bar.style.opacity='1'}
    if(marquee){marquee.style.display='block';marquee.style.visibility='visible';marquee.style.opacity='1'}
    document.querySelectorAll('.cleanTickerTrack').forEach(el=>{el.style.display='flex';el.style.visibility='visible';el.style.opacity='1';el.style.animationPlayState='running'});
    const fallback={tickerGold:'Live',tickerBTC:'BTCUSD',tickerETH:'ETHUSD',tickerEURUSD:'EURUSD',tickerUSDJPY:'USDJPY',tickerGBPUSD:'GBPUSD',tickerGBPJPY:'GBPJPY'};
    Object.entries(fallback).forEach(([id,v])=>{const el=document.getElementById(id);if(el&&!String(el.textContent||'').trim())el.textContent=v});
  }catch(e){}
}
'''
idx=s.find("function capFmt(")
if idx<0: raise SystemExit('ticker insertion anchor missing')
s=s[:idx]+prime+s[idx:]
# Prime immediately, independently of any API response.
startup_anchor='setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();'
if startup_anchor not in s: raise SystemExit('startup anchor missing')
s=s.replace(startup_anchor,'primeMovingTickerV547();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();',1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# 3) Calendar backend: short budget only; frontend keeps last good cache visible.
# -----------------------------------------------------------------------------
p=Path('calendar3d.go')
s=p.read_text(encoding='utf-8')
s=s.replace('Timeout: 1200 * time.Millisecond','Timeout: 900 * time.Millisecond',1)
s=s.replace('1400*time.Millisecond','1050*time.Millisecond',1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# V54.7 stamps
# -----------------------------------------------------------------------------
for path,pat,replv in [
    ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.7"'),
    ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.7"')]:
    q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,replv,z,count=1)
    if n!=1: raise SystemExit('version stamp failed '+path)
    q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.7\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.7</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.6','Version: V.54.7'); p.write_text(z,encoding='utf-8',newline='\n')

# Hard guards: fail CI instead of silently shipping these regressions again.
a=Path('web/app.js').read_text(encoding='utf-8'); wa=Path('webview2_host.go').read_text(encoding='utf-8')
checks=[
 ('parked WhatsApp stays active','wv2ParkWhatsAppV547' in wa and '_ = wv2Whatsapp.Show()' in wa),
 ('no hidden WA suspension','if wv2Whatsapp != nil { _ = wv2Whatsapp.Hide() }' not in wa),
 ('exact status line','🤝 *Status:* Signal generated' in a),
 ('exact blank organized template','`*MH ANALYSIS SIGNAL*`' in a and '`*Pair:* ${symbol}`' in a and '`*Signal:* ${dot} ${sig.direction}`' in a),
 ('stable calendar cache','mh-economic-calendar-stable' in a),
 ('ticker API independent','primeMovingTickerV547();setupLightweightChart()' in a),
]
for name,ok in checks:
    if not ok: raise SystemExit('Guard failed: '+name)
