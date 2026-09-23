from pathlib import Path
import re


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'V55.1 anchor missing: {label}')
    return text.replace(old, new, 1)


def regex_once(text, pattern, repl, label):
    out, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'V55.1 regex anchor missing/duplicate: {label} ({n})')
    return out


# -----------------------------------------------------------------------------
# Frontend: paint cached ticker/calendar/recent immediately; never block startup
# on the MT5 lifecycle record scan.  Recent records use a fast local snapshot.
# -----------------------------------------------------------------------------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')

s = replace_once(
    s,
    """    if(Array.isArray(j?.recent)){\n      recentSession.splice(0,recentSession.length,...j.recent.slice(0,6));\n      renderRecentSignals();\n    }""",
    """    if(Array.isArray(j?.recent)&&j.recent.length){\n      recentSession.splice(0,recentSession.length,...j.recent.slice(0,6));\n      try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(_){}\n      renderRecentSignals();\n    }""",
    'do not wipe recent with empty UI cache',
)

old_recent = r"""async function loadRecentSignalsV5413(){
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
}"""
new_recent = r"""async function loadRecentSignalsV5413(){
  const ctl=new AbortController(),kill=setTimeout(()=>ctl.abort(),1200);
  try{
    const r=await fetch('/api/records-v2?fast=1',{cache:'no-store',signal:ctl.signal});if(!r.ok)throw new Error('records unavailable');
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
  finally{clearTimeout(kill)}
}"""
s = replace_once(s, old_recent, new_recent, 'fast Recent Signals loader')

calendar_anchor = "function renderEconomicCalendarV546(root,days){if(!root||!Array.isArray(days)||!days.length)return false;root.innerHTML=days.map(day=>`<div class=\"calDayV545\"><div class=\"calDateV545\">${escapeCalendarTextV545(day.label||day.date)}</div>${(day.events||[]).map(ev=>{const imp=String(ev.impact||'').toLowerCase();return `<div class=\"calEventV545\"><span class=\"calTimeV545\">${escapeCalendarTextV545(ev.time)}</span><span class=\"calCountryV545\">${escapeCalendarTextV545(ev.country)}</span><span class=\"calImpactV545 ${imp}\">${escapeCalendarTextV545(ev.impact)}</span><span class=\"calTitleV545\">${escapeCalendarTextV545(ev.title)}</span></div>`}).join('')}</div>`).join('');return true}\n"
prime_calendar = calendar_anchor + """function primeEconomicCalendarV551(){
  const root=$('#economicCalendarLocal');if(!root)return false;
  try{
    const cached=JSON.parse(localStorage.getItem('mh-economic-calendar-stable')||localStorage.getItem('mh-economic-calendar-v546')||localStorage.getItem('mh-economic-calendar-v545')||'null');
    if(cached?.days?.length)return renderEconomicCalendarV546(root,cached.days);
  }catch(_){}
  return !!root.querySelector('.calDayV545');
}
"""
s = replace_once(s, calendar_anchor, prime_calendar, 'calendar instant-prime helper')

old_start = """// v79.6 credentials are stored by native Windows settings dialogs, not editable HTML fields.
await refreshBackendSettings();
if(backendSettings.has_api_key){setDataState('neutralDot','Key saved')}else setDataState('neutralDot','Access key not saved');
autoSignalEnabled=localStorage.getItem(STORAGE_AUTO)==='1';
await loadPersistentUICacheV5411();await loadRecentSignalsV5413();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();requestAnimationFrame(()=>refreshPublicTicker());setTimeout(refreshPublicTicker,250);setTimeout(refreshPublicTicker,900);setTimeout(refreshPublicTicker,1800);setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,180000);
"""
new_start = """// V55.1 startup: last-known UI values paint BEFORE any awaited backend work.
// This removes the old 2–3 minute blank ticker/calendar caused by waiting for Records/MT5 sync.
primeTickerV549();
primeMovingTickerV547();
renderRecentSignals();
primeEconomicCalendarV551();
setupLightweightChart();setupChartControls();loadChart();
const startupUICacheV551=loadPersistentUICacheV5411().then(()=>{primeTickerV549();renderRecentSignals();primeEconomicCalendarV551()}).catch(()=>false);
loadRecentSignalsV5413().catch(()=>0);
loadEconomicCalendarV545().catch(()=>{});
refreshPublicTicker();
refreshMarketCap();
requestAnimationFrame(()=>refreshPublicTicker());setTimeout(refreshPublicTicker,250);setTimeout(refreshPublicTicker,900);setTimeout(refreshPublicTicker,1800);
// v79.6 credentials are stored by native Windows settings dialogs, not editable HTML fields.
await refreshBackendSettings();
if(backendSettings.has_api_key){setDataState('neutralDot','Key saved')}else setDataState('neutralDot','Access key not saved');
autoSignalEnabled=localStorage.getItem(STORAGE_AUTO)==='1';
void startupUICacheV551;
setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,60*60*1000);
"""
s = replace_once(s, old_start, new_start, 'non-blocking startup order')

