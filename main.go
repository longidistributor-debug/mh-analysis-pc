package main

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

//go:embed web/*
var webFS embed.FS

type settings struct {
	APIKey       string `json:"api_key"`
	WhatsAppLink string `json:"whatsapp_link"`
	WhatsAppLink2 string `json:"whatsapp_link2"`
}

var settingsMu sync.RWMutex
var cfg settings
var server *http.Server
var hostHWND, btnAnalysis, btnWhatsapp uintptr
var serverURL string

func settingsPath() string {
	b := os.Getenv("LOCALAPPDATA")
	if b == "" {
		b = os.TempDir()
	}
	return filepath.Join(b, "MHAnalysis", "settings-v795.json")
}
func loadSettings() {
	b, e := os.ReadFile(settingsPath())
	if e == nil {
		_ = json.Unmarshal(b, &cfg)
	}
}
func saveSettings() error {
	settingsMu.RLock()
	v := cfg
	settingsMu.RUnlock()
	p := settingsPath()
	_ = os.MkdirAll(filepath.Dir(p), 0755)
	b, _ := json.MarshalIndent(v, "", "  ")
	return os.WriteFile(p, b, 0600)
}
func getSettings() settings { settingsMu.RLock(); defer settingsMu.RUnlock(); return cfg }

func warmStartupTickerV5413() {
	c := loadUICacheV5411()
	if len(c.Ticker) >= 5 { return }
	done := make(chan struct{})
	go func(){ _ = refreshTickerV5411(); close(done) }()
	select {
	case <-done:
	case <-time.After(1600 * time.Millisecond):
	}
}

func main() {
	loadSettings()
	warmStartupTickerV5413()
	warmStartupCalendarV55()
	sub, err := fs.Sub(webFS, "web")
	if err != nil {
		return
	}
	mux := http.NewServeMux()
	registerLicenseRoutes(mux)
	mux.HandleFunc("/api/license/nav-notice", licNavNoticeHandler)
	mux.HandleFunc("/api/update/status", mhUpdateStatusHandlerV001)
	mux.HandleFunc("/api/update/start", mhUpdateStartHandlerV001)
	mux.HandleFunc("/api/update/progress", mhUpdateProgressHandlerV001)
	mux.HandleFunc("/api/settings", settingsHandler)
	mux.HandleFunc("/api/history", historyHandler)
	mux.HandleFunc("/api/public-ticker", publicTickerHandlerV5411)
	mux.HandleFunc("/api/ui-cache", uiCacheHandlerV5411)
	mux.HandleFunc("/api/marketcap", marketcapHandler)
	mux.HandleFunc("/api/news-risk", newsRiskHandler)
	mux.HandleFunc("/api/economic-calendar", economicCalendarHandler)
	mux.HandleFunc("/api/open-support-external", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", 405)
			return
		}
		// Open support outside MH Analysis; never replace the internal WhatsApp automation view.
		_ = exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", "https://wa.me/923434824609").Start()
		w.WriteHeader(204)
	})
	mux.HandleFunc("/api/open-whatsapp", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			postMessage(hostHWND, wmSwitchWhatsApp, 0, 0)
			w.WriteHeader(204)
			return
		}
		http.Error(w, "method", 405)
	})
	mux.HandleFunc("/api/open-api-settings", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", 405)
			return
		}
		postMessage(hostHWND, chWMOpenAPISettings, 0, 0)
		w.WriteHeader(204)
	})
	mux.HandleFunc("/api/open-whatsapp-settings", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", 405)
			return
		}
		postMessage(hostHWND, chWMOpenWhatsAppSettings, 0, 0)
		w.WriteHeader(204)
	})
	registerRecordsRoutes(mux)        // MH_RECORDS_V796_PATCH
	registerEASignalBridgeRoutes(mux) // V30 automatic unique-signal pending bridge
	registerMT5PrefillRoutes(mux)     // MH_NATIVE_MT5_PREFILL_V796
	registerRecordsV2Routes(mux)      // MH_RECORDS_MT5_LOCAL_V797
	mux.HandleFunc("/api/send-whatsapp", sendWhatsappHandler)
	mux.HandleFunc("/api/shutdown", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(204)
		go func() { time.Sleep(80 * time.Millisecond); postMessage(hostHWND, wmClose, 0, 0) }()
	})
	mux.Handle("/", noCache(http.FileServer(http.FS(sub))))
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		messageBox(0, "Could not start local MH Analysis service.", "MH Analysis", 0x10)
		return
	}
	serverURL = "http://" + ln.Addr().String() + "/"
	server = &http.Server{Handler: licenseGate(mux), ReadHeaderTimeout: 10 * time.Second}
	go server.Serve(ln)
	runWebView2Host()
	_ = server.Close()
}
func noCache(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
		h.ServeHTTP(w, r)
	})
}

func settingsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	switch r.Method {
	case http.MethodGet:
		v := getSettings()
		_ = json.NewEncoder(w).Encode(map[string]any{"has_api_key": strings.TrimSpace(v.APIKey) != "", "has_whatsapp": strings.TrimSpace(v.WhatsAppLink) != "" || strings.TrimSpace(v.WhatsAppLink2) != "", "whatsapp_link": v.WhatsAppLink, "whatsapp_link2": v.WhatsAppLink2})
	case http.MethodPost:
		var m map[string]*string
		if json.NewDecoder(r.Body).Decode(&m) != nil {
			http.Error(w, "bad json", 400)
			return
		}
		settingsMu.Lock()
		if p, ok := m["api_key"]; ok {
			if p == nil {
				cfg.APIKey = ""
			} else {
				cfg.APIKey = strings.TrimSpace(*p)
			}
		}
		if p, ok := m["whatsapp_link"]; ok {
			if p == nil { cfg.WhatsAppLink = "" } else { cfg.WhatsAppLink = strings.TrimSpace(*p) }
		}
		if p, ok := m["whatsapp_link2"]; ok {
			if p == nil { cfg.WhatsAppLink2 = "" } else { cfg.WhatsAppLink2 = strings.TrimSpace(*p) }
		}
		settingsMu.Unlock()
		_ = saveSettings()
		v := getSettings()
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "has_api_key": v.APIKey != "", "has_whatsapp": strings.TrimSpace(v.WhatsAppLink) != "" || strings.TrimSpace(v.WhatsAppLink2) != ""})
	default:
		http.Error(w, "method", 405)
	}
}

type candle struct {
	T int64   `json:"t"`
	O float64 `json:"o"`
	H float64 `json:"h"`
	L float64 `json:"l"`
	C float64 `json:"c"`
	V float64 `json:"v"`
}

var rateMu sync.Mutex
var calls []time.Time

