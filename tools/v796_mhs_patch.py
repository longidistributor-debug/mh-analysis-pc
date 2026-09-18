from pathlib import Path
import re


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 exact match, found {n}')
    return text.replace(old, new, 1)


def regex_once(text, pattern, repl, label):
    out, n = re.subn(pattern, lambda _m: repl, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 regex match, found {n}')
    return out


def between(text, start, end):
    a = text.index(start)
    b = text.index(end, a)
    return text[a:b]

# -----------------------------------------------------------------------------
# V79.6 MH-S is deliberately based on the historical V79.6-era MH Analysis
# source.  The WhatsApp backend/native sender is NOT rewritten here.
# -----------------------------------------------------------------------------
main_p = Path('main.go')
main = main_p.read_text(encoding='utf-8')
sender_http_before = between(main, 'func sendWhatsappHandler', '// --- Native Windows host')
sender_native_before = between(main, 'func processWhatsAppQueue', 'func runHost')

# Dark native host background + delayed reveal. The host window is already
# created hidden in V79.6. Keep it hidden while the embedded local page paints,
# then reveal maximized. This avoids the white/gray startup flash without
# touching analysis or WhatsApp delivery.
main = replace_once(
    main,
    'var ole32 = syscall.NewLazyDLL("ole32.dll")',
    'var ole32 = syscall.NewLazyDLL("ole32.dll")\nvar gdi32 = syscall.NewLazyDLL("gdi32.dll")',
    'add gdi32',
)
main = replace_once(
    main,
    'var pCoInitializeEx = ole32.NewProc("CoInitializeEx")',
    'var pCoInitializeEx = ole32.NewProc("CoInitializeEx")\nvar pGetStockObject = gdi32.NewProc("GetStockObject")',
    'add stock brush proc',
)
main = replace_once(
    main,
    '\twmWhatsAppClick  = 0x8004\n',
    '\twmWhatsAppClick  = 0x8004\n\twmShowReady      = 0x8005\n',
    'ready window message',
)
main = replace_once(
    main,
    '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)''',
    '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\t// The window itself is still hidden here. The local page is tiny and\n\t\t// embedded, so give WebView2 a brief paint window and reveal only then.\n\t\ttime.AfterFunc(450*time.Millisecond, func() { postMessage(hostHWND, wmShowReady, 0, 0) })''',
    'delayed host reveal',
)
main = replace_once(
    main,
    '\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: 6, LpszClassName: cls}',
    '\tbgBrush, _, _ := pGetStockObject.Call(4) // BLACK_BRUSH: no white startup flash\n\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: bgBrush, LpszClassName: cls}',
    'dark native background',
)
main = replace_once(
    main,
    'uintptr(unsafe.Pointer(wstr("MH Analysis"))), wsOverlapped, 0, 0, 1280, 820',
    'uintptr(unsafe.Pointer(wstr("MH Analysis • V79.6 MH-S"))), wsOverlapped, 0, 0, 1280, 820',
    'window title',
)
main = replace_once(
    main,
    '''\tcase wmWhatsAppClick:\n\t\tclickWhatsAppSend()\n\t\treturn 0\n\tcase wmSize:''',
    '''\tcase wmWhatsAppClick:\n\t\tclickWhatsAppSend()\n\t\treturn 0\n\tcase wmShowReady:\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)\n\t\tresizeWebViews()\n\t\treturn 0\n\tcase wmSize:''',
    'ready reveal handler',
)

# Prove the historical WhatsApp delivery rail itself is byte-for-byte untouched.
if between(main, 'func sendWhatsappHandler', '// --- Native Windows host') != sender_http_before:
    raise SystemExit('V79.6 WhatsApp HTTP sender changed unexpectedly')
if between(main, 'func processWhatsAppQueue', 'func runHost') != sender_native_before:
    raise SystemExit('V79.6 native WhatsApp queue/click sender changed unexpectedly')
main_p.write_text(main, encoding='utf-8')

# -----------------------------------------------------------------------------
# HTML: visible V79.6 MH-S label, RSI panel, LOW/MEDIUM/HIGH calendar.
# -----------------------------------------------------------------------------
index_p = Path('web/index.html')
html = index_p.read_text(encoding='utf-8')
html = replace_once(
    html,
    '<div class="version">v80.0 NATIVE WEBVIEW2 • ADAPTIVE SMC/ICT</div>',
    '<div class="version">V79.6 MH-S</div>',
    'visible version label',
)
html = replace_once(
    html,
    '<div class="priceCanvasWrap"><div id="priceChart" class="lightweightChart"></div><div id="chartEmpty" class="chartEmpty">Save API key to load chart</div></div>',
    '<div class="priceCanvasWrap"><div id="priceChart" class="lightweightChart"></div><div id="chartEmpty" class="chartEmpty">Save API key to load chart</div></div>\n        <div class="rsiCanvasWrap"><div class="rsiLabel" id="rsiLabel">RSI (14) —</div><canvas id="rsiCanvas"></canvas></div>',
    'RSI panel',
)
html = replace_once(
    html,
    '<iframe src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>',
    '<iframe id="economicCalendarFrame" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>',
    'all-impact economic calendar',
)
html = replace_once(
    html,
    '<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.0/dist/lightweight-charts.standalone.production.js"></script>',
    '<script src="/lightweight-charts.standalone.production.js"></script>',
    'local chart library',
)
index_p.write_text(html, encoding='utf-8')

# -----------------------------------------------------------------------------
# JS: keep V79.6 analysis engine; change only requested presentation/scheduling
# and WhatsApp message formatting/wiring. The native WhatsApp sender is untouched.
# -----------------------------------------------------------------------------
app_p = Path('web/app.js')
js = app_p.read_text(encoding='utf-8')

message_fn = r'''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||(action==='RE-EVALUATE'?d?.originalSignal:null),isSell=sig?.direction==='SELL',dot=sig?(isSell?'🔴':'🟢'):'⚪';
  const rr=(()=>{if(!sig)return null;const risk=Math.abs(Number(sig.entry)-Number(sig.sl)),reward=Math.abs(Number(sig.tp2)-Number(sig.entry));return risk>0&&Number.isFinite(reward)?reward/risk:null})();
  const when=new Date().toLocaleString();
  const title=action==='RE-EVALUATE'?'*MH ANALYSIS RE-EVALUATE*':'*MH ANALYSIS SIGNAL*';
  const lines=[title,`*Pair:* ${symbol}`,`*Timeframe:* ${timeframe}`,`*Time:* ${when}`,''];
  if(action==='RE-EVALUATE'){
    if(sig){
      lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${fmt(sig.entry)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*SL:* ${fmt(sig.sl)}`);
    }else lines.push('*Signal:* ⚪ NO ACTIVE SIGNAL');
    lines.push(`*BUY Score:* ${d?.buyScore??'—'}`,`*SELL Score:* ${d?.sellScore??'—'}`,`*Status:* ${status||d?.explanation||'Re-evaluation completed.'}`);
    return lines.join('\n');
  }
  if(sig){
    const confirms=(Array.isArray(d?._ranked)?d._ranked.slice(0,3).flatMap(x=>Array.isArray(x?.reasons)?x.reasons:[]):[]).filter(Boolean).slice(0,5);
    const warnings=Array.isArray(d?.warnings)?d.warnings.filter(Boolean).join(' • '):(d?.warning||'None');
    lines.push(
      `*Signal:* ${dot} ${sig.direction}`,
      `*Entry:* ${fmt(sig.entry)}`,
      `*TP1:* ${fmt(sig.tp1)}`,
      `*TP2:* ${fmt(sig.tp2)}`,
      `*SL:* ${fmt(sig.sl)}`,
      `*RR:* ${Number.isFinite(rr)?`1:${rr.toFixed(2)}`:'—'}`,
      `*Score:* ${sig.score}/100`,
      `*Current Setup:* ${d?.bestFamily||sig.setupReason||'Best current setup'}`,
      `*Analysis:* ${d?.explanation||'Current setup confirmed by the analysis engine.'}`,
      `*Confirmations:* ${confirms.length?confirms.join(' • '):'See current analysis confirmations.'}`,
      `*Warnings:* ${warnings}`,
      `*Status:* ${status||'Signal generated'}`
    );
  }else{
    const warnings=Array.isArray(d?.warnings)?d.warnings.filter(Boolean).join(' • '):(d?.warning||'None');
    lines.push(
      '*Signal:* ⚪ NO TRADE',
      `*BUY Score:* ${d?.buyScore??'—'}`,
      `*SELL Score:* ${d?.sellScore??'—'}`,
      `*Reason:* ${d?.explanation||'No statistically clear directional edge on the fresh analysis.'}`,
      `*Warnings:* ${warnings}`,
      `*Status:* ${status||'No clear edge'}`
    );
  }
  return lines.join('\n');
}'''
js = regex_once(
    js,
    r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}\nasync function sendDecisionWhatsApp",
    message_fn + '\nasync function sendDecisionWhatsApp',
    'organized WhatsApp formatter',
)

