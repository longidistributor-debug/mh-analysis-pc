package main

import (
    "os"
    "path/filepath"
)

// V55.2 Records-only persistence guard.
// Older signal-records-v*.json files were being merged back into the canonical
// store on every load, so a record deleted from signal-records.json could
// reappear immediately. Canonicalize once at startup, then retire only those
// legacy mirrors. No signal/analysis/WhatsApp behavior is changed.
func init() {
    canonical := mt5LocalRecordsPath()
    legacy, _ := filepath.Glob(filepath.Join(mt5RecordsDir(), "signal-records-v*.json"))
    if len(legacy) == 0 {
        return
    }

    // Merge everything once before retiring the mirrors, so no existing record
    // is lost during migration.
    merged := loadMT5LocalStore()
    if err := saveMT5LocalStore(merged); err != nil {
        return
    }
    for _, p := range legacy {
        if filepath.Clean(p) != filepath.Clean(canonical) {
            _ = os.Remove(p)
        }
    }
}
