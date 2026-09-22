package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

// MH_RECORDS_MT5_LOCAL_V797
// Records v2 uses only the local MT5 EA lifecycle event file. It does not
// request FCS/market history for outcome verification.

type mt5LocalRecord struct {
	ID              string  `json:"id"`
	SignalID        string  `json:"signal_id,omitempty"`
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
	OrderTicket     uint64  `json:"order_ticket,omitempty"`
	PositionID      uint64  `json:"position_id,omitempty"`
	DealTicket      uint64  `json:"deal_ticket,omitempty"`
	PendingPlacedAt int64   `json:"pending_placed_at,omitempty"`
	ActivatedAt     int64   `json:"activated_at,omitempty"`
	ClosedAt        int64   `json:"closed_at,omitempty"`
	ClosePrice      float64 `json:"close_price,omitempty"`
	RealizedProfit  float64 `json:"realized_profit,omitempty"`
	ManualClose     bool    `json:"manual_close,omitempty"`
	ManualResult    string  `json:"manual_result,omitempty"`
	Cancelled       bool    `json:"cancelled,omitempty"`
	CancelReason    string  `json:"cancel_reason,omitempty"`
	LastMT5Event    string  `json:"last_mt5_event,omitempty"`
	LastMT5Reason   string  `json:"last_mt5_reason,omitempty"`
}

type mt5LocalStore struct {
	Version int              `json:"version"`
	Records []mt5LocalRecord `json:"records"`
}

type mt5LocalCapture struct {
	SignalID  string  `json:"signal_id"`
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

type mt5LifecycleEvent struct {
	SignalID       string  `json:"signal_id"`
	Event          string  `json:"event"`
	OrderTicket    uint64  `json:"order_ticket"`
	PositionID     uint64  `json:"position_id"`
	DealTicket     uint64  `json:"deal_ticket"`
	Symbol         string  `json:"symbol"`
	Time           int64   `json:"time"`
	Price          float64 `json:"price"`
	Volume         float64 `json:"volume"`
	Profit         float64 `json:"profit"`
	NetProfit      float64 `json:"net_profit"`
	Reason         string  `json:"reason"`
	PositionClosed bool    `json:"position_closed"`
}

type mt5ResetRequest struct {
	From      string `json:"from"`
	To        string `json:"to"`
	Timeframe string `json:"timeframe"`
	Date      string `json:"date"`
}

var mt5RecordsMu sync.Mutex

func mt5LocalRecordsPath() string {
	b := os.Getenv("LOCALAPPDATA")
	if b == "" {
		b = os.TempDir()
	}
	return filepath.Join(b, "MHAnalysis", "signal-records-v796.json")
}

func mt5LifecyclePath() (string, error) {
	appData := strings.TrimSpace(os.Getenv("APPDATA"))
	if appData == "" {
		return "", fmt.Errorf("Windows APPDATA is unavailable")
	}
	return filepath.Join(appData, "MetaQuotes", "Terminal", "Common", "Files", "MH_Analysis", "trade_events.jsonl"), nil
}

func loadMT5LocalStore() mt5LocalStore {
	s := mt5LocalStore{Version: 2, Records: []mt5LocalRecord{}}
	b, err := os.ReadFile(mt5LocalRecordsPath())
	if err != nil {
		return s
	}
	if json.Unmarshal(b, &s) != nil {
		return mt5LocalStore{Version: 2, Records: []mt5LocalRecord{}}
	}
	if s.Version < 2 {
		s.Version = 2
	}
	if s.Records == nil {
		s.Records = []mt5LocalRecord{}
	}
	for i := range s.Records {
		if s.Records[i].SignalID == "" && strings.HasPrefix(s.Records[i].ID, "MH") {
			s.Records[i].SignalID = s.Records[i].ID
		}
	}
	return s
}

func saveMT5LocalStore(s mt5LocalStore) error {
	p := mt5LocalRecordsPath()
	if err := os.MkdirAll(filepath.Dir(p), 0755); err != nil {
		return err
	}
	s.Version = 2
	b, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, b, 0600); err != nil {
		return err
	}
	_ = os.Remove(p)
	return os.Rename(tmp, p)
}

