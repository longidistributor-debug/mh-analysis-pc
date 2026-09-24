package main

import (
    "encoding/json"
    "net/http"
    "os"
    "path/filepath"
    "strconv"
    "strings"
    "sync"
    "time"
)

type v558ModeState struct {
    SLAdjustment bool `json:"sl_adjustment"`
    FastScalping bool `json:"fast_scalping"`
    Progressive  bool `json:"progressive_v1"`
}

var v558ModeMu sync.RWMutex
var v558Modes = v558ModeState{Progressive: true}

func registerV558ModeRoutes(mux *http.ServeMux) {
    mux.HandleFunc("/api/mt5/modes", v558ModesHandler)
    mux.HandleFunc("/api/mt5/fast-send", v558FastSendHandler)
    mux.HandleFunc("/api/mt5/fast-status", v558FastStatusHandler)
}

func v558Snapshot() v558ModeState {
    v558ModeMu.RLock()
    defer v558ModeMu.RUnlock()
    return v558Modes
}

func v558WriteMailbox(name, line string) error {
    dir, err := mt5CommonBridgeDir()
    if err != nil { return err }
    tmp := filepath.Join(dir, name+".new")
    dst := filepath.Join(dir, name)
    eaPublishMu.Lock()
    defer eaPublishMu.Unlock()
    if err := os.WriteFile(tmp, []byte(line), 0644); err != nil { return err }
    _ = os.Remove(dst)
    if err := os.Rename(tmp, dst); err != nil { _ = os.Remove(tmp); return err }
    return nil
}

func v558PublishConfig() error {
    s := v558Snapshot()
    line := strings.Join([]string{
        "V.55.8",
        strconv.FormatBool(s.SLAdjustment),
        "true",
        strconv.FormatBool(s.FastScalping),
        "0.01","2.00","4.00","100.00","200.00",
    }, "|") + "\r\n"
    return v558WriteMailbox("config.txt", line)
}

func v558SetButtonText(hwnd uintptr, label string, on bool) {
    if hwnd == 0 { return }
    text := label + ": OFF"
    if on { text = label + ": ON" }
    wv2SendMessageV545.Call(hwnd, 0x000C, 0, uintptr(unsafePointerStringV558(text)))
}

func unsafePointerStringV558(s string) uintptr {
    return uintptr(unsafe.Pointer(chWstr(s)))
}

func v558RefreshNativeButtons() {
    s := v558Snapshot()
    v558SetButtonText(btnSLAdjustment, "SL Adjustment", s.SLAdjustment)
    v558SetButtonText(btnFastScalping, "Fast Scalping", s.FastScalping)
}

func v558ToggleSLAdjustment() {
    v558ModeMu.Lock()
    v558Modes.SLAdjustment = !v558Modes.SLAdjustment
    v558ModeMu.Unlock()
    _ = v558PublishConfig()
    v558RefreshNativeButtons()
}

func v558ToggleFastScalping() {
    v558ModeMu.Lock()
    v558Modes.FastScalping = !v558Modes.FastScalping
    v558ModeMu.Unlock()
    _ = v558PublishConfig()
    v558RefreshNativeButtons()
}

func v558ModesHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    switch r.Method {
    case http.MethodGet:
        s := v558Snapshot()
        _ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"sl_adjustment":s.SLAdjustment,"fast_scalping":s.FastScalping,"progressive_v1":true})
    case http.MethodPost:
        var q struct { SLAdjustment *bool `json:"sl_adjustment"`; FastScalping *bool `json:"fast_scalping"` }
        if json.NewDecoder(r.Body).Decode(&q) != nil { http.Error(w,"bad json",400); return }
        v558ModeMu.Lock()
        if q.SLAdjustment != nil { v558Modes.SLAdjustment = *q.SLAdjustment }
        if q.FastScalping != nil { v558Modes.FastScalping = *q.FastScalping }
        v558Modes.Progressive = true
        v558ModeMu.Unlock()
        if err := v558PublishConfig(); err != nil { http.Error(w,err.Error(),500); return }
        v558RefreshNativeButtons()
        _ = json.NewEncoder(w).Encode(map[string]any{"ok":true})
    default:
        http.Error(w,"method",http.StatusMethodNotAllowed)
    }
}

func v558FastSendHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    if r.Method != http.MethodPost { http.Error(w,"method",http.StatusMethodNotAllowed); return }
    if !v558Snapshot().FastScalping { http.Error(w,"fast scalping is off",409); return }
    var q struct { SignalID, Symbol, Type string; Entry float64 }
    if json.NewDecoder(r.Body).Decode(&q) != nil { http.Error(w,"bad json",400); return }
    q.SignalID = cleanEAToken(q.SignalID)
    if q.SignalID == "" { q.SignalID = "SCALP"+strconv.FormatInt(time.Now().UnixMilli(),10) }
    q.Symbol = normalizeEABridgeSymbol(q.Symbol)
    q.Type = strings.ToUpper(cleanEAToken(q.Type))
    if q.Symbol!="XAUUSD" && q.Symbol!="BTCUSD" { http.Error(w,"unsupported symbol",400); return }
    if q.Type!="FAST_BUY" && q.Type!="FAST_SELL" { http.Error(w,"unsupported fast type",400); return }
    if q.Entry<=0 { http.Error(w,"entry must be positive",400); return }
    line := strings.Join([]string{q.SignalID,q.Symbol,q.Type,strconv.FormatFloat(q.Entry,'f',-1,64),"0","0","0.01","2.00","4.00","100.00","200.00"},"|")+"\r\n"
    if err := v558WriteMailbox("fast_scalp.txt",line); err != nil { http.Error(w,err.Error(),500); return }
    _ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"signal_id":q.SignalID})
}

func v558FastStatusHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type","application/json")
    if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
    dir, err := mt5CommonBridgeDir()
    if err != nil { http.Error(w,err.Error(),500); return }
    b, err := os.ReadFile(filepath.Join(dir,"fast_status.txt"))
    if err != nil {
        if os.IsNotExist(err) { _ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":"","exists":false}); return }
        http.Error(w,err.Error(),500); return
    }
    line := strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b),"\r\n","\n"),"\n",2)[0])
    _ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"status":line,"exists":line!=""})
}
