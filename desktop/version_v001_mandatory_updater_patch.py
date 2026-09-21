from pathlib import Path

MARK = "MH_MANDATORY_UPDATE_V001"
VERSION = "V.01"
MANIFEST_URL = "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/final-current-v796/update.json"

# -----------------------------------------------------------------------------
# Local API routes.
# -----------------------------------------------------------------------------
p = Path("main.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    route_anchor = '\tmux.HandleFunc("/api/shutdown", func(w http.ResponseWriter, r *http.Request) {\n'
    if route_anchor not in s:
        raise SystemExit("shutdown route anchor missing")
    routes = (
        '\tmux.HandleFunc("/api/update/status", mhUpdateStatusHandlerV001) // ' + MARK + '\n'
        '\tmux.HandleFunc("/api/update/start", mhUpdateStartHandlerV001)\n'
        '\tmux.HandleFunc("/api/update/progress", mhUpdateProgressHandlerV001)\n'
    )
    s = s.replace(route_anchor, routes + route_anchor, 1)
    s = s.replace('package main\n', 'package main\n\n// ' + MARK + '\n', 1)
    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Native shell mandatory-update lock. When a newer mandatory release is seen,
# the existing Analysis browser is promoted to a full-client black update screen
# and the native tab bar is hidden/disabled so the update cannot be bypassed by
# switching to WhatsApp / Records / MT5.
# -----------------------------------------------------------------------------
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    proc_anchor = '\tchSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")\n'
    if proc_anchor not in s:
        raise SystemExit("user32 proc anchor missing")
    s = s.replace(proc_anchor, proc_anchor + '\tchEnableWindowV001      = chUser32.NewProc("EnableWindow") // '+MARK+'\n', 1)

    vars_anchor = '\tchDesiredView = 1\n'
    if vars_anchor not in s:
        raise SystemExit("view variable anchor missing")
    s = s.replace(vars_anchor, vars_anchor + '\tchMandatoryUpdateV001 bool // '+MARK+'\n', 1)

    resize_anchor = '\tw := int32(r.R - r.L)\n'
    if resize_anchor not in s:
        raise SystemExit("resize width anchor missing")
    resize_block = r'''
	w := int32(r.R - r.L)
	chViewMu.Lock()
	updateLockV001 := chMandatoryUpdateV001
	chViewMu.Unlock()
	if updateLockV001 {
		fullH := int32(r.B - r.T)
		if fullH < 1 { fullH = 1 }
		if chAnalysisWnd != 0 {
			chSetWindowPos.Call(chAnalysisWnd, 0, 0, 0, uintptr(w), uintptr(fullH), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
			chShowWindowAsync.Call(chAnalysisWnd, chSWShow)
		}
		if chWhatsappWnd != 0 { chShowWindowAsync.Call(chWhatsappWnd, chSWHide) }
		if chRecordsWnd != 0 { chShowWindowAsync.Call(chRecordsWnd, chSWHide) }
		if chMT5Wnd != 0 { chShowWindowAsync.Call(chMT5Wnd, chSWHide) }
		for _, b := range []uintptr{btnAnalysis, btnWhatsapp, btnRecords, btnMT5, chSignalLinkBtn} {
			if b != 0 { chShowWindow.Call(b, chSWHide) }
		}
		return
	}
'''
    s = s.replace(resize_anchor, resize_block, 1)

    switch_anchor = 'func chSwitchView(which int) {\n'
    if switch_anchor not in s:
        raise SystemExit("switch view anchor missing")
    switch_guard = r'''func chSwitchView(which int) {
	chViewMu.Lock()
	lockedV001 := chMandatoryUpdateV001
	chViewMu.Unlock()
	if lockedV001 {
		chApplyDesiredBrowserView()
		chResizeChildren()
		return
	}
'''
    s = s.replace(switch_anchor, switch_guard, 1)

    helper_anchor = '\nfunc chPopWhatsAppTask() (waTask, bool) {'
    if helper_anchor not in s:
        raise SystemExit("native helper insertion anchor missing")
    helper = r'''

// MH_MANDATORY_UPDATE_V001: lock the entire EXE to the update surface.
func chSetMandatoryUpdateLockV001(locked bool) {
	chViewMu.Lock()
	chMandatoryUpdateV001 = locked
	if locked { chDesiredView = 1 }
	chViewMu.Unlock()
	if locked {
		for _, b := range []uintptr{btnAnalysis, btnWhatsapp, btnRecords, btnMT5, chSignalLinkBtn} {
			if b != 0 {
				chEnableWindowV001.Call(b, 0)
				chShowWindow.Call(b, chSWHide)
			}
		}
	} else {
		for _, b := range []uintptr{btnAnalysis, btnWhatsapp, btnRecords, btnMT5} {
			if b != 0 {
				chEnableWindowV001.Call(b, 1)
				chShowWindow.Call(b, chSWShow)
			}
		}
	}
	chApplyDesiredBrowserView()
	chResizeChildren()
}
'''
    s = s.replace(helper_anchor, helper + helper_anchor, 1)
    s = s.replace('package main\n', 'package main\n\n// ' + MARK + '\n', 1)
    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Updater backend. Only the EXE is replaced. LOCALAPPDATA settings, license
# identity/session, Records JSON, WhatsApp browser profile and MT5 files are not
# touched, so an update resumes with the user's existing state.
# -----------------------------------------------------------------------------
updater_go = r'''package main

// MH_MANDATORY_UPDATE_V001

import (
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

const mhPublicVersionV001 = "V.01"
const mhUpdateManifestURLV001 = "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/final-current-v796/update.json"

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
    if v := strings.TrimSpace(os.Getenv("MH_UPDATE_MANIFEST_URL")); v != "" { return v }
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

func mhFetchManifestV001() (mhUpdateManifestV001, error) {
    var m mhUpdateManifestV001
    u := mhUpdateManifestURLResolvedV001()
    sep := "?"
    if strings.Contains(u, "?") { sep = "&" }
    req, err := http.NewRequest(http.MethodGet, u+sep+"mh="+strconv.FormatInt(time.Now().UnixNano(),10), nil)
    if err != nil { return m, err }
    req.Header.Set("Cache-Control", "no-cache")
    req.Header.Set("Pragma", "no-cache")
    req.Header.Set("User-Agent", "MH-Analysis-"+mhPublicVersionV001)
    cli := &http.Client{Timeout: 15*time.Second}
    resp, err := cli.Do(req)
    if err != nil { return m, err }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK { return m, fmt.Errorf("update service returned %d", resp.StatusCode) }
    if err := json.NewDecoder(io.LimitReader(resp.Body, 64<<10)).Decode(&m); err != nil { return m, err }
    m.Version = strings.TrimSpace(m.Version)
    m.DownloadURL = strings.TrimSpace(m.DownloadURL)
    m.SHA256 = strings.ToLower(strings.TrimSpace(m.SHA256))
    if m.Version == "" || m.DownloadURL == "" || len(m.SHA256) != 64 { return m, errors.New("invalid update manifest") }
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
    if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
    m, err := mhFetchManifestV001()
    if err != nil {
        mhWriteJSONV001(w, map[string]any{
            "ok": false, "verified": false, "required": true,
            "current": mhPublicVersionV001,
            "error": "Unable to verify the required MH Analysis version. Check internet and retry.",
        })
        return
    }
    required := m.Mandatory && mhNewerVersionV001(m.Version, mhPublicVersionV001)
    if required { go chSetMandatoryUpdateLockV001(true) }
    mhWriteJSONV001(w, map[string]any{
        "ok": true, "verified": true, "required": required, "mandatory": m.Mandatory,
        "current": mhPublicVersionV001, "latest": m.Version, "notes": m.Notes,
    })
}

func mhUpdateProgressHandlerV001(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
    mhUpdateMuV001.Lock(); st := mhUpdateStateCurrentV001; mhUpdateMuV001.Unlock()
    mhWriteJSONV001(w, st)
}

func mhSetUpdateStateV001(st mhUpdateStateV001) {
    mhUpdateMuV001.Lock(); mhUpdateStateCurrentV001 = st; mhUpdateMuV001.Unlock()
}

func mhUpdateStartHandlerV001(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost { http.Error(w,"method",http.StatusMethodNotAllowed); return }
    m, err := mhFetchManifestV001()
    if err != nil { http.Error(w,"Update verification failed. Check internet and retry.", http.StatusBadGateway); return }
    if !m.Mandatory || !mhNewerVersionV001(m.Version, mhPublicVersionV001) {
        mhWriteJSONV001(w, map[string]any{"ok":true,"already_current":true,"version":mhPublicVersionV001})
        return
    }
    mhUpdateMuV001.Lock()
    busy := mhUpdateStateCurrentV001.Phase == "downloading" || mhUpdateStateCurrentV001.Phase == "verifying" || mhUpdateStateCurrentV001.Phase == "installing"
    if !busy { mhUpdateStateCurrentV001 = mhUpdateStateV001{Phase:"downloading",Percent:0,Latest:m.Version} }
    mhUpdateMuV001.Unlock()
    go chSetMandatoryUpdateLockV001(true)
    if !busy { go mhDownloadAndInstallV001(m) }
    mhWriteJSONV001(w, map[string]any{"ok":true,"started":!busy,"latest":m.Version})
}

func mhDownloadAndInstallV001(m mhUpdateManifestV001) {
    req, err := http.NewRequest(http.MethodGet, m.DownloadURL, nil)
    if err != nil { mhUpdateFailV001(err); return }
    req.Header.Set("Cache-Control","no-cache")
    req.Header.Set("User-Agent","MH-Analysis-Updater-"+mhPublicVersionV001)
    cli := &http.Client{Timeout: 10*time.Minute}
    resp, err := cli.Do(req)
    if err != nil { mhUpdateFailV001(err); return }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK { mhUpdateFailV001(fmt.Errorf("download returned %d",resp.StatusCode)); return }

    base := os.Getenv("LOCALAPPDATA")
    if base == "" { base = os.TempDir() }
    dir := filepath.Join(base,"MHAnalysis","updates")
    if err := os.MkdirAll(dir,0700); err != nil { mhUpdateFailV001(err); return }
    tmp := filepath.Join(dir,"MH Analysis "+strings.ReplaceAll(m.Version,".","-")+".exe.download")
    f, err := os.Create(tmp)
    if err != nil { mhUpdateFailV001(err); return }
    h := sha256.New()
    total := resp.ContentLength
    var done int64
    buf := make([]byte,256*1024)
    for {
        n, er := resp.Body.Read(buf)
        if n > 0 {
            if _, err = f.Write(buf[:n]); err != nil { f.Close(); mhUpdateFailV001(err); return }
            _, _ = h.Write(buf[:n])
            done += int64(n)
            pct := 0
            if total > 0 { pct = int(done*100/total); if pct > 99 { pct = 99 } }
            mhSetUpdateStateV001(mhUpdateStateV001{Phase:"downloading",Percent:pct,Downloaded:done,Total:total,Latest:m.Version})
        }
        if er == io.EOF { break }
        if er != nil { f.Close(); mhUpdateFailV001(er); return }
    }
    if err := f.Sync(); err != nil { f.Close(); mhUpdateFailV001(err); return }
    if err := f.Close(); err != nil { mhUpdateFailV001(err); return }

    mhSetUpdateStateV001(mhUpdateStateV001{Phase:"verifying",Percent:99,Downloaded:done,Total:total,Latest:m.Version})
    got := hex.EncodeToString(h.Sum(nil))
    if !strings.EqualFold(got,m.SHA256) {
        _ = os.Remove(tmp)
        mhUpdateFailV001(errors.New("download integrity check failed"))
        return
    }

    exe, err := os.Executable()
    if err != nil { mhUpdateFailV001(err); return }
    exe, _ = filepath.Abs(exe)
    if err := mhSpawnReplaceHelperV001(tmp, exe); err != nil { mhUpdateFailV001(err); return }
    mhSetUpdateStateV001(mhUpdateStateV001{Phase:"installing",Percent:100,Downloaded:done,Total:total,Latest:m.Version})
    go func(){ time.Sleep(900*time.Millisecond); postMessage(hostHWND, wmClose, 0, 0) }()
}

func mhUpdateFailV001(err error) {
    msg := "Update failed. Please retry."
    if err != nil && strings.TrimSpace(err.Error()) != "" { msg = "Update failed: " + err.Error() }
    mhSetUpdateStateV001(mhUpdateStateV001{Phase:"error",Error:msg})
}

func mhPSQuoteV001(s string) string { return "'" + strings.ReplaceAll(s,"'","''") + "'" }

func mhSpawnReplaceHelperV001(src, dst string) error {
    pid := os.Getpid()
    work := filepath.Dir(dst)
    ps := "$ErrorActionPreference='SilentlyContinue';" +
        "$p="+strconv.Itoa(pid)+";" +
        "$src="+mhPSQuoteV001(src)+";" +
        "$dst="+mhPSQuoteV001(dst)+";" +
        "$wd="+mhPSQuoteV001(work)+";" +
        "for($i=0;$i -lt 120;$i++){if(-not(Get-Process -Id $p -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 250};" +
        "$ok=$false;for($i=0;$i -lt 80;$i++){try{Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop;$ok=$true;break}catch{Start-Sleep -Milliseconds 400}};" +
        "if($ok){Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue;Start-Process -FilePath $dst -WorkingDirectory $wd}"
    cmd := exec.Command("powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-Command",ps)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow:true}
    return cmd.Start()
}
'''
Path("updater.go").write_text(updater_go, encoding="utf-8")

# -----------------------------------------------------------------------------
# Mandatory black update screen. Shown by default until the online version check
# succeeds. If V.02+ is published as mandatory, this screen remains and the app
# cannot switch tabs until replacement/restart finishes.
# -----------------------------------------------------------------------------
p = Path("web/index.html")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = s.replace('<link rel="stylesheet" href="/runtime-fixes.css" />', '<link rel="stylesheet" href="/runtime-fixes.css" />\n<link rel="stylesheet" href="/update-v001.css" />', 1)
    overlay = r'''<div id="mhMandatoryUpdateV001" class="mhUpdateGateV001" role="dialog" aria-modal="true" aria-label="MH Analysis Update">
  <div class="mhUpdateCenterV001">
    <img src="/mh-logo.png" class="mhUpdateLogoV001" alt="MH Analysis" />
    <div class="mhUpdateBrandV001"><span>MH</span> ANALYSIS</div>
    <div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.01</div>
    <div class="mhUpdateTitleV001" id="mhUpdateTitleV001">Checking required version…</div>
    <div class="mhUpdateSubV001" id="mhUpdateSubV001">Please wait.</div>
    <button type="button" id="mhUpdateNowV001" class="mhUpdateButtonV001">Update Now - To Access</button>
    <div class="mhUpdateProgressWrapV001" id="mhUpdateProgressWrapV001">
      <div class="mhUpdateTrackV001"><div class="mhUpdateFillV001" id="mhUpdateFillV001"></div></div>
      <div class="mhUpdatePercentV001" id="mhUpdatePercentV001">0%</div>
    </div>
    <button type="button" id="mhUpdateRetryV001" class="mhUpdateRetryV001">Retry Check</button>
    <div class="mhUpdateStateV001" id="mhUpdateStateV001"></div>
  </div>
</div>
'''
    body_anchor = '<body>\n'
    if body_anchor not in s:
        raise SystemExit("body anchor missing")
    s = s.replace(body_anchor, body_anchor + overlay, 1)
    s = s.replace('<script src="/app.js"></script>', '<script src="/update-v001.js"></script>\n<script src="/app.js"></script>', 1)
    s = s.replace('<div class="version">v79.6 AUTO CYCLE (HAMMAD & SOMI)</div>', '<div class="version">V.01 AUTO CYCLE (HAMMAD & SOMI)</div>', 1)
    p.write_text(s, encoding="utf-8")

css = r'''/* MH_MANDATORY_UPDATE_V001 */
.mhUpdateGateV001{position:fixed;inset:0;z-index:2147483646;background:#000;display:flex;align-items:center;justify-content:center;color:#fff;font-family:"Segoe UI",Arial,sans-serif;overflow:hidden}
.mhUpdateGateV001.mhUpdateHiddenV001{display:none!important}
.mhUpdateCenterV001{width:min(560px,92vw);display:flex;flex-direction:column;align-items:center;text-align:center;padding:34px 26px}
.mhUpdateLogoV001{width:86px;height:86px;object-fit:cover;border-radius:14px;box-shadow:0 0 0 1px #5f4a13,0 0 35px rgba(255,213,0,.12)}
.mhUpdateBrandV001{margin-top:18px;font-size:31px;font-weight:950;letter-spacing:.08em;color:#f4f5f7}.mhUpdateBrandV001 span{color:#ffd400}
.mhUpdateVersionV001{margin-top:6px;color:#9aa4ad;font-size:11px;font-weight:800;letter-spacing:.14em}
.mhUpdateTitleV001{margin-top:30px;font-size:21px;font-weight:850;color:#fff}.mhUpdateSubV001{margin-top:9px;color:#aab3bc;font-size:12px;line-height:1.5;min-height:20px}
.mhUpdateButtonV001{margin-top:25px;min-width:300px;height:50px;border:1px solid #f4ca00;border-radius:8px;background:#ffd400;color:#090909;font-size:13px;font-weight:950;letter-spacing:.04em;cursor:pointer}.mhUpdateButtonV001:hover{filter:brightness(1.06)}.mhUpdateButtonV001:disabled{opacity:.55;cursor:wait}
.mhUpdateProgressWrapV001{display:none;width:min(430px,82vw);margin-top:24px}.mhUpdateProgressWrapV001.show{display:flex;align-items:center;gap:12px}.mhUpdateTrackV001{height:11px;border-radius:99px;background:#1a1a1a;border:1px solid #343434;overflow:hidden;flex:1}.mhUpdateFillV001{height:100%;width:0;background:linear-gradient(90deg,#d8b300,#ffd800);transition:width .18s ease}.mhUpdatePercentV001{width:42px;text-align:right;color:#ffd400;font-size:12px;font-weight:900}
.mhUpdateRetryV001{display:none;margin-top:20px;background:#101010;border:1px solid #535353;color:#fff;border-radius:7px;padding:10px 18px;font-size:11px;font-weight:800;cursor:pointer}.mhUpdateRetryV001.show{display:block}.mhUpdateStateV001{margin-top:12px;color:#9da6ae;font-size:10px;line-height:1.45;min-height:16px;max-width:460px}
'''
Path("web/update-v001.css").write_text(css, encoding="utf-8")

js = r'''// MH_MANDATORY_UPDATE_V001
(() => {
  const gate=document.getElementById('mhMandatoryUpdateV001');
  if(!gate)return;
  const title=document.getElementById('mhUpdateTitleV001');
  const sub=document.getElementById('mhUpdateSubV001');
  const btn=document.getElementById('mhUpdateNowV001');
  const retry=document.getElementById('mhUpdateRetryV001');
  const wrap=document.getElementById('mhUpdateProgressWrapV001');
  const fill=document.getElementById('mhUpdateFillV001');
  const pct=document.getElementById('mhUpdatePercentV001');
  const state=document.getElementById('mhUpdateStateV001');
  let verifiedOnce=false, required=false, progressTimer=0, checking=false;

  function showGate(){gate.classList.remove('mhUpdateHiddenV001')}
  function hideGate(){gate.classList.add('mhUpdateHiddenV001')}
  function percent(v){const n=Math.max(0,Math.min(100,Number(v)||0));fill.style.width=n+'%';pct.textContent=Math.round(n)+'%'}
  function checkError(msg){showGate();title.textContent='Update Check Required';sub.textContent=msg||'Internet is required to verify the latest MH Analysis version.';btn.style.display='none';retry.classList.add('show');state.textContent='Access remains locked until the version check succeeds.'}

  async function checkVersion(initial=false){
    if(checking)return;checking=true;
    if(initial){showGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}
    try{
      const r=await fetch('/api/update/status',{cache:'no-store'});
      const j=await r.json();
      if(!j.verified){if(!verifiedOnce)checkError(j.error);return}
      verifiedOnce=true;
      if(j.required){
        required=true;showGate();
        title.textContent='Update Required';
        sub.textContent=`${j.latest||'New version'} is required before MH Analysis can continue.`;
        btn.style.display='inline-block';btn.disabled=false;btn.textContent='Update Now - To Access';
        retry.classList.remove('show');state.textContent='Your login, Records, WhatsApp settings and saved data will remain unchanged.';
      }else if(!required){
        hideGate();
      }
    }catch(e){if(!verifiedOnce)checkError('Could not reach the update service. Check internet and retry.')}
    finally{checking=false}
  }

  async function pollProgress(){
    try{
      const r=await fetch('/api/update/progress',{cache:'no-store'});const j=await r.json();
      if(j.phase==='downloading'){
        title.textContent='Downloading Update';wrap.classList.add('show');percent(j.percent);state.textContent=j.total>0?'Downloading securely…':'Downloading update…';
      }else if(j.phase==='verifying'){
        title.textContent='Verifying Update';wrap.classList.add('show');percent(99);state.textContent='Checking update integrity…';
      }else if(j.phase==='installing'){
        title.textContent='Installing Update';wrap.classList.add('show');percent(100);state.textContent='MH Analysis will restart automatically with the new version.';
      }else if(j.phase==='error'){
        clearInterval(progressTimer);progressTimer=0;title.textContent='Update Failed';sub.textContent=j.error||'Please retry.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';retry.classList.add('show');state.textContent='No saved MH Analysis data was removed.';
      }
    }catch(_){/* keep current progress surface; process may be restarting */}
  }

  async function startUpdate(){
    showGate();btn.disabled=true;btn.textContent='Starting…';retry.classList.remove('show');wrap.classList.add('show');percent(0);title.textContent='Preparing Update';sub.textContent='Keep MH Analysis open while the update downloads.';state.textContent='';
    try{
      const r=await fetch('/api/update/start',{method:'POST',cache:'no-store'});
      if(!r.ok)throw new Error((await r.text())||'Update could not start.');
      btn.style.display='none';
      if(!progressTimer){progressTimer=setInterval(pollProgress,250)}
      pollProgress();
    }catch(e){title.textContent='Update Failed';sub.textContent=e?.message||'Update could not start.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';retry.classList.add('show')}
  }

  btn.addEventListener('click',startUpdate);
  retry.addEventListener('click',()=>checkVersion(true));
  checkVersion(true);
  setInterval(()=>checkVersion(false),60000);
})();
'''
Path("web/update-v001.js").write_text(js, encoding="utf-8")

print(MARK + ": V.01 mandatory black-screen in-place updater applied")
