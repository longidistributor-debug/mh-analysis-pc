package main

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// V56.9 precision context:
// - one provider request per analysis via FCS multi_url
// - true higher-timeframe candles from the provider (not synthetic aggregation)
// - live bid/ask spread context
// - local forward-trade calibration from MT5 lifecycle records

type v569SnapshotRequest struct {
	Symbol string `json:"symbol"`
	Period string `json:"period"`
	Reason string `json:"reason"`
}

type v569CalibrationBucket struct {
	Wins   float64
	Losses float64
	BE     int
}

func v569HigherPeriod(period string) string {
	switch strings.ToLower(strings.TrimSpace(period)) {
	case "1m", "1":
		return "5"
	case "5m", "5":
		return "15"
	case "15m", "15":
		return "60"
	case "30m", "30":
		return "120"
	case "1h", "60m", "60":
		return "240"
	default:
		return "60"
	}
}

func v569DisplayPeriod(period string) string {
	switch strings.TrimSpace(period) {
	case "1":
		return "1m"
	case "5":
		return "5m"
	case "15":
		return "15m"
	case "30":
		return "30m"
	case "60":
		return "1h"
	case "120":
		return "2h"
	case "240":
		return "4h"
	default:
		return period
	}
}

func v569MarketPaths(symbol, primaryPeriod, htfPeriod string) (string, string, string, bool) {
	sym := strings.ToUpper(strings.TrimSpace(symbol))
	primaryPeriod = normalizePeriod(primaryPeriod)
	if htfPeriod == "" {
		htfPeriod = v569HigherPeriod(primaryPeriod)
	}
	switch sym {
	case "XAUUSD":
		return fmt.Sprintf("forex/history?symbol=XAUUSD&period=%s&type=commodity&length=300&is_chart=0", primaryPeriod),
			fmt.Sprintf("forex/history?symbol=XAUUSD&period=%s&type=commodity&length=300&is_chart=0", htfPeriod),
			fmt.Sprintf("forex/latest?symbol=XAUUSD&type=commodity&period=%s", primaryPeriod), true
	case "BTCUSDT":
		return fmt.Sprintf("crypto/history?symbol=BINANCE:BTCUSDT&period=%s&length=300&is_chart=0", primaryPeriod),
			fmt.Sprintf("crypto/history?symbol=BINANCE:BTCUSDT&period=%s&length=300&is_chart=0", htfPeriod),
			fmt.Sprintf("crypto/latest?symbol=BINANCE:BTCUSDT&period=%s", primaryPeriod), true
	default:
		return "", "", "", false
	}
}

func v569MultiPart(root map[string]any, n int) any {
	for _, k := range []string{fmt.Sprintf("url%d", n), fmt.Sprintf("%d", n), fmt.Sprintf("url[%d]", n)} {
		v, ok := root[k]
		if !ok {
			continue
		}
		if arr, ok := v.([]any); ok && len(arr) > 0 {
			if m, ok := arr[0].(map[string]any); ok {
				if x, ok := m["response"]; ok {
					return x
				}
			}
			return arr
		}
		if m, ok := v.(map[string]any); ok {
			if x, ok := m["response"]; ok {
				return x
			}
		}
		return v
	}
	return nil
}

func v569FindQuote(v any) (ask, bid, close float64, ok bool) {
	var walk func(any) bool
	walk = func(x any) bool {
		switch z := x.(type) {
		case map[string]any:
			a, aok := fnum(z["a"])
			b, bok := fnum(z["b"])
			c, cok := fnum(z["c"])
			if aok && bok && a > 0 && b > 0 && a >= b {
				ask, bid = a, b
				if cok {
					close = c
				} else {
					close = (a + b) / 2
				}
				return true
			}
			for _, key := range []string{"active", "response", "data", "latest"} {
				if child, exists := z[key]; exists && walk(child) {
					return true
				}
			}
			for _, child := range z {
				if walk(child) {
					return true
				}
			}
		case []any:
			for _, child := range z {
				if walk(child) {
					return true
				}
			}
		}
		return false
	}
	ok = walk(v)
	return
}

func v569AnalysisSnapshotHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	if !allowCall() {
		w.WriteHeader(http.StatusTooManyRequests)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Too many fresh market requests. Please wait about a minute."})
		return
	}
	var q v569SnapshotRequest
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	cfg := getSettings()
	if strings.TrimSpace(cfg.APIKey) == "" {
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Access Key is not saved."})
		return
	}
	primaryPeriod := normalizePeriod(q.Period)
	htfPeriod := v569HigherPeriod(primaryPeriod)
	p1, p2, p3, supported := v569MarketPaths(q.Symbol, primaryPeriod, htfPeriod)
	if !supported {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Unsupported symbol"})
		return
	}

	u, _ := url.Parse("https://api-v4.fcsapi.com/forex/multi_url")
	z := u.Query()
	z.Set("access_key", cfg.APIKey)
	z.Set("url[1]", p1)
	z.Set("url[2]", p2)
	z.Set("url[3]", p3)
	u.RawQuery = z.Encode()

	cli := &http.Client{Timeout: 20 * time.Second}
	req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", "MH-Analysis/V56.9")
	resp, err := cli.Do(req)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Precision snapshot connection failed: " + err.Error()})
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	var root map[string]any
	if json.Unmarshal(body, &root) != nil {
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Precision snapshot returned unreadable data"})
		return
	}
	primary := extractCandles(v569MultiPart(root, 1))
	htf := extractCandles(v569MultiPart(root, 2))
	if len(primary) > 300 {
		primary = primary[len(primary)-300:]
	}
	if len(htf) > 300 {
		htf = htf[len(htf)-300:]
	}
	if resp.StatusCode >= 400 || len(primary) == 0 {
		status := resp.StatusCode
		if status < 400 {
			status = http.StatusBadGateway
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": extractError(root, "No usable primary candles returned")})
		return
	}

	ask, bid, closePrice, quoteOK := v569FindQuote(v569MultiPart(root, 3))
	quote := map[string]any{"available": quoteOK}
	if quoteOK {
		spread := math.Max(0, ask-bid)
		quote["ask"] = ask
		quote["bid"] = bid
		quote["close"] = closePrice
		quote["spread"] = spread
		if closePrice > 0 {
			quote["spread_pct"] = spread / closePrice * 100
		}
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"candles":     primary,
		"htf_candles": htf,
		"htf_period":  v569DisplayPeriod(htfPeriod),
		"quote":       quote,
		"meta": map[string]any{
			"source":             "FCS multi_url precision snapshot",
			"symbol":             strings.ToUpper(strings.TrimSpace(q.Symbol)),
			"period":             q.Period,
			"count":              len(primary),
			"htf_count":          len(htf),
			"external_api_calls": 1,
		},
	})
}

