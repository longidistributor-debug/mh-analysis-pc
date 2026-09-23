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

// MH_EA_SIGNAL_READER_BRIDGE_V800
// signal.txt is a latest-signal mailbox, not a consume-and-delete queue.
// The EA deduplicates by signal_id. V799 therefore atomically replaces signal.txt
// instead of waiting for the EA to delete it (the decoder never deletes it).
// active_state.txt accepted format from the decoder:
// FLAT
// ACTIVE|BUY/SELL|SYMBOL|POSITION/PENDING|TICKET|MAGIC
// manage.txt: MANAGE_ID|SYMBOL|BUY/SELL|SL|TP|REASON

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

type eaManageRequest struct {
	ManageID  string  `json:"manage_id"`
	Symbol    string  `json:"symbol"`
	Direction string  `json:"direction"`
	SL        float64 `json:"sl"`
	TP        float64 `json:"tp"`
	Reason    string  `json:"reason"`
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
	mux.HandleFunc("/api/mt5/ea/manage", eaManageHandler)
	mux.HandleFunc("/api/mt5/ea/manage-status", eaManageStatusHandler)
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
	// Broker terminals often append suffixes such as XAUUSDm / XAUUSD.pro.
	// Canonicalize them so active_state from MT5 matches the app symbols.
	if strings.HasPrefix(s,"XAUUSD") { return "XAUUSD" }
	if strings.HasPrefix(s,"BTCUSDT") || strings.HasPrefix(s,"BTCUSD") { return "BTCUSD" }
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
		line = strings.TrimSpace(line)
		if line == "" || strings.EqualFold(line,"FLAT") { continue }
		p := strings.Split(line,"|")
		// Decoder V1.21+: ACTIVE|DIRECTION|SYMBOL|POSITION/PENDING|TICKET|MAGIC
		if len(p) >= 5 && strings.EqualFold(strings.TrimSpace(p[0]),"ACTIVE") {
			t := eaActiveTrade{Type:strings.ToUpper(strings.TrimSpace(p[1])),Symbol:normalizeEABridgeSymbol(p[2]),State:strings.ToUpper(strings.TrimSpace(p[3])),Ticket:strings.TrimSpace(p[4])}
			if t.Symbol!="" && eaDirection(t.Type)!="" { out=append(out,t) }
			continue
		}
		// Backward compatibility with the earlier bridge format.
		if len(p) < 4 { continue }
		t := eaActiveTrade{Symbol:normalizeEABridgeSymbol(p[0]),Type:strings.ToUpper(strings.TrimSpace(p[1])),Ticket:strings.TrimSpace(p[2]),State:strings.ToUpper(strings.TrimSpace(p[3]))}
		if t.Symbol!="" && eaDirection(t.Type)!="" && t.State!="CLOSED" && t.State!="CANCELLED" && t.State!="EXPIRED" { out=append(out,t) }
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

func eaManageHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json")
	if r.Method!=http.MethodPost{http.Error(w,"method",http.StatusMethodNotAllowed);return}
	var q eaManageRequest
	if err:=json.NewDecoder(r.Body).Decode(&q);err!=nil{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"bad manage payload"});return}
	q.ManageID=cleanEAToken(q.ManageID);q.Symbol=normalizeEABridgeSymbol(q.Symbol);q.Direction=eaDirection(q.Direction);q.Reason=cleanEAToken(q.Reason)
	if q.ManageID==""{q.ManageID="MHM"+strconv.FormatInt(time.Now().UnixMilli(),10)}
	if !eaSafeToken.MatchString(q.ManageID){w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"invalid manage id"});return}
	if q.Symbol!="XAUUSD"&&q.Symbol!="BTCUSD"{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported EA bridge symbol"});return}
	if q.Direction!="BUY"&&q.Direction!="SELL"{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"direction must be BUY or SELL"});return}
	if q.SL<=0||q.TP<=0{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"sl/tp must be positive"});return}
	dir,err:=mt5CommonBridgeDir();if err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}
	line:=strings.Join([]string{q.ManageID,q.Symbol,q.Direction,strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),q.Reason},"|")+"\r\n"
	dst:=filepath.Join(dir,"manage.txt");tmp:=filepath.Join(dir,"manage.new")
	eaPublishMu.Lock();defer eaPublishMu.Unlock()
	if err:=os.WriteFile(tmp,[]byte(line),0644);err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":"could not write EA manage command: "+err.Error()});return}
	_=os.Remove(dst)
	if err:=os.Rename(tmp,dst);err!=nil{_=os.Remove(tmp);w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":"could not publish EA manage command: "+err.Error()});return}
	_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"manage_id":q.ManageID,"symbol":q.Symbol,"direction":q.Direction,"sl":q.SL,"tp":q.TP})
}

func eaManageStatusHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json")
	if r.Method!=http.MethodGet{http.Error(w,"method",http.StatusMethodNotAllowed);return}
	dir,err:=mt5CommonBridgeDir();if err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}
	b,err:=os.ReadFile(filepath.Join(dir,"manage_status.txt"))
	if err!=nil{if os.IsNotExist(err){_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":"","exists":false});return};w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}
	line:=strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b),"\r\n","\n"),"\n",2)[0])
	_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":line,"exists":line!=""})
}

func eaSignalSendHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost { http.Error(w, "method", http.StatusMethodNotAllowed); return }
	var q eaSignalRequest
	if err := json.NewDecoder(r.Body).Decode(&q); err != nil { w.WriteHeader(http.StatusBadRequest); _ = json.NewEncoder(w).Encode(map[string]any{"error":"bad signal payload"}); return }
	q.SignalID=cleanEAToken(q.SignalID); q.Symbol=normalizeEABridgeSymbol(q.Symbol); q.Type=strings.ToUpper(cleanEAToken(q.Type))
	if q.SignalID=="" { q.SignalID="MH"+strconv.FormatInt(time.Now().UnixMilli(),10) }
	if !eaSafeToken.MatchString(q.SignalID) { w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"invalid signal id"}); return }
	if q.Symbol!="XAUUSD" && q.Symbol!="BTCUSD" { w.WriteHeader(http.StatusBadRequest); _=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported EA bridge symbol"}); return }
	switch q.Type {case "BUY","SELL","BUY_LIMIT","SELL_LIMIT","BUY_STOP","SELL_STOP":default:w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported pending signal type"});return}
	if q.Entry<=0||q.SL<=0||q.TP<=0 { w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"entry/sl/tp must be positive"});return }
	if q.Lot<0 {q.Lot=0}; if q.Expiry<0 {q.Expiry=0}

	// Reversal safety remains app-side using the live state endpoint. Do not add a
	// second execution lock here; approved signals must reach the decoder reliably.
	dir,err:=mt5CommonBridgeDir(); if err!=nil {w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}
	eaPublishMu.Lock(); defer eaPublishMu.Unlock()
	dst:=filepath.Join(dir,"signal.txt")
	line:=strings.Join([]string{q.SignalID,q.Symbol,q.Type,strconv.FormatFloat(q.Entry,'f',-1,64),strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),strconv.FormatFloat(q.Lot,'f',-1,64),strconv.FormatInt(q.Expiry,10)},"|")+"\r\n"
	tmp:=filepath.Join(dir,"signal.new")
	if err:=os.WriteFile(tmp,[]byte(line),0644);err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":"could not write EA signal: "+err.Error()});return}
	// Windows rename does not replace an existing destination, so remove the old
	// mailbox only while holding the publisher lock, then atomically rename the new one.
	_ = os.Remove(dst)
	if err:=os.Rename(tmp,dst);err!=nil{_ = os.Remove(tmp);w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":"could not publish EA signal: "+err.Error()});return}
	_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"signal_id":q.SignalID,"symbol":q.Symbol,"type":q.Type,"file":dst})
}

func eaSignalStatusHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json");if r.Method!=http.MethodGet{http.Error(w,"method",http.StatusMethodNotAllowed);return};dir,err:=mt5CommonBridgeDir();if err!=nil{w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return};p:=filepath.Join(dir,"status.txt");b,err:=os.ReadFile(p);if err!=nil{if os.IsNotExist(err){_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":"","exists":false});return};w.WriteHeader(http.StatusInternalServerError);_=json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return};line:=strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b),"\r\n","\n"),"\n",2)[0]);_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":line,"exists":line!=""})
}
