from pathlib import Path
import re


def require_replace(text, old, new, label, count=1):
    if old not in text:
        raise SystemExit(f"V55 migration anchor missing: {label}")
    return text.replace(old, new, count)

# -----------------------------------------------------------------------------
# WhatsApp: one persistent logged-in WebView. Background automation never steals
# Windows focus; it fills the exact composer and sends with Chromium CDP Enter.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')
s = require_replace(
    s,
    '\twv2Whatsapp            *edge.Chromium\n',
    '\twv2Whatsapp            *edge.Chromium\n\twv2WhatsappCoreV55     uintptr\n',
    'WhatsApp core declaration',
)
old_nav = '''\t\tb.NavigationCompletedCallback = func(_ *edge.ICoreWebView2, _ *edge.ICoreWebView2NavigationCompletedEventArgs) {
\t\t\tif wv2WAProcessing && wv2WAActiveToken != 0 {
\t\t\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, wv2WAActiveToken, 0)
\t\t\t}
\t\t}'''
new_nav = '''\t\tb.NavigationCompletedCallback = func(sender *edge.ICoreWebView2, _ *edge.ICoreWebView2NavigationCompletedEventArgs) {
\t\t\tif sender != nil { wv2WhatsappCoreV55 = uintptr(unsafe.Pointer(sender)) }
\t\t\tif wv2WAProcessing && wv2WAActiveToken != 0 {
\t\t\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, wv2WAActiveToken, 0)
\t\t\t}
\t\t}'''
s = require_replace(s, old_nav, new_nav, 'WhatsApp NavigationCompleted core capture')

old_case2 = '''\tcase 2:
\t\twv2WAResolvedTarget = ""
\t\tif wv2Whatsapp != nil {
\t\t\tchMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)'''
new_case2 = '''\tcase 2:
\t\twv2WAResolvedTarget = ""
\t\tif wv2Whatsapp != nil {
\t\t\t// Manual WhatsApp always restores the root chat UI in the SAME persistent
\t\t\t// profile. This prevents the off-screen background renderer from reopening
\t\t\t// as a blank theme-colour surface.
\t\t\tif !wv2WAProcessing { wv2Whatsapp.Navigate("https://web.whatsapp.com/") }
\t\t\tchMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)'''
s = require_replace(s, old_case2, new_case2, 'manual WhatsApp restore')

old_queue = '''\t// Fast path: if this exact Signal Link already resolved to the current hidden group chat,
\t// do not navigate/reload WhatsApp again. This keeps MH Analysis responsive.
\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Focus()
\twv2WAResolvedTarget = ""
\twv2Whatsapp.Navigate(target)
\ttime.AfterFunc(140*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppRefocusV5411, 0, 0) })
'''
new_queue = '''\t// Background send must never take Windows focus. Keep the same logged-in
\t// WhatsApp renderer alive off-screen. If the saved Signal Link is already the
\t// active chat, do not reload it; otherwise navigate once and let
\t// NavigationCompleted trigger the composer pass.
\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\tif wv2WAResolvedTarget != "" && strings.EqualFold(strings.TrimSpace(wv2WAResolvedTarget), target) {
\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, token, 0)
\t} else {
\t\twv2Whatsapp.Navigate(target)
\t}
'''
s = require_replace(s, old_queue, new_queue, 'background WhatsApp queue focus removal')

fn_start = s.index('func wv2EvalWhatsAppV54(token uintptr)')
script_start = s.index('\tscript := fmt.Sprintf(`(()=>{', fn_start)
script_end = s.index('\twv2ParkWhatsAppV547()', script_start)
new_script = r'''\tscript := fmt.Sprintf(`(()=>{
const msg=%s,isGroup=%s,token=%d;
const ack=(st)=>{try{window.external.invoke('MHWA|'+token+'|'+st)}catch(e){};return st};
const sentKey='mh-v55-sent-'+token,armedKey='mh-v55-armed-'+token;
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
  sessionStorage.setItem(sentKey,'1');sessionStorage.removeItem(armedKey);return ack('sent');
}
box.focus();
if(current!==wanted){
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
if(norm(box.innerText||box.textContent)!==wanted)return ack('waiting-composer');
sessionStorage.setItem(armedKey,'1');
box.focus();
return ack('composer-ready');
})()`, string(msgJSON), string(groupJSON), token)
'''.replace(r'\t','\t')
s = s[:script_start] + new_script + s[script_end:]
old_after = '''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Focus()
\twv2Whatsapp.Eval(script)
\ttime.AfterFunc(520*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppNativeEnterV5414, token, 0) })
\ttime.AfterFunc(980*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
}'''
new_after = '''\twv2ParkWhatsAppV547()
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Eval(script)
}'''
s = require_replace(s, old_after, new_after, 'WhatsApp eval no-focus tail')