p.write_text(s, encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# Records: /api/records-v2?fast=1 returns the persistent local store immediately
# and does not scan the MT5 lifecycle journal on application startup.
# -----------------------------------------------------------------------------
p = Path('records_mt5_local.go')
s = p.read_text(encoding='utf-8')
old_handler = r'''func mt5LocalRecordsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	eventsRead, matched, syncErr := syncMT5Lifecycle(&s)
	_ = saveMT5LocalStore(s)
	rs := mt5RecordsSnapshot(s)
	mt5RecordsMu.Unlock()

	resp := map[string]any{
		"records":                   rs,
		"summary":                   mt5LocalSummary(rs),
		"server_time":               time.Now().Unix(),
		"source":                    "LOCAL_MT5",
		"external_market_api_calls": 0,
		"events_read":               eventsRead,
		"events_matched":            matched,
	}
	if syncErr != nil {
		resp["warning"] = syncErr.Error()
	}
	_ = json.NewEncoder(w).Encode(resp)
}'''
new_handler = r'''func mt5LocalRecordsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	if r.URL.Query().Get("fast") == "1" {
		rs := mt5RecordsSnapshot(s)
		mt5RecordsMu.Unlock()
		_ = json.NewEncoder(w).Encode(map[string]any{
			"records": rs, "summary": mt5LocalSummary(rs), "server_time": time.Now().Unix(),
			"source": "LOCAL_RECORDS_FAST", "external_market_api_calls": 0,
			"events_read": 0, "events_matched": 0,
		})
		return
	}
	eventsRead, matched, syncErr := syncMT5Lifecycle(&s)
	_ = saveMT5LocalStore(s)
	rs := mt5RecordsSnapshot(s)
	mt5RecordsMu.Unlock()

	resp := map[string]any{
		"records":                   rs,
		"summary":                   mt5LocalSummary(rs),
		"server_time":               time.Now().Unix(),
		"source":                    "LOCAL_MT5",
		"external_market_api_calls": 0,
		"events_read":               eventsRead,
		"events_matched":            matched,
	}
	if syncErr != nil {
		resp["warning"] = syncErr.Error()
	}
	_ = json.NewEncoder(w).Encode(resp)
}'''
s = replace_once(s, old_handler, new_handler, 'fast records endpoint')
p.write_text(s, encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# Calendar: cache-first local renderer, legacy cache migration, rate-limit-safe
# hourly refresh, CDN primary and nfs fallback. No Myfxbook iframe/provider UI.
# -----------------------------------------------------------------------------
calendar_go = r'''package main

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type calendarFeedEvent struct{ Title, Country, Date, Impact, Forecast, Previous, Actual string }
type calendarUiEvent struct {
	Time string `json:"time"`
	Country string `json:"country"`
	Title string `json:"title"`
	Impact string `json:"impact"`
	Forecast string `json:"forecast"`
	Previous string `json:"previous"`
	Actual string `json:"actual"`
}
type calendarUiDay struct {
	Date string `json:"date"`
	Label string `json:"label"`
	Events []calendarUiEvent `json:"events"`
}
type calendarDiskV55 struct {
	CachedAt int64 `json:"cached_at"`
	Days []calendarUiDay `json:"days"`
}

const calendarRefreshEveryV551 = 60 * time.Minute

var calendar3Mu sync.Mutex
var calendar3At time.Time
var calendar3Cache map[string]any
var calendar3Refreshing bool

func calendarDiskPathV55() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" { base = os.TempDir() }
	return filepath.Join(base, "MHAnalysis", "economic-calendar.json")
}

func calendarCachedAtV551(out map[string]any) time.Time {
	if out == nil { return time.Time{} }
	switch v := out["cached_at"].(type) {
	case int64:
		if v > 0 { return time.Unix(v, 0) }
	case int:
		if v > 0 { return time.Unix(int64(v), 0) }
	case float64:
		if v > 0 { return time.Unix(int64(v), 0) }
	}
	return time.Time{}
}

func loadCalendarDiskV55() (map[string]any, bool) {
	b, err := os.ReadFile(calendarDiskPathV55())
	if err != nil { return nil, false }
	var d calendarDiskV55
	if json.Unmarshal(b, &d) != nil || len(d.Days) == 0 { return nil, false }
	return map[string]any{"days": d.Days, "source": "Economic calendar • last known values", "cached_at": d.CachedAt}, true
}

func loadLegacyCalendarV551() (map[string]any, bool) {
	c := loadUICacheV5411()
	if len(c.Calendar) == 0 { return nil, false }
	b, _ := json.Marshal(c.Calendar)
	var days []calendarUiDay
	if json.Unmarshal(b, &days) != nil || len(days) == 0 { return nil, false }
	at := time.Now().Add(-2 * time.Hour).Unix()
	if st, err := os.Stat(uiCachePathV5411()); err == nil { at = st.ModTime().Unix() }
	return map[string]any{"days": days, "source": "Economic calendar • migrated cache", "cached_at": at}, true
}

func loadBestCalendarV551() (map[string]any, bool) {
	if out, ok := loadCalendarDiskV55(); ok { return out, true }
	return loadLegacyCalendarV551()
}

func mirrorCalendarUICacheV551(days []calendarUiDay) {
	if len(days) == 0 { return }
	b, _ := json.Marshal(days)
	var generic []any
	if json.Unmarshal(b, &generic) != nil { return }
	uiCacheMuV5411.Lock()
	c := loadUICacheV5411()
	c.Calendar = generic
	saveUICacheV5411(c)
	uiCacheMuV5411.Unlock()
}

func saveCalendarDiskV55(out map[string]any) {
	days, ok := out["days"].([]calendarUiDay)
	if !ok || len(days) == 0 { return }
	p := calendarDiskPathV55()
	_ = os.MkdirAll(filepath.Dir(p), 0755)
	at := time.Now().Unix()
	if t := calendarCachedAtV551(out); !t.IsZero() { at = t.Unix() }
	b, _ := json.Marshal(calendarDiskV55{CachedAt: at, Days: days})
	tmp := p + ".tmp"
	if os.WriteFile(tmp, b, 0600) == nil { _ = os.Remove(p); _ = os.Rename(tmp, p) }
	mirrorCalendarUICacheV551(days)
}

func (e *calendarFeedEvent) UnmarshalJSON(b []byte) error {
	type raw struct {
		Title string `json:"title"`; Country string `json:"country"`; Date string `json:"date"`; Impact string `json:"impact"`
		Forecast string `json:"forecast"`; Previous string `json:"previous"`; Actual string `json:"actual"`
	}
	var x raw
	if err := json.Unmarshal(b, &x); err != nil { return err }
	e.Title=x.Title; e.Country=x.Country; e.Date=x.Date; e.Impact=x.Impact; e.Forecast=x.Forecast; e.Previous=x.Previous; e.Actual=x.Actual
	return nil
}

func fetchCalendarFeed(cli *http.Client, endpoint string) []calendarFeedEvent {
	req, _ := http.NewRequest(http.MethodGet, endpoint, nil)
	req.Header.Set("User-Agent", "MH-Analysis/55.1")
	resp, err := cli.Do(req)
	if err != nil { return nil }
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 { return nil }
	var out []calendarFeedEvent
	if json.NewDecoder(resp.Body).Decode(&out) != nil { return nil }
	return out
}

func fetchFirstCalendarV551(cli *http.Client, endpoints ...string) []calendarFeedEvent {
	for _, endpoint := range endpoints {
		if out := fetchCalendarFeed(cli, endpoint); len(out) > 0 { return out }
	}
	return nil
}

func buildEconomicCalendarV55(timeout time.Duration) map[string]any {
	cli := &http.Client{Timeout: timeout}
	raw := fetchFirstCalendarV551(cli,
		"https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
		"https://nfs.faireconomy.media/ff_calendar_thisweek.json",
	)
	now := time.Now()
	if len(raw) == 0 || now.Weekday() == time.Friday || now.Weekday() == time.Saturday || now.Weekday() == time.Sunday {
		raw = append(raw, fetchFirstCalendarV551(cli,
			"https://cdn-nfs.faireconomy.media/ff_calendar_nextweek.json",
			"https://nfs.faireconomy.media/ff_calendar_nextweek.json",
		)...)
	}
	if len(raw) == 0 { return nil }

	type timed struct{ t time.Time; e calendarFeedEvent }
	items := make([]timed, 0, len(raw))
	seen := map[string]bool{}
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	for _, ev := range raw {
		impact := strings.ToLower(strings.TrimSpace(ev.Impact))
		if impact != "high" && impact != "medium" && impact != "med" && impact != "low" { continue }
		t, err := time.Parse(time.RFC3339, strings.TrimSpace(ev.Date))
		if err != nil { continue }
		local := t.Local()
		if local.Before(today) { continue }
		key := local.Format(time.RFC3339)+"|"+strings.TrimSpace(ev.Country)+"|"+strings.TrimSpace(ev.Title)
		if seen[key] { continue }
		seen[key] = true
		items = append(items, timed{t: local, e: ev})
	}
	sort.Slice(items, func(i,j int) bool { return items[i].t.Before(items[j].t) })
	selected := make([]string,0,3)
	dateSeen := map[string]bool{}
	for _, it := range items {
		d := it.t.Format("2006-01-02")
		if !dateSeen[d] { dateSeen[d]=true; selected=append(selected,d); if len(selected)==3 { break } }
	}
	days := make([]calendarUiDay,0,len(selected))
	for _, d := range selected {
		day := calendarUiDay{Date:d,Events:[]calendarUiEvent{}}
		for _, it := range items {
			if it.t.Format("2006-01-02") != d { continue }
			if day.Label == "" { day.Label = it.t.Format("Monday, Jan 2, 2006") }
			impact := strings.TrimSpace(it.e.Impact)
			if strings.EqualFold(impact,"med") { impact="Medium" }
			day.Events = append(day.Events, calendarUiEvent{Time:it.t.Format("03:04 PM"),Country:strings.ToUpper(strings.TrimSpace(it.e.Country)),Title:strings.TrimSpace(it.e.Title),Impact:impact,Forecast:strings.TrimSpace(it.e.Forecast),Previous:strings.TrimSpace(it.e.Previous),Actual:strings.TrimSpace(it.e.Actual)})
		}
		if len(day.Events)>0 { days=append(days,day) }
	}
	if len(days)==0 { return nil }
	return map[string]any{"days":days,"source":"Economic calendar • Low / Medium / High","cached_at":time.Now().Unix()}
}

func installCalendarCacheV551(out map[string]any, persist bool) {
	if out == nil { return }
	at := calendarCachedAtV551(out)
	if at.IsZero() { at = time.Now() }
	calendar3Mu.Lock(); calendar3Cache=out; calendar3At=at; calendar3Mu.Unlock()
	if persist { saveCalendarDiskV55(out) }
}

func refreshCalendarBackgroundV55() {
	calendar3Mu.Lock()
	if calendar3Refreshing { calendar3Mu.Unlock(); return }
	calendar3Refreshing=true
	calendar3Mu.Unlock()
	go func(){
		if out:=buildEconomicCalendarV55(1800*time.Millisecond); out!=nil { installCalendarCacheV551(out,true) }
		calendar3Mu.Lock(); calendar3Refreshing=false; calendar3Mu.Unlock()
	}()
}

func warmStartupCalendarV55() {
	if out,ok:=loadBestCalendarV551(); ok {
		installCalendarCacheV551(out,false)
		if at:=calendarCachedAtV551(out); at.IsZero() || time.Since(at) >= calendarRefreshEveryV551 { refreshCalendarBackgroundV55() }
		return
	}
	// First-ever run has no cache. Do not block the MH Analysis window; populate
	// the disk cache in the background and every later reopen paints instantly.
	refreshCalendarBackgroundV55()
}

func economicCalendarHandler(w http.ResponseWriter,r *http.Request){
	if r.Method!=http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	w.Header().Set("Content-Type","application/json")
	calendar3Mu.Lock(); cached:=calendar3Cache; age:=time.Since(calendar3At); calendar3Mu.Unlock()
	if cached!=nil {
		_ = json.NewEncoder(w).Encode(cached)
		if age >= calendarRefreshEveryV551 { refreshCalendarBackgroundV55() }
		return
	}
	if disk,ok:=loadBestCalendarV551(); ok {
		installCalendarCacheV551(disk,false)
		_ = json.NewEncoder(w).Encode(disk)
		if at:=calendarCachedAtV551(disk); at.IsZero() || time.Since(at) >= calendarRefreshEveryV551 { refreshCalendarBackgroundV55() }
		return
	}
	refreshCalendarBackgroundV55()
	_ = json.NewEncoder(w).Encode(map[string]any{"days":[]calendarUiDay{},"source":"Economic calendar loading"})
}
'''
Path('calendar3d.go').write_text(calendar_go, encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# WhatsApp + MT5 host: keep WhatsApp fully rendered behind active view (never
# off-screen/reloaded), confirm composer clear before dequeuing, and use DOM click
# first then native+CDP Enter fallback. MT5 repeated clicks use instant child path.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')

s = replace_once(
    s,
    '\twv2WAResolvedTarget    string\n',
    '\twv2WAResolvedTarget    string\n\twv2MT5PreparingV551    bool\n',
    'MT5 preparing state',
)

s = regex_once(
    s,
    r'func wv2ParkWhatsAppV547\(\) \{.*?\n\}',
    r'''func wv2ParkWhatsAppV547() {
	if wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
	if w<1 { w=1 }; if h<1 { h=1 }
	// Keep WhatsApp at full desktop size and rendered at all times. It is parked
	// at HWND_BOTTOM instead of being moved outside the parent client area, so
	// Chromium never enters an off-screen/throttled state and the tab paints
	// instantly when raised.
	chMoveWindow.Call(wv2WhatsappContainer, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
	chShowWindow.Call(wv2WhatsappContainer, chSWShow)
	_ = wv2Whatsapp.Show()
	wv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged()
	chSetWindowPos.Call(wv2WhatsappContainer, 1, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoActivate)
}''',
    'full-size WhatsApp parking',
)

old_case2 = r'''	case 2:
		wv2WAResolvedTarget = ""
		if wv2Whatsapp != nil {
			// Manual WhatsApp always restores the root chat UI in the SAME persistent
			// profile. This prevents the off-screen background renderer from reopening
			// as a blank theme-colour surface.
			if !wv2WAProcessing { wv2Whatsapp.Navigate("https://web.whatsapp.com/") }
			chMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)
			chShowWindow.Call(wv2WhatsappContainer,chSWShow)
			chSetWindowPos.Call(wv2WhatsappContainer,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
			_ = wv2Whatsapp.Show(); wv2Whatsapp.Resize(); _=wv2Whatsapp.NotifyParentWindowPositionChanged(); wv2Whatsapp.Focus(); chRedrawWindowV5414.Call(wv2WhatsappContainer,0,0,0x0001|0x0080|0x0100); chUpdateWindow.Call(wv2WhatsappContainer)
		}'''
new_case2 = r'''	case 2:
		if wv2Whatsapp != nil {
			// Never navigate/reload on tab selection. The exact same persistent
			// renderer has remained full-size and alive behind the other views.
			chMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)
			chShowWindow.Call(wv2WhatsappContainer,chSWShow)
			chSetWindowPos.Call(wv2WhatsappContainer,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
			_ = wv2Whatsapp.Show(); wv2Whatsapp.Resize(); _=wv2Whatsapp.NotifyParentWindowPositionChanged()
			chRedrawWindowV5414.Call(wv2WhatsappContainer,0,0,0x0001|0x0080|0x0100); chUpdateWindow.Call(wv2WhatsappContainer)
			wv2Whatsapp.Focus()
		}'''
s = replace_once(s, old_case2, new_case2, 'no-reload manual WhatsApp view')

s = regex_once(
    s,
    r'func wv2ShowMT5\(\) \{.*?\n\}\n\nfunc wv2RestoreDesiredFocusV5411',
    r'''func wv2ShowMT5() {
	v546HideAllMT5TopLevel()
	chMu.Lock()
	hwnd:=chMT5Wnd
	preparing:=wv2MT5PreparingV551 || chMT5StartingV34
	chMu.Unlock()
	if hwnd != 0 {
		parent,_,_:=v36GetParent.Call(hwnd)
		if parent==hostHWND {
			chMu.Lock(); wv2MT5PreparingV551=false; chMu.Unlock()
			wv2ActivateMT5V5412()
			return
		}
	}
	// Repeated clicks while the first embed is being prepared must do nothing;
	// this avoids the old blank/flick/restart loop.
	if preparing { return }
	chMu.Lock(); wv2MT5PreparingV551=true; chMu.Unlock()
	wv2SetDesiredView(4)
	wv2ParkWhatsAppV547()
	// Keep MH Analysis visible only during the first embed. Once the child HWND
	// exists, every later MH MT5 click switches synchronously with no blank frame.
	if wv2Container != 0 && wv2Browser != nil {
		var r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
		w:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
		chShowWindow.Call(wv2Container,chSWShow); _=wv2Browser.Show()
		chSetWindowPos.Call(wv2Container,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
		wv2Browser.Resize()
	}
	go func() {
		err:=chEnsureMT5TerminalV36()
		chMu.Lock(); wv2MT5PreparingV551=false; chMu.Unlock()
		if err != nil {
			messageBox(hostHWND, err.Error(), "MH MT5", 0x10)
			postMessage(hostHWND, wmSwitchAnalysis, 0, 0)
			return
		}
		postMessage(hostHWND, wmMT5ReadyV5412, 0, 0)
	}()
}

func wv2RestoreDesiredFocusV5411''',
    'stable MT5 switch path',
)

s = regex_once(
    s,
    r'func wv2EvalWhatsAppV54\(token uintptr\) \{.*?\n\}\n\nfunc wv2WhatsAppInputHWNDV5414',
    r'''func wv2EvalWhatsAppV54(token uintptr) {
	if wv2Whatsapp == nil || !wv2WAProcessing || token == 0 || token != wv2WAActiveToken { return }
	msgJSON, _ := json.Marshal(wv2WAActiveMessage)
	groupJSON, _ := json.Marshal(wv2WAActiveGroup)
	script := fmt.Sprintf(`(()=>{
const msg=%s,isGroup=%s,token=%d;
const ack=(st)=>{try{window.external.invoke('MHWA|'+token+'|'+st)}catch(e){};return st};
const sentKey='mh-v551-sent-'+token,armedKey='mh-v551-armed-'+token,clickKey='mh-v551-click-'+token;
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
    ack('opening-group');
    if(href&&/^https?:/i.test(href)){location.assign(href);return 'opening-group'}
    preferred.click();return 'opening-group';
  }
  return ack('waiting-group-link');
}
if(host!=='web.whatsapp.com')return ack('waiting-whatsapp');
const getBox=()=>document.querySelector('footer [contenteditable="true"][role="textbox"]')||document.querySelector('footer [contenteditable="true"]')||document.querySelector('footer div[role="textbox"]');
const box=getBox();
if(!box)return ack('waiting-chat');
const norm=(v)=>String(v||'').replace(/\r/g,'').trim();
const wanted=norm(msg),current=norm(box.innerText||box.textContent);
if(sessionStorage.getItem(armedKey)==='1'&&!current){
  sessionStorage.setItem(sentKey,'1');sessionStorage.removeItem(armedKey);sessionStorage.removeItem(clickKey);return ack('sent');
}
box.focus();
if(current!==wanted){
  try{
    const sel=window.getSelection(),range=document.createRange();range.selectNodeContents(box);sel.removeAllRanges();sel.addRange(range);
    document.execCommand('delete',false,null);sel.removeAllRanges();
  }catch(e){}
  try{box.innerHTML=''}catch(e){try{box.textContent=''}catch(_){}}
  try{box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward',data:null}))}catch(e){box.dispatchEvent(new Event('input',{bubbles:true}))}
  let inserted=false;try{inserted=document.execCommand('insertText',false,msg)}catch(e){}
  if(!inserted){box.textContent=msg}
  try{box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}))}catch(e){box.dispatchEvent(new Event('input',{bubbles:true}))}
  sessionStorage.removeItem(clickKey);
}
if(norm(box.innerText||box.textContent)!==wanted)return ack('waiting-composer');
sessionStorage.setItem(armedKey,'1');
box.focus();
const send=document.querySelector('footer [data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]')||document.querySelector('[data-testid="compose-btn-send"]');
let clicks=Number(sessionStorage.getItem(clickKey)||'0')||0;
if(send&&clicks<2){sessionStorage.setItem(clickKey,String(clicks+1));send.click();return ack('send-clicked')}
return ack('native-enter');
})()`, string(msgJSON), string(groupJSON), token)
	wv2ParkWhatsAppV547()
	_ = wv2Whatsapp.Show()
	wv2Whatsapp.Eval(script)
}

func wv2WhatsAppInputHWNDV5414''',
    'confirmed WhatsApp send flow',
)

s = regex_once(
    s,
    r'func wv2WhatsAppNativeEnterV5414\(token uintptr\) \{.*?\n\}\n\nfunc wv2WhatsAppAckV542',
    r'''func wv2WhatsAppNativeEnterV5414(token uintptr) {
	if token == 0 || token != wv2WAActiveToken || !wv2WAProcessing { return }
	// The renderer remains fully alive behind the active view. Give its composer
	// input focus without changing z-order, then deliver both native Windows Enter
	// and Chromium CDP Enter. We no longer treat mere CDP call acceptance as proof
	// that WhatsApp actually sent the message.
	wv2ParkWhatsAppV547(); _ = wv2Whatsapp.Show(); wv2Whatsapp.Focus()
	h := wv2WhatsAppInputHWNDV5414()
	if h != 0 {
		down := uintptr(1 | (0x1C << 16))
		up := uintptr(1 | (0x1C << 16) | (1 << 30) | (1 << 31))
		chSendMessageV5414.Call(h,0x0100,13,down)
		chSendMessageV5414.Call(h,0x0102,13,down)
		chSendMessageV5414.Call(h,0x0101,13,up)
	}
	_ = wv2WhatsAppTrustedEnterV55()
	time.AfterFunc(70*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })
}

func wv2WhatsAppAckV542''',
    'native Enter always runs',
)

s = regex_once(
    s,
    r'func wv2WhatsAppAckV542\(token uintptr\) \{.*?\n\}\n\nfunc wv2FinishWhatsAppV54',
    r'''func wv2WhatsAppAckV542(token uintptr) {
	if token == 0 || token != wv2WAActiveToken || token != wv2WALastAckToken { return }
	switch wv2WALastAckStatus {
	case "sent":
		wv2WAResolvedTarget = wv2WAActiveTarget
		wv2FinishWhatsAppV54(token)
	case "send-clicked":
		time.AfterFunc(220*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
	case "native-enter", "composer-ready":
		wv2WhatsAppNativeEnterV5414(token)
		time.AfterFunc(280*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
	case "waiting-composer":
		time.AfterFunc(140*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
	}
}

func wv2FinishWhatsAppV54''',
    'WhatsApp ack state machine',
)

s = replace_once(s, 'chWstr("Version: V.55.0")', 'chWstr("Version: V.55.1")', 'native version label')
p.write_text(s, encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# Ticker refresh: cached values are returned instantly; external refresh is not
# hammered every 20 seconds. This also makes reopen behaviour deterministic.
# -----------------------------------------------------------------------------
p = Path('ui_cache_v5411.go')
s = p.read_text(encoding='utf-8')
s = replace_once(s, 'time.Since(tickerRefreshAtV5411) > 20*time.Second', 'time.Since(tickerRefreshAtV5411) > 5*time.Minute', 'ticker background refresh cadence')
p.write_text(s, encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# Version visible in the web updater gate.
# -----------------------------------------------------------------------------
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
s = s.replace('V.55.0', 'V.55.1')
if 'V.55.1' not in s:
    raise SystemExit('V55.1 web version stamp failed')
if 'myfxbook' in s.lower() or 'mfbcdn' in s.lower():
    raise SystemExit('Myfxbook provider markup still exists')
p.write_text(s, encoding='utf-8', newline='\n')
Path('VERSION').write_text('V.55.1\n', encoding='utf-8', newline='\n')


# -----------------------------------------------------------------------------
# Direct-source publisher: dynamic V55.x version, no patch execution.
# -----------------------------------------------------------------------------
publish = r'''name: Publish MH Analysis V55 Clean Runtime

on:
  push:
    branches:
      - v55-clean-runtime
    paths:
      - 'VERSION'
      - '*.go'
      - 'web/**'
      - 'go.mod'
      - 'go.sum'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  publish:
    runs-on: windows-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-go@v5
        with:
          go-version: '1.23.2'
          cache: false

      - name: Verify clean direct source
        shell: powershell
        run: |
          $ErrorActionPreference='Stop'
          $version=(Get-Content VERSION -Raw).Trim()
          if($version -notmatch '^V\.55\.\d+$'){throw "Expected V.55.x direct clean source, got $version"}
          $legacy=Get-ChildItem '.github\scripts' -Filter 'v54*_patch.py' -ErrorAction SilentlyContinue
          if($legacy){throw 'Legacy V54 build-time patch chain is still present. V55 must build directly from committed source.'}
          $bad=gofmt -l *.go
          if($bad){throw "gofmt required: $bad"}
          node --check web/app.js
          if($LASTEXITCODE -ne 0){throw 'JavaScript validation failed'}
          if(Select-String -Path web\index.html,web\app.js -Pattern 'myfxbook|mfbcdn' -Quiet){throw 'Myfxbook calendar dependency returned'}
          if(-not (Select-String -Path web\app.js -Pattern '/api/records-v2\?fast=1' -Quiet)){throw 'Fast Recent Signals startup path missing'}
          if(-not (Select-String -Path webview2_host.go -Pattern 'send-clicked' -Quiet)){throw 'Confirmed WhatsApp click/send state machine missing'}
          if(-not (Select-String -Path calendar3d.go -Pattern 'cdn-nfs\.faireconomy\.media' -Quiet)){throw 'Calendar CDN source missing'}

      - name: Test and build V55
        shell: powershell
        run: |
          $ErrorActionPreference='Stop'
          go test ./...
          if($LASTEXITCODE -ne 0){throw 'Go tests failed'}
          New-Item -ItemType Directory -Force dist | Out-Null
          $env:GOOS='windows';$env:GOARCH='amd64';$env:CGO_ENABLED='0'
          go build -trimpath -ldflags='-H=windowsgui -s -w' -o 'dist/MH Analysis.exe' .
          if($LASTEXITCODE -ne 0 -or -not(Test-Path 'dist/MH Analysis.exe')){throw 'Windows build failed'}
          $sha=(Get-FileHash 'dist/MH Analysis.exe' -Algorithm SHA256).Hash.ToLower()
          "${sha}  MH Analysis.exe" | Set-Content -Encoding ascii 'dist/SHA256SUMS.txt'

      - uses: actions/upload-artifact@v4
        with:
          name: MH-Analysis-V55-Clean-Runtime
          path: |
            dist/MH Analysis.exe
            dist/SHA256SUMS.txt
          if-no-files-found: error

      - name: Publish mandatory V55 updater
        shell: powershell
        run: |
          $ErrorActionPreference='Stop'
          $version=(Get-Content VERSION -Raw).Trim()
          $sha=(Get-FileHash 'dist\MH Analysis.exe' -Algorithm SHA256).Hash.ToLower()
          $tmp=Join-Path $env:RUNNER_TEMP 'v55-update'
          New-Item -ItemType Directory -Force $tmp | Out-Null
          Copy-Item 'dist\MH Analysis.exe' (Join-Path $tmp 'MH Analysis.exe')
          $manifest=[ordered]@{
            version=$version
            mandatory=$true
            download_url='https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/mh-analysis-update-channel/MH%20Analysis.exe'
            sha256=$sha
            notes='V55.1 direct-source runtime: WhatsApp stays permanently rendered and background sends are confirmed by composer clear with click plus native/CDP Enter fallback; MH MT5 repeated clicks switch directly to the embedded child; ticker/calendar/recent values paint from persistent cache before backend work; calendar uses a local cached ForexFactory feed with hourly refresh and no Myfxbook iframe.'
          } | ConvertTo-Json -Compress
          [IO.File]::WriteAllText((Join-Path $tmp 'update.json'),$manifest,(New-Object Text.UTF8Encoding($false)))
          [IO.File]::WriteAllText((Join-Path $tmp 'VERSION'),$version+[Environment]::NewLine,(New-Object Text.UTF8Encoding($false)))
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git checkout --orphan __v55_update
          git rm -rf . 2>$null
          Get-ChildItem -Force | Where-Object {$_.Name -ne '.git'} | Remove-Item -Recurse -Force
          Copy-Item (Join-Path $tmp 'MH Analysis.exe') '.\MH Analysis.exe'
          Copy-Item (Join-Path $tmp 'update.json') '.\update.json'
          Copy-Item (Join-Path $tmp 'VERSION') '.\VERSION'
          git add .
          git commit -m "Publish MH Analysis $version clean runtime"
          git push --force origin HEAD:mh-analysis-update-channel
          if($LASTEXITCODE -ne 0){throw 'Updater publish failed'}
'''
Path('.github/workflows/publish-v55-clean.yml').write_text(publish, encoding='utf-8', newline='\n')

# Final source-level guards before the workflow tests/builds.
checks = {
    'web/app.js': ['/api/records-v2?fast=1', 'primeEconomicCalendarV551()', 'V55.1 startup: last-known UI values paint BEFORE'],
    'webview2_host.go': ['send-clicked', 'native-enter', 'wv2MT5PreparingV551', 'Version: V.55.1'],
    'calendar3d.go': ['cdn-nfs.faireconomy.media', 'calendarRefreshEveryV551 = 60 * time.Minute'],
}
for fn, needles in checks.items():
    txt = Path(fn).read_text(encoding='utf-8')
    for needle in needles:
        if needle not in txt:
            raise SystemExit(f'V55.1 guard missing {needle!r} in {fn}')
if 'x:=w+32' in Path('webview2_host.go').read_text(encoding='utf-8'):
    raise SystemExit('WhatsApp is still parked off-screen')
if 'wv2Whatsapp.Navigate("https://web.whatsapp.com/")' in Path('webview2_host.go').read_text(encoding='utf-8'):
    raise SystemExit('Manual WhatsApp still forces a reload')
print('V55.1 direct-source fixes applied')