func recordNumberOK(v float64) bool {
	return !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0
}

// MH_SAME_SIGNAL_GUARD_V30
func sameSignalDisplayPriceV30(a, b float64) bool {
	if !recordNumberOK(a) || !recordNumberOK(b) {
		return false
	}
	scale := 100000.0
	if math.Max(math.Abs(a), math.Abs(b)) >= 100 {
		scale = 100.0
	}
	return math.Round(a*scale) == math.Round(b*scale)
}
func sameSignalPointV30(x mt5LocalRecord, q mt5LocalCapture) bool {
	return strings.EqualFold(strings.TrimSpace(x.Symbol), strings.TrimSpace(q.Symbol)) &&
		strings.EqualFold(strings.TrimSpace(x.Timeframe), strings.TrimSpace(q.Timeframe)) &&
		strings.EqualFold(strings.TrimSpace(x.Direction), strings.TrimSpace(q.Direction)) &&
		sameSignalDisplayPriceV30(x.Entry, q.Entry) && sameSignalDisplayPriceV30(x.SL, q.SL) &&
		sameSignalDisplayPriceV30(x.TP1, q.TP1) && sameSignalDisplayPriceV30(x.TP2, q.TP2)
}
func activeRecordV30(x mt5LocalRecord) bool {
	if recordTerminalMT5(x) {
		return false
	}
	st := strings.ToUpper(strings.TrimSpace(x.Status))
	if strings.Contains(st, "CANCEL") || strings.Contains(st, "EXPIRED") || strings.Contains(st, "REJECT") || strings.Contains(st, "CLOSED") || strings.Contains(st, "TP HIT") || strings.Contains(st, "SL HIT") || strings.Contains(st, "BREAK EVEN") {
		return false
	}
	return true
}
func findSameActiveV30(s mt5LocalStore, q mt5LocalCapture) int {
	for i := len(s.Records) - 1; i >= 0; i-- {
		if activeRecordV30(s.Records[i]) && sameSignalPointV30(s.Records[i], q) {
			return i
		}
	}
	return -1
}
func mt5DuplicateSignalHandlerV30(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q mt5LocalCapture
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Timeframe = strings.TrimSpace(q.Timeframe)
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	_, _, _ = syncMT5Lifecycle(&s)
	i := findSameActiveV30(s, q)
	_ = saveMT5LocalStore(s)
	mt5RecordsMu.Unlock()
	if i >= 0 {
		x := s.Records[i]
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "duplicate": true, "same_signal": true, "existing_signal_id": x.SignalID, "existing_status": x.Status})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "duplicate": false})
}

func samePriceLoose(a, b float64) bool {
	if a <= 0 || b <= 0 {
		return false
	}
	tol := math.Max(1e-6, math.Max(math.Abs(a), math.Abs(b))*0.00005)
	return math.Abs(a-b) <= tol
}

func symbolFamilyEqual(recordSymbol, eventSymbol string) bool {
	a := strings.ToUpper(strings.TrimSpace(recordSymbol))
	b := strings.ToUpper(strings.TrimSpace(eventSymbol))
	if a == b || strings.HasPrefix(b, a) || strings.HasPrefix(a, b) {
		return true
	}
	if a == "BTCUSDT" && strings.HasPrefix(b, "BTCUSD") {
		return true
	}
	if b == "BTCUSDT" && strings.HasPrefix(a, "BTCUSD") {
		return true
	}
	if a == "XAUUSD" && strings.HasPrefix(b, "XAUUSD") {
		return true
	}
	return false
}

