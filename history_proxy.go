package main

import (
    "bytes"
    "encoding/json"
    "io"
    "net/http"
    "net/http/httptest"
    "strings"
    "sync"
    "time"
)

type historyCacheEntry struct {
    Body        []byte
    ContentType string
    StoredAt    time.Time
}

var desktopHistoryCacheMu sync.Mutex
var desktopHistoryCache = map[string]historyCacheEntry{}

func desktopHistoryHandler(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        http.Error(w, "method", http.StatusMethodNotAllowed)
        return
    }

    body, err := io.ReadAll(io.LimitReader(r.Body, 64<<10))
    if err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    _ = r.Body.Close()

    var q struct {
        Symbol string `json:"symbol"`
        Period string `json:"period"`
        Reason string `json:"reason"`
    }
    _ = json.Unmarshal(body, &q)
    key := strings.ToUpper(strings.TrimSpace(q.Symbol)) + "|" + strings.ToLower(strings.TrimSpace(q.Period))
    reason := strings.ToLower(strings.TrimSpace(q.Reason))

    desktopHistoryCacheMu.Lock()
    cached, hasCached := desktopHistoryCache[key]
    desktopHistoryCacheMu.Unlock()

    // A chart repaint should not burn another provider request if we already have
    // usable candles. NEW ANALYZE may reuse a chart snapshot only when it is very fresh.
    maxAge := time.Duration(0)
    if reason == "chart" {
        maxAge = 75 * time.Second
    } else if reason == "analysis" {
        maxAge = 0
    }
    if hasCached && maxAge > 0 && time.Since(cached.StoredAt) <= maxAge {
        if cached.ContentType != "" {
            w.Header().Set("Content-Type", cached.ContentType)
        } else {
            w.Header().Set("Content-Type", "application/json")
        }
        w.Header().Set("X-MH-History-Cache", "fresh")
        _, _ = w.Write(cached.Body)
        return
    }

    clone := r.Clone(r.Context())
    clone.Body = io.NopCloser(bytes.NewReader(body))
    rec := httptest.NewRecorder()
    historyHandler(rec, clone)
    res := rec.Result()
    defer res.Body.Close()
    out, _ := io.ReadAll(res.Body)

    if res.StatusCode >= 200 && res.StatusCode < 300 && len(out) > 0 {
        desktopHistoryCacheMu.Lock()
        desktopHistoryCache[key] = historyCacheEntry{Body: append([]byte(nil), out...), ContentType: res.Header.Get("Content-Type"), StoredAt: time.Now()}
        desktopHistoryCacheMu.Unlock()
    }

    // If the provider temporarily rate-limits a chart refresh, keep the chart alive
    // from cache instead of replacing it with a blank panel. Analysis requests still
    // surface the real provider error when no sufficiently fresh snapshot exists.
    if res.StatusCode == http.StatusTooManyRequests && reason == "chart" && hasCached {
        w.Header().Set("Content-Type", "application/json")
        w.Header().Set("X-MH-History-Cache", "rate-limit-fallback")
        _, _ = w.Write(cached.Body)
        return
    }

    for k, vals := range res.Header {
        for _, v := range vals {
            w.Header().Add(k, v)
        }
    }
    w.WriteHeader(res.StatusCode)
    _, _ = w.Write(out)
}
