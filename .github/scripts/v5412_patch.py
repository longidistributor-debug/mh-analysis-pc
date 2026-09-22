from pathlib import Path
import re, runpy

# Build on the last V54.11 runtime, then fix only the three reported regressions.
runpy.run_path('.github/scripts/v5411_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) WhatsApp: NEW ANALYZE and RE-EVALUATE must always queue/send their status
#    independently of Record/EA de-duplication. Keep the exact organized template.
# -----------------------------------------------------------------------------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')

pat = r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}"
repl = """function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null;
  const isRe=action==='RE-EVALUATE';
  const statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge');
  const reason=isRe?(d?.explanation||status||d?.bestFamily||sig?.setupReason||'Market re-evaluation'):'';
  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];
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
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.12 WhatsApp template replacement failed')

# Auto mode previously suppressed WhatsApp whenever Record/EA marked the signal as
# the same active signal. That is the wrong coupling: Record/EA stays deduplicated,
# but WhatsApp must still report every scheduled NEW/RE-EVALUATE result.
old = "if(d?._sameActiveSignal){setAutoStatus('Same signal still active • no new signal sent','warn');scheduleFixedAfterDecision(d,action,triggerAt);return;}"
new = "if(d?._sameActiveSignal){setAutoStatus('Same signal still active • WhatsApp update will still be sent • no duplicate Record / MT5 pending','warn');}"
if old not in s:
    raise SystemExit('V54.12 auto WhatsApp de-dup gate anchor missing')
s = s.replace(old, new, 1)

# Manual NEW ANALYZE: always await the background queue call. Do not suppress it
# just because the trading fanout found the same active signal.
pat = r"try\{\n\s*if\(!d\._sameActiveSignal\)\{sendDecisionWhatsApp\(d,'NEW ANALYSIS','Signal generated'\);setAutoStatus\('NEW ANALYZE queued to WhatsApp','good'\)\}\n\s*else setAutoStatus\('Same signal still active • no duplicate signal sent','warn'\);\n\s*\}catch\(e\)\{setAutoStatus\(`WhatsApp queue failed • \$\{e\.message\|\|e\}`,'bad'\)\}"
repl = """try{
        await sendDecisionWhatsApp(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));
        if(d._sameActiveSignal)setAutoStatus('NEW ANALYZE queued to WhatsApp • same signal active • no duplicate Record / MT5 pending','good');
        else setAutoStatus('NEW ANALYZE queued to WhatsApp','good');
      }catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}"""
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.12 manual NEW WhatsApp anchor missing')

# Manual RE-EVALUATE was fire-and-forget, so failures became silent promise
# rejections. Await the queue request while the trading UI remains released.
old = "try{sendDecisionWhatsApp(current,'RE-EVALUATE','Signal generated');setAutoStatus('RE-EVALUATE queued to WhatsApp','good')}catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}"
new = "try{await sendDecisionWhatsApp(current,'RE-EVALUATE',status);setAutoStatus('RE-EVALUATE queued to WhatsApp','good')}catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}"
if old not in s:
    raise SystemExit('V54.12 manual RE-EVALUATE WhatsApp anchor missing')
s = s.replace(old, new, 1)

# -----------------------------------------------------------------------------
# 2) Ticker + Calendar: do not start a blank moving strip. Read the cross-restart
#    disk cache first, paint values, then start motion/network refresh. Persist the
#    calendar in the same disk cache so it can paint immediately on next launch.
# -----------------------------------------------------------------------------
pat = r"async function loadPersistentUICacheV5411\(\)\{.*?\n\}"
repl = """async function loadPersistentUICacheV5411(){
  try{
    const r=await fetch('/api/ui-cache',{cache:'no-store'}); if(!r.ok)return false;
    const j=await r.json();
    if(j?.ticker)applyTickerCacheV549(j.ticker);
    if(Array.isArray(j?.calendar)&&j.calendar.length){
      const root=$('#economicCalendarLocal');
      if(root&&typeof renderEconomicCalendarV546==='function')renderEconomicCalendarV546(root,j.calendar);
    }
    if(Array.isArray(j?.recent)){
      recentSession.splice(0,recentSession.length,...j.recent.slice(0,6));
      renderRecentSignals();
    }
    return true;
  }catch(e){return false}
}"""
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.12 persistent UI cache loader anchor missing')

calendar_save = "try{localStorage.setItem('mh-economic-calendar-stable',JSON.stringify({days,at:Date.now()}))}catch(e){}"
if calendar_save not in s:
    raise SystemExit('V54.12 calendar success persistence anchor missing')
s = s.replace(calendar_save, calendar_save + "\n      savePersistentUICacheV5411({calendar:days});", 1)

startup = 'loadPersistentUICacheV5411();renderRecentSignals();primeMovingTickerV547();primeTickerV549();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
startup2 = 'await loadPersistentUICacheV5411();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
if startup not in s:
    raise SystemExit('V54.12 startup/cache ordering anchor missing')
s = s.replace(startup, startup2, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# Persist calendar alongside ticker/recent in the existing disk-backed UI cache.
p = Path('ui_cache_v5411.go')
s = p.read_text(encoding='utf-8')
old = '\tTicker map[string]any `json:"ticker,omitempty"`\n\tRecent []any          `json:"recent,omitempty"`'
new = '\tTicker   map[string]any `json:"ticker,omitempty"`\n\tRecent   []any          `json:"recent,omitempty"`\n\tCalendar []any          `json:"calendar,omitempty"`'
if old not in s:
    raise SystemExit('V54.12 UI cache struct anchor missing')
s = s.replace(old, new, 1)
anchor = '''\t\tif raw, ok := patch["recent"]; ok {
\t\t\tvar v []any
\t\t\tif json.Unmarshal(raw, &v) == nil {
\t\t\t\tif len(v) > 6 {
\t\t\t\t\tv = v[:6]
\t\t\t\t}
\t\t\t\tc.Recent = v
\t\t\t}
\t\t}'''
addition = anchor + '''
\t\tif raw, ok := patch["calendar"]; ok {
\t\t\tvar v []any
\t\t\tif json.Unmarshal(raw, &v) == nil && len(v) > 0 {
\t\t\t\tif len(v) > 3 { v = v[:3] }
\t\t\t\tc.Calendar = v
\t\t\t}
\t\t}'''
if anchor not in s:
    raise SystemExit('V54.12 UI cache recent handler anchor missing')
s = s.replace(anchor, addition, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# Replace the third-party iframe with the already-existing fast local calendar
# renderer. A remote iframe can never guarantee immediate values; local disk cache can.
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
iframe = '<iframe id="economicCalendarWidgetV5411" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar" loading="eager"></iframe>'
local = '<div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>'
if iframe not in s:
    raise SystemExit('V54.12 V54.11 calendar iframe anchor missing')
s = s.replace(iframe, local, 1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/runtime-fixes.css')
css = p.read_text(encoding='utf-8')
css += '''\n/* V54.12: local cached calendar paints immediately; never wait on a remote iframe. */\n.calendarCrop{background:transparent!important;overflow:auto!important}.economicCalendarLocal{display:block!important;width:100%!important;height:100%!important;max-height:340px!important;visibility:visible!important;opacity:1!important}\n'''
p.write_text(css, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 3) MH MT5: label it correctly and never expose WhatsApp while MT5 is starting.
#    Keep MH Analysis on top until the MT5 HWND is successfully embedded, then
#    atomically switch to the embedded child. No standalone terminal is shown.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')
s = s.replace('"MT5 System"', '"MH MT5"')

if 'wmMT5ReadyV5412' not in s:
    anchor = '\twmWhatsAppRefocusV5411     = 0x8F57'
    if anchor not in s:
        raise SystemExit('V54.12 MT5 message constant anchor missing')
    s = s.replace(anchor, anchor + '\n\twmMT5ReadyV5412           = 0x8F58', 1)

pat = r"func wv2ShowMT5\(\) \{.*?\n\}"
repl = '''func wv2ActivateMT5V5412() {
\twv2SetDesiredView(4)
\twv2HideAll()
\twv2ParkWhatsAppV547()
\tif chMT5Wnd == 0 { postMessage(hostHWND, wmSwitchAnalysis, 0, 0); return }
\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\tchMoveWindow.Call(chMT5Wnd,0,uintptr(barH),uintptr(w),uintptr(h),1)
\tchShowWindow.Call(chMT5Wnd,chSWShow)
\tchSetWindowPos.Call(chMT5Wnd,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\tchFocusEmbeddedBrowser(chMT5Wnd)
}

func wv2ShowMT5() {
\tv546HideAllMT5TopLevel()
\twv2SetDesiredView(4)
\t// Do not uncover the parked WhatsApp renderer while MT5 is being prepared.
\t// Keep the MH Analysis surface on top until the terminal has become a child HWND.
\twv2ParkWhatsAppV547()
\tif wv2Container != 0 && wv2Browser != nil {
\t\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\t\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\t\tchShowWindow.Call(wv2Container,chSWShow); _=wv2Browser.Show()
\t\tchSetWindowPos.Call(wv2Container,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\t\twv2Browser.Resize(); wv2Browser.Focus()
\t}
\tgo func() {
\t\tif err := chEnsureMT5TerminalV36(); err != nil {
\t\t\tmessageBox(hostHWND, err.Error(), "MH MT5", 0x10)
\t\t\tpostMessage(hostHWND, wmSwitchAnalysis, 0, 0)
\t\t\treturn
\t\t}
\t\tpostMessage(hostHWND, wmMT5ReadyV5412, 0, 0)
\t}()
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.12 MT5 show function replacement failed')

handler_anchor = '''\tcase wmWhatsAppRefocusV5411:
\t\twv2ParkWhatsAppV547(); wv2RestoreDesiredFocusV5411(); return 0'''
handler_new = handler_anchor + '''
\tcase wmMT5ReadyV5412:
\t\twv2ActivateMT5V5412(); return 0'''
if handler_anchor not in s:
    raise SystemExit('V54.12 MT5 ready handler anchor missing')
s = s.replace(handler_anchor, handler_new, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# Version stamps.
# -----------------------------------------------------------------------------
for path, pat, val in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.12"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.12"'),
]:
    q = Path(path); z = q.read_text(encoding='utf-8'); z, n = re.subn(pat, val, z, count=1)
    if n != 1: raise SystemExit('V54.12 version stamp failed ' + path)
    q.write_text(z, encoding='utf-8', newline='\n')
Path('VERSION').write_text('V.54.12\n', encoding='ascii')
p = Path('web/index.html'); z = p.read_text(encoding='utf-8'); z = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.12</div>', z, count=1); p.write_text(z, encoding='utf-8', newline='\n')
p = Path('webview2_host.go'); z = p.read_text(encoding='utf-8').replace('Version: V.54.11', 'Version: V.54.12'); p.write_text(z, encoding='utf-8', newline='\n')

# Hard guards: fail the build rather than silently reintroducing the exact issues.
a = Path('web/app.js').read_text(encoding='utf-8')
wa = Path('webview2_host.go').read_text(encoding='utf-8')
html = Path('web/index.html').read_text(encoding='utf-8')
cache = Path('ui_cache_v5411.go').read_text(encoding='utf-8')
checks = [
    ('WA organized heading/status', '`*MH ANALYSIS SIGNAL*`' in a and '`🤝 *Status:* ${statusValue}`' in a),
    ('WA same-signal still sends', 'WhatsApp update will still be sent' in a and 'scheduleFixedAfterDecision(d,action,triggerAt);return;' not in a),
    ('WA manual NEW awaited', "await sendDecisionWhatsApp(d,'NEW ANALYSIS'" in a),
    ('WA manual RE-EVALUATE awaited', "await sendDecisionWhatsApp(current,'RE-EVALUATE',status)" in a),
    ('ticker disk cache awaited before movement', 'await loadPersistentUICacheV5411();renderRecentSignals();primeTickerV549();primeMovingTickerV547()' in a),
    ('calendar disk cache frontend', 'savePersistentUICacheV5411({calendar:days})' in a and 'j?.calendar' in a),
    ('calendar disk cache backend', 'Calendar []any' in cache and 'patch["calendar"]' in cache),
    ('calendar local renderer restored', 'id="economicCalendarLocal"' in html and 'economicCalendarWidgetV5411' not in html),
    ('MH MT5 label', '"MH MT5"' in wa and '"MT5 System"' not in wa),
    ('MT5 no WhatsApp exposure while starting', 'wv2ActivateMT5V5412' in wa and 'wmMT5ReadyV5412' in wa and 'Keep the MH Analysis surface on top' in wa),
]
for name, ok in checks:
    if not ok: raise SystemExit('Guard failed: ' + name)