native_start = s.index('func wv2WhatsAppNativeEnterV5414(token uintptr)')
native_end = s.index('\nfunc wv2WhatsAppAckV542(token uintptr)', native_start)
new_native = '''func wv2WhatsAppNativeEnterV5414(token uintptr) {
\tif token == 0 || token != wv2WAActiveToken || !wv2WAProcessing { return }
\t// Primary V55 route: Chromium DevTools sends a browser-trusted Enter directly
\t// to the focused WhatsApp composer. It works while the WebView is parked and
\t// does not move the user's mouse or foreground window.
\tif wv2WhatsAppTrustedEnterV55() { return }
\t// Compatibility fallback only when the WebView2 core has not been captured yet.
\th := wv2WhatsAppInputHWNDV5414(); if h == 0 { return }
\tdown := uintptr(1 | (0x1C << 16))
\tup := uintptr(1 | (0x1C << 16) | (1 << 30) | (1 << 31))
\tchSendMessageV5414.Call(h,0x0100,13,down)
\tchSendMessageV5414.Call(h,0x0102,13,down)
\tchSendMessageV5414.Call(h,0x0101,13,up)
}
'''
s = s[:native_start] + new_native + s[native_end:]

ack_start = s.index('func wv2WhatsAppAckV542(token uintptr)')
ack_end = s.index('\nfunc wv2FinishWhatsAppV54(token uintptr)', ack_start)
new_ack = '''func wv2WhatsAppAckV542(token uintptr) {
\tif token == 0 || token != wv2WAActiveToken || token != wv2WALastAckToken { return }
\tswitch wv2WALastAckStatus {
\tcase "sent":
\t\twv2WAResolvedTarget = wv2WAActiveTarget
\t\twv2FinishWhatsAppV54(token)
\tcase "composer-ready":
\t\twv2WhatsAppNativeEnterV5414(token)
\t\ttime.AfterFunc(420*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
\tcase "waiting-composer":
\t\ttime.AfterFunc(140*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
\t}
}
'''
s = s[:ack_start] + new_ack + s[ack_end:]

# MT5 activation: never show an HWND until it is verified as a child of MH Analysis.
act_start = s.index('func wv2ActivateMT5V5412()')
act_end = s.index('\nfunc wv2ShowMT5()', act_start)
new_act = '''func wv2ActivateMT5V5412() {
\tv546HideAllMT5TopLevel()
\tif chMT5Wnd == 0 { postMessage(hostHWND, wmSwitchAnalysis, 0, 0); return }
\tparent, _, _ := v36GetParent.Call(chMT5Wnd)
\tif parent != hostHWND {
\t\tchShowWindow.Call(chMT5Wnd, chSWHide)
\t\tif !v36EmbedMT5(chMT5Wnd) { postMessage(hostHWND, wmSwitchAnalysis, 0, 0); return }
\t\tparent, _, _ = v36GetParent.Call(chMT5Wnd)
\t\tif parent != hostHWND { chShowWindow.Call(chMT5Wnd, chSWHide); postMessage(hostHWND, wmSwitchAnalysis, 0, 0); return }
\t}
\twv2SetDesiredView(4)
\twv2HideAll()
\twv2ParkWhatsAppV547()
\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\tchMoveWindow.Call(chMT5Wnd,0,uintptr(barH),uintptr(w),uintptr(h),1)
\tchShowWindow.Call(chMT5Wnd,chSWShow)
\tchSetWindowPos.Call(chMT5Wnd,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\tchFocusEmbeddedBrowser(chMT5Wnd)
\tv546HideAllMT5TopLevel()
\tgo v55MaintainMT5Embed(8*time.Second)
}
'''
s = s[:act_start] + new_act + s[act_end:]

