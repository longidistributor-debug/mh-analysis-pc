package main

import (
	"os"
	"path/filepath"
)

// V55.1 deletion guard: once the canonical Records store exists it is the
// single source of truth. Old signal-records-v*.json migration snapshots must
// not be merged back after the user deletes a selected date/range, otherwise
// deleted rows reappear on the next Records refresh.
func init() {
	canonical := mt5LocalRecordsPath()
	if _, err := os.Stat(canonical); err != nil {
		return // first migration is still allowed when no canonical store exists
	}
	legacy, _ := filepath.Glob(filepath.Join(mt5RecordsDir(), "signal-records-v*.json"))
	for _, p := range legacy {
		_ = os.Remove(p)
	}
}
