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
)

const licDefaultBaseURL = "https://mh-analysis.vercel.app"
const licAppVersion = "80.1"

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
	OK          bool   `json:"ok"`
	Error       string `json:"error"`
	Code        string `json:"code"`
	Message     string `json:"message"`
	ChallengeID string `json:"challenge_id"`
	Challenge   string `json:"challenge"`
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
	Username    string `json:"username"`
	ValidFrom   string `json:"valid_from"`
	ValidUntil  string `json:"valid_until"`
	DeviceBound bool   `json:"device_bound"`
	MaxDevices  int    `json:"max_devices"`
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

func licEnsureDevice() (*licDevice, error) {
	var disk licDeviceDisk
	if err := licReadProtected(licDevicePath(), &disk); err == nil && disk.PrivateKey != "" {
		raw, err := base64.StdEncoding.DecodeString(disk.PrivateKey)
		if err == nil && len(raw) == ed25519.PrivateKeySize {
			priv := ed25519.PrivateKey(raw)
			pub := priv.Public().(ed25519.PublicKey)
			der, err := x509.MarshalPKIXPublicKey(pub)
			if err != nil {
				return nil, err
			}
			sum := sha256.Sum256(der)
			return &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}, nil
		}
	}
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	der, err := x509.MarshalPKIXPublicKey(pub)
	if err != nil {
		return nil, err
	}
	if err = licWriteProtected(licDevicePath(), licDeviceDisk{PrivateKey: base64.StdEncoding.EncodeToString(priv)}); err != nil {
		return nil, err
	}
	sum := sha256.Sum256(der)
	return &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}, nil
}

func licPublicKeyPEM(der []byte) string {
	enc := base64.StdEncoding.EncodeToString(der)
	var b strings.Builder
	b.WriteString("-----BEGIN PUBLIC KEY-----\n")
	for len(enc) > 64 {
		b.WriteString(enc[:64])
		b.WriteByte('\n')
		enc = enc[64:]
	}
	if enc != "" {
		b.WriteString(enc)
		b.WriteByte('\n')
	}
	b.WriteString("-----END PUBLIC KEY-----\n")
	return b.String()
}

func licLoadSession() *licSession {
	if licSessionMem != nil {
		return licSessionMem
	}
	var s licSession
	if err := licReadProtected(licSessionPath(), &s); err != nil || s.Username == "" || s.AccessToken == "" {
		return nil
	}
	licSessionMem = &s
	return licSessionMem
}

func licSaveSession(s *licSession) error {
	s.SavedAt = time.Now()
	if err := licWriteProtected(licSessionPath(), s); err != nil {
		return err
	}
	licSessionMem = s
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
	req.Header.Set("Accept", "application/json")
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
	return resp.StatusCode, env, nil
}

func licMachineInfo() map[string]string {
	host, _ := os.Hostname()
	return map[string]string{
		"device_name": host,
		"os_version": runtime.GOOS,
		"arch":        runtime.GOARCH,
		"app_version": licAppVersion,
	}
}

func licRemoteCode(env licRemoteEnvelope, status int) string {
	code := strings.TrimSpace(env.Error)
	if code == "" {
		code = strings.TrimSpace(env.Code)
	}
	code = strings.ToLower(code)
	if code != "" {
		return code
	}
	switch status {
	case http.StatusUnauthorized:
		return "authorization_required"
	case http.StatusForbidden:
		return "authorization_denied"
	case http.StatusTooManyRequests:
		return "too_many_attempts"
	default:
		return "license_server_error"
	}
}

func licSetRemoteError(status int, env licRemoteEnvelope, err error) {
	licAuthorized = false
	licLastCheck = time.Now()
	if err != nil {
		licLastCode = "internet_required"
		licLastMessage = "Internet connection is required to verify your MH Analysis license."
		return
	}
	licLastCode = licRemoteCode(env, status)
	licLastMessage = strings.TrimSpace(env.Message)
	if licLastMessage == "" {
		switch licLastCode {
		case "license_expired":
			licLastMessage = "Your access has expired. Contact administrator for renewal."
		case "license_not_started":
			licLastMessage = "Your license is not active yet. Contact administrator."
		case "device_not_authorized":
			licLastMessage = "This account is already activated on another device. Contact administrator."
		case "account_disabled":
			licLastMessage = "This account is disabled. Contact administrator."
		case "invalid_credentials":
			licLastMessage = "Invalid username or password."
		case "session_invalid", "session_revoked":
			licLastMessage = "Your secure session has ended. Please log in again."
		case "too_many_attempts":
			licLastMessage = "Too many attempts. Please try again later."
		default:
			licLastMessage = "License authorization failed. Contact administrator."
		}
	}
}