s = s.replace('chWstr("Version: V.54.14")', 'chWstr("Version: V.55.0")')
s = s.replace('MHAnalysisWebView2HostV54', 'MHAnalysisWebView2HostV55')
p.write_text(s, encoding='utf-8', newline='\n')

# Same-WebView CDP bridge. It deliberately reuses the callback ABI already in the
# repository, but NEVER starts a second WhatsApp controller/profile.
Path('whatsapp_v55.go').write_text(r'''//go:build windows

package main

import (
    "unsafe"
)

func wv2WhatsAppCDPFireV55(method, params string) bool {
    if wv2WhatsappCoreV55 == 0 { return false }
    desktopNativeWaInitTables()
    cb := &desktopNativeWaAsyncCB{Vtbl: &desktopNativeWaAsyncTable, Ref: 1, Ch: make(chan desktopNativeWaAsyncResult, 1)}
    ptr := uintptr(unsafe.Pointer(cb))
    desktopNativeWaPending.Store(ptr, cb)
    hr := comCall(
        wv2WhatsappCoreV55,
        36,
        uintptr(unsafe.Pointer(wstr(method))),
        uintptr(unsafe.Pointer(wstr(params))),
        ptr,
    )
    if int32(hr) < 0 {
        desktopNativeWaPending.Delete(ptr)
        return false
    }
    return true
}

func wv2WhatsAppTrustedEnterV55() bool {
    events := []string{
        `{"type":"rawKeyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
        `{"type":"char","key":"Enter","code":"Enter","text":"\r","unmodifiedText":"\r","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
        `{"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
    }
    for _, params := range events {
        if !wv2WhatsAppCDPFireV55("Input.dispatchKeyEvent", params) { return false }
    }
    return true
}
''', encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# MT5: enforce child-only window ownership and kill an MH-started terminal if
# Windows refuses embedding, so a standalone system terminal is never left open.
# -----------------------------------------------------------------------------
p = Path('mt5_embed_v36.go')
s = p.read_text(encoding='utf-8')
ensure_start = s.index('func chEnsureMT5TerminalV36() error {')
new_tail = r'''func v55MaintainMT5Embed(wait time.Duration) {
    deadline := time.Now().Add(wait)
    for time.Now().Before(deadline) {
        v546HideAllMT5TopLevel()
        chMu.Lock(); hwnd := chMT5Wnd; chMu.Unlock()
        if hwnd != 0 {
            parent, _, _ := v36GetParent.Call(hwnd)
            if parent != hostHWND {
                chShowWindow.Call(hwnd, chSWHide)
                _ = v36EmbedMT5(hwnd)
            }
        }
        time.Sleep(12 * time.Millisecond)
    }
    v546HideAllMT5TopLevel()
}

func v55MT5HideGuard(stop <-chan struct{}) {
    ticker := time.NewTicker(8 * time.Millisecond)
    defer ticker.Stop()
    for {
        select {
        case <-stop:
            v546HideAllMT5TopLevel()
            return
        case <-ticker.C:
            v546HideAllMT5TopLevel()
        }
    }
}

func chEnsureMT5TerminalV36() error {
    chMu.Lock(); existingEmbedded := chMT5Wnd; chMu.Unlock()
    if existingEmbedded != 0 {
        parent, _, _ := v36GetParent.Call(existingEmbedded)
        if parent == hostHWND {
            chResizeChildren(); chShowWindow.Call(existingEmbedded, chSWShow); chFocusEmbeddedBrowser(existingEmbedded)
            go v55MaintainMT5Embed(5*time.Second); go mt5ApplyLatestQueued(); return nil
        }
        chShowWindow.Call(existingEmbedded, chSWHide)
        chMu.Lock(); if chMT5Wnd == existingEmbedded { chMT5Wnd = 0 }; chMu.Unlock()
    }

    chMu.Lock()
    if chMT5StartingV34 { chMu.Unlock(); return nil }
    chMT5StartingV34 = true
    chMu.Unlock()
    defer func(){ chMu.Lock(); chMT5StartingV34 = false; chMu.Unlock() }()

    v546HideAllMT5TopLevel()
    if hwnd := v5410FindMT5Candidate(); hwnd != 0 {
        stop := make(chan struct{})
        go v55MT5HideGuard(stop)
        ok := v546EmbedOnlyMT5(5*time.Second)
        close(stop)
        if !ok { return errors.New("Installed MT5 was detected, but Windows refused child embedding. MH Analysis kept the standalone MT5 window hidden. Make sure MH Analysis and MT5 use the same Windows privilege level.") }
        go v55MaintainMT5Embed(8*time.Second); go mt5ApplyLatestQueued(); return nil
    }

    path, err := chMT5Executable()
    if err != nil { return err }
    v5410MT5ExeBase = strings.ToLower(filepath.Base(path))
    stop := make(chan struct{})
    go v55MT5HideGuard(stop)
    cmd := exec.Command(path)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow:true, CreationFlags:0x08000000}
    if err := cmd.Start(); err != nil { close(stop); return fmt.Errorf("Could not start MT5: %w", err) }
    chMu.Lock(); chMT5Cmd = cmd; chMu.Unlock()
    ok := v546EmbedOnlyMT5(20*time.Second)
    close(stop)
    if !ok {
        _ = cmd.Process.Kill()
        chMu.Lock(); if chMT5Cmd == cmd { chMT5Cmd = nil }; chMu.Unlock()
        v546HideAllMT5TopLevel()
        return errors.New("MT5 could not be embedded inside MH Analysis. The MH-started standalone terminal was closed instead of being left open.")
    }
    go v55MaintainMT5Embed(10*time.Second)
    go mt5ApplyLatestQueued()
    return nil
}
'''
s = s[:ensure_start] + new_tail
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# Recent Signals: one stable record store forever. Merge every historical
# signal-records-v*.json once, de-duplicate, and persist to signal-records.json.
# -----------------------------------------------------------------------------
p = Path('records_mt5_local.go')
s = p.read_text(encoding='utf-8')
start = s.index('func mt5LocalRecordsPath() string {')
end = s.index('\nfunc saveMT5LocalStore(s mt5LocalStore) error {', start)
new_records = r'''func mt5RecordsDir() string {
    b := os.Getenv("LOCALAPPDATA")
    if b == "" { b = os.TempDir() }
    return filepath.Join(b, "MHAnalysis")
}

func mt5LocalRecordsPath() string {
    return filepath.Join(mt5RecordsDir(), "signal-records.json")
}

func mt5LifecyclePath() (string, error) {
    appData := strings.TrimSpace(os.Getenv("APPDATA"))
    if appData == "" { return "", fmt.Errorf("Windows APPDATA is unavailable") }
    return filepath.Join(appData, "MetaQuotes", "Terminal", "Common", "Files", "MH_Analysis", "trade_events.jsonl"), nil
}

func normalizeMT5StoreV55(s mt5LocalStore) mt5LocalStore {
    if s.Version < 2 { s.Version = 2 }
    if s.Records == nil { s.Records = []mt5LocalRecord{} }
    for i := range s.Records {
        if s.Records[i].SignalID == "" && strings.HasPrefix(s.Records[i].ID, "MH") { s.Records[i].SignalID = s.Records[i].ID }
    }
    return s
}

func loadMT5StoreFileV55(path string) (mt5LocalStore, bool) {
    b, err := os.ReadFile(path)
    if err != nil { return mt5LocalStore{}, false }
    var s mt5LocalStore
    if json.Unmarshal(b, &s) != nil { return mt5LocalStore{}, false }
    return normalizeMT5StoreV55(s), true
}

func loadMT5LocalStore() mt5LocalStore {
    canonical := mt5LocalRecordsPath()
    paths := []string{canonical}
    legacy, _ := filepath.Glob(filepath.Join(mt5RecordsDir(), "signal-records-v*.json"))
    paths = append(paths, legacy...)
    merged := mt5LocalStore{Version: 2, Records: []mt5LocalRecord{}}
    index := map[string]int{}
    canonicalCount := -1
    for _, path := range paths {
        st, ok := loadMT5StoreFileV55(path)
        if !ok { continue }
        if filepath.Clean(path) == filepath.Clean(canonical) { canonicalCount = len(st.Records) }
        for _, rec := range st.Records {
            key := strings.TrimSpace(rec.SignalID)
            if key == "" { key = strings.TrimSpace(rec.ID) }
            if key == "" { key = fmt.Sprintf("%d|%s|%s|%s|%.8f", rec.CreatedAt, rec.Symbol, rec.Timeframe, rec.Direction, rec.Entry) }
            if at, exists := index[key]; exists {
                if rec.CreatedAt >= merged.Records[at].CreatedAt { merged.Records[at] = rec }
                continue
            }
            index[key] = len(merged.Records)
            merged.Records = append(merged.Records, rec)
        }
    }
    merged = normalizeMT5StoreV55(merged)
    if canonicalCount < 0 || len(merged.Records) > canonicalCount { _ = saveMT5LocalStore(merged) }
    return merged
}
'''
s = s[:start] + new_records + s[end:]
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# Economic calendar: no remote iframe at all. Stable disk cache paints instantly;
# current data refreshes in background from the JSON feed.
# -----------------------------------------------------------------------------
Path('calendar3d.go').write_text(r'''package main

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
    Time string `json:"time"`; Country string `json:"country"`; Title string `json:"title"`; Impact string `json:"impact"`
    Forecast string `json:"forecast"`; Previous string `json:"previous"`; Actual string `json:"actual"`
}
type calendarUiDay struct { Date string `json:"date"`; Label string `json:"label"`; Events []calendarUiEvent `json:"events"` }
type calendarDiskV55 struct { CachedAt int64 `json:"cached_at"`; Days []calendarUiDay `json:"days"` }

var calendar3Mu sync.Mutex
var calendar3At time.Time
var calendar3Cache map[string]any
var calendar3Refreshing bool

func calendarDiskPathV55() string {
    base := os.Getenv("LOCALAPPDATA"); if base == "" { base = os.TempDir() }
    return filepath.Join(base, "MHAnalysis", "economic-calendar.json")
}

func loadCalendarDiskV55() (map[string]any, bool) {
    b, err := os.ReadFile(calendarDiskPathV55()); if err != nil { return nil, false }
    var d calendarDiskV55; if json.Unmarshal(b, &d) != nil || len(d.Days) == 0 { return nil, false }
    return map[string]any{"days": d.Days, "source": "Economic calendar • last known values", "cached_at": d.CachedAt}, true
}

func saveCalendarDiskV55(out map[string]any) {
    days, ok := out["days"].([]calendarUiDay); if !ok || len(days) == 0 { return }
    p := calendarDiskPathV55(); _ = os.MkdirAll(filepath.Dir(p), 0755)
    b, _ := json.Marshal(calendarDiskV55{CachedAt: time.Now().Unix(), Days: days})
    tmp := p + ".tmp"; if os.WriteFile(tmp, b, 0600) == nil { _ = os.Remove(p); _ = os.Rename(tmp, p) }
}

func (e *calendarFeedEvent) UnmarshalJSON(b []byte) error {
    type raw struct { Title string `json:"title"`; Country string `json:"country"`; Date string `json:"date"`; Impact string `json:"impact"`; Forecast string `json:"forecast"`; Previous string `json:"previous"`; Actual string `json:"actual"` }
    var x raw; if err := json.Unmarshal(b, &x); err != nil { return err }
    e.Title=x.Title; e.Country=x.Country; e.Date=x.Date; e.Impact=x.Impact; e.Forecast=x.Forecast; e.Previous=x.Previous; e.Actual=x.Actual
    return nil
}

func fetchCalendarFeed(cli *http.Client, endpoint string) []calendarFeedEvent {
    req, _ := http.NewRequest(http.MethodGet, endpoint, nil); req.Header.Set("User-Agent", "MH-Analysis/55")
    resp, err := cli.Do(req); if err != nil { return nil }; defer resp.Body.Close()
    if resp.StatusCode < 200 || resp.StatusCode >= 300 { return nil }
    var out []calendarFeedEvent; if json.NewDecoder(resp.Body).Decode(&out) != nil { return nil }; return out
}

func buildEconomicCalendarV55(timeout time.Duration) map[string]any {
    cli := &http.Client{Timeout: timeout}
    ch := make(chan []calendarFeedEvent, 2)
    go func(){ ch <- fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json") }()
    go func(){ ch <- fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json") }()
    raw := make([]calendarFeedEvent,0,96)
    timer := time.NewTimer(timeout + 300*time.Millisecond); defer timer.Stop()
    for i:=0; i<2; i++ { select { case part:=<-ch: raw=append(raw,part...); case <-timer.C: i=2 } }
    type timed struct{ t time.Time; e calendarFeedEvent }
    items:=make([]timed,0,len(raw)); seen:=map[string]bool{}
    now:=time.Now(); today:=time.Date(now.Year(),now.Month(),now.Day(),0,0,0,0,now.Location())
    for _,ev:=range raw {
        impact:=strings.ToLower(strings.TrimSpace(ev.Impact)); if impact!="high"&&impact!="medium"&&impact!="med"&&impact!="low" { continue }
        t,err:=time.Parse(time.RFC3339,strings.TrimSpace(ev.Date)); if err!=nil { continue }; local:=t.Local(); if local.Before(today){continue}
        key:=local.Format(time.RFC3339)+"|"+strings.TrimSpace(ev.Country)+"|"+strings.TrimSpace(ev.Title); if seen[key]{continue}; seen[key]=true
        items=append(items,timed{t:local,e:ev})
    }
    sort.Slice(items,func(i,j int)bool{return items[i].t.Before(items[j].t)})
    selected:=make([]string,0,3); dateSeen:=map[string]bool{}
    for _,it:=range items { d:=it.t.Format("2006-01-02"); if !dateSeen[d]{dateSeen[d]=true;selected=append(selected,d);if len(selected)==3{break}} }
    days:=make([]calendarUiDay,0,len(selected))
    for _,d:=range selected {
        day:=calendarUiDay{Date:d,Events:[]calendarUiEvent{}}
        for _,it:=range items { if it.t.Format("2006-01-02")!=d{continue}; if day.Label==""{day.Label=it.t.Format("Monday, Jan 2, 2006")}; impact:=strings.TrimSpace(it.e.Impact);if strings.EqualFold(impact,"med"){impact="Medium"};day.Events=append(day.Events,calendarUiEvent{Time:it.t.Format("03:04 PM"),Country:strings.ToUpper(strings.TrimSpace(it.e.Country)),Title:strings.TrimSpace(it.e.Title),Impact:impact,Forecast:strings.TrimSpace(it.e.Forecast),Previous:strings.TrimSpace(it.e.Previous),Actual:strings.TrimSpace(it.e.Actual)}) }
        if len(day.Events)>0{days=append(days,day)}
    }
    if len(days)==0{return nil}
    return map[string]any{"days":days,"source":"Economic calendar • Low / Medium / High","cached_at":time.Now().Unix()}
}

func setCalendarCacheV55(out map[string]any) {
    if out==nil{return}; calendar3Mu.Lock(); calendar3Cache=out; calendar3At=time.Now(); calendar3Mu.Unlock(); saveCalendarDiskV55(out)
}

func refreshCalendarBackgroundV55() {
    calendar3Mu.Lock(); if calendar3Refreshing{calendar3Mu.Unlock();return}; calendar3Refreshing=true; calendar3Mu.Unlock()
    go func(){
        if out:=buildEconomicCalendarV55(3500*time.Millisecond);out!=nil{setCalendarCacheV55(out)}
        calendar3Mu.Lock();calendar3Refreshing=false;calendar3Mu.Unlock()
    }()
}

func warmStartupCalendarV55() {
    if out,ok:=loadCalendarDiskV55();ok{calendar3Mu.Lock();calendar3Cache=out;calendar3At=time.Now();calendar3Mu.Unlock();refreshCalendarBackgroundV55();return}
    if out:=buildEconomicCalendarV55(2300*time.Millisecond);out!=nil{setCalendarCacheV55(out)}
}

func economicCalendarHandler(w http.ResponseWriter,r *http.Request){
    if r.Method!=http.MethodGet{http.Error(w,"method",http.StatusMethodNotAllowed);return};w.Header().Set("Content-Type","application/json")
    calendar3Mu.Lock();cached:=calendar3Cache;age:=time.Since(calendar3At);calendar3Mu.Unlock()
    if cached!=nil{_ = json.NewEncoder(w).Encode(cached);if age>2*time.Minute{refreshCalendarBackgroundV55()};return}
    if disk,ok:=loadCalendarDiskV55();ok{calendar3Mu.Lock();calendar3Cache=disk;calendar3At=time.Now();calendar3Mu.Unlock();_ = json.NewEncoder(w).Encode(disk);refreshCalendarBackgroundV55();return}
    if out:=buildEconomicCalendarV55(3500*time.Millisecond);out!=nil{setCalendarCacheV55(out);_ = json.NewEncoder(w).Encode(out);return}
    _ = json.NewEncoder(w).Encode(map[string]any{"days":[]calendarUiDay{},"source":"Economic calendar refreshing"})
}
''', encoding='utf-8', newline='\n')

# Startup cache warming.
p = Path('main.go'); s = p.read_text(encoding='utf-8')
s = require_replace(s, '\twarmStartupTickerV5413()\n', '\twarmStartupTickerV5413()\n\twarmStartupCalendarV55()\n', 'calendar startup warm')
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# Frontend: Recent Signals always represent analyses (even same-active updates),
# queue WhatsApp synchronously to the native sender, and never reference Myfxbook.
# -----------------------------------------------------------------------------
p = Path('web/app.js'); s = p.read_text(encoding='utf-8')
s = require_replace(s, 'function addRecent(d,state=\'NEW\'){\n  if(d?._sameActiveSignal){renderRecentSignals();return}\n', 'function addRecent(d,state=\'NEW\'){\n', 'Recent Signals same-active suppression')

old_send = '''function sendDecisionWhatsApp(d,action,status=''){
  const message=decisionWhatsAppMessage(d,action,status);
  setTimeout(()=>{(async()=>{
    try{
      await refreshBackendSettings();
      if(!backendSettings.has_whatsapp)throw new Error('WhatsApp Signal Link is not saved. Open the WhatsApp tab and set Signal Link.');
      const r=await fetch('/api/send-whatsapp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
      let j={};try{j=await r.json()}catch(_){ }
      if(!r.ok)throw new Error(j.error||'WhatsApp queue failed');
    }catch(e){console.warn('Background WhatsApp send failed',e)}
  })()},0);
  return Promise.resolve({ok:true,queued:true,background:true});
}'''
new_send = '''async function sendDecisionWhatsApp(d,action,status=''){
  const message=decisionWhatsAppMessage(d,action,status);
  await refreshBackendSettings();
  if(!backendSettings.has_whatsapp)throw new Error('WhatsApp Signal Link is not saved. Open the WhatsApp tab and set Signal Link.');
  const r=await fetch('/api/send-whatsapp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
  let j={};try{j=await r.json()}catch(_){ }
  if(!r.ok)throw new Error(j.error||'WhatsApp queue failed');
  return j;
}'''
s = require_replace(s, old_send, new_send, 'WhatsApp queue acknowledgement')

old_calendar_catch = "}catch(e){if(!root.children.length)if(!root.querySelector('.calDayV545'))root.innerHTML='<div class=\"calendarLoading\">Loading calendar…</div>';setTimeout(loadEconomicCalendarV545,1500)}finally{clearTimeout(kill)}"
new_calendar_catch = "}catch(e){if(!root.querySelector('.calDayV545'))root.innerHTML='<div class=\"calendarLoading\">Calendar data refreshing…</div>';setTimeout(loadEconomicCalendarV545,1500)}finally{clearTimeout(kill)}"
s = require_replace(s, old_calendar_catch, new_calendar_catch, 'calendar retry text')
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/index.html'); s = p.read_text(encoding='utf-8')
s = s.replace('<link rel="preconnect" href="https://widget.mfbcdn.net" />\n','')
s = s.replace('id="mhUpdateVersionV001">V.54.14<', 'id="mhUpdateVersionV001">V.55.0<')
if 'widget.mfbcdn.net' in s or 'myfxbook' in s.lower(): raise SystemExit('Myfxbook reference remained in V55 HTML')
p.write_text(s, encoding='utf-8', newline='\n')

# Version stamps.
Path('VERSION').write_text('V.55.0\n', encoding='ascii')
for file, pattern, repl in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.55.0"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.55.0"'),
]:
    q=Path(file); z=q.read_text(encoding='utf-8'); z,n=re.subn(pattern,repl,z,count=1)
    if n!=1: raise SystemExit('V55 version stamp failed: '+file)
    q.write_text(z,encoding='utf-8',newline='\n')

# Remove the historical V54 patch chain and V54 publishing workflows. V55's
# normal build must compile only the files committed in the repository.
for q in Path('.github/scripts').glob('v54*_patch.py'):
    q.unlink()
for q in Path('.github/workflows').glob('publish-v54*.yml'):
    q.unlink()
