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
	"time"
)

// MH_EA_SIGNAL_READER_BRIDGE_V35
// Normal pending-signal protocol is unchanged. V35 adds an isolated config/scalp
// protocol for the updated EA; older EAs simply ignore the additional files.
type eaSignalRequest struct {
	SignalID string  `json:"signal_id"`
	Symbol   string  `json:"symbol"`
	Type     string  `json:"type"`
	Entry    float64 `json:"entry"`
	SL       float64 `json:"sl"`
	TP       float64 `json:"tp"`
	Lot      float64 `json:"lot"`
	Expiry   int64   `json:"expiry"`
	SLAdjustment bool `json:"sl_adjustment"`
	ProgressiveV1 bool `json:"progressive_v1"`
	FastScalping bool `json:"fast_scalping"`
	FastLot float64 `json:"fast_lot"`
	FastTPMin float64 `json:"fast_tp_min"`
	FastTPMax float64 `json:"fast_tp_max"`
	DailyLossLimit float64 `json:"daily_loss_limit"`
	DailyProfitStop float64 `json:"daily_profit_stop"`
}

var eaSafeToken = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,80}$`)

func registerEASignalBridgeRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/mt5/ea/send", eaSignalSendHandler)
	mux.HandleFunc("/api/mt5/ea/status", eaSignalStatusHandler)
}
func mt5CommonBridgeDir() (string, error) {
	appData := strings.TrimSpace(os.Getenv("APPDATA")); if appData=="" { return "",fmt.Errorf("Windows APPDATA is unavailable") }
	dir:=filepath.Join(appData,"MetaQuotes","Terminal","Common","Files","MH_Analysis"); if err:=os.MkdirAll(dir,0755);err!=nil{return "",fmt.Errorf("could not create MT5 Common Files bridge: %w",err)}; return dir,nil
}
func normalizeEABridgeSymbol(s string) string { s=strings.ToUpper(strings.TrimSpace(s)); if s=="BTCUSDT"{return "BTCUSD"}; return s }
func cleanEAToken(s string) string { s=strings.TrimSpace(s);s=strings.ReplaceAll(s,"|","_");s=strings.ReplaceAll(s,"\r","_");s=strings.ReplaceAll(s,"\n","_");return s }
func atomicEAWrite(dir,name,line string) error { tmp:=filepath.Join(dir,name+".new");dst:=filepath.Join(dir,name);if err:=os.WriteFile(tmp,[]byte(line),0644);err!=nil{return err};_ = os.Remove(dst);if err:=os.Rename(tmp,dst);err!=nil{_ = os.Remove(tmp);return err};return nil }

func eaSignalSendHandler(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json");if r.Method!=http.MethodPost{http.Error(w,"method",http.StatusMethodNotAllowed);return}
	var q eaSignalRequest;if err:=json.NewDecoder(r.Body).Decode(&q);err!=nil{w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"bad signal payload"});return}
	q.SignalID=cleanEAToken(q.SignalID);q.Symbol=normalizeEABridgeSymbol(q.Symbol);q.Type=strings.ToUpper(cleanEAToken(q.Type));if q.SignalID==""{q.SignalID="MH"+strconv.FormatInt(time.Now().UnixMilli(),10)}
	if !eaSafeToken.MatchString(q.SignalID){w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"invalid signal id"});return}
	dir,err:=mt5CommonBridgeDir();if err!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return}

	if q.Type=="MH_CONFIG"{
		if q.FastLot<=0{q.FastLot=.01};if q.FastLot>.01{q.FastLot=.01};if q.FastTPMin<=0{q.FastTPMin=2};if q.FastTPMax<q.FastTPMin{q.FastTPMax=q.FastTPMin};if q.DailyLossLimit<=0{q.DailyLossLimit=100};if q.DailyProfitStop<=0{q.DailyProfitStop=200}
		line:=strings.Join([]string{"V35",strconv.FormatBool(q.SLAdjustment),strconv.FormatBool(q.ProgressiveV1),strconv.FormatBool(q.FastScalping),strconv.FormatFloat(q.FastLot,'f',2,64),strconv.FormatFloat(q.FastTPMin,'f',2,64),strconv.FormatFloat(q.FastTPMax,'f',2,64),strconv.FormatFloat(q.DailyLossLimit,'f',2,64),strconv.FormatFloat(q.DailyProfitStop,'f',2,64)},"|")+"\r\n"
		if err:=atomicEAWrite(dir,"config.txt",line);err!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":"could not publish EA config: "+err.Error()});return};_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"mode":"config"});return
	}
	if q.Type=="FAST_BUY"||q.Type=="FAST_SELL"{
		if q.Symbol!="XAUUSD"&&q.Symbol!="BTCUSD"{w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"unsupported EA bridge symbol"});return};q.Lot=.01;if q.FastTPMin<=0{q.FastTPMin=2};if q.FastTPMax<q.FastTPMin{q.FastTPMax=q.FastTPMin};if q.DailyLossLimit<=0{q.DailyLossLimit=100};if q.DailyProfitStop<=0{q.DailyProfitStop=200}
		line:=strings.Join([]string{q.SignalID,q.Symbol,q.Type,strconv.FormatFloat(q.Entry,'f',-1,64),"0","0","0.01",strconv.FormatFloat(q.FastTPMin,'f',2,64),strconv.FormatFloat(q.FastTPMax,'f',2,64),strconv.FormatFloat(q.DailyLossLimit,'f',2,64),strconv.FormatFloat(q.DailyProfitStop,'f',2,64)},"|")+"\r\n"
		if err:=atomicEAWrite(dir,"fast_scalp.txt",line);err!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":"could not publish fast scalp: "+err.Error()});return};_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"signal_id":q.SignalID,"symbol":q.Symbol,"type":q.Type,"lot":.01});return
	}

	if q.Symbol!="XAUUSD"&&q.Symbol!="BTCUSD"{w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"unsupported EA bridge symbol"});return}
	switch q.Type{case"BUY","SELL","BUY_LIMIT","SELL_LIMIT","BUY_STOP","SELL_STOP":default:w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"unsupported pending signal type"});return}
	if q.Entry<=0||q.SL<=0||q.TP<=0{w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"error":"entry/sl/tp must be positive"});return};if q.Lot<0{q.Lot=0};if q.Expiry<0{q.Expiry=0}
	line:=strings.Join([]string{q.SignalID,q.Symbol,q.Type,strconv.FormatFloat(q.Entry,'f',-1,64),strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),strconv.FormatFloat(q.Lot,'f',-1,64),strconv.FormatInt(q.Expiry,10)},"|")+"\r\n"
	if err:=atomicEAWrite(dir,"signal.txt",line);err!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":"could not publish EA signal: "+err.Error()});return};_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"signal_id":q.SignalID,"symbol":q.Symbol,"type":q.Type,"file":filepath.Join(dir,"signal.txt")})
}
func eaSignalStatusHandler(w http.ResponseWriter,r *http.Request){w.Header().Set("Content-Type","application/json");if r.Method!=http.MethodGet{http.Error(w,"method",http.StatusMethodNotAllowed);return};dir,err:=mt5CommonBridgeDir();if err!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return};p:=filepath.Join(dir,"status.txt");b,err:=os.ReadFile(p);if err!=nil{if os.IsNotExist(err){_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":"","exists":false});return};w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"error":err.Error()});return};line:=strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b),"\r\n","\n"),"\n",2)[0]);_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":line,"exists":line!=""})}
