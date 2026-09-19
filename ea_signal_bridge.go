package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// MH_EA_SIGNAL_READER_BRIDGE_V796
// Explicit per-signal handoff from MH Analysis to the user's attached MT5 EA.
// The EA reads Common\Files\MH_Analysis\signal.txt and writes status.txt.

type eaSignalRequest struct {
	SignalID string  `json:"signal_id"`
	Symbol   string  `json:"symbol"`
	Type     string  `json:"type"`
	Entry    float64 `json:"entry"`
	SL       float64 `json:"sl"`
	TP       float64 `json:"tp"`
	Lot      float64 `json:"lot"`
	Expiry   int64   `json:"expiry"`
}

var eaSafeToken = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,80}$`)

func registerEASignalBridgeRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/mt5/ea/send", eaSignalSendHandler)
	mux.HandleFunc("/api/mt5/ea/status", eaSignalStatusHandler)
}

func mt5CommonBridgeDir() (string, error) {
	appData := strings.TrimSpace(os.Getenv("APPDATA"))
	if appData == "" {
		return "", fmt.Errorf("Windows APPDATA is unavailable")
	}
	dir := filepath.Join(appData, "MetaQuotes", "Terminal", "Common", "Files", "MH_Analysis")
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", fmt.Errorf("could not create MT5 Common Files bridge: %w", err)
	}
	return dir, nil
}

func normalizeEABridgeSymbol(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	// MH Analysis uses BTCUSDT for market-data analysis while MT5 brokers commonly
	// expose the same BTC/USD instrument as BTCUSD, optionally with a suffix.
	// The user's EA already resolves broker suffixes from this base symbol.
	if s == "BTCUSDT" {
		return "BTCUSD"
	}
	return s
}

func cleanEAToken(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "|", "_")
	s = strings.ReplaceAll(s, "\r", "_")
	s = strings.ReplaceAll(s, "\n", "_")
	return s
}

func eaSignalSendHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}

	var q eaSignalRequest
	if err := json.NewDecoder(r.Body).Decode(&q); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "bad signal payload"})
		return
	}

	q.SignalID = cleanEAToken(q.SignalID)
	q.Symbol = normalizeEABridgeSymbol(q.Symbol)
	q.Type = strings.ToUpper(cleanEAToken(q.Type))

	if q.SignalID == "" {
		q.SignalID = "MH" + strconv.FormatInt(time.Now().UnixMilli(), 10)
	}
	if !eaSafeToken.MatchString(q.SignalID) {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "invalid signal id"})
		return
	}
	if q.Symbol != "XAUUSD" && q.Symbol != "BTCUSD" {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "unsupported EA bridge symbol"})
		return
	}
	switch q.Type {
	case "BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP":
	default:
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "unsupported pending signal type"})
		return
	}
	if q.Entry <= 0 || q.SL <= 0 || q.TP <= 0 {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "entry/sl/tp must be positive"})
		return
	}
	// lot=0 intentionally tells the supplied EA to use its own DefaultLot input.
	if q.Lot < 0 {
		q.Lot = 0
	}
	if q.Expiry < 0 {
		q.Expiry = 0
	}

	dir, err := mt5CommonBridgeDir()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}

	line := strings.Join([]string{
		q.SignalID,
		q.Symbol,
		q.Type,
		strconv.FormatFloat(q.Entry, 'f', -1, 64),
		strconv.FormatFloat(q.SL, 'f', -1, 64),
		strconv.FormatFloat(q.TP, 'f', -1, 64),
		strconv.FormatFloat(q.Lot, 'f', -1, 64),
		strconv.FormatInt(q.Expiry, 10),
	}, "|") + "\r\n"

	// Write to a temporary file first, then swap it into signal.txt. If the EA
	// polls during the tiny swap window it simply sees no file and retries 250ms later.
	tmp := filepath.Join(dir, "signal.new")
	dst := filepath.Join(dir, "signal.txt")
	if err := os.WriteFile(tmp, []byte(line), 0644); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "could not write EA signal: " + err.Error()})
		return
	}
	_ = os.Remove(dst)
	if err := os.Rename(tmp, dst); err != nil {
		_ = os.Remove(tmp)
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "could not publish EA signal: " + err.Error()})
		return
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":        true,
		"signal_id": q.SignalID,
		"symbol":    q.Symbol,
		"type":      q.Type,
		"file":      dst,
	})
}

func eaSignalStatusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	dir, err := mt5CommonBridgeDir()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}
	p := filepath.Join(dir, "status.txt")
	b, err := os.ReadFile(p)
	if err != nil {
		if os.IsNotExist(err) {
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "status": "", "exists": false})
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
		return
	}
	line := strings.TrimSpace(strings.SplitN(strings.ReplaceAll(string(b), "\r\n", "\n"), "\n", 2)[0])
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "status": line, "exists": line != ""})
}
