package main

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"
)

type ffCalendarEvent struct {
	Title    string `json:"title"`
	Country  string `json:"country"`
	Date     string `json:"date"`
	Impact   string `json:"impact"`
	Forecast string `json:"forecast"`
	Previous string `json:"previous"`
}

var newsRiskMu sync.Mutex
var newsRiskAt time.Time
var newsRiskCached map[string]any

func newsRiskHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	newsRiskMu.Lock()
	if newsRiskCached != nil && time.Since(newsRiskAt) < 2*time.Minute {
		out := newsRiskCached
		newsRiskMu.Unlock()
		_ = json.NewEncoder(w).Encode(out)
		return
	}
	newsRiskMu.Unlock()

	out := map[string]any{
		"high":   false,
		"events": []string{},
		"source": "ForexFactory weekly calendar",
	}

	cli := &http.Client{Timeout: 8 * time.Second}
	req, _ := http.NewRequest(http.MethodGet, "https://nfs.faireconomy.media/ff_calendar_thisweek.json", nil)
	req.Header.Set("User-Agent", "MH-Analysis/8.1")
	resp, err := cli.Do(req)
	if err == nil {
		defer resp.Body.Close()
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			var events []ffCalendarEvent
			if json.NewDecoder(resp.Body).Decode(&events) == nil {
				now := time.Now()
				names := make([]string, 0, 3)
				for _, ev := range events {
					if !strings.EqualFold(strings.TrimSpace(ev.Impact), "High") {
						continue
					}
					cur := strings.ToUpper(strings.TrimSpace(ev.Country))
					if cur != "USD" {
						continue
					}
					t, e := time.Parse(time.RFC3339, strings.TrimSpace(ev.Date))
					if e != nil {
						continue
					}
					delta := t.Sub(now)
					if delta < -45*time.Minute || delta > 60*time.Minute {
						continue
					}
					title := strings.TrimSpace(ev.Title)
					if title == "" {
						title = "High-impact USD event"
					}
					names = append(names, title)
					if len(names) >= 3 {
						break
					}
				}
				if len(names) > 0 {
					out["high"] = true
					out["events"] = names
				}
			}
		}
	}

	newsRiskMu.Lock()
	newsRiskAt = time.Now()
	newsRiskCached = out
	newsRiskMu.Unlock()
	_ = json.NewEncoder(w).Encode(out)
}
