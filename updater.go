package main

// MH_MANDATORY_UPDATE_V001

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const mhPublicVersionV001 = "V.55.11"
const mhUpdateManifestURLV001 = "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/mh-analysis-update-channel/update.json"

type mhUpdateManifestV001 struct {
	Version     string `json:"version"`
	Mandatory   bool   `json:"mandatory"`
	DownloadURL string `json:"download_url"`
	SHA256      string `json:"sha256"`
	Notes       string `json:"notes,omitempty"`
}

type mhUpdateStateV001 struct {
	Phase      string `json:"phase"`
	Percent    int    `json:"percent"`
	Downloaded int64  `json:"downloaded"`
	Total      int64  `json:"total"`
	Error      string `json:"error,omitempty"`
	Latest     string `json:"latest,omitempty"`
}

var mhUpdateMuV001 sync.Mutex
var mhUpdateStateCurrentV001 = mhUpdateStateV001{Phase: "idle"}

func mhUpdateManifestURLResolvedV001() string {
	if v := strings.TrimSpace(os.Getenv("MH_UPDATE_MANIFEST_URL")); v != "" {
		return v
	}
	return mhUpdateManifestURLV001
}

func mhVersionNumberV001(v string) int {
	v = strings.TrimSpace(strings.ToUpper(v))
	v = strings.TrimPrefix(v, "VERSION")
	v = strings.TrimPrefix(v, "V")
	v = strings.TrimPrefix(v, ".")
	parts := strings.Split(v, ".")
	total := 0
	for _, p := range parts {
		n, _ := strconv.Atoi(strings.TrimSpace(p))
		total = total*1000 + n
	}
	return total
}

func mhNewerVersionV001(latest, current string) bool {
	return mhVersionNumberV001(latest) > mhVersionNumberV001(current)
}

func mhCurrentExecutableSHA256V001() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	f, err := os.Open(exe)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// V54.1 loop guard: if the running executable is byte-for-byte the file
// published by the current manifest, it is already current even if stale
// version metadata survived an older installer/update path.
func mhManifestMatchesCurrentExecutableV001(m mhUpdateManifestV001) bool {
	want := strings.ToLower(strings.TrimSpace(m.SHA256))
	if len(want) != 64 {
		return false
	}
	got, err := mhCurrentExecutableSHA256V001()
	if err != nil {
		return false
	}
	return strings.EqualFold(got, want)
}

