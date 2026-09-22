package main

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type uiCacheV5411 struct {
	Ticker map[string]any `json:"ticker,omitempty"`
	Recent []any          `json:"recent,omitempty"`
}

var uiCacheMuV5411 sync.Mutex
var tickerRefreshMuV5411 sync.Mutex
var tickerRefreshAtV5411 time.Time

func uiCachePathV5411() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "MHAnalysis", "ui-cache-v5411.json")
}

func loadUICacheV5411() uiCacheV5411 {
	var c uiCacheV5411
	b, err := os.ReadFile(uiCachePathV5411())
	if err == nil {
		_ = json.Unmarshal(b, &c)
	}
	return c
}

func saveUICacheV5411(c uiCacheV5411) {
	p := uiCachePathV5411()
	_ = os.MkdirAll(filepath.Dir(p), 0755)
	b, _ := json.Marshal(c)
	tmp := p + ".tmp"
	if os.WriteFile(tmp, b, 0600) == nil {
		_ = os.Rename(tmp, p)
	}
}

func uiCacheHandlerV5411(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	uiCacheMuV5411.Lock()
	defer uiCacheMuV5411.Unlock()
	c := loadUICacheV5411()
	switch r.Method {
	case http.MethodGet:
		_ = json.NewEncoder(w).Encode(c)
	case http.MethodPost:
		var patch map[string]json.RawMessage
		if json.NewDecoder(r.Body).Decode(&patch) != nil {
			http.Error(w, "bad json", http.StatusBadRequest)
			return
		}
		if raw, ok := patch["ticker"]; ok {
			var t map[string]any
			if json.Unmarshal(raw, &t) == nil && len(t) > 0 {
				c.Ticker = t
			}
		}
		if raw, ok := patch["recent"]; ok {
			var v []any
			if json.Unmarshal(raw, &v) == nil {
				if len(v) > 6 {
					v = v[:6]
				}
				c.Recent = v
			}
		}
		saveUICacheV5411(c)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	default:
		http.Error(w, "method", http.StatusMethodNotAllowed)
	}
}

func refreshTickerV5411() map[string]any {
	uiCacheMuV5411.Lock()
	base := loadUICacheV5411().Ticker
	uiCacheMuV5411.Unlock()
	if base == nil {
		base = map[string]any{}
	}
	out := map[string]any{}
	for k, v := range base {
		out[k] = v
	}
	var outMu sync.Mutex
	put := func(k string, v any) { outMu.Lock(); out[k] = v; outMu.Unlock() }
	cli := &http.Client{Timeout: 1300 * time.Millisecond}
	var wg sync.WaitGroup
	wg.Add(3)
	go func() {
		defer wg.Done()
		fetchJSON(cli, "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true", func(v any) {
			if m, ok := v.(map[string]any); ok {
				if b, ok := m["bitcoin"].(map[string]any); ok {
					if x, ok := fnum(b["usd"]); ok && x > 0 { put("btc_usd", x) }
					if x, ok := fnum(b["usd_24h_change"]); ok { put("btc_change_24h", x) }
				}
				if e, ok := m["ethereum"].(map[string]any); ok {
					if x, ok := fnum(e["usd"]); ok && x > 0 { put("eth_usd", x) }
					if x, ok := fnum(e["usd_24h_change"]); ok { put("eth_change_24h", x) }
				}
			}
		})
	}()
	go func() {
		defer wg.Done()
		fetchJSON(cli, "https://xaus.com/api/v1/spot", func(v any) {
			if g := findNumberByKeys(v, "price", "usd", "gold", "xau"); g > 0 { put("gold_usd", g) }
		})
	}()
	go func() {
		defer wg.Done()
		fetchJSON(cli, "https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP", func(v any) {
			if m, ok := v.(map[string]any); ok {
				if rates, ok := m["rates"].(map[string]any); ok {
					eur, _ := fnum(rates["EUR"]); jpy, _ := fnum(rates["JPY"]); gbp, _ := fnum(rates["GBP"])
					if eur > 0 { put("eurusd", 1/eur) }
					if jpy > 0 { put("usdjpy", jpy) }
					if gbp > 0 { put("gbpusd", 1/gbp) }
					if gbp > 0 && jpy > 0 { put("gbpjpy", jpy/gbp) }
				}
			}
		})
	}()
	wg.Wait()
	uiCacheMuV5411.Lock()
	c := loadUICacheV5411()
	c.Ticker = out
	saveUICacheV5411(c)
	uiCacheMuV5411.Unlock()
	return out
}

func publicTickerHandlerV5411(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	uiCacheMuV5411.Lock()
	cached := loadUICacheV5411().Ticker
	uiCacheMuV5411.Unlock()
	if len(cached) > 0 {
		_ = json.NewEncoder(w).Encode(cached)
		tickerRefreshMuV5411.Lock()
		if time.Since(tickerRefreshAtV5411) > 20*time.Second {
			tickerRefreshAtV5411 = time.Now()
			go refreshTickerV5411()
		}
		tickerRefreshMuV5411.Unlock()
		return
	}
	fresh := refreshTickerV5411()
	_ = json.NewEncoder(w).Encode(fresh)
}