func readMT5LifecycleEvents() ([]mt5LifecycleEvent, error) {
	p, err := mt5LifecyclePath()
	if err != nil {
		return nil, err
	}
	f, err := os.Open(p)
	if err != nil {
		if os.IsNotExist(err) {
			return []mt5LifecycleEvent{}, nil
		}
		return nil, err
	}
	defer f.Close()

	out := []mt5LifecycleEvent{}
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var ev mt5LifecycleEvent
		if json.Unmarshal([]byte(line), &ev) != nil {
			continue
		}
		ev.SignalID = strings.TrimSpace(ev.SignalID)
		ev.Event = strings.ToUpper(strings.TrimSpace(ev.Event))
		ev.Reason = strings.ToUpper(strings.TrimSpace(ev.Reason))
		if ev.SignalID == "" || ev.Event == "" {
			continue
		}
		out = append(out, ev)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Time == out[j].Time {
			return i < j
		}
		return out[i].Time < out[j].Time
	})
	return out, nil
}

func findRecordForEvent(s *mt5LocalStore, ev mt5LifecycleEvent) int {
	for i := range s.Records {
		if s.Records[i].SignalID == ev.SignalID || s.Records[i].ID == ev.SignalID {
			return i
		}
	}
	if ev.Event == "PENDING_PLACED" || ev.Event == "PENDING_ACTIVE" {
		best, bestGap := -1, int64(1<<62-1)
		for i := range s.Records {
			r := &s.Records[i]
			if r.SignalID != "" || !symbolFamilyEqual(r.Symbol, ev.Symbol) || !samePriceLoose(r.Entry, ev.Price) {
				continue
			}
			gap := ev.Time - r.CreatedAt
			if gap < 0 {
				gap = -gap
			}
			if gap <= 120 && gap < bestGap {
				best, bestGap = i, gap
			}
		}
		if best >= 0 {
			s.Records[best].SignalID = ev.SignalID
			if s.Records[best].ID == "" {
				s.Records[best].ID = ev.SignalID
			}
			return best
		}
	}
	return -1
}

