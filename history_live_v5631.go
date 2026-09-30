package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sort"
	"strings"
	"time"
)

// desktopHistoryLiveHandlerV5631 keeps the existing direct FCS history flow intact,
// then (for analysis/re-evaluation only) merges FCS latest/active OHLC into the
// selected-timeframe candles. This restores the older history + latest behavior
// without changing signal, EA, lot, SL or TP logic.
func desktopHistoryLiveHandlerV5631(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		desktopHistoryHandler(w, r)
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

	clone := r.Clone(r.Context())
	clone.Body = io.NopCloser(bytes.NewReader(body))
	rec := httptest.NewRecorder()
	desktopHistoryHandler(rec, clone)
	res := rec.Result()
	defer res.Body.Close()
	out, _ := io.ReadAll(res.Body)

	// Preserve the exact existing history/provider error path.
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		copyHistoryResponseV5631(w, res, out)
		return
	}

	reason := strings.ToLower(strings.TrimSpace(q.Reason))
	if reason != "analysis" && reason != "reeval" && reason != "re-evaluate" {
		copyHistoryResponseV5631(w, res, out)
		return
	}

	var payload struct {
		Candles []candle       `json:"candles"`
		Meta    map[string]any `json:"meta"`
	}
	if json.Unmarshal(out, &payload) != nil || len(payload.Candles) == 0 {
		copyHistoryResponseV5631(w, res, out)
		return
	}
	if payload.Meta == nil {
		payload.Meta = map[string]any{}
	}
	payload.Meta["source"] = "FCS API v4"
	payload.Meta["live_merged"] = false
	payload.Meta["live_status"] = "history-only"

	// Keep the existing hard cap: each actual FCS request consumes one slot.
	// History already used one slot inside historyHandler; latest uses a second slot.
	if !allowCall() {
		payload.Meta["live_status"] = "latest-rate-limited"
		writeHistoryPayloadV5631(w, payload)
		return
	}

	cfg := getSettings()
	if strings.TrimSpace(cfg.APIKey) == "" {
		payload.Meta["live_status"] = "latest-key-missing"
		writeHistoryPayloadV5631(w, payload)
		return
	}

	sym := strings.ToUpper(strings.TrimSpace(q.Symbol))
	per := normalizeHistoryPeriodV5624(sym, q.Period)
	cli := &http.Client{Timeout: 12 * time.Second}
	live, liveErr := fetchFCSLatestCandleV5631(cli, cfg.APIKey, sym, per)
	if liveErr != nil {
		payload.Meta["live_status"] = "latest-error: " + liveErr.Error()
		writeHistoryPayloadV5631(w, payload)
		return
	}

	payload.Candles = mergeLiveCandleV5631(payload.Candles, live, per)
	if len(payload.Candles) > 300 {
		payload.Candles = payload.Candles[len(payload.Candles)-300:]
	}
	payload.Meta["count"] = len(payload.Candles)
	payload.Meta["live_merged"] = true
	payload.Meta["live_status"] = "live-merged"
	writeHistoryPayloadV5631(w, payload)
}

func copyHistoryResponseV5631(w http.ResponseWriter, res *http.Response, body []byte) {
	for k, vals := range res.Header {
		for _, v := range vals {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(res.StatusCode)
	_, _ = w.Write(body)
}

func writeHistoryPayloadV5631(w http.ResponseWriter, payload struct {
	Candles []candle       `json:"candles"`
	Meta    map[string]any `json:"meta"`
}) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(payload)
}

func extractFCSActiveCandleV5631(root any) (candle, bool) {
	var best candle
	found := false
	var walk func(any)
	walk = func(v any) {
		switch x := v.(type) {
		case map[string]any:
			if a, ok := x["active"].(map[string]any); ok {
				if c, ok := candleFromMap(a, nil); ok && (!found || c.T > best.T) {
					best, found = c, true
				}
			}
			for _, y := range x {
				walk(y)
			}
		case []any:
			for _, y := range x {
				walk(y)
			}
		}
	}
	walk(root)
	if found {
		return best, true
	}
	cs := extractCandles(root)
	if len(cs) > 0 {
		return cs[len(cs)-1], true
	}
	return candle{}, false
}

func fetchFCSLatestCandleV5631(cli *http.Client, apiKey, sym, per string) (candle, error) {
	endpoint := ""
	fcsSym := ""
	typ := ""
	switch strings.ToUpper(strings.TrimSpace(sym)) {
	case "XAUUSD":
		endpoint = "https://api-v4.fcsapi.com/forex/latest"
		fcsSym = "XAUUSD"
		typ = "commodity"
	case "BTCUSDT":
		endpoint = "https://api-v4.fcsapi.com/crypto/latest"
		fcsSym = "BINANCE:BTCUSDT"
	default:
		return candle{}, fmt.Errorf("unsupported latest symbol")
	}

	u, _ := url.Parse(endpoint)
	z := u.Query()
	z.Set("access_key", strings.TrimSpace(apiKey))
	z.Set("symbol", fcsSym)
	z.Set("period", per)
	if typ != "" {
		z.Set("type", typ)
	}
	u.RawQuery = z.Encode()

	req, _ := http.NewRequest(http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", "MH-Analysis/V.56.31")
	resp, err := cli.Do(req)
	if err != nil {
		return candle{}, fmt.Errorf("latest connection failed: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))

	var root any
	if json.Unmarshal(body, &root) != nil {
		return candle{}, fmt.Errorf("latest returned unreadable data")
	}
	if resp.StatusCode >= 400 {
		return candle{}, fmt.Errorf("%s", extractError(root, fmt.Sprintf("latest HTTP %d", resp.StatusCode)))
	}
	c, ok := extractFCSActiveCandleV5631(root)
	if !ok {
		return candle{}, fmt.Errorf("latest returned no active candle")
	}
	return c, nil
}

func periodSecondsV5631(per string) int64 {
	switch strings.ToLower(strings.TrimSpace(per)) {
	case "1", "1m":
		return 60
	case "5", "5m":
		return 5 * 60
	case "15", "15m":
		return 15 * 60
	case "20", "20m":
		return 20 * 60
	case "30", "30m":
		return 30 * 60
	case "60", "1h", "60m":
		return 60 * 60
	}
	return 0
}

func mergeLiveCandleV5631(cs []candle, live candle, per string) []candle {
	if live.T <= 0 {
		return cs
	}
	sec := periodSecondsV5631(per)
	if sec > 0 {
		live.T = (live.T / sec) * sec
	}
	out := append([]candle(nil), cs...)
	if len(out) == 0 {
		return []candle{live}
	}

	for i := len(out) - 1; i >= 0; i-- {
		t := out[i].T
		if sec > 0 {
			t = (t / sec) * sec
		}
		if t == live.T {
			base := out[i]
			if live.O == 0 {
				live.O = base.O
			}
			if live.H < base.H {
				live.H = base.H
			}
			if live.H < live.C {
				live.H = live.C
			}
			if live.L == 0 || live.L > base.L {
				live.L = base.L
			}
			if live.L > live.C {
				live.L = live.C
			}
			out[i] = live
			return out
		}
		if t < live.T {
			out = append(out, live)
			sort.Slice(out, func(i, j int) bool { return out[i].T < out[j].T })
			return out
		}
	}
	return out
}
