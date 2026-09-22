//go:build windows

package main

// MH_SECURE_LICENSE_V801
// Server-authoritative login, single-device Ed25519 binding, DPAPI-protected local session,
// periodic online authorization, expiry/disable enforcement, and no self-registration.

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows/registry"
)

const licDefaultBaseURL = "https://mh-analysis.vercel.app"
const licAppVersion = "V.37"

type licDataBlob struct {
	cbData uint32
	pbData *byte
}

var (
	licCrypt32               = syscall.NewLazyDLL("crypt32.dll")
	licKernel32              = syscall.NewLazyDLL("kernel32.dll")
	licCryptProtectData      = licCrypt32.NewProc("CryptProtectData")
	licCryptUnprotectData    = licCrypt32.NewProc("CryptUnprotectData")
	licLocalFree             = licKernel32.NewProc("LocalFree")
	licMu                    sync.Mutex
	licDeviceMu              sync.Mutex
	licSessionMem            *licSession
	licAuthorized            bool
	licLastCheck             time.Time
	licLastCode              string
	licLastMessage           string
	licHTTP                  = &http.Client{Timeout: 12 * time.Second}
	licRemoteCheckMinSpacing = 90 * time.Second
)

type licDeviceDisk struct {
	PrivateKey string `json:"private_key"`
}

type licDevice struct {
	Private ed25519.PrivateKey
	Public  ed25519.PublicKey
	DER     []byte
	ID      string
}

type licUserInfo struct {
	Username   string `json:"username"`
	ValidFrom  string `json:"valid_from"`
	ValidUntil string `json:"valid_until"`
	DeviceID   string `json:"device_id"`
}

type licSession struct {
	Username    string      `json:"username"`
	AccessToken string      `json:"access_token"`
	User        licUserInfo `json:"user"`
	SavedAt     time.Time   `json:"saved_at"`
}

type licRemoteEnvelope struct {
	OK          bool        `json:"ok"`
	Code        string      `json:"code"`
	Error       string      `json:"error"`
	Message     string      `json:"message"`
	AccessToken string      `json:"access_token"`
	User        licUserInfo `json:"user"`
	ChallengeID string      `json:"challenge_id"`
	Challenge   string      `json:"challenge"`
	ExpiresIn   int         `json:"expires_in"`
}

func licBaseURL() string {
	if v := strings.TrimSpace(os.Getenv("MH_AUTH_BASE_URL")); v != "" {
		return strings.TrimRight(v, "/")
	}
	return licDefaultBaseURL
}

func licRootDir() string {
	b := os.Getenv("LOCALAPPDATA")
	if b == "" {
		b = os.TempDir()
	}
	return filepath.Join(b, "MHAnalysis")
}

func licDevicePath() string  { return filepath.Join(licRootDir(), "license-device-v1.bin") }
func licSessionPath() string { return filepath.Join(licRootDir(), "license-session-v1.bin") }

func licBlobFromBytes(b []byte) licDataBlob {
	if len(b) == 0 {
		return licDataBlob{}
	}
	return licDataBlob{cbData: uint32(len(b)), pbData: &b[0]}
}

func licBytesFromBlob(b licDataBlob) []byte {
	if b.cbData == 0 || b.pbData == nil {
		return nil
	}
	src := unsafe.Slice(b.pbData, int(b.cbData))
	out := make([]byte, len(src))
	copy(out, src)
	return out
}

func licDPAPIProtect(data []byte) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("empty dpapi input")
	}
	in := licBlobFromBytes(data)
	var out licDataBlob
	r, _, e := licCryptProtectData.Call(
		uintptr(unsafe.Pointer(&in)),
		0, 0, 0, 0,
		uintptr(0x1),
		uintptr(unsafe.Pointer(&out)),
	)
	if r == 0 {
		return nil, fmt.Errorf("CryptProtectData failed: %v", e)
	}
	defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	return licBytesFromBlob(out), nil
}

func licDPAPIUnprotect(data []byte) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("empty dpapi input")
	}
	in := licBlobFromBytes(data)
	var out licDataBlob
	r, _, e := licCryptUnprotectData.Call(
		uintptr(unsafe.Pointer(&in)),
		0, 0, 0, 0, 0,
		uintptr(0x1),
		uintptr(unsafe.Pointer(&out)),
	)
	if r == 0 {
		return nil, fmt.Errorf("CryptUnprotectData failed: %v", e)
	}
	defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	return licBytesFromBlob(out), nil
}

func licWriteProtected(path string, v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return err
	}
	enc, err := licDPAPIProtect(raw)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err = os.WriteFile(tmp, enc, 0600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func licReadProtected(path string, v any) error {
	enc, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	raw, err := licDPAPIUnprotect(enc)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, v)
}