scheduler = r'''function setAutoStatus(text,kind=''){const el=$('#autoSignalStatus');if(!el)return;el.textContent=text;el.className=`autoSignalStatus ${kind}`.trim()}
function actionLabel(a){return a==='REEVAL'?'RE-EVALUATE':'NEW ANALYZE'}
let fixedClockLastTick=0,fixedPhaseAnalysisKey='',fixedReevalDoneKey='',fixedNewDoneKey='';
function hhmm(ms){const d=new Date(ms);return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`}
function fixedClockInfo(ms=Date.now()){
  const d=new Date(ms),minute=d.getMinutes(),phase=Math.floor(minute/15)+1,startMinute=Math.floor(minute/15)*15;
  const start=new Date(d);start.setMinutes(startMinute,0,0);
  const startMs=start.getTime(),reevalMs=startMs+5*60*1000,endMs=startMs+15*60*1000;
  const key=`${start.getFullYear()}-${start.getMonth()+1}-${start.getDate()}-${start.getHours()}-${startMinute}`;
  return{phase,key,startMs,reevalMs,endMs,startLabel:hhmm(startMs),endLabel:hhmm(endMs)};
}
function stopAutoTimers(){if(autoSignalTimer){clearInterval(autoSignalTimer);autoSignalTimer=null}if(autoCountdownTimer){clearInterval(autoCountdownTimer);autoCountdownTimer=null}}
function updateAutoButton(){
  const b=$('#autoSignalToggle');if(!b)return;
  b.className=`autoSignalToggle ${autoSignalEnabled?'on':'off'}`;
  if(!autoSignalEnabled){b.textContent='Get Signal: OFF';setAutoStatus('Manual only');return}
  const now=Date.now(),p=fixedClockInfo(now),canReeval=fixedPhaseAnalysisKey===p.key&&fixedReevalDoneKey!==p.key&&now<p.reevalMs;
  const nextAt=canReeval?p.reevalMs:p.endMs,nextAction=canReeval?'REEVAL':'NEW';
  autoSignalNextAt=nextAt;autoSignalNextAction=nextAction;
  const left=Math.max(0,nextAt-now),m=Math.floor(left/60000),sec=Math.floor((left%60000)/1000);
  b.textContent=`Get Signal: ON • ${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  const phaseText=`1H Phase ${p.phase} • ${p.startLabel}–${p.endLabel}`;
  if(autoSignalRunning)setAutoStatus(`${phaseText} • Running ${actionLabel(autoSignalNextAction)}…`,'warn');
  else setAutoStatus(`${phaseText} • Next ${actionLabel(nextAction)} in ${m}:${String(sec).padStart(2,'0')}`,'good');
}
function scheduleAutoAction(){if(autoSignalEnabled)updateAutoButton()}
function noteCurrentPhaseAnalysis(){if(!autoSignalEnabled)return;fixedPhaseAnalysisKey=fixedClockInfo().key;updateAutoButton()}
async function autoSendAndSchedule(d,action,status=''){
  if(!autoSignalEnabled)return;
  try{setAutoStatus(`Sending ${action.toLowerCase()}…`,'warn');await sendDecisionWhatsApp(d,action,status)}
  catch(e){setAutoStatus(e.message,'bad')}
  finally{updateAutoButton()}
}
async function setAutoSignalEnabled(on){
  if(on){
    await refreshBackendSettings();
    // WhatsApp delivery is independent from the market-data access key.
    if(!backendSettings.has_whatsapp){
      autoSignalEnabled=false;localStorage.setItem(STORAGE_AUTO,'0');stopAutoTimers();updateAutoButton();
      setAutoStatus('Set WhatsApp link/profile first','bad');
      const saved=await openWhatsappSettingsPrompt();if(!saved)return;await refreshBackendSettings();
    }
  }
  autoSignalEnabled=!!on;localStorage.setItem(STORAGE_AUTO,autoSignalEnabled?'1':'0');
  stopAutoTimers();
  if(!autoSignalEnabled){autoSignalNextAt=0;fixedClockLastTick=0;updateAutoButton();return}
  const now=Date.now(),p=fixedClockInfo(now);
  fixedClockLastTick=now;fixedPhaseAnalysisKey='';fixedReevalDoneKey='';fixedNewDoneKey='';
  autoSignalTimer=setInterval(fixedClockTick,250);autoCountdownTimer=setInterval(updateAutoButton,1000);updateAutoButton();
  // If Get Signal is enabled essentially on a fixed boundary, do not miss the
  // new phase event. Enabling later in the phase never creates a private timer.
  if(now-p.startMs<1500){fixedNewDoneKey=p.key;setTimeout(()=>runScheduledAutoAction('NEW',p.key),80)}
}
async function runScheduledAutoAction(action,phaseKey=''){
  if(!autoSignalEnabled)return;
  const p=fixedClockInfo();if(phaseKey&&p.key!==phaseKey)return;
  if(autoSignalRunning||busy){setTimeout(()=>runScheduledAutoAction(action,phaseKey),500);return}
  autoSignalRunning=true;autoSignalNextAction=action;
  try{if(action==='REEVAL')await executeReevaluate(true);else await executeNewAnalysis(true)}
  finally{autoSignalRunning=false;updateAutoButton()}
}
function fixedClockTick(){
  if(!autoSignalEnabled)return;
  const now=Date.now();if(!fixedClockLastTick){fixedClockLastTick=now;updateAutoButton();return}
  if(now<fixedClockLastTick-1000){fixedClockLastTick=now;fixedPhaseAnalysisKey='';fixedReevalDoneKey='';fixedNewDoneKey='';updateAutoButton();return}
  const last=fixedClockLastTick,p=fixedClockInfo(now);fixedClockLastTick=now;
  // A phase boundary always owns NEW ANALYZE. Manual actions never cancel it.
  if(p.startMs>last&&p.startMs<=now&&fixedNewDoneKey!==p.key){
    fixedNewDoneKey=p.key;fixedPhaseAnalysisKey='';fixedReevalDoneKey='';
    runScheduledAutoAction('NEW',p.key);updateAutoButton();return;
  }
  // The fixed +5m slot is valid only when NEW ANALYZE completed in this phase.
  if(p.reevalMs>last&&p.reevalMs<=now&&fixedPhaseAnalysisKey===p.key&&fixedReevalDoneKey!==p.key){
    fixedReevalDoneKey=p.key;runScheduledAutoAction('REEVAL',p.key);
  }
  updateAutoButton();
}'''
js = regex_once(
    js,
    r"function setAutoStatus\(text,kind=''\)\{.*?\nasync function executeNewAnalysis",
    scheduler + '\nasync function executeNewAnalysis',
    'fixed wall-clock scheduler',
)