func applyLifecycleEvent(r *mt5LocalRecord, ev mt5LifecycleEvent) {
	if ev.OrderTicket > 0 {
		r.OrderTicket = ev.OrderTicket
	}
	if ev.PositionID > 0 {
		r.PositionID = ev.PositionID
	}
	if ev.DealTicket > 0 {
		r.DealTicket = ev.DealTicket
	}
	if ev.Time > 0 {
		r.LastCheckedAt = ev.Time
	}
	r.LastMT5Event = ev.Event
	r.LastMT5Reason = ev.Reason
	r.Note = "MT5: " + strings.ReplaceAll(ev.Event, "_", " ")
	if ev.Reason != "" {
		r.Note += " • " + ev.Reason
	}

	switch ev.Event {
	case "PENDING_PLACED":
		r.PendingPlacedAt = ev.Time
		if !recordTerminalMT5(*r) {
			r.Status = "PENDING PLACED"
		}
	case "PENDING_ACTIVE":
		r.ActivatedAt = ev.Time
		r.EntryAt = ev.Time
		r.Status = "OPEN"
		r.Cancelled = false
		r.CancelReason = ""
	case "PENDING_CANCELLED_MANUAL":
		r.Cancelled = true
		r.CancelReason = "MANUAL"
		r.ClosedAt = ev.Time
		r.Status = "CANCELLED MANUAL"
	case "PENDING_CANCELLED_EA":
		r.Cancelled = true
		r.CancelReason = "EA"
		r.ClosedAt = ev.Time
		r.Status = "CANCELLED EA"
	case "PENDING_CANCELLED":
		r.Cancelled = true
		r.CancelReason = ev.Reason
		r.ClosedAt = ev.Time
		r.Status = "CANCELLED"
	case "PENDING_EXPIRED":
		r.Cancelled = true
		r.CancelReason = "EXPIRED"
		r.ClosedAt = ev.Time
		r.Status = "EXPIRED"
	case "PENDING_REJECTED":
		r.Cancelled = true
		r.CancelReason = "REJECTED"
		r.ClosedAt = ev.Time
		r.Status = "REJECTED"
	case "TP_HIT":
		r.TPHit = true
		r.TP1At = ev.Time
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "TP HIT"
	case "SL_HIT":
		r.SLHit = true
		r.SLAt = ev.Time
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "SL HIT"
	case "BREAK_EVEN":
		r.BreakEvenHit = true
		r.BreakEvenAt = ev.Time
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "BREAK EVEN"
	case "MANUAL_CLOSE_POSITIVE":
		r.ManualClose = true
		r.ManualResult = "POSITIVE"
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "MANUAL +POSITIVE"
	case "MANUAL_CLOSE_NEGATIVE":
		r.ManualClose = true
		r.ManualResult = "NEGATIVE"
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "MANUAL -NEGATIVE"
	case "MANUAL_CLOSE_BREAK_EVEN":
		r.ManualClose = true
		r.ManualResult = "BREAK_EVEN"
		r.BreakEvenHit = true
		r.BreakEvenAt = ev.Time
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "MANUAL BREAK EVEN"
	case "EA_CLOSE_POSITIVE", "CLOSED_POSITIVE":
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "CLOSED +POSITIVE"
	case "EA_CLOSE_NEGATIVE", "CLOSED_NEGATIVE":
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "CLOSED -NEGATIVE"
	case "EA_CLOSE_BREAK_EVEN", "CLOSED_BREAK_EVEN":
		r.BreakEvenHit = true
		r.BreakEvenAt = ev.Time
		r.ClosedAt = ev.Time
		r.ClosePrice = ev.Price
		r.RealizedProfit = ev.NetProfit
		r.Status = "BREAK EVEN"
	case "TP_PARTIAL":
		r.TPHit = true
		r.TP1At = ev.Time
		r.RealizedProfit += ev.NetProfit
		r.Status = "TP PARTIAL"
	case "SL_PARTIAL":
		r.SLHit = true
		r.RealizedProfit += ev.NetProfit
		r.Status = "SL PARTIAL"
	case "BREAK_EVEN_PARTIAL":
		r.BreakEvenHit = true
		r.RealizedProfit += ev.NetProfit
		r.Status = "BREAK EVEN PARTIAL"
	case "MANUAL_PARTIAL_POSITIVE", "MANUAL_PARTIAL_NEGATIVE", "MANUAL_PARTIAL_BREAK_EVEN":
		r.ManualClose = true
		r.RealizedProfit += ev.NetProfit
		r.Status = strings.ReplaceAll(ev.Event, "_", " ")
	case "EA_PARTIAL_POSITIVE", "EA_PARTIAL_NEGATIVE", "EA_PARTIAL_BREAK_EVEN", "PARTIAL_POSITIVE", "PARTIAL_NEGATIVE", "PARTIAL_BREAK_EVEN":
		r.RealizedProfit += ev.NetProfit
		r.Status = strings.ReplaceAll(ev.Event, "_", " ")
	}
}

func recordTerminalMT5(r mt5LocalRecord) bool {
	if r.Cancelled || r.ClosedAt > 0 {
		return true
	}
	switch r.Status {
	case "TP HIT", "SL HIT", "BREAK EVEN", "MANUAL +POSITIVE", "MANUAL -NEGATIVE", "MANUAL BREAK EVEN", "CLOSED +POSITIVE", "CLOSED -NEGATIVE":
		return true
	default:
		return false
	}
}

func resetMT5Derived(r *mt5LocalRecord) {
	r.Status = "SIGNAL GENERATED"
	r.EntryAt = 0
	r.TP1At = 0
	r.TP2At = 0
	r.SLAt = 0
	r.BreakEvenAt = 0
	r.LastCandleAt = 0
	r.LastCheckedAt = 0
	r.TPHit = false
	r.SLHit = false
	r.BreakEvenHit = false
	r.Ambiguous = false
	r.Note = ""
	r.OrderTicket = 0
	r.PositionID = 0
	r.DealTicket = 0
	r.PendingPlacedAt = 0
	r.ActivatedAt = 0
	r.ClosedAt = 0
	r.ClosePrice = 0
	r.RealizedProfit = 0
	r.ManualClose = false
	r.ManualResult = ""
	r.Cancelled = false
	r.CancelReason = ""
	r.LastMT5Event = ""
	r.LastMT5Reason = ""
}

