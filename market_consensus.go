package main

import (
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

type marketConsensusSource struct {
	Name  string  `json:"name"`
	Price float64 `json:"price"`
	OK    bool    `json:"ok"`
}

func marketConsensusFetch(cli *http.Client, name, u string, pick func(any) float64, ch chan<- marketConsensusSource, wg *sync.WaitGroup) {
	defer wg.Done()
	resp, err := cli.Get(u)
	if err != nil {
		ch <- marketConsensusSource{Name: name}
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		ch <- marketConsensusSource{Name: name}
		return
	}
	var v any
	if json.NewDecoder(resp.Body).Decode(&v) != nil {
		ch <- marketConsensusSource{Name: name}
		return
	}
	p := pick(v)
	ch <- marketConsensusSource{Name: name, Price: p, OK: p > 0}
}

func marketConsensusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	symbol := strings.ToUpper(strings.TrimSpace(r.URL.Query().Get("symbol")))
	if symbol == "BTCUSD" {
		symbol = "BTCUSDT"
	}
	if symbol != "XAUUSD" && symbol != "BTCUSDT" {
		http.Error(w, "unsupported symbol", http.StatusBadRequest)
		return
	}

	cli := &http.Client{Timeout: 2500 * time.Millisecond}
	ch := make(chan marketConsensusSource, 2)
	var wg sync.WaitGroup
	wg.Add(2)

	if symbol == "XAUUSD" {
		go marketConsensusFetch(cli, "xaus.com", "https://xaus.com/api/v1/spot", func(v any) float64 {
			return findNumberByKeys(v, "price", "usd", "gold", "xau")
		}, ch, &wg)
		go marketConsensusFetch(cli, "gold-api.com", "https://api.gold-api.com/price/XAU", func(v any) float64 {
			return findNumberByKeys(v, "price")
		}, ch, &wg)
	} else {
		go marketConsensusFetch(cli, "coingecko", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", func(v any) float64 {
			if m, ok := v.(map[string]any); ok {
				if b, ok := m["bitcoin"].(map[string]any); ok {
					if p, ok := fnum(b["usd"]); ok { return p }
				}
			}
			return 0
		}, ch, &wg)
		go marketConsensusFetch(cli, "binance", "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", func(v any) float64 {
			if m, ok := v.(map[string]any); ok {
				if p, ok := fnum(m["price"]); ok { return p }
			}
			return 0
		}, ch, &wg)
	}

	wg.Wait()
	close(ch)
	sources := make([]marketConsensusSource, 0, 2)
	prices := make([]float64, 0, 2)
	for s := range ch {
		sources = append(sources, s)
		if s.OK && s.Price > 0 { prices = append(prices, s.Price) }
	}
	sort.Slice(sources, func(i, j int) bool { return sources[i].Name < sources[j].Name })
	available := len(prices) == 2
	medianPrice := 0.0
	spreadPct := 0.0
	if len(prices) == 2 {
		medianPrice = (prices[0] + prices[1]) / 2
		if medianPrice > 0 {
			spreadPct = 100 * (prices[0] - prices[1]) / medianPrice
			if spreadPct < 0 { spreadPct = -spreadPct }
		}
	}
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok": available,
		"available": available,
		"symbol": symbol,
		"sources": sources,
		"median_price": medianPrice,
		"source_spread_pct": spreadPct,
		"checked_at_unix": time.Now().Unix(),
	})
}