js = replace_once(
    js,
    "    renderDecision(d,reason,'NEW');\n    if(autoSignalEnabled)await autoSendAndSchedule(d,'NEW ANALYSIS',d.signal?'Signal generated':'No clear edge');",
    "    renderDecision(d,reason,'NEW');\n    if(autoSignalEnabled){noteCurrentPhaseAnalysis();await autoSendAndSchedule(d,'NEW ANALYSIS',d.signal?'Signal generated':'No clear edge')}\n",
    'manual/auto NEW send without timer reset',
)

old_no_active = "  if(!a){if(!fromAuto)showError(`No active ${symbol} ${timeframe} signal. Press NEW ANALYZE first.`);if(autoSignalEnabled){setAutoStatus('No active signal • NEW ANALYZE in 5m','warn');scheduleAutoAction('NEW',AUTO_RETRY_NO_SIGNAL_DELAY)}return null}"
new_no_active = """  if(!a){
    const skipped={signal:null,originalSignal:null,buyScore:'—',sellScore:'—',explanation:`No active ${symbol} ${timeframe} signal exists to re-evaluate.`};
    if(!fromAuto)showError(`No active ${symbol} ${timeframe} signal. Press NEW ANALYZE first.`);
    if(autoSignalEnabled){try{await sendDecisionWhatsApp(skipped,'RE-EVALUATE','NO ACTIVE SIGNAL — nothing to re-evaluate')}catch(e){setAutoStatus(e.message,'bad')}}
    updateAutoButton();return skipped;
  }"""
