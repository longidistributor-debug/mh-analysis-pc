package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

// MH_EA_SIGNAL_READER_BRIDGE_V798
// Existing signal handoff is preserved. The EA still reads signal.txt and writes status.txt.
// V798 additionally reads active_state.txt so MH Analysis can lock opposite-direction
// handoffs while a real MT5 position/pending order is still active.
// active_state.txt format (one line per live position/order):
// SYMBOL|TYPE|TICKET|STATE|ENTRY|SL|TP|LOT|UPDATED_UNIX
// Example: XAUUSD|BUY|123456|POSITION|2365.10|2358.00|2378.00|0.02|1789990000
// Empty/missing active_state.txt means no active MT5 exposure is reported.

type eaSignalRequest struct {
	SignalID string  `json:"signal_id"`
	Symbol   string  `json:"symbol"`
	Type     string  `json:"type"`
	Entry    float64 `json:"entry"`
	SL       float64 `json:"sl"`
	TP       float64 `json:"tp"`
	Lot      float64 `json:"lot"`
	Expiry   int64   `json:"expiry"`
}

type eaActiveTrade struct {
	Symbol  string  `json:"symbol"`
	Type    string  `json:"type"`
	Ticket  string  `json:"ticket"`
	State   string  `json:"state"`
	Entry   float64 `json:"entry"`
	SL      float64 `json:"sl"`
	TP      float64 `json:"tp"`
	Lot     float64 `json:"lot"`
	Updated int64   `json:"updated"`
}

