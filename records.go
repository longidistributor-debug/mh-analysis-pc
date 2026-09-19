package main

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type tradeRecord struct {
	ID              string  `json:"id"`
	CreatedAt       int64   `json:"created_at"`
	LocalDate       string  `json:"local_date"`
	LocalTime       string  `json:"local_time"`
	Symbol          string  `json:"symbol"`
	Timeframe       string  `json:"timeframe"`
	Direction       string  `json:"direction"`
	Entry           float64 `json:"entry"`
	SL              float64 `json:"sl"`
	TP1             float64 `json:"tp1"`
	TP2             float64 `json:"tp2"`
	Score           float64 `json:"score"`
	Setup           string  `json:"setup"`
	Status          string  `json:"status"`
	EntryAt         int64   `json:"entry_at,omitempty"`
	TP1At           int64   `json:"tp1_at,omitempty"`
	TP2At           int64   `json:"tp2_at,omitempty"`
	SLAt            int64   `json:"sl_at,omitempty"`
	BreakEvenAt     int64   `json:"break_even_at,omitempty"`
	LastCandleAt    int64   `json:"last_candle_at,omitempty"`
	LastCheckedAt   int64   `json:"last_checked_at,omitempty"`
	TPHit           bool    `json:"tp_hit"`
	SLHit           bool    `json:"sl_hit"`
	BreakEvenHit    bool    `json:"break_even_hit"`
	Ambiguous       bool    `json:"ambiguous"`
	Note            string  `json:"note,omitempty"`
}

type tradeRecordStore struct {
	Version int           `json:"version"`
	Records []tradeRecord `json:"records"`
}

type recordCapture struct {
	Symbol    string  `json:"symbol"`
	Timeframe string  `json:"timeframe"`
	Direction string  `json:"direction"`
	Entry     float64 `json:"entry"`
	SL        float64 `json:"sl"`
	TP1       float64 `json:"tp1"`
	TP2       float64 `json:"tp2"`
	Score     float64 `json:"score"`
	Setup     string  `json:"setup"`
	Action    string  `json:"action"`
}

var recordsMu sync.Mutex
var recordsLoaded bool
var recordsStore = tradeRecordStore{Version: 1, Records: []tradeRecord{}}

func recordsPath() string {
	b := os.Getenv("LOCALAPPDATA")
	if b == "" {
		b = os.TempDir()
	}
	return filepath.Join(b, "MHAnalysis", "signal-records-v796.json")
}

func loadRecordsLocked() {
	if recordsLoaded {
		return
	}
	recordsLoaded = true
	b, err := os.ReadFile(recordsPath())
	if err != nil {
		return
	}
	var s tradeRecordStore
	if json.Unmarshal(b, &s) == nil {
		if s.Version == 0 {
			s.Version = 1
		}
		if s.Records == nil {
			s.Records = []tradeRecord{}
		}
		recordsStore = s
	}
}

func saveRecordsLocked() error {
	p := recordsPath()
	if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(recordsStore, "", "  ")
	if err != nil {
		return err
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, b, 0600); err != nil {
		return err
	}
	return os.Rename(tmp, p)
}

func finiteRecordNumber(v float64) bool { return !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0 }

func nearRecordPrice(a, b float64) bool {
	tol := math.Max(1e-8, math.Max(math.Abs(a), math.Abs(b))*1e-7)
	return math.Abs(a-b) <= tol
}

func captureRecordHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q recordCapture
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Timeframe = strings.TrimSpace(q.Timeframe)
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	q.Action = strings.ToUpper(strings.TrimSpace(q.Action))
	q.Setup = strings.TrimSpace(q.Setup)
	if q.Action != "NEW" || (q.Direction != "BUY" && q.Direction != "SELL") || q.Symbol == "" || q.Timeframe == "" || !finiteRecordNumber(q.Entry) || !finiteRecordNumber(q.SL) || !finiteRecordNumber(q.TP1) || !finiteRecordNumber(q.TP2) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false})
		return
	}
	now := time.Now()
	recordsMu.Lock()
	defer recordsMu.Unlock()
	loadRecordsLocked()
	// Prevent an accidental double-click/render from creating a duplicate trade.
	for i := len(recordsStore.Records) - 1; i >= 0 && i >= len(recordsStore.Records)-6; i-- {
		x := recordsStore.Records[i]
		if now.Unix()-x.CreatedAt > 45 {
			break
		}
		if x.Symbol == q.Symbol && x.Timeframe == q.Timeframe && x.Direction == q.Direction && nearRecordPrice(x.Entry, q.Entry) && nearRecordPrice(x.SL, q.SL) && nearRecordPrice(x.TP1, q.TP1) && nearRecordPrice(x.TP2, q.TP2) {
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": x.ID})
			return
		}
	}
	x := tradeRecord{
		ID:        fmt.Sprintf("%d-%s-%s", now.UnixNano(), q.Symbol, q.Timeframe),
		CreatedAt: now.Unix(),
		LocalDate: now.Format("2006-01-02"),
		LocalTime: now.Format("15:04:05"),
		Symbol:    q.Symbol,
		Timeframe: q.Timeframe,
		Direction: q.Direction,
		Entry:     q.Entry,
		SL:        q.SL,
		TP1:       q.TP1,
		TP2:       q.TP2,
		Score:     q.Score,
		Setup:     q.Setup,
		Status:    "NOT CHECKED",
	}
	recordsStore.Records = append(recordsStore.Records, x)
	if err := saveRecordsLocked(); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Could not save signal record."})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": true, "record": x})
}

func terminalRecordStatus(s string) bool {
	switch s {
	case "TP2 HIT", "SL HIT", "BREAK EVEN", "AMBIGUOUS":
		return true
	default:
		return false
	}
}

func recordsSummary(rs []tradeRecord) map[string]any {
	total := len(rs)
	trades, wins, losses, be, tpHits, slHits, ambiguous := 0, 0, 0, 0, 0, 0, 0
	for _, x := range rs {
		if x.EntryAt > 0 {
			trades++
		}
		if x.TPHit {
			tpHits++
		}
		if x.SLHit {
			slHits++
		}
		switch x.Status {
		case "TP2 HIT":
			wins++
		case "SL HIT":
			losses++
		case "BREAK EVEN":
			be++
		case "AMBIGUOUS":
			ambiguous++
		}
	}
	closed := wins + losses + be
	accuracy := 0.0
	if closed > 0 {
		accuracy = float64(wins) * 100 / float64(closed)
	}
	pending := total - wins - losses - be - ambiguous
	if pending < 0 {
		pending = 0
	}
	return map[string]any{
		"total_signals": total,
		"total_trades":  trades,
		"wins":          wins,
		"losses":        losses,
		"break_even":    be,
		"tp_hits":       tpHits,
		"sl_hits":       slHits,
		"ambiguous":     ambiguous,
		"pending":       pending,
		"accuracy":      math.Round(accuracy*10) / 10,
	}
}

func recordsSnapshotLocked() []tradeRecord {
	out := append([]tradeRecord(nil), recordsStore.Records...)
	sort.SliceStable(out, func(i, j int) bool { return out[i].CreatedAt > out[j].CreatedAt })
	return out
}

func recordsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	recordsMu.Lock()
	loadRecordsLocked()
	rs := recordsSnapshotLocked()
	recordsMu.Unlock()
	_ = json.NewEncoder(w).Encode(map[string]any{"records": rs, "summary": recordsSummary(rs), "server_time": time.Now().Unix()})
}

