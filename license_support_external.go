//go:build windows

package main

// MH_LICENSE_EXTERNAL_SUPPORT_V804
// Opens the fixed MH Analysis support link in the user's normal Windows default browser.
// The URL is not accepted from the request, so this endpoint cannot be used as a generic URL launcher.

import (
	"encoding/json"
	"net/http"
	"os/exec"
)

const mhSupportURLV804 = "https://wa.me/923434824609"

func licHandleSupportOpenV804(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "method_not_allowed"})
		return
	}
	cmd := exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", mhSupportURLV804)
	if err := cmd.Start(); err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "browser_open_failed"})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
}