js = replace_once(js, old_no_active, new_no_active, 'no-active RE-EVALUATE WhatsApp status')

# RSI panel: use screenshot-style 75/30 reference levels, dynamic label, purple line.
lines = js.splitlines()
changed = False
for i, line in enumerate(lines):
    if line.startswith('function drawRsiChart(canvas,arr){'):
        lines[i] = """function drawRsiChart(canvas,arr){if(!canvas)return;const {w,h,d}=canvasSize(canvas),ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);ctx.fillStyle='#050a0d';ctx.fillRect(0,0,w,h);const label=$('#rsiLabel');if(!arr.length){if(label)label.textContent='RSI (14) —';return}const closes=arr.map(x=>x.c),vals=[];for(let i=0;i<closes.length;i++)vals.push(i<14?50:rsi(closes.slice(0,i+1),14));const last=vals.at(-1),y=v=>8*d+(100-v)/100*(h-16*d),x=i=>8*d+i*(w-16*d)/Math.max(1,vals.length-1);[75,30].forEach(v=>{drawLine(ctx,8*d,y(v),w-8*d,y(v),'#b39b16',1*d,[]);ctx.fillStyle='#d6c83b';ctx.font=`${8*d}px Segoe UI`;ctx.fillText(String(v),w-24*d,y(v)-3*d)});ctx.strokeStyle='#9272e5';ctx.lineWidth=1.25*d;ctx.beginPath();vals.forEach((v,i)=>{const xx=x(i),yy=y(v);if(i===0)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy)});ctx.stroke();if(label)label.textContent=`RSI (14) ${last.toFixed(2)}`}"""
        changed = True
        break