func accuracyHistory(symbol string, length int) ([]candle, error) {
	if !allowCall() {
		return nil, fmt.Errorf("API rate limit is busy; wait about a minute and run Accuracy Check again")
	}
	v := getSettings()
	if strings.TrimSpace(v.APIKey) == "" {
		return nil, fmt.Errorf("Access Key is not saved")
	}
	var endpoint, fcsSym, typ string
	switch symbol {
	case "XAUUSD":
		endpoint, fcsSym, typ = "https://api-v4.fcsapi.com/forex/history", "XAUUSD", "commodity"
	case "BTCUSDT":
		endpoint, fcsSym, typ = "https://api-v4.fcsapi.com/crypto/history", "BINANCE:BTCUSDT", "crypto"
	default:
		return nil, fmt.Errorf("unsupported symbol %s", symbol)
	}
	if length < 60 {
		length = 60
	}
	if length > 10000 {
		length = 10000
	}
	u, _ := url.Parse(endpoint)
	z := u.Query()
	z.Set("access_key", v.APIKey)
	z.Set("symbol", fcsSym)
	z.Set("period", "1m")
	z.Set("type", typ)
	z.Set("length", fmt.Sprintf("%d", length))
	z.Set("is_chart", "0")
	u.RawQuery = z.Encode()
	cli := &http.Client{Timeout: 22 * time.Second}
	req, _ := http.NewRequest(http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", "MH-Analysis/79.6-Records")
	resp, err := cli.Do(req)
	if err != nil {
		return nil, fmt.Errorf("1m history connection failed: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 12<<20))
	var root any
	if json.Unmarshal(body, &root) != nil {
		return nil, fmt.Errorf("1m history returned unreadable data")
	}
	cs := extractCandles(root)
	if resp.StatusCode >= 400 || len(cs) == 0 {
		msg := "1m history was unavailable"
		if m, ok := root.(map[string]any); ok {
			if s, ok := m["msg"].(string); ok && strings.TrimSpace(s) != "" {
				msg = s
			}
			if s, ok := m["error"].(string); ok && strings.TrimSpace(s) != "" {
				msg = s
			}
		}
		return nil, fmt.Errorf("%s", msg)
	}
	sort.Slice(cs, func(i, j int) bool { return cs[i].T < cs[j].T })
	return cs, nil
}

func candleTouches(c candle, p float64) bool { return c.L <= p && c.H >= p }

func markAmbiguousRecord(x *tradeRecord, c candle, note string) {
	x.Status = "AMBIGUOUS"
	x.Ambiguous = true
	x.Note = note
	x.LastCandleAt = c.T
}

func evaluateRecord(x *tradeRecord, cs []candle, checkedAt int64) {
	if terminalRecordStatus(x.Status) || len(cs) == 0 {
		return
	}
	oldest := cs[0].T
	if x.LastCandleAt == 0 && oldest > x.CreatedAt+120 {
		x.Status = "NEEDS HISTORY"
		x.Note = "Provider did not return 1m candles far enough back for this signal. No result was guessed."
		x.LastCheckedAt = checkedAt
		return
	}
	if x.LastCandleAt > 0 && oldest > x.LastCandleAt+3600 {
		x.Status = "NEEDS HISTORY"
		x.Note = "There is a gap before the returned 1m history. No result was guessed."
		x.LastCheckedAt = checkedAt
		return
	}

	entryActive := x.EntryAt > 0
	tp1Active := x.TP1At > 0
	for _, c := range cs {
		if c.T <= x.LastCandleAt || c.T+60 <= x.CreatedAt {
			continue
		}
		partialSignalMinute := c.T <= x.CreatedAt && x.CreatedAt < c.T+60
		if !entryActive {
			if !candleTouches(c, x.Entry) {
				x.LastCandleAt = c.T
				continue
			}
			x.EntryAt = c.T
			if partialSignalMinute {
				x.EntryAt = x.CreatedAt
			}
			entryActive = true
			touchSL := candleTouches(c, x.SL)
			touchTarget := candleTouches(c, x.TP1) || candleTouches(c, x.TP2)
			if touchSL || touchTarget {
				markAmbiguousRecord(x, c, "Entry and an outcome level were inside the same first 1m candle, so exact order cannot be proven without tick data.")
				break
			}
			x.Status = "OPEN"
			x.LastCandleAt = c.T
			continue
		}

		if tp1Active {
			touchBE := candleTouches(c, x.Entry)
			touchTP2 := candleTouches(c, x.TP2)
			if touchBE && touchTP2 {
				markAmbiguousRecord(x, c, "TP2 and Break-Even were both inside the same 1m candle; exact order is unknown.")
				break
			}
			if touchTP2 {
				x.TP2At = c.T
				x.TPHit = true
				x.Status = "TP2 HIT"
				x.Note = "TP1 was reached first; TP2 was later reached on 1m history."
				x.LastCandleAt = c.T
				break
			}
			if touchBE {
				x.BreakEvenAt = c.T
				x.BreakEvenHit = true
				x.Status = "BREAK EVEN"
				x.Note = "TP1 had already activated Break-Even; price later returned to Entry."
				x.LastCandleAt = c.T
				break
			}
			x.Status = "TP1 ACTIVE"
			x.LastCandleAt = c.T
			continue
		}

		touchSL := candleTouches(c, x.SL)
		touchTP1 := candleTouches(c, x.TP1)
		touchTP2 := candleTouches(c, x.TP2)
		if touchSL && (touchTP1 || touchTP2) {
			markAmbiguousRecord(x, c, "SL and TP were both inside the same 1m candle, so exact first touch cannot be proven without tick data.")
			break
		}
		if touchSL {
			x.SLAt = c.T
			x.SLHit = true
			x.Status = "SL HIT"
			x.Note = "SL was reached before TP1 on the available 1m candles."
			x.LastCandleAt = c.T
			break
		}
		if touchTP2 {
			x.TP1At, x.TP2At = c.T, c.T
			x.TPHit = true
			x.Status = "TP2 HIT"
			x.Note = "Price reached TP2 before SL on the available 1m candles."
			x.LastCandleAt = c.T
			break
		}
		if touchTP1 {
			x.TP1At = c.T
			x.TPHit = true
			tp1Active = true
			x.Status = "TP1 ACTIVE"
			x.Note = "TP1 reached; Break-Even is now tracked at Entry while TP2 remains active."
			x.LastCandleAt = c.T
			continue
		}
		x.Status = "OPEN"
		x.LastCandleAt = c.T
	}
	x.LastCheckedAt = checkedAt
	if x.EntryAt == 0 && x.Status != "AMBIGUOUS" && x.Status != "NEEDS HISTORY" {
		x.Status = "WAITING ENTRY"
	}
}

func accuracyHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	now := time.Now().Unix()
	recordsMu.Lock()
	loadRecordsLocked()
	groups := map[string][]int{}
	earliest := map[string]int64{}
	for i := range recordsStore.Records {
		x := recordsStore.Records[i]
		if terminalRecordStatus(x.Status) {
			continue
		}
		groups[x.Symbol] = append(groups[x.Symbol], i)
		start := x.CreatedAt
		if x.LastCandleAt > 0 {
			start = x.LastCandleAt
		}
		if earliest[x.Symbol] == 0 || start < earliest[x.Symbol] {
			earliest[x.Symbol] = start
		}
	}
	recordsMu.Unlock()

	warnings := []string{}
	callsUsed := 0
	checkedSymbols := []string{}
	for symbol, indexes := range groups {
		mins := int(math.Ceil(float64(now-earliest[symbol])/60.0)) + 5
		if mins < 60 {
			mins = 60
		}
		if mins > 10000 {
			mins = 10000
		}
		cs, err := accuracyHistory(symbol, mins)
		if err != nil {
			warnings = append(warnings, symbol+": "+err.Error())
			continue
		}
		callsUsed++
		checkedSymbols = append(checkedSymbols, symbol)
		recordsMu.Lock()
		loadRecordsLocked()
		for _, idx := range indexes {
			if idx >= 0 && idx < len(recordsStore.Records) {
				evaluateRecord(&recordsStore.Records[idx], cs, now)
			}
		}
		_ = saveRecordsLocked()
		recordsMu.Unlock()
	}

	recordsMu.Lock()
	loadRecordsLocked()
	rs := recordsSnapshotLocked()
	recordsMu.Unlock()
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":              true,
		"records":         rs,
		"summary":         recordsSummary(rs),
		"api_calls_used":  callsUsed,
		"checked_symbols": checkedSymbols,
		"warnings":        warnings,
		"checked_at":      now,
	})
}

func registerRecordsRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/records", recordsHandler)
	mux.HandleFunc("/api/records/capture", captureRecordHandler)
	mux.HandleFunc("/api/records/accuracy", accuracyHandler)
}
