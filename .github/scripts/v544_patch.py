from pathlib import Path
import re
import runpy

# Reapply the already working V54.3 build-time patch first.
runpy.run_path('.github/scripts/v543_patch.py', run_name='__main__')

# ---------------- 1) FAST LOCAL ECONOMIC CALENDAR ----------------
p=Path('calendar3d.go')
s=p.read_text(encoding='utf-8')
# Fetch this/next week concurrently and cap total wait.
old='''\tcli := &http.Client{Timeout: 8 * time.Second}\n\traw := append(fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json"), fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json")...)'''
new='''\tcli := &http.Client{Timeout: 3 * time.Second}\n\ttype calResult struct{ events []calendarFeedEvent }\n\tch := make(chan calResult, 2)\n\tgo func(){ ch <- calResult{events: fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json")} }()\n\tgo func(){ ch <- calResult{events: fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json")} }()\n\traw := make([]calendarFeedEvent,0,64)\n\ttimer := time.NewTimer(3200*time.Millisecond)\n\tdefer timer.Stop()\n\tfor i:=0;i<2;i++ {\n\t\tselect {\n\t\tcase x := <-ch: raw = append(raw, x.events...)\n\t\tcase <-timer.C: i=2\n\t\t}\n\t}'''
if old not in s: raise SystemExit('calendar fetch anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

# Replace slow external iframe with the app's local calendar renderer.
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('<div><div class="brandName">MH ANALYSIS</div><div class="version">V.34 (Late - CH Shaukat Ali)</div></div>', '<div><div class="brandName">MH ANALYSIS</div><div class="version">CH Shaukat Ali</div></div>',1)
old_cal='''        <div class="calendarCrop">\n          <iframe src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>\n        </div>'''
new_cal='''        <div class="calendarCrop">\n          <div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>\n        </div>'''
if old_cal not in s: raise SystemExit('calendar iframe anchor missing')
s=s.replace(old_cal,new_cal,1)
p.write_text(s,encoding='utf-8',newline='\n')

# ---------------- 2/4/5) UI NON-BLOCKING + EXACT WHATSAPP + EA INDEPENDENT ----------------
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# Exact requested WhatsApp template. No Action line, no extra appended status line.
pat=r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl=r'''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||(action==='RE-EVALUATE'?d?.originalSignal:null),isSell=sig?.direction==='SELL',dot=sig?(isSell?'🔴':'🟢'):'⚪';
  const statusText=status||(sig?'Signal generated':'No clear edge');
  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusText}`,'',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,''];
  if(sig){lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d.bestFamily||sig.setupReason||'Best current setup'}`)}
  else{lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*BUY Score:* ${d?.buyScore??'—'}`,`*SELL Score:* ${d?.sellScore??'—'}`,`*Reason:* ${d?.explanation||'No statistically clear directional edge on the fresh analysis.'}`)}
  return lines.join('\\n');
}'''
s,n=re.subn(pat,lambda m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('WhatsApp formatter replacement failed')

# New Analysis must never wait for Records/EA handoff. The handoff itself still runs.
s=s.replace("if(d.signal&&!d._sameActiveSignal){await dispatchUniqueSignalV36(d);} // V36_CANONICAL_SIGNAL_FANOUT",
            "if(d.signal&&!d._sameActiveSignal){dispatchUniqueSignalV36(d).catch(e=>console.warn('Background Record/EA handoff failed',e));} // V544 NON-BLOCKING FANOUT",1)

# Make EA handoff independent of Records: EA request starts immediately; Records cannot gate it.
start=s.find('async function dispatchUniqueSignalV36(d){')
end=s.find('\nasync function executeNewAnalysis(',start)
if start<0 or end<0: raise SystemExit('dispatchUniqueSignalV36 block missing')
new_dispatch=r'''async function dispatchUniqueSignalV36(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const signalId=`MH${Date.now()}_${symbol}_${timeframe}`;
  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);
  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);
  const eaPayload={signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:Number(sig.tp1),lot:0.02,expiry:0};
  const recordPayload={signal_id:signalId,symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2),score:Number(sig.score)||0,setup:d.bestFamily||sig.setupReason||'',action:'NEW'};
  const eaPromise=fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(eaPayload)})
    .then(async r=>{let j={};try{j=await r.json()}catch(_){};if(!r.ok)throw new Error(j.error||`EA bridge HTTP ${r.status}`);return j})
    .catch(e=>{console.warn('EA pending handoff failed',e);return null});
  const recordPromise=fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordPayload)})
    .then(async r=>{let j={};try{j=await r.json()}catch(_){};if(!r.ok)throw new Error(j.error||`Records HTTP ${r.status}`);return j})
    .catch(e=>{console.warn('Record capture failed',e);return null});
  try{prepareMT5SignalV796(d,'NEW')}catch(_){}
  const [ea,record]=await Promise.all([eaPromise,recordPromise]);
  if(ea)setAutoStatus(`MT5 pending sent • ${pending}`,'good');
  return {record,ea,signal_id:signalId};
}'''
s=s[:start]+new_dispatch+s[end:]

# Local economic calendar renderer; loads immediately and refreshes every 3 minutes.
calendar_js=r'''
function escapeCalendarTextV544(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadEconomicCalendarV544(){
  const root=$('#economicCalendarLocal');if(!root)return;
  const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),3800);
  try{
    const r=await fetch('/api/economic-calendar',{cache:'no-store',signal:ctl.signal});
    const j=await r.json();if(!r.ok)throw new Error('Calendar unavailable');
    const days=Array.isArray(j.days)?j.days:[];
    if(!days.length){root.innerHTML='<div class="calendarLoading">No upcoming calendar events.</div>';return;}
    root.innerHTML=days.map(day=>`<div class="calDayV544"><div class="calDateV544">${escapeCalendarTextV544(day.label||day.date)}</div>${(day.events||[]).map(ev=>{const imp=String(ev.impact||'').toLowerCase();return `<div class="calEventV544"><span class="calTimeV544">${escapeCalendarTextV544(ev.time)}</span><span class="calCountryV544">${escapeCalendarTextV544(ev.country)}</span><span class="calImpactV544 ${imp}">${escapeCalendarTextV544(ev.impact)}</span><span class="calTitleV544">${escapeCalendarTextV544(ev.title)}</span></div>`}).join('')}</div>`).join('');
  }catch(e){root.innerHTML='<div class="calendarLoading">Calendar retrying…</div>';setTimeout(loadEconomicCalendarV544,2500)}finally{clearTimeout(kill)}
}
'''
insert_at=s.find("$('#openKey').onclick=openNativeApiSettings;")
if insert_at<0: raise SystemExit('calendar JS insertion anchor missing')
s=s[:insert_at]+calendar_js+s[insert_at:]
s=s.replace('setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);',
            'setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV544();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV544,180000);',1)
p.write_text(s,encoding='utf-8',newline='\n')

# Calendar styling.
p=Path('web/runtime-fixes.css')
css=p.read_text(encoding='utf-8')
css += '''\n/* V54.4 fast local economic calendar */\n.economicCalendarLocal{height:100%;overflow:auto;padding:6px 8px;font-size:11px;line-height:1.25}.calendarLoading{padding:12px;color:#9fb3ad}.calDayV544{margin-bottom:8px}.calDateV544{font-weight:700;color:#d9e5e1;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.08)}.calEventV544{display:grid;grid-template-columns:62px 38px 54px 1fr;gap:5px;padding:4px 0;align-items:start}.calTimeV544{color:#aab9b4}.calCountryV544{font-weight:700}.calImpactV544{font-size:9px;text-transform:uppercase}.calImpactV544.high{color:#ff6675}.calImpactV544.medium,.calImpactV544.med{color:#f1c85a}.calImpactV544.low{color:#77d99d}.calTitleV544{color:#e6efec;min-width:0}\n'''
p.write_text(css,encoding='utf-8',newline='\n')

# ---------------- 2/5) EA MAILBOX MUST NOT BLOCK UI ----------------
p=Path('ea_signal_bridge.go')
s=p.read_text(encoding='utf-8')
old=r'''\teaPublishMu.Lock(); defer eaPublishMu.Unlock()
\tdst:=filepath.Join(dir,"signal.txt")
\tdeadline:=time.Now().Add(6*time.Second)
\tfor {
\t\t_,statErr:=os.Stat(dst)
\t\tif os.IsNotExist(statErr) { break }
\t\tif statErr!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":"could not inspect EA mailbox: "+statErr.Error()}); return }
\t\tif time.Now().After(deadline) { w.WriteHeader(http.StatusConflict); _=json.NewEncoder(w).Encode(map[string]any{"error":"previous MT5 signal is still waiting for EA consumption; new signal was not overwritten"}); return }
\t\ttime.Sleep(100*time.Millisecond)
\t}'''.replace('\\t','\t').replace('\\n','\n')
new=r'''\teaPublishMu.Lock(); defer eaPublishMu.Unlock()
\tdst:=filepath.Join(dir,"signal.txt")
\t// V54.4: never block New Analysis/Re-Evaluate waiting for EA consumption.
\t// Latest generated signal is published immediately; if the EA is attached it consumes signal.txt and places the pending order.
\t_ = os.Remove(dst)'''.replace('\\t','\t').replace('\\n','\n')
if old not in s: raise SystemExit('EA 6-second mailbox wait anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

# ---------------- SINGLE WHATSAPP LINK LOCK ----------------
p=Path('main.go')
s=p.read_text(encoding='utf-8')
s=s.replace('\tWhatsAppLink2 string `json:"whatsapp_link2"`\n','',1)
s=s.replace('strings.TrimSpace(v.WhatsAppLink) != "" || strings.TrimSpace(v.WhatsAppLink2) != ""','strings.TrimSpace(v.WhatsAppLink) != ""')
s=s.replace(', "whatsapp_link2": v.WhatsAppLink2','')
s=re.sub(r'\n\t\tif p, ok := m\["whatsapp_link2"\]; ok \{.*?\n\t\t\}', '', s, count=1, flags=re.S)
s=s.replace('saved := []string{strings.TrimSpace(v.WhatsAppLink), strings.TrimSpace(v.WhatsAppLink2)}','saved := []string{strings.TrimSpace(v.WhatsAppLink)}',1)
s=s.replace('targets := make([]string, 0, 2)','targets := make([]string, 0, 1)',1)
p.write_text(s,encoding='utf-8',newline='\n')

# ---------------- 3/6) FIXED SUBTITLE + CURRENT VERSION UNDER TITLE-BAR AREA ----------------
p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8')
s=s.replace('wv2WAProcessing        bool\n)', 'wv2WAProcessing        bool\n\twv2VersionLabel        uintptr\n)',1)
# After app host is created, place a native label at top-right toolbar, under the system minimize/maximize area.
anchor='''\tbtnAnalysis, _, _ = chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSChild|chWSVisible,8,7,140,30,hostHWND,idAnalysis,inst,0)'''
repl='''\twv2VersionLabel, _, _ = chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("STATIC"))),uintptr(unsafe.Pointer(chWstr("Version: V.54.4"))),chWSChild|chWSVisible,1040,14,150,22,hostHWND,0,inst,0)\n'''+anchor
if anchor not in s: raise SystemExit('native toolbar anchor missing')
s=s.replace(anchor,repl,1)
# Reposition label responsively.
s=s.replace('if chSignalLinkBtn != 0 { chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1) }', 'if chSignalLinkBtn != 0 { chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1) }\n\tif wv2VersionLabel != 0 { x:=w-165; if x<760 { x=760 }; chMoveWindow.Call(wv2VersionLabel, uintptr(x), 13, 155, 22, 1) }',1)
s=s.replace('uintptr(unsafe.Pointer(chWstr("MH Analysis"))), chWSOverlapped', 'uintptr(unsafe.Pointer(chWstr("MH Analysis — Version: V.54.4"))), chWSOverlapped',1)
p.write_text(s,encoding='utf-8',newline='\n')

# ---------------- V54.4 VERSION STAMPS ----------------
for path,pat,repl in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.4"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.4"')]:
 q=Path(path);z=q.read_text(encoding='utf-8');z,n=re.subn(pat,repl,z,count=1)
 if n!=1: raise SystemExit('version stamp failed '+path)
 q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.4\n',encoding='ascii')
p=Path('web/index.html');s=p.read_text(encoding='utf-8');s=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.4</div>',s,count=1);p.write_text(s,encoding='utf-8',newline='\n')

# Guards
checks={
 'calendar local': 'economicCalendarLocal' in Path('web/index.html').read_text(encoding='utf-8'),
 'calendar 3 sec': 'Timeout: 3 * time.Second' in Path('calendar3d.go').read_text(encoding='utf-8'),
 'no EA 6 sec': 'deadline:=time.Now().Add(6*time.Second)' not in Path('ea_signal_bridge.go').read_text(encoding='utf-8'),
 'EA independent': 'const eaPromise=fetch' in Path('web/app.js').read_text(encoding='utf-8'),
 'fanout nonblocking': 'V544 NON-BLOCKING FANOUT' in Path('web/app.js').read_text(encoding='utf-8'),
 'exact WA status': '🤝 *Status:*' in Path('web/app.js').read_text(encoding='utf-8'),
 'no WA action': '*Action:*' not in Path('web/app.js').read_text(encoding='utf-8'),
 'single WA link': 'WhatsAppLink2' not in Path('main.go').read_text(encoding='utf-8'),
 'subtitle': 'CH Shaukat Ali</div>' in Path('web/index.html').read_text(encoding='utf-8'),
 'native version': 'Version: V.54.4' in Path('webview2_host.go').read_text(encoding='utf-8'),
}
for k,v in checks.items():
 if not v: raise SystemExit('Guard failed: '+k)