func licUserFromEnvelope(env licRemoteEnvelope, fallbackUser, deviceID string) licUserInfo {
	u := strings.TrimSpace(env.Username)
	if u == "" {
		u = fallbackUser
	}
	return licUserInfo{Username: u, ValidFrom: env.ValidFrom, ValidUntil: env.ValidUntil, DeviceID: deviceID}
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
	if callErr != nil || status < 200 || status >= 300 || !vr.OK {
		licSetRemoteError(status, vr, callErr)
		return false
	}
	if vr.AccessToken != "" {
		s.AccessToken = vr.AccessToken
	}
	s.User = licUserFromEnvelope(vr, s.Username, d.ID)
	s.Username = s.User.Username
	if err := licSaveSession(s); err != nil {
		licAuthorized = false
		licLastCode = "local_secure_storage_failed"
		licLastMessage = "Could not securely save the license session."
		return false
	}
	licAuthorized = true
	licLastCheck = time.Now()
	licLastCode = ""
	licLastMessage = ""
	return true
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
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_key_failed", "message": "Could not create secure device identity."})
		return
	}

	status, ch, callErr := licPost("auth/challenge", map[string]any{
		"username":  q.Username,
		"device_id": d.ID,
	}, "")
	if callErr != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "internet_required", "message": "Internet connection is required to log in."})
		return
	}
	if status < 200 || status >= 300 || !ch.OK || ch.ChallengeID == "" || ch.Challenge == "" {
		code := licRemoteCode(ch, status)
		msg := ch.Message
		if msg == "" {
			msg = "Could not start secure device verification."
		}
		if status < 400 {
			status = http.StatusUnauthorized
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": code, "message": msg})
		return
	}

	sig := ed25519.Sign(d.Private, []byte(ch.Challenge))
	status, rr, callErr := licPost("auth/login", map[string]any{
		"username":     q.Username,
		"password":     q.Password,
		"challenge_id": ch.ChallengeID,
		"signature":    base64.StdEncoding.EncodeToString(sig),
		"public_key":   licPublicKeyPEM(d.DER),
		"device_id":    d.ID,
		"device_info":  licMachineInfo(),
	}, "")
	if callErr != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "internet_required", "message": "Internet connection is required to log in."})
		return
	}
	if status < 200 || status >= 300 || !rr.OK || rr.AccessToken == "" {
		code := licRemoteCode(rr, status)
		msg := rr.Message
		if msg == "" {
			switch code {
			case "invalid_credentials":
				msg = "Invalid username or password."
			case "license_expired":
				msg = "Your access has expired. Contact administrator for renewal."
			case "device_not_authorized":
				msg = "This account is already activated on another device. Contact administrator."
			default:
				msg = "License authorization failed."
			}
		}
		if status < 400 {
			status = http.StatusUnauthorized
		}
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": code, "message": msg})
		return
	}

	user := licUserFromEnvelope(rr, q.Username, d.ID)
	s := &licSession{Username: user.Username, AccessToken: rr.AccessToken, User: user}
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
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "secure_storage_failed", "message": "Login succeeded but the secure Windows session could not be saved."})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":          true,
		"authorized":  true,
		"username":    user.Username,
		"valid_from":  user.ValidFrom,
		"valid_until": user.ValidUntil,
		"device_id":   d.ID,
	})
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
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":          true,
			"authorized":  true,
			"username":    licSessionMem.User.Username,
			"valid_from":  licSessionMem.User.ValidFrom,
			"valid_until": licSessionMem.User.ValidUntil,
			"device_id":   licSessionMem.User.DeviceID,
		})
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
	if strings.TrimSpace(licLastMessage) != "" {
		return licLastMessage
	}
	return "Login is required to use MH Analysis."
}

func registerLicenseRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/license/login", licHandleLogin)
	mux.HandleFunc("/api/license/status", licHandleStatus)
	mux.HandleFunc("/api/license/logout", licHandleLogout)
}

func licenseGate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if strings.HasPrefix(p, "/api/license/") || p == "/api/shutdown" {
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
