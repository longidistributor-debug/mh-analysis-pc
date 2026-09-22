from pathlib import Path
import re, runpy

# Keep the V54.8 runtime, then change only the user-confirmed remaining regressions.
runpy.run_path('.github/scripts/v548_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) Exact WhatsApp template with REAL newlines (not literal \\n text).
#    Labels/headline bold; values normal. Re-Evaluate gets its own status + reason.
# 2) Recent Signals: current signal must appear immediately and persist across reloads.
# 3) Ticker: paint cached values first and start its fetch before heavy chart work.
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
  if(isRe){lines.push('',`*Reason:* ${reason}`)}
  lines.push('',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,'');
  if(sig){
    const dot=sig.direction==='SELL'?'🔴':'🟢';
    lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);
  }else{
    lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`);
  }
  return lines.join('\n');
}"""
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.9 WhatsApp template replacement failed')

# Persist/restore Recent Signals and always include the current latest row.
s=s.replace('const recentSession=[];',"const recentSession=(()=>{try{const x=JSON.parse(localStorage.getItem('mh-recent-signals-stable')||'[]');return Array.isArray(x)?x.slice(0,6):[]}catch(e){return[]}})();",1)
s=s.replace("if(recentSession.length>6)recentSession.length=6;\n  // V36: Records are written only by the canonical V2 fanout.","if(recentSession.length>6)recentSession.length=6;\n  try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(e){}\n  // V36: Records are written only by the canonical V2 fanout.",1)
s=s.replace('const previous=recentSession.slice(1,5);','const previous=recentSession.slice(0,5);',1)

# Ticker stable cache helpers. They make old values visible immediately while fresh values refresh.
ticker_helper="""
function applyTickerCacheV549(j){
  try{
    if(Number.isFinite(Number(j?.gold_usd))&&Number(j.gold_usd)>0){publicGoldPrice=Number(j.gold_usd);$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`}
    if(Number.isFinite(Number(j?.btc_usd)))$('#tickerBTC').textContent=`$${Number(j.btc_usd).toLocaleString(undefined,{maximumFractionDigits:2})}`;
    if(Number.isFinite(Number(j?.eth_usd)))$('#tickerETH').textContent=`$${Number(j.eth_usd).toLocaleString(undefined,{maximumFractionDigits:2})}`;
    if(Number.isFinite(Number(j?.eurusd)))$('#tickerEURUSD').textContent=Number(j.eurusd).toFixed(5);
    if(Number.isFinite(Number(j?.usdjpy)))$('#tickerUSDJPY').textContent=Number(j.usdjpy).toFixed(3);
    if(Number.isFinite(Number(j?.gbpusd)))$('#tickerGBPUSD').textContent=Number(j.gbpusd).toFixed(5);
    if(Number.isFinite(Number(j?.gbpjpy)))$('#tickerGBPJPY').textContent=Number(j.gbpjpy).toFixed(3);
    const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
    document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>{if(vals[i])el.textContent=vals[i]});
  }catch(e){}
}
function primeTickerV549(){
  try{const c=JSON.parse(localStorage.getItem('mh-public-ticker-stable')||'null');if(c)applyTickerCacheV549(c)}catch(e){}
  try{const cached=(candleCache.get('XAUUSD|15m')||restoreCandles('XAUUSD|15m')||[]);if(cached.length&&(!$('#tickerGold').textContent||$('#tickerGold').textContent==='—')){$('#tickerGold').textContent=`$${fmt(Number(cached.at(-1).c))}`}}catch(e){}
  const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
  document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>el.textContent=vals[i]||'—');
}
"""
idx=s.find('async function refreshPublicTicker(){')
if idx<0: raise SystemExit('public ticker function missing')
s=s[:idx]+ticker_helper+s[idx:]
needle="if(r.ok){\n      if(Number.isFinite(Number(j.gold_usd))"
if needle not in s: raise SystemExit('public ticker success anchor missing')
s=s.replace(needle,"if(r.ok){\n      try{localStorage.setItem('mh-public-ticker-stable',JSON.stringify(j));applyTickerCacheV549(j)}catch(e){}\n      if(Number.isFinite(Number(j.gold_usd))",1)

startup='primeMovingTickerV547();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();'
if startup not in s: raise SystemExit('V54.8 startup anchor missing')
s=s.replace(startup,'primeMovingTickerV547();primeTickerV549();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();',1)
startup2='primeMovingTickerV547();primeTickerV549();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
s=s.replace(startup2,'renderRecentSignals();'+startup2,1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# 2) WhatsApp background: keep a FULL-SIZE renderer clipped to a 1px edge so
# WhatsApp stays in desktop-chat layout while remaining invisible to the user.
# Always navigate the exact saved Signal Link for every queued send.
# -----------------------------------------------------------------------------
p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8')
pat=r"func wv2ParkWhatsAppV547\(\) \{.*?\n\}"
park='''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
\tif w<1 { w=1 }; if h<1 { h=1 }
\tx:=w-1; if x<0 { x=0 }
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Resize()
}'''
s,n=re.subn(pat,lambda _m:park,s,count=1,flags=re.S)
if n!=1: raise SystemExit('WhatsApp park function replacement failed')

navpat=r"\twv2ParkWhatsAppV547\(\)\n\t_ = wv2Whatsapp.Show\(\)\n\twv2Whatsapp.Focus\(\)\n\tif wv2WAResolvedTarget == target \{\n\t\tpostMessage\(hostHWND, wmWhatsAppEvalV54, token, 0\)\n\t\} else \{\n\t\twv2Whatsapp.Navigate\(target\)\n\t\}"
navnew='''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2WAResolvedTarget = ""
\twv2Whatsapp.Navigate(target)'''
s,n=re.subn(navpat,lambda _m:navnew,s,count=1)
if n!=1: raise SystemExit('WhatsApp navigation block replacement failed')

s=s.replace('\twv2ParkWhatsAppV547()\n\t_ = wv2Whatsapp.Show()\n\twv2Whatsapp.Focus()\n\twv2Whatsapp.Eval(script)',
            '\twv2ParkWhatsAppV547()\n\t_ = wv2Whatsapp.Show()\n\twv2Whatsapp.Eval(script)',1)
p.write_text(s,encoding='utf-8',newline='\n')

# -----------------------------------------------------------------------------
# 3) Calendar: public embedded calendar is immediate primary display and does
# not depend on the user's FCS key. Local endpoint remains background fallback.
# -----------------------------------------------------------------------------
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
old='<div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>'
new='<iframe id="economicCalendarImmediateV549" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar" loading="eager"></iframe><div id="economicCalendarLocal" class="economicCalendarLocal" style="display:none"></div>'
if old not in s: raise SystemExit('calendar local div anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('web/runtime-fixes.css')
css=p.read_text(encoding='utf-8')
css+='''\n/* V54.9 immediate public calendar */\n#economicCalendarImmediateV549{display:block!important;width:100%!important;height:340px!important;border:0!important;background:#fff!important;transform:translateY(-30px)!important}#economicCalendarLocal{display:none!important}\n'''
p.write_text(css,encoding='utf-8',newline='\n')

for path,pat,val in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.9"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.9"')]:
 q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
 if n!=1: raise SystemExit('version stamp failed '+path)
 q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.9\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.9</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.8','Version: V.54.9'); p.write_text(z,encoding='utf-8',newline='\n')

a=Path('web/app.js').read_text(encoding='utf-8'); wa=Path('webview2_host.go').read_text(encoding='utf-8'); html=Path('web/index.html').read_text(encoding='utf-8')
checks=[
 ('real newline join', "return lines.join('\\n');" in a and "return lines.join('\\\\n');" not in a),
 ('exact heading/status', '`*MH ANALYSIS SIGNAL*`' in a and "statusValue=isRe?'Re-Evaluate'" in a),
 ('reeval reason', '`*Reason:* ${reason}`' in a),
 ('recent persistent immediate', 'mh-recent-signals-stable' in a and 'renderRecentSignals();primeMovingTickerV547()' in a),
 ('ticker persistent immediate', 'mh-public-ticker-stable' in a and 'primeTickerV549();refreshPublicTicker()' in a),
 ('WA full desktop layout hidden', 'uintptr(w), uintptr(h)' in wa and 'wv2Whatsapp.Resize()' in wa),
 ('WA always exact target navigate', 'wv2WAResolvedTarget = ""' in wa and 'wv2Whatsapp.Navigate(target)' in wa),
 ('WA no retry focus steal', 'wv2Whatsapp.Focus()\n\twv2Whatsapp.Eval(script)' not in wa),
 ('calendar public eager', 'economicCalendarImmediateV549' in html and 'loading="eager"' in html),
]
for name,ok in checks:
 if not ok: raise SystemExit('Guard failed: '+name)
