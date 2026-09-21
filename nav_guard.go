package main

import (
    "encoding/json"
    "net/http"
    "sync"
    "time"
)

var licNavNoticeMu sync.Mutex
var licNavNoticeText string
var licNavNoticeAt time.Time

func licSetNavNotice(section string) {
    licNavNoticeMu.Lock()
    licNavNoticeText = "Login required to open " + section + "."
    licNavNoticeAt = time.Now()
    licNavNoticeMu.Unlock()
}

func licNavNoticeHandler(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet { http.Error(w, "method", http.StatusMethodNotAllowed); return }
    licNavNoticeMu.Lock()
    text := licNavNoticeText
    fresh := !licNavNoticeAt.IsZero() && time.Since(licNavNoticeAt) < 3*time.Second
    if fresh { licNavNoticeText = "" }
    licNavNoticeMu.Unlock()
    w.Header().Set("Content-Type", "application/json")
    w.Header().Set("Cache-Control", "no-store")
    _ = json.NewEncoder(w).Encode(map[string]any{"notice": fresh, "message": text})
}