func v569Outcome(r mt5LocalRecord) (float64, bool) {
	if r.Cancelled || r.ActivatedAt <= 0 || !recordTerminalMT5(r) {
		return 0, false
	}
	if r.RealizedProfit > 0.01 {
		return 1, true
	}
	if r.RealizedProfit < -0.01 {
		return 0, true
	}
	if r.TP2At > 0 || r.TPHit {
		return 1, true
	}
	if r.SLAt > 0 || r.SLHit {
		return 0, true
	}
	if r.BreakEvenAt > 0 || r.BreakEvenHit || strings.Contains(strings.ToUpper(r.ManualResult), "BREAK") {
		return 0.5, true
	}
	st := strings.ToUpper(strings.TrimSpace(r.Status))
	if strings.Contains(st, "+POSITIVE") {
		return 1, true
	}
	if strings.Contains(st, "-NEGATIVE") {
		return 0, true
	}
	if strings.Contains(st, "BREAK EVEN") {
		return 0.5, true
	}
	return 0, false
}

func v569BucketStats(b v569CalibrationBucket) map[string]any {
	decisive := b.Wins + b.Losses
	posterior := (4.0 + b.Wins) / (8.0 + decisive)
	shrink := math.Min(1, decisive/20.0)
	mult := 1 + (posterior-0.5)*0.8*shrink
	if mult < 0.86 {
		mult = 0.86
	}
	if mult > 1.14 {
		mult = 1.14
	}
	adj := (posterior - 0.5) * 24 * shrink
	if adj < -6 {
		adj = -6
	}
	if adj > 6 {
		adj = 6
	}
	return map[string]any{
		"sample":     int(decisive),
		"wins":       b.Wins,
		"losses":     b.Losses,
		"break_even": b.BE,
		"win_rate":   posterior,
		"multiplier": mult,
		"adjustment": adj,
	}
}

func v569ModelCalibrationHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	symbol := strings.ToUpper(strings.TrimSpace(r.URL.Query().Get("symbol")))
	tf := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("timeframe")))

	mt5RecordsMu.Lock()
	store := loadMT5LocalStore()
	_, _, _ = syncMT5Lifecycle(&store)
	_ = saveMT5LocalStore(store)
	mt5RecordsMu.Unlock()

	families := map[string]v569CalibrationBucket{}
	directions := map[string]v569CalibrationBucket{"BUY": {}, "SELL": {}}
	overall := v569CalibrationBucket{}
	for _, rec := range store.Records {
		if symbol != "" && !symbolFamilyEqual(symbol, rec.Symbol) {
			continue
		}
		if tf != "" && strings.ToLower(strings.TrimSpace(rec.Timeframe)) != tf {
			continue
		}
		dir := strings.ToUpper(strings.TrimSpace(rec.Direction))
		if dir != "BUY" && dir != "SELL" {
			continue
		}
		outcome, ok := v569Outcome(rec)
		if !ok {
			continue
		}
		apply := func(b v569CalibrationBucket) v569CalibrationBucket {
			if outcome > 0.75 {
				b.Wins++
			} else if outcome < 0.25 {
				b.Losses++
			} else {
				b.BE++
			}
			return b
		}
		overall = apply(overall)
		directions[dir] = apply(directions[dir])
		setup := strings.TrimSpace(rec.Setup)
		if setup != "" {
			key := dir + "|" + setup
			families[key] = apply(families[key])
		}
	}

	familyOut := map[string]any{}
	for k, b := range families {
		if b.Wins+b.Losses < 2 {
			continue
		}
		familyOut[k] = v569BucketStats(b)
	}
	directionOut := map[string]any{}
	for _, dir := range []string{"BUY", "SELL"} {
		directionOut[dir] = v569BucketStats(directions[dir])
	}
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":                 true,
		"symbol":             symbol,
		"timeframe":          tf,
		"overall":            v569BucketStats(overall),
		"directions":         directionOut,
		"families":           familyOut,
		"external_api_calls": 0,
	})
}

func registerV569PrecisionRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/analysis-snapshot-v569", v569AnalysisSnapshotHandler)
	mux.HandleFunc("/api/model-calibration-v569", v569ModelCalibrationHandler)
}