func syncMT5Lifecycle(s *mt5LocalStore) (int, int, error) {
	events, err := readMT5LifecycleEvents()
	if err != nil {
		return 0, 0, err
	}
	matched := 0
	prepared := map[int]bool{}
	for _, ev := range events {
		idx := findRecordForEvent(s, ev)
		if idx < 0 {
			continue
		}
		if !prepared[idx] {
			resetMT5Derived(&s.Records[idx])
			prepared[idx] = true
		}
		applyLifecycleEvent(&s.Records[idx], ev)
		matched++
	}
	return len(events), matched, nil
}

func mt5ResultClass(r mt5LocalRecord) string {
	switch r.Status {
	case "TP HIT", "MANUAL +POSITIVE", "CLOSED +POSITIVE":
		return "WIN"
	case "SL HIT", "MANUAL -NEGATIVE", "CLOSED -NEGATIVE":
		return "LOSS"
	case "BREAK EVEN", "MANUAL BREAK EVEN":
		return "BE"
	default:
		return ""
	}
}

func mt5LocalSummary(rs []mt5LocalRecord) map[string]any {
	total, placed, activated, wins, losses, be, manual, cancelled := len(rs), 0, 0, 0, 0, 0, 0, 0
	for _, r := range rs {
		if r.PendingPlacedAt > 0 || r.OrderTicket > 0 {
			placed++
		}
		if r.ActivatedAt > 0 || r.EntryAt > 0 || r.PositionID > 0 {
			activated++
		}
		if r.ManualClose {
			manual++
		}
		if r.Cancelled {
			cancelled++
		}
		switch mt5ResultClass(r) {
		case "WIN":
			wins++
		case "LOSS":
			losses++
		case "BE":
			be++
		}
	}
	closed := wins + losses + be
	accuracy := 0.0
	if closed > 0 {
		accuracy = float64(wins) * 100 / float64(closed)
	}
	pending := total - wins - losses - be - cancelled
	if pending < 0 {
		pending = 0
	}
	return map[string]any{
		"total_signals": total,
		"orders_placed": placed,
		"activated":     activated,
		"wins":          wins,
		"losses":        losses,
		"break_even":    be,
		"manual_close":  manual,
		"cancelled":     cancelled,
		"pending":       pending,
		"accuracy":      math.Round(accuracy*10) / 10,
	}
}

func mt5RecordsSnapshot(s mt5LocalStore) []mt5LocalRecord {
	out := append([]mt5LocalRecord(nil), s.Records...)
	sort.SliceStable(out, func(i, j int) bool { return out[i].CreatedAt > out[j].CreatedAt })
	return out
}

func captureMT5LocalRecord(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q mt5LocalCapture
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.SignalID = strings.TrimSpace(q.SignalID)
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Timeframe = strings.TrimSpace(q.Timeframe)
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	q.Action = strings.ToUpper(strings.TrimSpace(q.Action))
	q.Setup = strings.TrimSpace(q.Setup)
	if q.SignalID == "" || q.Action != "NEW" || (q.Direction != "BUY" && q.Direction != "SELL") || q.Symbol == "" || q.Timeframe == "" || !recordNumberOK(q.Entry) || !recordNumberOK(q.SL) || !recordNumberOK(q.TP1) || !recordNumberOK(q.TP2) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false})
		return
	}

	mt5RecordsMu.Lock()
	defer mt5RecordsMu.Unlock()
	s := loadMT5LocalStore()
	for _, x := range s.Records {
		if x.SignalID == q.SignalID || x.ID == q.SignalID {
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": q.SignalID})
			return
		}
	}
	_, _, _ = syncMT5Lifecycle(&s)
	if i := findSameActiveV30(s, q); i >= 0 {
		x := s.Records[i]
		_ = saveMT5LocalStore(s)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "same_signal": true, "existing_signal_id": x.SignalID, "existing_status": x.Status})
		return
	}
	now := time.Now()
	x := mt5LocalRecord{
		ID: q.SignalID, SignalID: q.SignalID,
		CreatedAt: now.Unix(), LocalDate: now.Format("2006-01-02"), LocalTime: now.Format("15:04:05"),
		Symbol: q.Symbol, Timeframe: q.Timeframe, Direction: q.Direction,
		Entry: q.Entry, SL: q.SL, TP1: q.TP1, TP2: q.TP2, Score: q.Score, Setup: q.Setup,
		Status: "SIGNAL GENERATED",
	}
	s.Records = append(s.Records, x)
	_, _, _ = syncMT5Lifecycle(&s)
	if err := saveMT5LocalStore(s); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "Could not save signal record."})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": true, "record": x})
}

