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
}

var settingsMu sync.RWMutex
var cfg settings
var server *http.Server
var hostHWND, btnAnalysis, btnWhatsapp uintptr
var serverURL string

func settingsPath() string {
	b := os.Getenv("LOCALAPPDATA")
	if b == "" { b = os.TempDir() }
	return filepath.Join(b, "MHAnalysis", "settings-v795.json")
}
func loadSettings() { b,e:=os.ReadFile(settingsPath()); if e==nil { _=json.Unmarshal(b,&cfg) } }
func saveSettings() error { settingsMu.RLock(); v:=cfg; settingsMu.RUnlock(); p:=settingsPath(); _=os.MkdirAll(filepath.Dir(p),0755); b,_:=json.MarshalIndent(v,"","  "); return os.WriteFile(p,b,0600) }
func getSettings() settings { settingsMu.RLock(); defer settingsMu.RUnlock(); return cfg }

func main() {
	loadSettings()
	sub,err:=fs.Sub(webFS,"web"); if err!=nil{return}
	mux:=http.NewServeMux()
	registerLicenseRoutes(mux)
	mux.HandleFunc("/api/license/nav-notice",licNavNoticeHandler)
	mux.HandleFunc("/api/update/status",mhUpdateStatusHandlerV001)
	mux.HandleFunc("/api/update/start",mhUpdateStartHandlerV001)
	mux.HandleFunc("/api/update/progress",mhUpdateProgressHandlerV001)
	mux.HandleFunc("/api/settings",settingsHandler)
	mux.HandleFunc("/api/history",historyHandler)
	mux.HandleFunc("/api/public-ticker",publicTickerHandler)
	mux.HandleFunc("/api/marketcap",marketcapHandler)
	mux.HandleFunc("/api/news-risk",newsRiskHandler)
	mux.HandleFunc("/api/economic-calendar",economicCalendarHandler)
	mux.HandleFunc("/api/open-whatsapp",func(w http.ResponseWriter,r *http.Request){if r.Method==http.MethodPost{postMessage(hostHWND,wmSwitchWhatsApp,0,0);w.WriteHeader(204);return};http.Error(w,"method",405)})
	mux.HandleFunc("/api/open-api-settings",func(w http.ResponseWriter,r *http.Request){if r.Method!=http.MethodPost{http.Error(w,"method",405);return};postMessage(hostHWND,chWMOpenAPISettings,0,0);w.WriteHeader(204)})
	mux.HandleFunc("/api/open-whatsapp-settings",func(w http.ResponseWriter,r *http.Request){if r.Method!=http.MethodPost{http.Error(w,"method",405);return};postMessage(hostHWND,chWMOpenWhatsAppSettings,0,0);w.WriteHeader(204)})
	registerRecordsRoutes(mux)
	registerMT5PrefillRoutes(mux)
	registerRecordsV2Routes(mux)
	mux.HandleFunc("/api/send-whatsapp",sendWhatsappHandler)
	mux.HandleFunc("/api/shutdown",func(w http.ResponseWriter,r *http.Request){w.WriteHeader(204);go func(){time.Sleep(80*time.Millisecond);postMessage(hostHWND,wmClose,0,0)}()})
	mux.Handle("/",noCache(http.FileServer(http.FS(sub))))
	ln,err:=net.Listen("tcp","127.0.0.1:0"); if err!=nil{messageBox(0,"Could not start local MH Analysis service.","MH Analysis",0x10);return}
	serverURL="http://"+ln.Addr().String()+"/"
	server=&http.Server{Handler:licenseGate(mux),ReadHeaderTimeout:10*time.Second}; go server.Serve(ln)
	// V.09: one native MH Analysis window with WebView2 embedded directly.
	runWebView2Host()
	_=server.Close()
}
func noCache(h http.Handler) http.Handler { return http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.Header().Set("Cache-Control","no-store, no-cache, must-revalidate, max-age=0");h.ServeHTTP(w,r)}) }

func settingsHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json")
	switch r.Method{
	case http.MethodGet:v:=getSettings();_=json.NewEncoder(w).Encode(map[string]any{"has_api_key":strings.TrimSpace(v.APIKey)!="","has_whatsapp":strings.TrimSpace(v.WhatsAppLink)!="","whatsapp_link":v.WhatsAppLink})
	case http.MethodPost:
		var m map[string]*string;if json.NewDecoder(r.Body).Decode(&m)!=nil{http.Error(w,"bad json",400);return}
		settingsMu.Lock();if p,ok:=m["api_key"];ok{if p==nil{cfg.APIKey=""}else{cfg.APIKey=strings.TrimSpace(*p)}};if p,ok:=m["whatsapp_link"];ok{if p==nil{cfg.WhatsAppLink=""}else{cfg.WhatsAppLink=strings.TrimSpace(*p)}};settingsMu.Unlock();_=saveSettings();v:=getSettings();_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"has_api_key":v.APIKey!="","has_whatsapp":v.WhatsAppLink!=""})
	default:http.Error(w,"method",405)}
}

type candle struct{T int64 `json:"t"`;O float64 `json:"o"`;H float64 `json:"h"`;L float64 `json:"l"`;C float64 `json:"c"`;V float64 `json:"v"`}
var rateMu sync.Mutex
var calls []time.Time
func allowCall()bool{rateMu.Lock();defer rateMu.Unlock();now:=time.Now();cut:=now.Add(-61*time.Second);j:=0;for _,t:=range calls{if t.After(cut){calls[j]=t;j++}};calls=calls[:j];if len(calls)>=3{return false};calls=append(calls,now);return true}

func historyHandler(w http.ResponseWriter,r *http.Request){
	if r.Method!=http.MethodPost{http.Error(w,"method",405);return};w.Header().Set("Content-Type","application/json");if !allowCall(){w.WriteHeader(429);_=json.NewEncoder(w).Encode(map[string]any{"error":"Too many fresh market requests. Please wait about a minute."});return}
	var q struct{Symbol,Period string};if json.NewDecoder(r.Body).Decode(&q)!=nil{http.Error(w,"bad request",400);return};v:=getSettings();if strings.TrimSpace(v.APIKey)==""{w.WriteHeader(401);_=json.NewEncoder(w).Encode(map[string]any{"error":"Access Key is not saved."});return}
	sym:=strings.ToUpper(strings.TrimSpace(q.Symbol));per:=normalizePeriod(q.Period);var endpoint,fcsSym,typ string;if sym=="XAUUSD"{endpoint="https://api-v4.fcsapi.com/forex/history";fcsSym="XAUUSD";typ="commodity"}else if sym=="BTCUSDT"{endpoint="https://api-v4.fcsapi.com/crypto/history";fcsSym="BINANCE:BTCUSDT";typ="crypto"}else{w.WriteHeader(400);_=json.NewEncoder(w).Encode(map[string]any{"error":"Unsupported symbol"});return}
	u,_:=url.Parse(endpoint);z:=u.Query();z.Set("access_key",v.APIKey);z.Set("symbol",fcsSym);z.Set("period",per);z.Set("type",typ);z.Set("length","300");z.Set("is_chart","0");u.RawQuery=z.Encode();cli:=&http.Client{Timeout:18*time.Second};req,_:=http.NewRequest(http.MethodGet,u.String(),nil);req.Header.Set("User-Agent","MH-Analysis/79.6");resp,err:=cli.Do(req);if err!=nil{w.WriteHeader(502);_=json.NewEncoder(w).Encode(map[string]any{"error":"History connection failed: "+err.Error()});return};defer resp.Body.Close();body,_:=io.ReadAll(io.LimitReader(resp.Body,8<<20));var root any;if json.Unmarshal(body,&root)!=nil{w.WriteHeader(502);_=json.NewEncoder(w).Encode(map[string]any{"error":"History service returned unreadable data"});return};out:=extractCandles(root);sort.Slice(out,func(i,j int)bool{return out[i].T<out[j].T});_=json.NewEncoder(w).Encode(map[string]any{"candles":out})
}

// Remaining helpers below are unchanged from the restored runtime.