func allowCall() bool {
	rateMu.Lock()
	defer rateMu.Unlock()
	now := time.Now()
	cut := now.Add(-61 * time.Second)
	j := 0
	for _, t := range calls {
		if t.After(cut) {
			calls[j] = t
			j++
		}
	}
	calls = calls[:j]
	if len(calls) >= 3 {
		return false
	}
	calls = append(calls, now)
	return true
}
func historyHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method", 405)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	if !allowCall() {
		w.WriteHeader(429)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Too many fresh market requests. Please wait about a minute."})
		return
	}
	var q struct{ Symbol, Period string }
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad request", 400)
		return
	}
	v := getSettings()
	if strings.TrimSpace(v.APIKey) == "" {
		w.WriteHeader(401)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Access Key is not saved."})
		return
	}
	sym := strings.ToUpper(strings.TrimSpace(q.Symbol))
	per := normalizePeriod(q.Period)
	var endpoint string
	var fcsSym, typ string
	if sym == "XAUUSD" {
		endpoint = "https://api-v4.fcsapi.com/forex/history"
		fcsSym = "XAUUSD"
		typ = "commodity"
	} else if sym == "BTCUSDT" {
		endpoint = "https://api-v4.fcsapi.com/crypto/history"
		fcsSym = "BINANCE:BTCUSDT"
		typ = "crypto"
	} else {
		w.WriteHeader(400)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Unsupported symbol"})
		return
	}
	u, _ := url.Parse(endpoint)
	z := u.Query()
	z.Set("access_key", v.APIKey)
	z.Set("symbol", fcsSym)
	z.Set("period", per)
	z.Set("type", typ)
	z.Set("length", "300")
	z.Set("is_chart", "0")
	u.RawQuery = z.Encode()
	cli := &http.Client{Timeout: 18 * time.Second}
	req, _ := http.NewRequest(http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", "MH-Analysis/79.6")
	resp, err := cli.Do(req)
	if err != nil {
		w.WriteHeader(502)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "History connection failed: " + err.Error()})
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	var root any
	if json.Unmarshal(body, &root) != nil {
		w.WriteHeader(502)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "History service returned unreadable data"})
		return
	}
	cs := extractCandles(root)
	if len(cs) > 300 {
		cs = cs[len(cs)-300:]
	}
	if resp.StatusCode >= 400 || len(cs) == 0 {
		status := resp.StatusCode
		if status < 400 {
			status = 502
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": extractError(root, "No usable candles returned"), "response_shape": fmt.Sprintf("%T", root)})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"candles": cs, "meta": map[string]any{"source": "direct history", "symbol": sym, "period": q.Period, "count": len(cs)}})
}
func normalizePeriod(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	switch s {
	case "1m":
		return "1"
	case "5m":
		return "5"
	case "15m":
		return "15"
	case "30m":
		return "30"
	case "1h", "60m":
		return "60"
	}
	return strings.TrimSuffix(s, "m")
}
func extractError(v any, def string) string {
	if m, ok := v.(map[string]any); ok {
		for _, k := range []string{"msg", "message", "error", "response"} {
			if x, ok := m[k]; ok {
				if s, ok := x.(string); ok && s != "" {
					return s
				}
			}
		}
	}
	return def
}
func fnum(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case json.Number:
		f, e := x.Float64()
		return f, e == nil
	case string:
		f, e := strconv.ParseFloat(strings.TrimSpace(x), 64)
		return f, e == nil
	case int:
		return float64(x), true
	}
	return 0, false
}
func fint64(v any) (int64, bool) {
	if f, ok := fnum(v); ok {
		if f > 1e12 {
			f /= 1000
		}
		return int64(f), true
	}
	if s, ok := v.(string); ok {
		layouts := []string{"2006-01-02 15:04:05", "2006-01-02T15:04:05Z", time.RFC3339}
		for _, l := range layouts {
			if t, e := time.Parse(l, s); e == nil {
				return t.Unix(), true
			}
		}
	}
	return 0, false
}
func val(m map[string]any, keys ...string) any {
	for _, k := range keys {
		if v, ok := m[k]; ok {
			return v
		}
	}
	return nil
}
func candleFromMap(m map[string]any, keyTime any) (c candle, ok bool) {
	o, o1 := fnum(val(m, "o", "open", "Open"))
	h, h1 := fnum(val(m, "h", "high", "High"))
	l, l1 := fnum(val(m, "l", "low", "Low"))
	cl, c1 := fnum(val(m, "c", "close", "Close"))
	if !(o1 && h1 && l1 && c1) {
		return c, false
	}
	t, t1 := fint64(val(m, "t", "time", "tm", "timestamp", "date", "datetime"))
	if !t1 && keyTime != nil {
		t, t1 = fint64(keyTime)
	}
	if !t1 {
		return c, false
	}
	vv, _ := fnum(val(m, "v", "volume", "Volume"))
	return candle{T: t, O: o, H: h, L: l, C: cl, V: vv}, true
}
func extractCandles(root any) []candle {
	out := []candle{}
	seen := map[int64]bool{}
	var walk func(any, any)
	walk = func(v any, key any) {
		switch x := v.(type) {
		case map[string]any:
			if c, ok := candleFromMap(x, key); ok {
				if !seen[c.T] {
					seen[c.T] = true
					out = append(out, c)
				}
			}
			for k, y := range x {
				walk(y, k)
			}
		case []any:
			for _, y := range x {
				walk(y, nil)
			}
		}
	}
	walk(root, nil)
	sort.Slice(out, func(i, j int) bool { return out[i].T < out[j].T })
	return out
}

var pubMu sync.Mutex
var pubAt time.Time
var pubCache map[string]any

func publicTickerHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	pubMu.Lock()
	if time.Since(pubAt) < 30*time.Second && pubCache != nil { c := pubCache; pubMu.Unlock(); _ = json.NewEncoder(w).Encode(c); return }
	pubMu.Unlock()
	type tickerPart map[string]any
	ch := make(chan tickerPart, 3)
	cli := &http.Client{Timeout: 2 * time.Second}
	go func(){ part:=tickerPart{}; fetchJSON(cli, "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true", func(v any) { if m,ok:=v.(map[string]any);ok { if b,ok:=m["bitcoin"].(map[string]any);ok { part["btc_usd"],_=fnum(b["usd"]); part["btc_change_24h"],_=fnum(b["usd_24h_change"]) }; if e,ok:=m["ethereum"].(map[string]any);ok { part["eth_usd"],_=fnum(e["usd"]); part["eth_change_24h"],_=fnum(e["usd_24h_change"]) } } }); ch<-part }()
	go func(){ part:=tickerPart{}; fetchJSON(cli, "https://xaus.com/api/v1/spot", func(v any) { if g:=findNumberByKeys(v,"price","usd","gold","xau");g>0 { part["gold_usd"]=g } }); ch<-part }()
	go func(){ part:=tickerPart{}; fetchJSON(cli, "https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP", func(v any) { if m,ok:=v.(map[string]any);ok { if rates,ok:=m["rates"].(map[string]any);ok { eur,_:=fnum(rates["EUR"]);jpy,_:=fnum(rates["JPY"]);gbp,_:=fnum(rates["GBP"]); if eur>0 {part["eurusd"]=1/eur}; if jpy>0 {part["usdjpy"]=jpy}; if gbp>0 {part["gbpusd"]=1/gbp} } } }); ch<-part }()
	out:=map[string]any{}
	timer:=time.NewTimer(2200*time.Millisecond); defer timer.Stop()
	for i:=0;i<3;i++ { select { case part:=<-ch: for k,v:=range part {out[k]=v}; case <-timer.C: i=3 } }
	pubMu.Lock(); pubAt=time.Now(); if len(out)>0 {pubCache=out} else if pubCache!=nil {out=pubCache}; pubMu.Unlock()
	_ = json.NewEncoder(w).Encode(out)
}
func fetchJSON(cli *http.Client, u string, fn func(any)) {
	resp, e := cli.Get(u)
	if e != nil {
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return
	}
	var v any
	if json.NewDecoder(io.LimitReader(resp.Body, 2<<20)).Decode(&v) == nil {
		fn(v)
	}
}
func findNumberByKeys(v any, keys ...string) float64 {
	switch x := v.(type) {
	case map[string]any:
		for _, k := range keys {
			if y, ok := x[k]; ok {
				if f, ok := fnum(y); ok && f > 0 {
					return f
				}
			}
		}
		for _, y := range x {
			if f := findNumberByKeys(y, keys...); f > 0 {
				return f
			}
		}
	case []any:
		for _, y := range x {
			if f := findNumberByKeys(y, keys...); f > 0 {
				return f
			}
		}
	}
	return 0
}

