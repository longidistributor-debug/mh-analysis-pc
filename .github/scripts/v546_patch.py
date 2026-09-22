from pathlib import Path
import re, runpy

# Start from the verified V54.5 build-time runtime.
runpy.run_path('.github/scripts/v545_patch.py', run_name='__main__')

# 1/2/5) Exact WhatsApp template + release MH Analysis immediately after capture.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
pat=r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl=r'''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null,isSell=sig?.direction==='SELL',dot=sig?(isSell?'🔴':'🟢'):'⚪';
  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${sig?'Signal generated':'No clear edge'}`,'',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,''];
  if(sig){lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d.bestFamily||sig.setupReason||'Best current setup'}`)}
  else{lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`)}
  return lines.join('\\n');
}'''
s,n=re.subn(pat,lambda m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('WhatsApp formatter replacement failed')

# Record/EA fanout must never keep MH Analysis disabled.
s=s.replace("if(d.signal&&!d._sameActiveSignal){await dispatchUniqueSignalV36(d);} // V36_CANONICAL_SIGNAL_FANOUT",
            "if(d.signal&&!d._sameActiveSignal){dispatchUniqueSignalV36(d).catch(e=>console.warn('Background Record/EA handoff failed',e));} // V546_BACKGROUND_FANOUT",1)

# As soon as signal/re-evaluation is rendered, controls are active again. Remaining sends continue in background.
s=s.replace("renderDecision(d,reason,'NEW');", "renderDecision(d,reason,'NEW');busy=false;setBusy(false);",1)
s=s.replace("renderDecision(current,`RE-EVALUATE SIGNAL: ${status}. ${current.explanation}`,'REEVAL');",
            "renderDecision(current,`RE-EVALUATE SIGNAL: ${status}. ${current.explanation}`,'REEVAL');busy=false;setBusy(false);",1)

# Manual WhatsApp: no settings/network wait while busy; sender already queues itself in background.
old="""      try{\n        await refreshBackendSettings();\n        if(backendSettings.has_whatsapp&&!d._sameActiveSignal){\n          setAutoStatus('Sending NEW ANALYZE to WhatsApp…','warn');\n          await sendDecisionWhatsApp(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));\n          setAutoStatus('NEW ANALYZE sent to WhatsApp','good');\n        }else if(d._sameActiveSignal)setAutoStatus('Same signal still active • no new WhatsApp / Record / MT5 pending','warn');\n        else setAutoStatus('Manual analysis ready • WhatsApp Signal Link not saved','warn');\n      }catch(e){setAutoStatus(`WhatsApp send failed • ${e.message||e}`,'bad')}"""
new="""      try{\n        if(!d._sameActiveSignal){sendDecisionWhatsApp(d,'NEW ANALYSIS','Signal generated');setAutoStatus('NEW ANALYZE queued to WhatsApp','good')}\n        else setAutoStatus('Same signal still active • no duplicate signal sent','warn');\n      }catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}"""
if old in s: s=s.replace(old,new,1)
old2="""      try{\n        await refreshBackendSettings();\n        if(backendSettings.has_whatsapp){\n          setAutoStatus('Sending RE-EVALUATE to WhatsApp…','warn');\n          await sendDecisionWhatsApp(current,'RE-EVALUATE',status);\n          setAutoStatus('RE-EVALUATE sent to WhatsApp','good');\n        }else setAutoStatus('Re-evaluation ready • WhatsApp number not saved','warn');\n      }catch(e){setAutoStatus(`WhatsApp send failed • ${e.message||e}`,'bad')}"""
new2="""      try{sendDecisionWhatsApp(current,'RE-EVALUATE','Signal generated');setAutoStatus('RE-EVALUATE queued to WhatsApp','good')}catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}"""
if old2 in s: s=s.replace(old2,new2,1)

# 4) Calendar: show cached calendar instantly, then refresh with a short network budget.
calpat=r"async function loadEconomicCalendarV545\(\)\{.*?\n\}"
calrepl=r'''function renderEconomicCalendarV546(root,days){if(!root||!Array.isArray(days)||!days.length)return false;root.innerHTML=days.map(day=>`<div class="calDayV545"><div class="calDateV545">${escapeCalendarTextV545(day.label||day.date)}</div>${(day.events||[]).map(ev=>{const imp=String(ev.impact||'').toLowerCase();return `<div class="calEventV545"><span class="calTimeV545">${escapeCalendarTextV545(ev.time)}</span><span class="calCountryV545">${escapeCalendarTextV545(ev.country)}</span><span class="calImpactV545 ${imp}">${escapeCalendarTextV545(ev.impact)}</span><span class="calTitleV545">${escapeCalendarTextV545(ev.title)}</span></div>`}).join('')}</div>`).join('');return true}
async function loadEconomicCalendarV545(){
  const root=$('#economicCalendarLocal');if(!root)return;
  try{const cached=JSON.parse(localStorage.getItem('mh-economic-calendar-v546')||'null');if(cached?.days)renderEconomicCalendarV546(root,cached.days)}catch(e){}
  const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),1500);
  try{const r=await fetch('/api/economic-calendar',{cache:'no-store',signal:ctl.signal});const j=await r.json();if(!r.ok)throw new Error('Calendar unavailable');const days=Array.isArray(j.days)?j.days:[];if(days.length){renderEconomicCalendarV546(root,days);try{localStorage.setItem('mh-economic-calendar-v546',JSON.stringify({days,at:Date.now()}))}catch(e){}}else if(!root.children.length)root.innerHTML='<div class="calendarLoading">No upcoming calendar events.</div>'}catch(e){if(!root.children.length)root.innerHTML='<div class="calendarLoading">Calendar retrying…</div>';setTimeout(loadEconomicCalendarV545,1800)}finally{clearTimeout(kill)}
}'''
s,n=re.subn(calpat,lambda m:calrepl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('calendar frontend replacement failed')

# 5) Moving bar: force immediate paint + repeated startup refreshes without tab switching.
startup='setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,180000);'
startup2="setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();requestAnimationFrame(()=>refreshPublicTicker());setTimeout(refreshPublicTicker,250);setTimeout(refreshPublicTicker,900);setTimeout(refreshPublicTicker,1800);setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,180000);"
if startup not in s: raise SystemExit('startup refresh anchor missing')
s=s.replace(startup,startup2,1)
p.write_text(s,encoding='utf-8',newline='\n')

# Calendar backend total wait <= ~1.4 sec.
p=Path('calendar3d.go'); s=p.read_text(encoding='utf-8'); s=s.replace('Timeout: 2 * time.Second','Timeout: 1200 * time.Millisecond',1).replace('2200*time.Millisecond','1400*time.Millisecond',1); p.write_text(s,encoding='utf-8',newline='\n')

# 3) MT5: hide every terminal top-level window before/during embedding; only child embed may be shown.
p=Path('mt5_embed_v36.go'); s=p.read_text(encoding='utf-8')
insert=r'''
func v546HideAllMT5TopLevel(){
    cb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{if hwnd==0||hwnd==hostHWND{return 1};var pid uint32;chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)));image:=v36ProcessImage(pid);if image=="terminal64.exe"||image=="terminal.exe"{parent,_,_:=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide)}};return 1});chEnumWindows.Call(cb,0)
}
func v546EmbedOnlyMT5(wait time.Duration) bool {
    deadline:=time.Now().Add(wait)
    for time.Now().Before(deadline){v546HideAllMT5TopLevel();if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if v36EmbedMT5(hwnd){return true}};time.Sleep(20*time.Millisecond)}
    return false
}
'''
anchor='\nfunc chEnsureMT5TerminalV36() error {'
if anchor not in s: raise SystemExit('MT5 anchor missing')
s=s.replace(anchor,insert+anchor,1)
s=s.replace('if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if !v54EmbedMT5WithRetry(hwnd,4*time.Second)', 'v546HideAllMT5TopLevel();if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if !v546EmbedOnlyMT5(4*time.Second)',1)
s=s.replace('if !v545EmbedStartedMT5Fast(18*time.Second)', 'if !v546EmbedOnlyMT5(18*time.Second)',1)
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('webview2_host.go'); s=p.read_text(encoding='utf-8'); s=s.replace('func wv2ShowMT5() {\n\twv2SetDesiredView(4)', 'func wv2ShowMT5() {\n\tv546HideAllMT5TopLevel()\n\twv2SetDesiredView(4)',1); p.write_text(s,encoding='utf-8',newline='\n')

# V54.6 stamps.
for path,pat,repl in [('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.6"'),('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.6"')]:
    q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,repl,z,count=1); 
    if n!=1: raise SystemExit('version stamp failed '+path)
    q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.6\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.6</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.5','Version: V.54.6'); p.write_text(z,encoding='utf-8',newline='\n')

# Regression guards.
a=Path('web/app.js').read_text(encoding='utf-8'); mt5=Path('mt5_embed_v36.go').read_text(encoding='utf-8')
checks=[('exact WA title','*MH ANALYSIS SIGNAL*' in a),('no Action','*Action:*' not in a),('background fanout','V546_BACKGROUND_FANOUT' in a),('UI release new',"renderDecision(d,reason,'NEW');busy=false;setBusy(false);" in a),('UI release reeval','busy=false;setBusy(false);' in a),('calendar cache','mh-economic-calendar-v546' in a),('ticker startup refresh','setTimeout(refreshPublicTicker,250)' in a),('MT5 embed only','v546EmbedOnlyMT5' in mt5 and 'v546HideAllMT5TopLevel' in mt5)]
for name,ok in checks:
    if not ok: raise SystemExit('Guard failed: '+name)