if not changed:
    raise SystemExit('RSI draw function not found')
js = '\n'.join(lines) + ('\n' if js.endswith('\n') else '')
js = replace_once(
    js,
    '  renderLoadedMap(arr);\n  renderSignalLevels();',
    "  renderLoadedMap(arr);\n  drawRsiChart($('#rsiCanvas'),arr);\n  renderSignalLevels();",
    'draw RSI with chart data',
)
js = replace_once(
    js,
    "if(!arr.length){empty?.classList.remove('hidden');empty.textContent='No candle data loaded.';candleSeries.setData([]);volumeSeries?.setData([]);return}",
    "if(!arr.length){empty?.classList.remove('hidden');empty.textContent='No candle data loaded.';candleSeries.setData([]);volumeSeries?.setData([]);drawRsiChart($('#rsiCanvas'),[]);return}",
    'clear RSI when chart empty',
)

calendar_js = r'''
let mhCalendarLocalDay='';
function mhLocalDayKey(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function refreshEconomicCalendar(force=false){
  const frame=$('#economicCalendarFrame');if(!frame)return;
  const day=mhLocalDayKey();if(!force&&day===mhCalendarLocalDay)return;mhCalendarLocalDay=day;
  const base=frame.dataset.baseSrc||String(frame.getAttribute('src')||'').replace(/([?&])mhday=[^&]*/g,'');frame.dataset.baseSrc=base;
  frame.src=base+(base.includes('?')?'&':'?')+'mhday='+encodeURIComponent(day);
}
'''
marker = "// v79.6 credentials are stored by native Windows settings dialogs, not editable HTML fields."
js = replace_once(js, marker, calendar_js + '\n' + marker, 'daily calendar watcher functions')
js = replace_once(
    js,
    "setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setTimeout(()=>loadContextChart(),250);",
    "setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();refreshEconomicCalendar(true);setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(()=>refreshEconomicCalendar(false),30000);setTimeout(()=>loadContextChart(),250);window.addEventListener('resize',()=>{const a=candleCache.get(keyFor())||[];if(a.length)drawRsiChart($('#rsiCanvas'),a)});",
    'calendar and RSI resize startup wiring',
)