var marketMu sync.Mutex
var marketAt time.Time
var marketCache map[string]any

func marketcapHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	marketMu.Lock()
	if time.Since(marketAt) < 60*time.Second && marketCache != nil {
		c := marketCache
		marketMu.Unlock()
		_ = json.NewEncoder(w).Encode(c)
		return
	}
	marketMu.Unlock()
	out := map[string]any{}
	cli := &http.Client{Timeout: 8 * time.Second}
	fetchJSON(cli, "https://api.coingecko.com/api/v3/global", func(v any) {
		if m, ok := v.(map[string]any); ok {
			if d, ok := m["data"].(map[string]any); ok {
				if tc, ok := d["total_market_cap"].(map[string]any); ok {
					out["total_market_cap"], _ = fnum(tc["usd"])
				}
				if p, ok := d["market_cap_percentage"].(map[string]any); ok {
					out["btc_dominance"], _ = fnum(p["btc"])
				}
			}
		}
	})
	fetchJSON(cli, "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_market_cap=true&include_24hr_change=true", func(v any) {
		if m, ok := v.(map[string]any); ok {
			if b, ok := m["bitcoin"].(map[string]any); ok {
				out["btc_market_cap"], _ = fnum(b["usd_market_cap"])
				out["btc_change_24h"], _ = fnum(b["usd_24h_change"])
			}
		}
	})
	marketMu.Lock()
	marketAt = time.Now()
	marketCache = out
	marketMu.Unlock()
	_ = json.NewEncoder(w).Encode(out)
}

// --- WhatsApp ---
type whatsappReq struct {
	Message string `json:"message"`
}
type waTask struct {
	target  string
	message string
}

var waMu sync.Mutex
var waQueue []waTask

func sendWhatsappHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method", 405)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	var q whatsappReq
	if json.NewDecoder(r.Body).Decode(&q) != nil || strings.TrimSpace(q.Message) == "" {
		http.Error(w, "bad request", 400)
		return
	}
	v := getSettings()
	saved := []string{strings.TrimSpace(v.WhatsAppLink), strings.TrimSpace(v.WhatsAppLink2)}
	targets := make([]string, 0, 2)
	for _, raw := range saved {
		if raw == "" { continue }
		target := ""
		if u, err := url.Parse(raw); err == nil && (u.Scheme == "https" || u.Scheme == "http") && (strings.EqualFold(u.Host, "chat.whatsapp.com") || strings.EqualFold(u.Host, "web.whatsapp.com") || strings.EqualFold(u.Host, "wa.me") || strings.HasSuffix(strings.ToLower(u.Host), ".whatsapp.com")) {
			target = raw
		} else if num := digits(raw); num != "" {
			target = "https://web.whatsapp.com/send?phone=" + num
		}
		if target == "" {
			w.WriteHeader(400)
			_ = json.NewEncoder(w).Encode(map[string]any{"error": "Each Signal Link must be a WhatsApp group/chat link or phone number."})
			return
		}
		targets = append(targets, target)
	}
	if len(targets) == 0 {
		w.WriteHeader(400)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "WhatsApp Signal Link is not saved."})
		return
	}
	waMu.Lock()
	for _, target := range targets { waQueue = append(waQueue, waTask{target: target, message: q.Message}) }
	waMu.Unlock()
	postMessage(hostHWND, wmWhatsAppSend, 0, 0)
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "queued": true, "destinations": len(targets)})
}
func digits(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// --- Native Windows host with REAL WebView2 controls (no visible Edge browser window) ---
var user32 = syscall.NewLazyDLL("user32.dll")
var kernel32 = syscall.NewLazyDLL("kernel32.dll")
var ole32 = syscall.NewLazyDLL("ole32.dll")
var pRegisterClassEx = user32.NewProc("RegisterClassExW")
var pCreateWindowEx = user32.NewProc("CreateWindowExW")
var pDefWindowProc = user32.NewProc("DefWindowProcW")
var pShowWindow = user32.NewProc("ShowWindow")
var pUpdateWindow = user32.NewProc("UpdateWindow")
var pGetMessage = user32.NewProc("GetMessageW")
var pTranslateMessage = user32.NewProc("TranslateMessage")
var pDispatchMessage = user32.NewProc("DispatchMessageW")
var pPostQuit = user32.NewProc("PostQuitMessage")
var pGetClientRect = user32.NewProc("GetClientRect")
var pPostMessage = user32.NewProc("PostMessageW")
var pLoadCursor = user32.NewProc("LoadCursorW")
var pLoadIcon = user32.NewProc("LoadIconW")
var pGetModuleHandle = kernel32.NewProc("GetModuleHandleW")
var pDestroyWindow = user32.NewProc("DestroyWindow")
var pMessageBox = user32.NewProc("MessageBoxW")
var pSetForegroundWindow = user32.NewProc("SetForegroundWindow")
var pCoInitializeEx = ole32.NewProc("CoInitializeEx")

const (
	wmDestroy        = 0x0002
	wmSize           = 0x0005
	wmCommand        = 0x0111
	wmClose          = 0x0010
	wmSwitchWhatsApp = 0x8001
	wmSwitchAnalysis = 0x8002
	wmWhatsAppSend   = 0x8003
	wmWhatsAppClick  = 0x8004
	wsOverlapped     = 0x00CF0000
	wsVisible        = 0x10000000
	wsChild          = 0x40000000
	swHide           = 0
	swShow           = 5
	swMaximize       = 3
	sizeMinimized    = 1
	barH             = 46
	idAnalysis       = 1001
	idWhatsapp       = 1002
)

type wndClassEx struct {
	CbSize        uint32
	Style         uint32
	LpfnWndProc   uintptr
	CbClsExtra    int32
	CbWndExtra    int32
	HInstance     uintptr
	HIcon         uintptr
	HCursor       uintptr
	HbrBackground uintptr
	LpszMenuName  *uint16
	LpszClassName *uint16
	HIconSm       uintptr
}
type point struct{ X, Y int32 }
type msg struct {
	Hwnd           uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Pt             point
	LPrivate       uint32
}
type rect struct{ L, T, R, B int32 }

func wstr(s string) *uint16 { p, _ := syscall.UTF16PtrFromString(s); return p }
func postMessage(h uintptr, m uint32, w, l uintptr) {
	if h != 0 {
		pPostMessage.Call(h, uintptr(m), w, l)
	}
}
func messageBox(h uintptr, text, title string, flags uintptr) {
	pMessageBox.Call(h, uintptr(unsafe.Pointer(wstr(text))), uintptr(unsafe.Pointer(wstr(title))), flags)
}

// Minimal COM/WebView2 ABI.
type guid struct {
	D1     uint32
	D2, D3 uint16
	D4     [8]byte
}
type cbVtbl struct{ QueryInterface, AddRef, Release, Invoke uintptr }
type cbObj struct {
	Vtbl *cbVtbl
	Kind int32
	Ref  uint32
}

var cbTable cbVtbl
var envCB, analysisCB, whatsappCB *cbObj
var wvEnv, analysisCtl, analysisCore, whatsappCtl, whatsappCore uintptr
var activeView = 1
var whatsappCreating bool
var runtimeDLL *syscall.DLL
var createEnvProc *syscall.Proc

var iidIUnknown = guid{D1: 0x00000000, D2: 0x0000, D3: 0x0000, D4: [8]byte{0xC0, 0, 0, 0, 0, 0, 0, 0x46}}
var iidEnvHandler = guid{D1: 0x4E8A3389, D2: 0xC9D8, D3: 0x4BD2, D4: [8]byte{0xB6, 0xB5, 0x12, 0x4F, 0xEE, 0x6C, 0xC1, 0x4D}}
var iidCtlHandler = guid{D1: 0x6C4819F3, D2: 0xC9B7, D3: 0x4260, D4: [8]byte{0x81, 0x27, 0xC9, 0xF5, 0xBD, 0xE7, 0xF6, 0x8C}}

func guidEq(a, b *guid) bool { return a != nil && b != nil && *a == *b }
func cbQI(this, riid, out uintptr) uintptr {
	if out == 0 {
		return uintptr(uint32(0x80004003))
	}
	*(*uintptr)(unsafe.Pointer(out)) = 0
	o := (*cbObj)(unsafe.Pointer(this))
	g := (*guid)(unsafe.Pointer(riid))
	ok := guidEq(g, &iidIUnknown)
	if o.Kind == 1 {
		ok = ok || guidEq(g, &iidEnvHandler)
	} else {
		ok = ok || guidEq(g, &iidCtlHandler)
	}
	if !ok {
		return uintptr(uint32(0x80004002))
	}
	*(*uintptr)(unsafe.Pointer(out)) = this
	o.Ref++
	return 0
}
func cbAddRef(this uintptr) uintptr {
	o := (*cbObj)(unsafe.Pointer(this))
	o.Ref++
	return uintptr(o.Ref)
}
func cbRelease(this uintptr) uintptr {
	o := (*cbObj)(unsafe.Pointer(this))
	if o.Ref > 1 {
		o.Ref--
	}
	return uintptr(o.Ref)
}
func cbInvoke(this, result, arg uintptr) uintptr {
	o := (*cbObj)(unsafe.Pointer(this))
	if int32(result) < 0 || arg == 0 {
		messageBox(hostHWND, fmt.Sprintf("WebView2 initialization failed (0x%08X).", uint32(result)), "MH Analysis", 0x10)
		return 0
	}
	switch o.Kind {
	case 1:
		wvEnv = arg
		analysisCB = newCB(2)
		if hr := createController(wvEnv, hostHWND, analysisCB); int32(hr) < 0 {
			messageBox(hostHWND, "Could not create MH Analysis WebView2 control.", "MH Analysis", 0x10)
		}
	case 2:
		analysisCtl = arg
		analysisCore = getCore(arg)
		if analysisCore == 0 {
			messageBox(hostHWND, "MH Analysis WebView2 core was unavailable.", "MH Analysis", 0x10)
			return 0
		}
		wvNavigate(analysisCore, serverURL)
		wvVisible(analysisCtl, true)
		resizeWebViews()
		pShowWindow.Call(hostHWND, swMaximize)
		pUpdateWindow.Call(hostHWND)
	case 3:
		whatsappCtl = arg
		whatsappCore = getCore(arg)
		whatsappCreating = false
		if whatsappCore != 0 {
			wvNavigate(whatsappCore, "https://web.whatsapp.com/")
			wvVisible(whatsappCtl, activeView == 2)
			resizeWebViews()
			if activeView == 2 {
				wvVisible(analysisCtl, false)
			}
			processWhatsAppQueue()
		}
	}
	return 0
}
func newCB(kind int32) *cbObj { o := &cbObj{Vtbl: &cbTable, Kind: kind, Ref: 1}; return o }
func initCallbacks() {
	cbTable = cbVtbl{syscall.NewCallback(cbQI), syscall.NewCallback(cbAddRef), syscall.NewCallback(cbRelease), syscall.NewCallback(cbInvoke)}
}
func vfunc(obj uintptr, index int) uintptr {
	if obj == 0 {
		return 0
	}
	vt := *(*uintptr)(unsafe.Pointer(obj))
	return *(*uintptr)(unsafe.Pointer(vt + uintptr(index)*unsafe.Sizeof(uintptr(0))))
}
func comCall(obj uintptr, index int, args ...uintptr) uintptr {
	fn := vfunc(obj, index)
	if fn == 0 {
		return uintptr(uint32(0x80004003))
	}
	a := append([]uintptr{obj}, args...)
	r, _, _ := syscall.SyscallN(fn, a...)
	return r
}
func createController(env, parent uintptr, cb *cbObj) uintptr {
	return comCall(env, 3, parent, uintptr(unsafe.Pointer(cb)))
}
func getCore(ctl uintptr) uintptr {
	var core uintptr
	hr := comCall(ctl, 25, uintptr(unsafe.Pointer(&core)))
	if int32(hr) < 0 {
		return 0
	}
	return core
}
func wvNavigate(core uintptr, u string) uintptr {
	return comCall(core, 5, uintptr(unsafe.Pointer(wstr(u))))
}
func wvVisible(ctl uintptr, on bool) {
	v := uintptr(0)
	if on {
		v = 1
	}
	_ = comCall(ctl, 4, v)
}
func wvBounds(ctl uintptr, r rect) {
	if ctl != 0 {
		_ = comCall(ctl, 6, uintptr(unsafe.Pointer(&r)))
		_ = comCall(ctl, 23)
	}
}
func wvExecute(core uintptr, script string) {
	if core != 0 {
		_ = comCall(core, 29, uintptr(unsafe.Pointer(wstr(script))), 0)
	}
}

func runtimeVersionKey(path string) []int {
	d := filepath.Dir(filepath.Dir(filepath.Dir(path)))
	v := filepath.Base(d)
	parts := strings.Split(v, ".")
	out := make([]int, len(parts))
	for i, p := range parts {
		out[i], _ = strconv.Atoi(p)
	}
	return out
}
func newerVersion(a, b []int) bool {
	n := len(a)
	if len(b) > n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		x, y := 0, 0
		if i < len(a) {
			x = a[i]
		}
		if i < len(b) {
			y = b[i]
		}
		if x != y {
			return x > y
		}
	}
	return false
}
func findWebViewRuntimeDLL() (string, error) {
	roots := []string{os.Getenv("ProgramFiles(x86)"), os.Getenv("ProgramFiles"), os.Getenv("LOCALAPPDATA")}
	var candidates []string
	patterns := []string{}
	for _, r := range roots {
		if r == "" {
			continue
		}
		patterns = append(patterns, filepath.Join(r, "Microsoft", "EdgeWebView", "Application", "*", "EBWebView", "x64", "EmbeddedBrowserWebView.dll"), filepath.Join(r, "Microsoft", "Edge", "Application", "*", "EBWebView", "x64", "EmbeddedBrowserWebView.dll"))
	}
	for _, pat := range patterns {
		m, _ := filepath.Glob(pat)
		candidates = append(candidates, m...)
	}
	if len(candidates) == 0 {
		return "", fmt.Errorf("Microsoft Edge WebView2 runtime (x64) was not found")
	}
	best := candidates[0]
	bk := runtimeVersionKey(best)
	for _, p := range candidates[1:] {
		k := runtimeVersionKey(p)
		if newerVersion(k, bk) {
			best, bk = p, k
		}
	}
	return best, nil
}
func startWebView2() error {
	path, err := findWebViewRuntimeDLL()
	if err != nil {
		return err
	}
	runtimeDLL, err = syscall.LoadDLL(path)
	if err != nil {
		return fmt.Errorf("could not load WebView2 runtime: %w", err)
	}
	createEnvProc, err = runtimeDLL.FindProc("CreateWebViewEnvironmentWithOptionsInternal")
	if err != nil {
		return fmt.Errorf("WebView2 runtime export missing")
	}
	profile := filepath.Join(os.Getenv("LOCALAPPDATA"), "MHAnalysis", "WebView2Profile")
	_ = os.MkdirAll(profile, 0755)
	envCB = newCB(1)
	r, _, _ := createEnvProc.Call(1, 0, uintptr(unsafe.Pointer(wstr(profile))), 0, uintptr(unsafe.Pointer(envCB)))
	if int32(r) < 0 {
		return fmt.Errorf("WebView2 environment start failed: 0x%08X", uint32(r))
	}
	return nil
}
func ensureWhatsappWebView() {
	if whatsappCore != 0 || whatsappCreating || wvEnv == 0 {
		return
	}
	whatsappCreating = true
	whatsappCB = newCB(3)
	if hr := createController(wvEnv, hostHWND, whatsappCB); int32(hr) < 0 {
		whatsappCreating = false
		messageBox(hostHWND, "Could not create WhatsApp WebView2 control.", "MH Analysis", 0x10)
	}
}
func resizeWebViews() {
	if hostHWND == 0 {
		return
	}
	var rc rect
	pGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&rc)))
	w := rc.R - rc.L
	h := rc.B - rc.T
	if w < 1 || h <= barH {
		return
	}
	r := rect{L: 0, T: barH, R: w, B: h}
	wvBounds(analysisCtl, r)
	wvBounds(whatsappCtl, r)
}
func switchAnalysis() {
	activeView = 1
	wvVisible(analysisCtl, true)
	wvVisible(whatsappCtl, false)
	resizeWebViews()
}
func switchWhatsapp() {
	activeView = 2
	ensureWhatsappWebView()
	if whatsappCtl != 0 {
		wvVisible(analysisCtl, false)
		wvVisible(whatsappCtl, true)
		resizeWebViews()
	}
}
func processWhatsAppQueue() {
	if whatsappCore == 0 {
		ensureWhatsappWebView()
		return
	}
	waMu.Lock()
	if len(waQueue) == 0 {
		waMu.Unlock()
		return
	}
	t := waQueue[0]
	waQueue = waQueue[1:]
	waMu.Unlock()
	wvNavigate(whatsappCore, t.target)
	// V33: the group URL opens the chat, but it does not carry the organized signal text.
	// Wait for WhatsApp Web, inject the queued message into the composer, then click Send.
	msgJSON, _ := json.Marshal(t.message)
	// V34_WA_RETRY: WhatsApp Web load time varies. Retry the exact same queued message
	// from Go until the composer is expected to exist; JS guards against duplicate injection.
	for _, delay := range []time.Duration{3 * time.Second, 6 * time.Second, 10 * time.Second, 15 * time.Second} {
		d := delay
		time.AfterFunc(d, func() {
			script := fmt.Sprintf(`(()=>{const msg=%s;const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(!box)return false;const mark='mh-v34-'+btoa(unescape(encodeURIComponent(msg))).slice(0,24);if(window[mark])return true;box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,msg);box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));const b=document.querySelector('[data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]');if(b){b.click();window[mark]=true;return true;}box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));window[mark]=true;return true;})()`, string(msgJSON))
			wvExecute(whatsappCore, script)
		})
	}
}
func clickWhatsAppSend() {
	script := `(()=>{const b=document.querySelector('[data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]');if(b){b.click();return true;}const box=document.querySelector('[contenteditable="true"][data-tab]');if(box){box.focus();box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));return true;}return false;})()`
	wvExecute(whatsappCore, script)
	time.AfterFunc(1200*time.Millisecond, func() { postMessage(hostHWND, wmWhatsAppSend, 0, 0) })
}