func mt5LocalRecordsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	eventsRead, matched, syncErr := syncMT5Lifecycle(&s)
	_ = saveMT5LocalStore(s)
	rs := mt5RecordsSnapshot(s)
	mt5RecordsMu.Unlock()

	resp := map[string]any{
		"records":                   rs,
		"summary":                   mt5LocalSummary(rs),
		"server_time":               time.Now().Unix(),
		"source":                    "LOCAL_MT5",
		"external_market_api_calls": 0,
		"events_read":               eventsRead,
		"events_matched":            matched,
	}
	if syncErr != nil {
		resp["warning"] = syncErr.Error()
	}
	_ = json.NewEncoder(w).Encode(resp)
}

func mt5LocalSyncHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	eventsRead, matched, err := syncMT5Lifecycle(&s)
	if err == nil {
		err = saveMT5LocalStore(s)
	}
	rs := mt5RecordsSnapshot(s)
	mt5RecordsMu.Unlock()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error(), "external_market_api_calls": 0})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":                        true,
		"records":                   rs,
		"summary":                   mt5LocalSummary(rs),
		"events_read":               eventsRead,
		"events_matched":            matched,
		"external_market_api_calls": 0,
		"source":                    "LOCAL_MT5",
	})
}

func validDateKey(s string) bool {
	if s == "" {
		return true
	}
	_, err := time.Parse("2006-01-02", s)
	return err == nil
}

func mt5LocalResetHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q mt5ResetRequest
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.From = strings.TrimSpace(q.From)
	q.To = strings.TrimSpace(q.To)
	q.Date = strings.TrimSpace(q.Date)
	q.Timeframe = strings.TrimSpace(q.Timeframe)
	if q.Timeframe == "ALL" || q.Timeframe == "all" {
		q.Timeframe = ""
	}
	if !validDateKey(q.From) || !validDateKey(q.To) || !validDateKey(q.Date) {
		http.Error(w, "invalid date", http.StatusBadRequest)
		return
	}
	if q.Date != "" {
		q.From, q.To = q.Date, q.Date
	}
	if q.From == "" && q.To == "" {
		http.Error(w, "date or range required", http.StatusBadRequest)
		return
	}
	if q.From != "" && q.To != "" && q.From > q.To {
		http.Error(w, "from is after to", http.StatusBadRequest)
		return
	}

	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	kept := make([]mt5LocalRecord, 0, len(s.Records))
	deleted := 0
	for _, x := range s.Records {
		inRange := true
		if q.From != "" && x.LocalDate < q.From {
			inRange = false
		}
		if q.To != "" && x.LocalDate > q.To {
			inRange = false
		}
		if q.Timeframe != "" && x.Timeframe != q.Timeframe {
			inRange = false
		}
		if inRange {
			deleted++
			continue
		}
		kept = append(kept, x)
	}
	s.Records = kept
	err := saveMT5LocalStore(s)
	rs := mt5RecordsSnapshot(s)
	mt5RecordsMu.Unlock()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":                        true,
		"deleted":                   deleted,
		"records":                   rs,
		"summary":                   mt5LocalSummary(rs),
		"external_market_api_calls": 0,
	})
}

func registerRecordsV2Routes(mux *http.ServeMux) {
	mux.HandleFunc("/api/records-v2", mt5LocalRecordsHandler)
	mux.HandleFunc("/api/records-v2/duplicate", mt5DuplicateSignalHandlerV30)
	mux.HandleFunc("/api/records-v2/capture", captureMT5LocalRecord)
	mux.HandleFunc("/api/records-v2/sync", mt5LocalSyncHandler)
	mux.HandleFunc("/api/records-v2/reset", mt5LocalResetHandler)
}