var eaSafeToken = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,80}$`)
var eaPublishMu sync.Mutex

func registerEASignalBridgeRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/mt5/ea/send", eaSignalSendHandler)
	mux.HandleFunc("/api/mt5/ea/status", eaSignalStatusHandler)
	mux.HandleFunc("/api/mt5/ea/active", eaActiveStateHandler)
}

func mt5CommonBridgeDir() (string, error) {
	appData := strings.TrimSpace(os.Getenv("APPDATA"))
	if appData == "" { return "", fmt.Errorf("Windows APPDATA is unavailable") }
	dir := filepath.Join(appData, "MetaQuotes", "Terminal", "Common", "Files", "MH_Analysis")
	if err := os.MkdirAll(dir, 0755); err != nil { return "", fmt.Errorf("could not create MT5 Common Files bridge: %w", err) }
	return dir, nil
}

func normalizeEABridgeSymbol(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	if s == "BTCUSDT" { return "BTCUSD" }
	return s
}

func cleanEAToken(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "|", "_")
	s = strings.ReplaceAll(s, "\r", "_")
	s = strings.ReplaceAll(s, "\n", "_")
	return s
}

func eaDirection(t string) string {
	t = strings.ToUpper(strings.TrimSpace(t))
	if strings.HasPrefix(t, "BUY") { return "BUY" }
	if strings.HasPrefix(t, "SELL") { return "SELL" }
	return ""
}

func parseEAFloat(s string) float64 {
	v, _ := strconv.ParseFloat(strings.TrimSpace(s), 64)
	return v
}

func readEAActiveTrades() ([]eaActiveTrade, error) {
	dir, err := mt5CommonBridgeDir(); if err != nil { return nil, err }
	b, err := os.ReadFile(filepath.Join(dir, "active_state.txt"))
	if err != nil {
		if os.IsNotExist(err) { return []eaActiveTrade{}, nil }
		return nil, err
	}
	lines := strings.Split(strings.ReplaceAll(string(b), "\r\n", "\n"), "\n")
	out := make([]eaActiveTrade, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line); if line == "" { continue }
		p := strings.Split(line, "|"); if len(p) < 4 { continue }
		t := eaActiveTrade{Symbol:normalizeEABridgeSymbol(p[0]), Type:strings.ToUpper(strings.TrimSpace(p[1])), Ticket:strings.TrimSpace(p[2]), State:strings.ToUpper(strings.TrimSpace(p[3]))}
		if len(p)>4 { t.Entry=parseEAFloat(p[4]) }; if len(p)>5 { t.SL=parseEAFloat(p[5]) }; if len(p)>6 { t.TP=parseEAFloat(p[6]) }; if len(p)>7 { t.Lot=parseEAFloat(p[7]) }; if len(p)>8 { t.Updated,_=strconv.ParseInt(strings.TrimSpace(p[8]),10,64) }
		if t.Symbol=="" || eaDirection(t.Type)=="" { continue }
		if t.State=="CLOSED" || t.State=="CANCELLED" || t.State=="EXPIRED" { continue }
		out=append(out,t)
	}
	return out,nil
}

func activeExposureFor(symbol string) ([]eaActiveTrade, string, error) {
	all,err:=readEAActiveTrades(); if err!=nil{return nil,"",err}
	symbol=normalizeEABridgeSymbol(symbol); matches:=[]eaActiveTrade{}; dir:=""
	for _,t:=range all { if t.Symbol!=symbol {continue}; d:=eaDirection(t.Type); if d==""{continue}; matches=append(matches,t); if dir==""{dir=d}else if dir!=d{dir="MIXED"} }
	return matches,dir,nil
}

func eaActiveStateHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method!=http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	sym:=normalizeEABridgeSymbol(r.URL.Query().Get("symbol"))
	if sym!="" { trades,dir,err:=activeExposureFor(sym); if err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}; _=json.NewEncoder(w).Encode(map[string]any{"ok":true,"symbol":sym,"active":len(trades)>0,"direction":dir,"trades":trades}); return }
	trades,err:=readEAActiveTrades(); if err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}; _=json.NewEncoder(w).Encode(map[string]any{"ok":true,"active":len(trades)>0,"trades":trades})
}

func eaSignalSendHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost { http.Error(w, "method", http.StatusMethodNotAllowed); return }
	var q eaSignalRequest
	if err := json.NewDecoder(r.Body).Decode(&q); err != nil { w.WriteHeader(http.StatusBadRequest); _ = json.NewEncoder(w).Encode(map[string]any{"error":"bad signal payload"}); return }
	q.SignalID = cleanEAToken(q.SignalID); q.Symbol = normalizeEABridgeSymbol(q.Symbol); q.Type = strings.ToUpper(cleanEAToken(q.Type))
	if q.SignalID == "" { q.SignalID = "MH" + strconv.FormatInt(time.Now().UnixMilli(),10) }
	if !eaSafeToken.MatchString(q.SignalID) { w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"invalid signal id"}); return }
	if q.Symbol != "XAUUSD" && q.Symbol != "BTCUSD" { w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported EA bridge symbol"}); return }
	switch q.Type { case "BUY","SELL","BUY_LIMIT","SELL_LIMIT","BUY_STOP","SELL_STOP": default: w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported pending signal type"}); return }
	if q.Entry<=0 || q.SL<=0 || q.TP<=0 { w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"entry/sl/tp must be positive"}); return }
	if q.Lot<0 { q.Lot=0 }; if q.Expiry<0 { q.Expiry=0 }

	// Hard server-side reversal guard. Analysis may still calculate normally, but an
	// opposite EA handoff cannot be published while MT5 reports live same-symbol exposure.
	trades,activeDir,err:=activeExposureFor(q.Symbol); if err!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":"could not read MT5 active state: "+err.Error()}); return }
	newDir:=eaDirection(q.Type)
	if len(trades)>0 && (activeDir=="MIXED" || (activeDir!="" && activeDir!=newDir)) {
		w.WriteHeader(http.StatusConflict)
		_=json.NewEncoder(w).Encode(map[string]any{"ok":false,"blocked":true,"code":"ACTIVE_TRADE_REVERSAL_LOCK","error":"Opposite signal blocked: active MT5 trade/pending order must be resolved first","symbol":q.Symbol,"active_direction":activeDir,"requested_direction":newDir,"trades":trades})
		return
	}

	dir,err:=mt5CommonBridgeDir(); if err!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()}); return }
	eaPublishMu.Lock(); defer eaPublishMu.Unlock()
	dst:=filepath.Join(dir,"signal.txt")
	deadline:=time.Now().Add(6*time.Second)
	for {
		_,statErr:=os.Stat(dst)
		if os.IsNotExist(statErr) { break }
		if statErr!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":"could not inspect EA mailbox: "+statErr.Error()}); return }
		if time.Now().After(deadline) { w.WriteHeader(http.StatusConflict); _=json.NewEncoder(w).Encode(map[string]any{"error":"previous MT5 signal is still waiting for EA consumption; new signal was not overwritten"}); return }
		time.Sleep(100*time.Millisecond)
	}
	line:=strings.Join([]string{q.SignalID,q.Symbol,q.Type,strconv.FormatFloat(q.Entry,'f',-1,64),strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),strconv.FormatFloat(q.Lot,'f',-1,64),strconv.FormatInt(q.Expiry,10)},"|")+"\r\n"
	tmp:=filepath.Join(dir,"signal.new")
	if err:=os.WriteFile(tmp,[]byte(line),0644); err!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":"could not write EA signal: "+err.Error()}); return }
	if err:=os.Rename(tmp,dst); err!=nil { _=os.Remove(tmp); w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":"could not publish EA signal: "+err.Error()}); return }
	_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"signal_id":q.SignalID,"symbol":q.Symbol,"type":q.Type,"file":dst})
}

func eaSignalStatusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	dir,err:=mt5CommonBridgeDir(); if err!=nil { w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()}); return }
	p:=filepath.Join(dir,"status.txt"); b,err:=os.ReadFile(p)
	if err!=nil { if os.IsNotExist(err) { _=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":"","exists":false}); return }; w.WriteHeader(http.StatusInternalServerError); _=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()}); return }
	line:=strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b),"\r\n","\n"),"\n",2)[0]); _=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":line,"exists":line!=""})
}