func mhFetchManifestV001() (mhUpdateManifestV001, error) {
	var m mhUpdateManifestV001
	u := mhUpdateManifestURLResolvedV001()
	sep := "?"
	if strings.Contains(u, "?") {
		sep = "&"
	}
	req, err := http.NewRequest(http.MethodGet, u+sep+"mh="+strconv.FormatInt(time.Now().UnixNano(), 10), nil)
	if err != nil {
		return m, err
	}
	req.Header.Set("Cache-Control", "no-cache")
	req.Header.Set("Pragma", "no-cache")
	req.Header.Set("User-Agent", "MH-Analysis-"+mhPublicVersionV001)
	resp, err := (&http.Client{Timeout: 15 * time.Second}).Do(req)
	if err != nil {
		return m, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return m, fmt.Errorf("update service returned %d", resp.StatusCode)
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
	if err != nil {
		return m, err
	}
	raw = bytes.TrimPrefix(raw, []byte{0xEF, 0xBB, 0xBF})
	raw = bytes.TrimSpace(raw)
	if err := json.Unmarshal(raw, &m); err != nil {
		return m, fmt.Errorf("invalid update manifest json: %w", err)
	}
	m.Version = strings.TrimSpace(m.Version)
	m.DownloadURL = strings.TrimSpace(m.DownloadURL)
	m.SHA256 = strings.ToLower(strings.TrimSpace(m.SHA256))
	if m.Version == "" || m.DownloadURL == "" || len(m.SHA256) != 64 {
		return m, errors.New("invalid update manifest")
	}
	if !strings.HasPrefix(strings.ToLower(m.DownloadURL), "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/") {
		return m, errors.New("untrusted update source")
	}
	return m, nil
}

func mhWriteJSONV001(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	_ = json.NewEncoder(w).Encode(v)
}

func mhUpdateStatusHandlerV001(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	m, err := mhFetchManifestV001()
	if err != nil {
		mhWriteJSONV001(w, map[string]any{"ok": false, "verified": false, "required": false, "current": mhPublicVersionV001, "error": err.Error()})
		return
	}
	binaryCurrent := mhManifestMatchesCurrentExecutableV001(m)
	required := m.Mandatory && !binaryCurrent && mhNewerVersionV001(m.Version, mhPublicVersionV001)
	mhWriteJSONV001(w, map[string]any{
		"ok":             true,
		"verified":       true,
		"required":       required,
		"mandatory":      m.Mandatory,
		"current":        mhPublicVersionV001,
		"latest":         m.Version,
		"binary_current": binaryCurrent,
		"notes":          m.Notes,
	})
}

func mhUpdateProgressHandlerV001(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mhUpdateMuV001.Lock()
	st := mhUpdateStateCurrentV001
	mhUpdateMuV001.Unlock()
	mhWriteJSONV001(w, st)
}

func mhSetUpdateStateV001(st mhUpdateStateV001) {
	mhUpdateMuV001.Lock()
	mhUpdateStateCurrentV001 = st
	mhUpdateMuV001.Unlock()
}

func mhUpdateStartHandlerV001(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	m, err := mhFetchManifestV001()
	if err != nil {
		http.Error(w, "Update verification failed. Check internet and retry.", http.StatusBadGateway)
		return
	}
	if mhManifestMatchesCurrentExecutableV001(m) || !m.Mandatory || !mhNewerVersionV001(m.Version, mhPublicVersionV001) {
		mhWriteJSONV001(w, map[string]any{"ok": true, "already_current": true, "version": mhPublicVersionV001})
		return
	}
	mhUpdateMuV001.Lock()
	busy := mhUpdateStateCurrentV001.Phase == "downloading" || mhUpdateStateCurrentV001.Phase == "verifying" || mhUpdateStateCurrentV001.Phase == "installing"
	if !busy {
		mhUpdateStateCurrentV001 = mhUpdateStateV001{Phase: "downloading", Percent: 0, Latest: m.Version}
	}
	mhUpdateMuV001.Unlock()
	if !busy {
		go mhDownloadAndInstallV001(m)
	}
	mhWriteJSONV001(w, map[string]any{"ok": true, "started": !busy, "latest": m.Version})
}

func mhDownloadAndInstallV001(m mhUpdateManifestV001) {
	req, err := http.NewRequest(http.MethodGet, m.DownloadURL, nil)
	if err != nil {
		mhUpdateFailV001(err)
		return
	}
	req.Header.Set("Cache-Control", "no-cache")
	req.Header.Set("User-Agent", "MH-Analysis-Updater-"+mhPublicVersionV001)
	resp, err := (&http.Client{Timeout: 10 * time.Minute}).Do(req)
	if err != nil {
		mhUpdateFailV001(err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		mhUpdateFailV001(fmt.Errorf("download returned %d", resp.StatusCode))
		return
	}
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	dir := filepath.Join(base, "MHAnalysis", "updates")
	if err := os.MkdirAll(dir, 0700); err != nil {
		mhUpdateFailV001(err)
		return
	}
	tmp := filepath.Join(dir, "MH Analysis "+strings.ReplaceAll(m.Version, ".", "-")+".exe.download")
	f, err := os.Create(tmp)
	if err != nil {
		mhUpdateFailV001(err)
		return
	}
	h := sha256.New()
	total := resp.ContentLength
	var done int64
	buf := make([]byte, 256*1024)
	for {
		n, er := resp.Body.Read(buf)
		if n > 0 {
			if _, err = f.Write(buf[:n]); err != nil {
				f.Close()
				mhUpdateFailV001(err)
				return
			}
			_, _ = h.Write(buf[:n])
			done += int64(n)
			pct := 0
			if total > 0 {
				pct = int(done * 100 / total)
				if pct > 99 {
					pct = 99
				}
			}
			mhSetUpdateStateV001(mhUpdateStateV001{Phase: "downloading", Percent: pct, Downloaded: done, Total: total, Latest: m.Version})
		}
		if er == io.EOF {
			break
		}
		if er != nil {
			f.Close()
			mhUpdateFailV001(er)
			return
		}
	}
	if err := f.Sync(); err != nil {
		f.Close()
		mhUpdateFailV001(err)
		return
	}
	if err := f.Close(); err != nil {
		mhUpdateFailV001(err)
		return
	}
	mhSetUpdateStateV001(mhUpdateStateV001{Phase: "verifying", Percent: 99, Downloaded: done, Total: total, Latest: m.Version})
	got := hex.EncodeToString(h.Sum(nil))
	if !strings.EqualFold(got, m.SHA256) {
		_ = os.Remove(tmp)
		mhUpdateFailV001(errors.New("download integrity check failed"))
		return
	}
	exe, err := os.Executable()
	if err != nil {
		mhUpdateFailV001(err)
		return
	}
	exe, _ = filepath.Abs(exe)
	if err := mhSpawnReplaceHelperV001(tmp, exe); err != nil {
		mhUpdateFailV001(err)
		return
	}
	mhSetUpdateStateV001(mhUpdateStateV001{Phase: "installing", Percent: 100, Downloaded: done, Total: total, Latest: m.Version})
	go func() {
		time.Sleep(900 * time.Millisecond)
		postMessage(hostHWND, wmClose, 0, 0)
	}()
}

func mhUpdateFailV001(err error) {
	msg := "Update failed. Please retry."
	if err != nil && strings.TrimSpace(err.Error()) != "" {
		msg = "Update failed: " + err.Error()
	}
	mhSetUpdateStateV001(mhUpdateStateV001{Phase: "error", Error: msg})
}

func mhPSQuoteV001(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "''") + "'"
}

func mhSpawnReplaceHelperV001(src, dst string) error {
	pid := os.Getpid()
	work := filepath.Dir(dst)
	ps := "$ErrorActionPreference='SilentlyContinue';" +
		"$p=" + strconv.Itoa(pid) + ";" +
		"$src=" + mhPSQuoteV001(src) + ";" +
		"$dst=" + mhPSQuoteV001(dst) + ";" +
		"$wd=" + mhPSQuoteV001(work) + ";" +
		"for($i=0;$i -lt 120;$i++){if(-not(Get-Process -Id $p -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 250};" +
		"$ok=$false;for($i=0;$i -lt 80;$i++){try{Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop;$ok=$true;break}catch{Start-Sleep -Milliseconds 400}};" +
		"if($ok){Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue;Start-Process -FilePath $dst -WorkingDirectory $wd}"
	cmd := exec.Command("powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd.Start()
}