func runHost() {
	runtime.LockOSThread()
	initCallbacks()
	_, _, _ = pCoInitializeEx.Call(0, 2)
	cls := wstr("MHAnalysisWebView2V800")
	hinst, _, _ := pGetModuleHandle.Call(0)
	cursor, _, _ := pLoadCursor.Call(0, 32512)
	icon, _, _ := pLoadIcon.Call(hinst, 1)
	wc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: 6, LpszClassName: cls}
	if r, _, _ := pRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc))); r == 0 {
		messageBox(0, "Could not initialize MH Analysis window.", "MH Analysis", 0x10)
		return
	}
	hwnd, _, _ := pCreateWindowEx.Call(0, uintptr(unsafe.Pointer(cls)), uintptr(unsafe.Pointer(wstr("MH Analysis"))), wsOverlapped, 0, 0, 1280, 820, 0, 0, hinst, 0)
	if hwnd == 0 {
		return
	}
	hostHWND = hwnd
	btnAnalysis, _, _ = pCreateWindowEx.Call(0, uintptr(unsafe.Pointer(wstr("BUTTON"))), uintptr(unsafe.Pointer(wstr("MH Analysis"))), wsChild|wsVisible, 8, 7, 140, 32, hwnd, idAnalysis, hinst, 0)
	btnWhatsapp, _, _ = pCreateWindowEx.Call(0, uintptr(unsafe.Pointer(wstr("BUTTON"))), uintptr(unsafe.Pointer(wstr("WhatsApp"))), wsChild|wsVisible, 156, 7, 140, 32, hwnd, idWhatsapp, hinst, 0)
	if err := startWebView2(); err != nil {
		messageBox(hwnd, err.Error(), "MH Analysis", 0x10)
		pDestroyWindow.Call(hwnd)
		return
	}
	var m msg
	for {
		r, _, _ := pGetMessage.Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) <= 0 {
			break
		}
		pTranslateMessage.Call(uintptr(unsafe.Pointer(&m)))
		pDispatchMessage.Call(uintptr(unsafe.Pointer(&m)))
	}
}
func wndProc(hwnd uintptr, m uint32, w, l uintptr) uintptr {
	switch m {
	case wmCommand:
		id := int(w & 0xffff)
		if id == idAnalysis {
			switchAnalysis()
		} else if id == idWhatsapp {
			switchWhatsapp()
		}
		return 0
	case wmSwitchWhatsApp:
		switchWhatsapp()
		return 0
	case wmSwitchAnalysis:
		switchAnalysis()
		return 0
	case wmWhatsAppSend:
		processWhatsAppQueue()
		return 0
	case wmWhatsAppClick:
		clickWhatsAppSend()
		return 0
	case wmSize:
		if w != sizeMinimized {
			resizeWebViews()
		}
		return 0
	case wmClose:
		pDestroyWindow.Call(hwnd)
		return 0
	case wmDestroy:
		if analysisCtl != 0 {
			_ = comCall(analysisCtl, 24)
		}
		if whatsappCtl != 0 {
			_ = comCall(whatsappCtl, 24)
		}
		pPostQuit.Call(0)
		return 0
	}
	r, _, _ := pDefWindowProc.Call(hwnd, uintptr(m), w, l)
	return r
}