# Guard the exact requested fixed-clock anchors.
for required in (
    'Math.floor(minute/15)+1',
    'startMs+5*60*1000',
    'startMs+15*60*1000',
    "runScheduledAutoAction('NEW',p.key)",
    "runScheduledAutoAction('REEVAL',p.key)",
    'fixedPhaseAnalysisKey===p.key',
    '*Entry:* ${fmt(sig.entry)}',
    "isSell?'🔴':'🟢'",
    "drawRsiChart($('#rsiCanvas'),arr)",
):
    if required not in js:
        raise SystemExit(f'V79.6 MH-S JS validation missing: {required}')
app_p.write_text(js, encoding='utf-8')

# -----------------------------------------------------------------------------
# CSS: no crop in Market Map, screenshot-like RSI section, responsive layout.
# -----------------------------------------------------------------------------
css_p = Path('web/styles.css')
css = css_p.read_text(encoding='utf-8')
css += r'''

/* V79.6 MH-S requested additions */
.mapStrip{grid-template-columns:minmax(92px,.82fr) repeat(8,minmax(0,1fr)) minmax(132px,1.12fr);overflow:hidden}
.mapMetric,.scoreBox{min-width:0;padding:4px 7px}
.mapMetric small,.scoreBox small{white-space:normal;line-height:1.08;overflow:visible}
.mapMetric b{min-width:0;overflow:visible;text-overflow:clip;font-size:10.5px}
#mapEq{white-space:nowrap;overflow:visible;text-overflow:clip}
.nativeChartShell{min-height:650px}
.priceCanvasWrap{min-height:390px;flex:1 1 auto}
.rsiCanvasWrap{height:118px;flex:0 0 118px;position:relative;border-top:1px solid #1b453b;background:#050a0d;overflow:hidden}
.rsiCanvasWrap canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.rsiLabel{position:absolute;z-index:2;left:9px;top:6px;color:#b9c8c4;font-size:9px;pointer-events:none}
.calendarCrop{height:170px;overflow:hidden;border-radius:6px;background:#050a0d}
.calendarCrop iframe{display:block;width:100%;height:230px;border:0;background:#050a0d}
@media(max-width:1100px){
  .mapStrip{grid-template-columns:78px repeat(8,minmax(0,1fr)) 112px;overflow:hidden}
  .mapMetric,.scoreBox{padding:3px 4px}.mapMetric small,.scoreBox small{font-size:6.5px}.mapMetric b,.scoreBox div{font-size:9px}
}
@media(max-width:900px){
  .appHeader{grid-template-columns:1fr auto}.bismillahArea{display:none}.mainGrid{grid-template-columns:1fr}.leftCol,.centerCol,.rightCol{grid-column:1/-1}.rightCol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.rightCol>.recentPanel{grid-column:1/-1}.marketToolbar{height:auto;grid-template-columns:1fr}.pairGroup,.capGrid,.tfGroup{grid-column:1/-1}.tfGroup{grid-template-columns:auto auto 1fr auto}.nativeChartShell{min-height:560px}.priceCanvasWrap{min-height:340px}
}
'''
css_p.write_text(css, encoding='utf-8')

print('Applied V79.6 MH-S requested-only patch; historical WhatsApp sender preserved exactly')
