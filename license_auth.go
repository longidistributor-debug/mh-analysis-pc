//go:build windows

package main

import (
	"encoding/json"
	"net/http"
	"strings"
)

const licAppVersion = "V.55.9"

// Compatibility layer: preserve the route names and gate expected by main.go.
// The actual secure authentication handlers remain the existing licHandle* functions.
func registerLicenseRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/license/login", licHandleLogin)
	mux.HandleFunc("/api/license/status", licHandleStatus)
	mux.HandleFunc("/api/license/logout", licHandleLogout)
}

func licAccessMessage() string {
	licMu.Lock()
	defer licMu.Unlock()
	if licLastMessage != "" {
		return licLastMessage
	}
	return "Login to MH Analysis first."
}

func licenseGate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if strings.HasPrefix(p, "/api/license/") || strings.HasPrefix(p, "/api/update/") || p == "/api/shutdown" {
			next.ServeHTTP(w, r)
			return
		}
		if strings.HasPrefix(p, "/api/") && !licEnsureAuthorized(false) {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("Cache-Control", "no-store")
			w.WriteHeader(http.StatusUnauthorized)
			licMu.Lock()
			code, message := licLastCode, licLastMessage
			licMu.Unlock()
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": code, "message": message})
			return
		}
		next.ServeHTTP(w, r)
	})
}
