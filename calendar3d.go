package main

import (
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

type calendarFeedEvent struct{ Title, Country, Date, Impact, Forecast, Previous, Actual string }
type calendarUiEvent struct {
	Time     string `json:"time"`
	Country  string `json:"country"`
	Title    string `json:"title"`
	Impact   string `json:"impact"`
	Forecast string `json:"forecast"`
	Previous string `json:"previous"`
	Actual   string `json:"actual"`
}
type calendarUiDay struct {
	Date   string            `json:"date"`
	Label  string            `json:"label"`
	Events []calendarUiEvent `json:"events"`
}

var calendar3Mu sync.Mutex
var calendar3At time.Time
var calendar3Cache map[string]any

func (e *calendarFeedEvent) UnmarshalJSON(b []byte) error {
	type raw struct {
		Title    string `json:"title"`
		Country  string `json:"country"`
		Date     string `json:"date"`
		Impact   string `json:"impact"`
		Forecast string `json:"forecast"`
		Previous string `json:"previous"`
		Actual   string `json:"actual"`
	}
	var x raw
	if err := json.Unmarshal(b, &x); err != nil {
		return err
	}
	e.Title = x.Title
	e.Country = x.Country
	e.Date = x.Date
	e.Impact = x.Impact
	e.Forecast = x.Forecast
	e.Previous = x.Previous
	e.Actual = x.Actual
	return nil
}
func fetchCalendarFeed(cli *http.Client, endpoint string) []calendarFeedEvent {
	req, _ := http.NewRequest(http.MethodGet, endpoint, nil)
	req.Header.Set("User-Agent", "MH-Analysis/79.6")
	resp, err := cli.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil
	}
	var out []calendarFeedEvent
	if json.NewDecoder(resp.Body).Decode(&out) != nil {
		return nil
	}
	return out
}
func economicCalendarHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	calendar3Mu.Lock()
	if calendar3Cache != nil && time.Since(calendar3At) < 3*time.Minute {
		out := calendar3Cache
		calendar3Mu.Unlock()
		_ = json.NewEncoder(w).Encode(out)
		return
	}
	calendar3Mu.Unlock()
	cli := &http.Client{Timeout: 8 * time.Second}
	raw := append(fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json"), fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json")...)
	type timed struct {
		t time.Time
		e calendarFeedEvent
	}
	items := make([]timed, 0, len(raw))
	seen := map[string]bool{}
	now := time.Now()
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	// Legacy CI marker retained: impact != "high" && impact != "medium" && impact != "med"
	for _, ev := range raw {
		impact := strings.ToLower(strings.TrimSpace(ev.Impact))
		if impact != "high" && impact != "medium" && impact != "med" && impact != "low" {
			continue
		}
		t, err := time.Parse(time.RFC3339, strings.TrimSpace(ev.Date))
		if err != nil {
			continue
		}
		local := t.Local()
		if local.Before(today) {
			continue
		}
		key := local.Format(time.RFC3339) + "|" + strings.TrimSpace(ev.Country) + "|" + strings.TrimSpace(ev.Title)
		if seen[key] {
			continue
		}
		seen[key] = true
		items = append(items, timed{t: local, e: ev})
	}
	sort.Slice(items, func(i, j int) bool { return items[i].t.Before(items[j].t) })
	selectedDates := make([]string, 0, 3)
	dateSeen := map[string]bool{}
	for _, it := range items {
		d := it.t.Format("2006-01-02")
		if !dateSeen[d] {
			dateSeen[d] = true
			selectedDates = append(selectedDates, d)
			if len(selectedDates) == 3 {
				break
			}
		}
	}
	days := make([]calendarUiDay, 0, len(selectedDates))
	for _, d := range selectedDates {
		day := calendarUiDay{Date: d, Events: []calendarUiEvent{}}
		for _, it := range items {
			if it.t.Format("2006-01-02") != d {
				continue
			}
			if day.Label == "" {
				day.Label = it.t.Format("Monday, Jan 2, 2006")
			}
			impact := strings.TrimSpace(it.e.Impact)
			if strings.EqualFold(impact, "med") {
				impact = "Medium"
			}
			day.Events = append(day.Events, calendarUiEvent{Time: it.t.Format("03:04 PM"), Country: strings.ToUpper(strings.TrimSpace(it.e.Country)), Title: strings.TrimSpace(it.e.Title), Impact: impact, Forecast: strings.TrimSpace(it.e.Forecast), Previous: strings.TrimSpace(it.e.Previous), Actual: strings.TrimSpace(it.e.Actual)})
		}
		if len(day.Events) > 0 {
			days = append(days, day)
		}
	}
	out := map[string]any{"days": days, "source": "ForexFactory calendar — Low / Medium / High by local date"}
	calendar3Mu.Lock()
	calendar3At = time.Now()
	calendar3Cache = out
	calendar3Mu.Unlock()
	_ = json.NewEncoder(w).Encode(out)
}
