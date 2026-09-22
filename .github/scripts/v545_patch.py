from pathlib import Path
import re
import runpy

# Start from the exact V54.3 build-time runtime that the user confirmed was sending WhatsApp correctly.
runpy.run_path('.github/scripts/v543_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) WHATSAPP: preserve V54.3 sender, lock exact requested template for BOTH
#    New Analysis and Re-Evaluate. Do not let caller-specific status text change it.
# -----------------------------------------------------------------------------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')
old = "  const statusText=status||(sig?'Signal generated':'No clear edge');"
new = "  const statusText=sig?'Signal generated':'No clear edge';"
if old not in s:
    raise SystemExit('WhatsApp status template anchor missing after V54.3 patch')
s = s.replace(old, new, 1)

# Recent Signals: current generated signal must show immediately (old code hid index 0).
s = s.replace('const previous=recentSession.slice(1,5);', 'const previous=recentSession.slice(0,5);', 1)

# Moving ticker: render cached GOLD immediately before waiting on public endpoints.
anchor = "async function refreshPublicTicker(){\n  try{"
pre = "async function refreshPublicTicker(){\n  try{\n    const cached=(candleCache.get('XAUUSD|15m')||candleCache.get(keyFor())||[]).map(normalizeCandle).filter(Boolean);\n    if(cached.length){publicGoldPrice=Number(cached.at(-1).c);if(Number.isFinite(publicGoldPrice))$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`}\n    const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');\n    document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>{if(vals[i]!=null)el.textContent=vals[i]});\n  }catch(e){}\n  try{"
if anchor not in s:
    raise SystemExit('ticker frontend anchor missing')
s = s.replace(anchor, pre, 1)

# Local fast economic calendar renderer.
calendar_js = r'''
function escapeCalendarTextV545(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadEconomicCalendarV545(){
  const root=$('#economicCalendarLocal');if(!root)return;
  const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),2600);
  try{
    const r=await fetch('/api/economic-calendar',{cache:'no-store',signal:ctl.signal});
    const j=await r.json();if(!r.ok)throw new Error('Calendar unavailable');
    const days=Array.isArray(j.days)?j.days:[];
    if(!days.length){root.innerHTML='<div class="calendarLoading">No upcoming calendar events.</div>';return;}
    root.innerHTML=days.map(day=>`<div class="calDayV545"><div class="calDateV545">${escapeCalendarTextV545(day.label||day.date)}</div>${(day.events||[]).map(ev=>{const imp=String(ev.impact||'').toLowerCase();return `<div class="calEventV545"><span class="calTimeV545">${escapeCalendarTextV545(ev.time)}</span><span class="calCountryV545">${escapeCalendarTextV545(ev.country)}</span><span class="calImpactV545 ${imp}">${escapeCalendarTextV545(ev.impact)}</span><span class="calTitleV545">${escapeCalendarTextV545(ev.title)}</span></div>`}).join('')}</div>`).join('');
  }catch(e){root.innerHTML='<div class="calendarLoading">Calendar retrying…</div>';setTimeout(loadEconomicCalendarV545,1800)}finally{clearTimeout(kill)}
}
'''
insert_at = s.find("$('#openKey').onclick=openNativeApiSettings;")
if insert_at < 0:
    raise SystemExit('calendar JS insertion anchor missing')
s = s[:insert_at] + calendar_js + s[insert_at:]

startup_old = 'setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);'
startup_new = 'setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();refreshPublicTicker();loadEconomicCalendarV545();setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,180000);'
if startup_old not in s:
    raise SystemExit('startup calendar anchor missing')
s = s.replace(startup_old, startup_new, 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 2/3) HEADER + RECORDS SUBTITLE + FAST LOCAL ECONOMIC CALENDAR (no iframe)
# -----------------------------------------------------------------------------
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
s = re.sub(r'<div><div class="brandName">MH ANALYSIS</div><div class="version">[^<]*</div></div>',
           '<div><div class="brandName">MH ANALYSIS</div><div class="version">CH Shaukat Ali</div></div>', s, count=1)
old_cal = '''        <div class="calendarCrop">\n          <iframe src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>\n        </div>'''
new_cal = '''        <div class="calendarCrop">\n          <div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>\n        </div>'''
if old_cal not in s:
    raise SystemExit('economic calendar iframe anchor missing')
s = s.replace(old_cal, new_cal, 1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/records.html')
s = p.read_text(encoding='utf-8')
s = re.sub(r'<div class="recordsVersion">[^<]*</div>', '<div class="recordsVersion">CH Shaukat Ali</div>', s, count=1)
# Keep footer clean/current rather than old embedded V.30/V.34 wording.
s = re.sub(r'<footer class="recordsFooter"><span>.*?</span><span id="lastRefresh">',
           '<footer class="recordsFooter"><span>MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved. • CH Shaukat Ali</span><span id="lastRefresh">', s, count=1)
p.write_text(s, encoding='utf-8', newline='\n')

# Calendar styling.
p = Path('web/runtime-fixes.css')
css = p.read_text(encoding='utf-8')
css += r'''
/* V54.5 fast local economic calendar */
.economicCalendarLocal{height:100%;max-height:235px;overflow:auto;padding:6px 8px;font-size:10px;line-height:1.25}.calendarLoading{padding:12px;color:#9fb3ad}.calDayV545{margin-bottom:8px}.calDateV545{font-weight:700;color:#d9e5e1;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.08)}.calEventV545{display:grid;grid-template-columns:58px 34px 50px 1fr;gap:5px;padding:4px 0;align-items:start}.calTimeV545{color:#aab9b4}.calCountryV545{font-weight:700}.calImpactV545{font-size:8px;text-transform:uppercase}.calImpactV545.high{color:#ff6675}.calImpactV545.medium,.calImpactV545.med{color:#f1c85a}.calImpactV545.low{color:#77d99d}.calTitleV545{color:#e6efec;min-width:0}
'''
p.write_text(css, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 3/5) BACKEND SPEED: calendar and moving ticker external calls run concurrently
#      with tight timeouts instead of serial 8-second waits.
# -----------------------------------------------------------------------------
p = Path('calendar3d.go')
s = p.read_text(encoding='utf-8')
old = '''\tcli := &http.Client{Timeout: 8 * time.Second}\n\traw := append(fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json"), fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json")...)'''
new = '''\tcli := &http.Client{Timeout: 2 * time.Second}\n\ttype calResult struct{ events []calendarFeedEvent }\n\tch := make(chan calResult, 2)\n\tgo func(){ ch <- calResult{events: fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json")} }()\n\tgo func(){ ch <- calResult{events: fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json")} }()\n\traw := make([]calendarFeedEvent,0,64)\n\ttimer := time.NewTimer(2200*time.Millisecond)\n\tdefer timer.Stop()\n\tfor i:=0;i<2;i++ {\n\t\tselect {\n\t\tcase x := <-ch: raw = append(raw, x.events...)\n\t\tcase <-timer.C: i=2\n\t\t}\n\t}'''
if old not in s:
    raise SystemExit('calendar backend anchor missing')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('main.go')
s = p.read_text(encoding='utf-8')
start = s.find('func publicTickerHandler(w http.ResponseWriter, r *http.Request) {')
end = s.find('\nfunc fetchJSON(', start)
if start < 0 or end < 0:
    raise SystemExit('publicTickerHandler block missing')
new_handler = r'''func publicTickerHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	pubMu.Lock()
	if time.Since(pubAt) < 30*time.Second && pubCache != nil {
		c := pubCache
		pubMu.Unlock()
		_ = json.NewEncoder(w).Encode(c)
		return
	}
	pubMu.Unlock()
	type tickerPart map[string]any
	ch := make(chan tickerPart, 3)
	cli := &http.Client{Timeout: 2 * time.Second}
	go func(){
		part:=tickerPart{}
		fetchJSON(cli, "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true", func(v any) {
			if m,ok:=v.(map[string]any);ok {
				if b,ok:=m["bitcoin"].(map[string]any);ok { part["btc_usd"],_=fnum(b["usd"]); part["btc_change_24h"],_=fnum(b["usd_24h_change"]) }
				if e,ok:=m["ethereum"].(map[string]any);ok { part["eth_usd"],_=fnum(e["usd"]); part["eth_change_24h"],_=fnum(e["usd_24h_change"]) }
			}
		}); ch<-part
	}()
	go func(){
		part:=tickerPart{}
		fetchJSON(cli, "https://xaus.com/api/v1/spot", func(v any) { if g:=findNumberByKeys(v,"price","usd","gold","xau");g>0 { part["gold_usd"]=g } }); ch<-part
	}()
	go func(){
		part:=tickerPart{}
		fetchJSON(cli, "https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP", func(v any) {
			if m,ok:=v.(map[string]any);ok { if rates,ok:=m["rates"].(map[string]any);ok {
				eur,_:=fnum(rates["EUR"]);jpy,_:=fnum(rates["JPY"]);gbp,_:=fnum(rates["GBP"])
				if eur>0 {part["eurusd"]=1/eur}; if jpy>0 {part["usdjpy"]=jpy}; if gbp>0 {part["gbpusd"]=1/gbp}
			} }
		}); ch<-part
	}()
	out:=map[string]any{}
	timer:=time.NewTimer(2200*time.Millisecond); defer timer.Stop()
	for i:=0;i<3;i++ { select { case part:=<-ch: for k,v:=range part {out[k]=v}; case <-timer.C: i=3 } }
	pubMu.Lock(); pubAt=time.Now(); if len(out)>0 {pubCache=out} else if pubCache!=nil {out=pubCache}; pubMu.Unlock()
	_ = json.NewEncoder(w).Encode(out)
}'''
s = s[:start] + new_handler + s[end:]
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 7) RECORDS: fresh V54.5 store, so old/pre-saved 1-2 records never reappear.
#    Old file is left untouched for safety but V54.5 no longer reads it.
# -----------------------------------------------------------------------------
p = Path('records_mt5_local.go')
s = p.read_text(encoding='utf-8')
s = s.replace('return filepath.Join(b, "MHAnalysis", "signal-records-v796.json")',
              'return filepath.Join(b, "MHAnalysis", "signal-records-v545.json")', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 8) MT5: hide terminal immediately and embed directly; reduce standalone flash.
# -----------------------------------------------------------------------------
p = Path('mt5_embed_v36.go')
s = p.read_text(encoding='utf-8')
insert = r'''
func v545EmbedStartedMT5Fast(wait time.Duration) bool {
    deadline:=time.Now().Add(wait)
    for time.Now().Before(deadline) {
        if hwnd:=v36FindRunningMT5();hwnd!=0 {
            chShowWindow.Call(hwnd,chSWHide)
            if v36EmbedMT5(hwnd){return true}
        }
        time.Sleep(60*time.Millisecond)
    }
    return false
}
'''
anchor = '\nfunc chEnsureMT5TerminalV36() error {'
if anchor not in s:
    raise SystemExit('MT5 ensure anchor missing')
s = s.replace(anchor, insert + anchor, 1)
s = s.replace('if hwnd:=v36FindRunningMT5();hwnd!=0{if !v54EmbedMT5WithRetry(hwnd,4*time.Second)',
              'if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if !v54EmbedMT5WithRetry(hwnd,4*time.Second)', 1)
s = s.replace('if !v54EmbedMT5WithRetry(0,18*time.Second){return errors.New("MT5 started, but its terminal window could not be embedded after automatic retries. Make sure MH Analysis and MT5 use the same Windows privilege level.")}',
              'if !v545EmbedStartedMT5Fast(18*time.Second){return errors.New("MT5 started, but its terminal window could not be embedded after automatic retries. Make sure MH Analysis and MT5 use the same Windows privilege level.")}', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 6) NATIVE VERSION LABEL: white bold text only, transparent/no background.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')
# Add local GDI/user32 procedures and constants.
marker = 'var chSetWindowDisplayAffinityV31 = chUser32.NewProc("SetWindowDisplayAffinity")\n'
extra = '''var chSetWindowDisplayAffinityV31 = chUser32.NewProc("SetWindowDisplayAffinity")\nvar wv2SetTextColorV545 = chGdi32.NewProc("SetTextColor")\nvar wv2SetBkModeV545 = chGdi32.NewProc("SetBkMode")\nvar wv2GetStockObjectV545 = chGdi32.NewProc("GetStockObject")\nvar wv2CreateFontV545 = chGdi32.NewProc("CreateFontW")\nvar wv2DeleteObjectV545 = chGdi32.NewProc("DeleteObject")\nvar wv2SendMessageV545 = chUser32.NewProc("SendMessageW")\n'''
if marker not in s:
    raise SystemExit('WebView2 proc marker missing')
s = s.replace(marker, extra, 1)
s = s.replace('\twv2WAProcessing        bool\n)', '\twv2WAProcessing        bool\n\twv2VersionLabel        uintptr\n\twv2VersionFont         uintptr\n)', 1)

# Responsive positioning in top client toolbar.
resize_anchor = 'if chSignalLinkBtn != 0 { chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1) }'
resize_new = resize_anchor + '\n\tif wv2VersionLabel != 0 { x:=w-170; if x<760 { x=760 }; chMoveWindow.Call(wv2VersionLabel, uintptr(x), 10, 160, 24, 1) }'
if resize_anchor not in s:
    raise SystemExit('version resize anchor missing')
s = s.replace(resize_anchor, resize_new, 1)

button_anchor = '\tbtnAnalysis, _, _ = chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSChild|chWSVisible,8,7,140,30,hostHWND,idAnalysis,inst,0)'
label_code = '''\twv2VersionLabel, _, _ = chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("STATIC"))),uintptr(unsafe.Pointer(chWstr("Version: V.54.5"))),chWSChild|chWSVisible,1040,10,160,24,hostHWND,0,inst,0)\n\twv2VersionFont, _, _ = wv2CreateFontV545.Call(^uintptr(14),0,0,0,700,0,0,0,1,0,0,5,0,uintptr(unsafe.Pointer(chWstr("Segoe UI"))))\n\tif wv2VersionFont != 0 { wv2SendMessageV545.Call(wv2VersionLabel,0x0030,wv2VersionFont,1) }\n''' + button_anchor
if button_anchor not in s:
    raise SystemExit('native button anchor missing')
s = s.replace(button_anchor, label_code, 1)

# Transparent white label; no box/background.
wnd_anchor = '\tswitch msg {\n\tcase chWMSize:'
wnd_new = '''\tswitch msg {\n\tcase 0x0138: // WM_CTLCOLORSTATIC\n\t\tif lp == wv2VersionLabel && wv2VersionLabel != 0 {\n\t\t\twv2SetTextColorV545.Call(wp,0x00FFFFFF)\n\t\t\twv2SetBkModeV545.Call(wp,1)\n\t\t\tb,_,_:=wv2GetStockObjectV545.Call(5) // NULL_BRUSH\n\t\t\treturn b\n\t\t}\n\tcase chWMSize:'''
if wnd_anchor not in s:
    raise SystemExit('wndproc anchor missing')
s = s.replace(wnd_anchor, wnd_new, 1)
s = s.replace('case chWMDestroy:\n\t\twv2Browser=nil;', 'case chWMDestroy:\n\t\tif wv2VersionFont!=0 {wv2DeleteObjectV545.Call(wv2VersionFont);wv2VersionFont=0}\n\t\twv2Browser=nil;', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# VERSION STAMPS
# -----------------------------------------------------------------------------
for path, pat, repl in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.5"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.5"'),
]:
    q = Path(path)
    z = q.read_text(encoding='utf-8')
    z, n = re.subn(pat, repl, z, count=1)
    if n != 1:
        raise SystemExit(f'version stamp failed {path}')
    q.write_text(z, encoding='utf-8', newline='\n')
Path('VERSION').write_text('V.54.5\n', encoding='ascii')

# Update in-page mandatory updater label only; brand subtitle remains CH Shaukat Ali.
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
s = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>',
           '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.5</div>', s, count=1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# GUARDS: fail build rather than silently reintroducing the listed regressions.
# -----------------------------------------------------------------------------
a = Path('web/app.js').read_text(encoding='utf-8')
i = Path('web/index.html').read_text(encoding='utf-8')
rh = Path('web/records.html').read_text(encoding='utf-8')
wa = Path('webview2_host.go').read_text(encoding='utf-8')
rec = Path('records_mt5_local.go').read_text(encoding='utf-8')
mt5 = Path('mt5_embed_v36.go').read_text(encoding='utf-8')
checks = [
    ('V54.3 confirmed sender preserved', 'wv2WALastAckStatus' in wa and 'window.external.invoke' in wa),
    ('WhatsApp exact Signal generated status', "const statusText=sig?'Signal generated':'No clear edge';" in a),
    ('WhatsApp Action line absent', '*Action:*' not in a),
    ('Records subtitle', '<div class="recordsVersion">CH Shaukat Ali</div>' in rh),
    ('Main subtitle', '<div class="version">CH Shaukat Ali</div>' in i),
    ('No slow calendar iframe', 'widget.mfbcdn.net' not in i and 'economicCalendarLocal' in i),
    ('Recent signals show latest', 'recentSession.slice(0,5)' in a),
    ('Fresh records store', 'signal-records-v545.json' in rec),
    ('White native version label', 'Version: V.54.5' in wa and 'wv2SetTextColorV545' in wa),
    ('Fast MT5 embed', 'v545EmbedStartedMT5Fast' in mt5),
]
for name, ok in checks:
    if not ok:
        raise SystemExit('Guard failed: '+name)