func licStableMachineID() (string, error) {
	k, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Cryptography`, registry.QUERY_VALUE)
	if err != nil {
		return "", fmt.Errorf("open MachineGuid: %w", err)
	}
	defer k.Close()
	guid, _, err := k.GetStringValue("MachineGuid")
	if err != nil || strings.TrimSpace(guid) == "" {
		return "", errors.New("Windows MachineGuid is unavailable")
	}
	sum := sha256.Sum256([]byte(strings.ToLower(strings.TrimSpace(guid))))
	return hex.EncodeToString(sum[:]), nil
}

func licEnsureDevice() (*licDevice, error) {
	licDeviceMu.Lock()
	defer licDeviceMu.Unlock()
	machineID, err := licStableMachineID()
	if err != nil {
		return nil, err
	}
	path := licDevicePath()
	var disk licDeviceDisk
	if _, statErr := os.Stat(path); statErr == nil {
		readErr := licReadProtected(path, &disk)
		if readErr == nil {
			raw, decErr := base64.StdEncoding.DecodeString(disk.PrivateKey)
			if decErr == nil && len(raw) == ed25519.PrivateKeySize {
				priv := ed25519.PrivateKey(raw)
				pub := priv.Public().(ed25519.PublicKey)
				der, marshalErr := x509.MarshalPKIXPublicKey(pub)
				if marshalErr == nil {
					return &licDevice{Private: priv, Public: pub, DER: der, ID: machineID}, nil
				}
			}
		}
		// V28 recovery: old/broken DPAPI blob must not brick this Windows device forever.
		_ = os.Remove(path + ".tmp")
		_ = os.Remove(path)
	} else if !os.IsNotExist(statErr) {
		return nil, fmt.Errorf("device identity file unavailable: %w", statErr)
	}

	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	der, err := x509.MarshalPKIXPublicKey(pub)
	if err != nil {
		return nil, err
	}
	if err = licWriteProtected(path, licDeviceDisk{PrivateKey: base64.StdEncoding.EncodeToString(priv)}); err != nil {
		return nil, err
	}
	return &licDevice{Private: priv, Public: pub, DER: der, ID: machineID}, nil
}

func licLoadSession() *licSession {
	// Login authorization is intentionally process-only.
	// Device binding and all non-auth application data remain persistent.
	return licSessionMem
}

func licSaveSession(s *licSession) error {
	s.SavedAt = time.Now()
	licSessionMem = s
	// Remove any session token left by older builds so reopening can never bypass login.
	_ = os.Remove(licSessionPath())
	return nil
}

func licClearSession() {
	licSessionMem = nil
	licAuthorized = false
	licLastCheck = time.Time{}
	_ = os.Remove(licSessionPath())
}

func licPost(path string, body any, bearerToken string) (int, licRemoteEnvelope, error) {
	var env licRemoteEnvelope
	raw, err := json.Marshal(body)
	if err != nil {
		return 0, env, err
	}
	req, err := http.NewRequest(http.MethodPost, licBaseURL()+"/api/"+strings.TrimLeft(path, "/"), bytes.NewReader(raw))
	if err != nil {
		return 0, env, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "MH-Analysis/"+licAppVersion)
	if bearerToken != "" {
		req.Header.Set("Authorization", "Bearer "+bearerToken)
	}
	resp, err := licHTTP.Do(req)
	if err != nil {
		return 0, env, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	_ = json.Unmarshal(b, &env)
	if env.Code == "" {
		env.Code = env.Error
	}
	return resp.StatusCode, env, nil
}

func licMachineInfo() map[string]string {
	host, _ := os.Hostname()
	return map[string]string{"machine_name": host, "os": runtime.GOOS, "arch": runtime.GOARCH, "app_version": licAppVersion}
}

func licSetRemoteError(status int, env licRemoteEnvelope, err error) {
	licAuthorized = false
	licLastCheck = time.Now()
	if err != nil {
		licLastCode = "internet_required"
		licLastMessage = "Internet connection is required to verify your MH Analysis license."
		return
	}
	licLastCode = strings.ToLower(strings.TrimSpace(env.Code))
	licLastMessage = env.Message
	if licLastCode == "" {
		switch status {
		case 401:
			licLastCode = "authorization_required"
		case 403:
			licLastCode = "authorization_denied"
		default:
			licLastCode = "license_server_error"
		}
	}
	if licLastMessage == "" {
		switch licLastCode {
		case "license_expired":
			licLastMessage = "Your access has expired. Contact administrator for renewal."
		case "unauthorized_device", "device_not_authorized":
			licLastMessage = "This account is already activated on another device. Contact administrator."
		case "account_disabled":
			licLastMessage = "This account is disabled. Contact administrator."
		case "license_not_started":
			licLastMessage = "Your license is not active yet. Contact administrator."
		case "database_unavailable":
			licLastMessage = "License database is temporarily unavailable."
		case "server_not_configured":
			licLastMessage = "License server is not configured."
		default:
			licLastMessage = "License authorization failed."
		}
	}
}

func licEnsureAuthorized(force bool) bool {
	licMu.Lock()
	defer licMu.Unlock()
	if licAuthorized && !force && time.Since(licLastCheck) < licRemoteCheckMinSpacing {
		return true
	}
	s := licLoadSession()
	if s == nil {
		licAuthorized = false
		licLastCode = "login_required"
		licLastMessage = "Enter your username and password to activate MH Analysis."
		return false
	}
	d, err := licEnsureDevice()
	if err != nil {
		licAuthorized = false
		licLastCode = "device_key_unavailable"
		licLastMessage = "Authorized device key is unavailable. Contact administrator for device reset."
		return false
	}
	if s.User.DeviceID != "" && s.User.DeviceID != d.ID {
		licAuthorized = false
		licLastCode = "device_not_authorized"
		licLastMessage = "This installation does not match the authorized device. Contact administrator."
		return false
	}
	status, vr, callErr := licPost("auth/verify", map[string]any{}, s.AccessToken)
	if callErr == nil && status >= 200 && status < 300 && vr.OK {
		s.User = vr.User
		_ = licSaveSession(s)
		licAuthorized = true
		licLastCheck = time.Now()
		licLastCode = ""
		licLastMessage = ""
		return true
	}
	licSetRemoteError(status, vr, callErr)
	if status == http.StatusUnauthorized {
		licClearSession()
		licLastCode = "session_invalid"
		licLastMessage = "Your secure session has ended. Please log in again."
	}
	return false
}

func licHandleLogin(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if json.NewDecoder(io.LimitReader(r.Body, 64<<10)).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Username = strings.ToLower(strings.TrimSpace(q.Username))
	if q.Username == "" || q.Password == "" {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "invalid_request"})
		return
	}
	d, err := licEnsureDevice()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_key_failed", "message": "Could not create secure device identity: " + err.Error()})
		return
	}
	status, ch, callErr := licPost("auth/challenge", map[string]any{"username": q.Username, "device_id": d.ID}, "")
	if callErr != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "internet_required", "message": "Internet connection is required to log in."})
		return
	}
	if status < 200 || status >= 300 || !ch.OK || ch.ChallengeID == "" || ch.Challenge == "" {
		if status < 400 {
			status = http.StatusUnauthorized
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": ch.Code, "message": ch.Message})
		return
	}
	sig := ed25519.Sign(d.Private, []byte(ch.Challenge))
	status, rr, callErr := licPost("auth/login", map[string]any{
		"username":     q.Username,
		"password":     q.Password,
		"challenge_id": ch.ChallengeID,
		"signature":    base64.StdEncoding.EncodeToString(sig),
		"public_key":   base64.StdEncoding.EncodeToString(d.DER),
		"device_id":    d.ID,
		"device_info":  licMachineInfo(),
	}, "")
	if callErr != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "internet_required", "message": "Internet connection is required to log in."})
		return
	}
	if status < 200 || status >= 300 || !rr.OK {
		if status < 400 {
			status = http.StatusUnauthorized
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": strings.ToLower(rr.Code), "message": rr.Message})
		return
	}
	if rr.User.DeviceID != "" && rr.User.DeviceID != d.ID {
		w.WriteHeader(http.StatusForbidden)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_not_authorized", "message": "This account is already activated on another device. Contact administrator."})
		return
	}
	s := &licSession{Username: rr.User.Username, AccessToken: rr.AccessToken, User: rr.User}
	licMu.Lock()
	err = licSaveSession(s)
	if err == nil {
		licAuthorized = true
		licLastCheck = time.Now()
		licLastCode = ""
		licLastMessage = ""
	}
	licMu.Unlock()
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "local_secure_storage_failed", "message": "Login succeeded but the secure Windows session could not be saved."})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "authorized": true, "username": rr.User.Username, "valid_from": rr.User.ValidFrom, "valid_until": rr.User.ValidUntil, "device_id": d.ID})
}

func licHandleStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	if r.Method != http.MethodGet && r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	ok := licEnsureAuthorized(true)
	licMu.Lock()
	defer licMu.Unlock()
	if ok && licSessionMem != nil {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "authorized": true, "username": licSessionMem.User.Username, "valid_from": licSessionMem.User.ValidFrom, "valid_until": licSessionMem.User.ValidUntil, "device_id": licSessionMem.User.DeviceID})
		return
	}
	w.WriteHeader(http.StatusUnauthorized)
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "authorized": false, "code": licLastCode, "message": licLastMessage})
}

func licHandleLogout(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	licMu.Lock()
	licClearSession()
	licMu.Unlock()
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
}

func licAccessMessage() string {
	licMu.Lock()
	defer licMu.Unlock()
	if licLastMessage != "" {
		return licLastMessage
	}
	return "Login to MH Analysis first."
}

func registerLicenseRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/license/login", licHandleLogin)
	mux.HandleFunc("/api/license/status", licHandleStatus)
	mux.HandleFunc("/api/license/logout", licHandleLogout)
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
