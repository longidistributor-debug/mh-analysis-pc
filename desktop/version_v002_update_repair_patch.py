from pathlib import Path

MARK = "MH_MANDATORY_UPDATE_V002"

# This patch runs AFTER version_v001_mandatory_updater_patch.py, so updater.go
# and web/update-v001.* already exist in the build workspace.

# -----------------------------------------------------------------------------
# Updater backend: V.02 uses a dedicated update channel and synchronizes native
# lock/unlock on the host UI thread. It also handles a manifest changing between
# status-check and button-click instead of leaving the UI stuck forever.
# -----------------------------------------------------------------------------
p = Path("updater.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = s.replace('// MH_MANDATORY_UPDATE_V001\n', '// MH_MANDATORY_UPDATE_V001\n// '+MARK+'\n', 1)
    s = s.replace('const mhPublicVersionV001 = "V.01"', 'const mhPublicVersionV001 = "V.02"', 1)
    s = s.replace(
        'const mhUpdateManifestURLV001 = "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/final-current-v796/update.json"',
        'const mhUpdateManifestURLV001 = "https://raw.githubusercontent.com/longidistributor-debug/mh-analysis-pc/mh-analysis-update-channel/update.json"',
        1,
    )

    # Status verification is authoritative. Keep everything locked if the check
    # fails; otherwise explicitly lock OR unlock on the native UI thread.
    old = '''    if err != nil {
        mhWriteJSONV001(w, map[string]any{
            "ok": false, "verified": false, "required": true,
            "current": mhPublicVersionV001,
            "error": "Unable to verify the required MH Analysis version. Check internet and retry.",
        })
        return
    }
    required := m.Mandatory && mhNewerVersionV001(m.Version, mhPublicVersionV001)
    if required { go chSetMandatoryUpdateLockV001(true) }
'''
    new = '''    if err != nil {
        postMessage(hostHWND, chWMUpdateLockV002, 1, 0)
        mhWriteJSONV001(w, map[string]any{
            "ok": false, "verified": false, "required": true,
            "current": mhPublicVersionV001,
            "error": "Unable to verify the required MH Analysis version. Check internet and retry.",
        })
        return
    }
    required := m.Mandatory && mhNewerVersionV001(m.Version, mhPublicVersionV001)
    if required { postMessage(hostHWND, chWMUpdateLockV002, 1, 0) } else { postMessage(hostHWND, chWMUpdateLockV002, 0, 0) }
'''
    if old not in s:
        raise SystemExit("updater status anchor missing")
    s = s.replace(old, new, 1)

    old = '''    if !m.Mandatory || !mhNewerVersionV001(m.Version, mhPublicVersionV001) {
        mhWriteJSONV001(w, map[string]any{"ok":true,"already_current":true,"version":mhPublicVersionV001})
        return
    }
'''
    new = '''    if !m.Mandatory || !mhNewerVersionV001(m.Version, mhPublicVersionV001) {
        mhSetUpdateStateV001(mhUpdateStateV001{Phase:"current",Percent:100,Latest:m.Version})
        postMessage(hostHWND, chWMUpdateLockV002, 0, 0)
        mhWriteJSONV001(w, map[string]any{"ok":true,"already_current":true,"version":mhPublicVersionV001,"latest":m.Version})
        return
    }
'''
    if old not in s:
        raise SystemExit("updater already-current anchor missing")
    s = s.replace(old, new, 1)
    s = s.replace('    go chSetMandatoryUpdateLockV001(true)\n', '    postMessage(hostHWND, chWMUpdateLockV002, 1, 0)\n', 1)

    # More robust future self-replace helper with a diagnostic log. V.01 -> V.02
    # still uses the V.01 helper already installed; this protects V.02 onward.
    start = s.find('func mhSpawnReplaceHelperV001(src, dst string) error {')
    end = s.find('\n}\n', start)
    if start < 0 or end < 0:
        raise SystemExit("replace helper anchor missing")
    end += 3
    helper = r'''func mhSpawnReplaceHelperV001(src, dst string) error {
    pid := os.Getpid()
    work := filepath.Dir(dst)
    base := os.Getenv("LOCALAPPDATA")
    if base == "" { base = os.TempDir() }
    logPath := filepath.Join(base,"MHAnalysis","updates","update.log")
    ps := "$ErrorActionPreference='Continue';" +
        "$p="+strconv.Itoa(pid)+";" +
        "$src="+mhPSQuoteV001(src)+";" +
        "$dst="+mhPSQuoteV001(dst)+";" +
        "$wd="+mhPSQuoteV001(work)+";" +
        "$log="+mhPSQuoteV001(logPath)+";" +
        "try{Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s')+' update helper started')}catch{};" +
        "for($i=0;$i -lt 160;$i++){if(-not(Get-Process -Id $p -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 250};" +
        "$ok=$false;for($i=0;$i -lt 120;$i++){try{Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop;$ok=$true;break}catch{try{Add-Content -LiteralPath $log -Value $_.Exception.Message}catch{};Start-Sleep -Milliseconds 400}};" +
        "if($ok){try{Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue}catch{};try{Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s')+' replacement complete')}catch{};Start-Process -FilePath $dst -WorkingDirectory $wd}else{try{Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s')+' replacement FAILED')}catch{}}"
    cmd := exec.Command("powershell.exe","-NoLogo","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-Command",ps)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow:true}
    return cmd.Start()
}
'''
    s = s[:start] + helper + s[end:]
    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Native host: version verification starts LOCKED. The server posts a custom
# message to the native UI thread to lock/unlock. While locked every native tab
# command/settings command is ignored, even if a button somehow paints briefly.
# -----------------------------------------------------------------------------
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = s.replace('// MH_MANDATORY_UPDATE_V001\n', '// MH_MANDATORY_UPDATE_V001\n// '+MARK+'\n', 1)
    s = s.replace('\tchMandatoryUpdateV001 bool // MH_MANDATORY_UPDATE_V001', '\tchMandatoryUpdateV001 = true // '+MARK+' verify-first lock', 1)
    const_anchor = '\tchWMCommand     = 0x0111\n'
    if const_anchor not in s:
        raise SystemExit("native message anchor missing")
    s = s.replace(const_anchor, const_anchor+'\tchWMUpdateLockV002 = 0x80A2 // '+MARK+'\n', 1)

    case_anchor = '\tcase chWMCommand:\n'
    if case_anchor not in s:
        raise SystemExit("native command case anchor missing")
    s = s.replace(case_anchor, '''\tcase chWMUpdateLockV002:
\t\tchSetMandatoryUpdateLockV001(wParam != 0)
\t\treturn 0
\tcase chWMCommand:
\t\tchViewMu.Lock(); lockedV002 := chMandatoryUpdateV001; chViewMu.Unlock()
\t\tif lockedV002 { return 0 }
''', 1)

    # Block custom settings/view messages while mandatory update is active.
    for label in ['chWMOpenAPISettings','chWMOpenWhatsAppSettings','wmSwitchAnalysis','wmSwitchWhatsApp','wmWhatsAppSend']:
        old = '\tcase '+label+':\n'
        if old in s:
            s = s.replace(old, old+'\t\tchViewMu.Lock(); lockedV002 := chMandatoryUpdateV001; chViewMu.Unlock()\n\t\tif lockedV002 { return 0 }\n', 1)

    p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Update UI: V.02 branding + robust start response. If manifest changes between
# check and click, do not leave a permanent stuck overlay.
# -----------------------------------------------------------------------------
p = Path("web/index.html")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = s.replace('id="mhUpdateVersionV001">V.01</div>', 'id="mhUpdateVersionV001">V.02</div>', 1)
    s = s.replace('<div class="version">V.01 AUTO CYCLE (HAMMAD & SOMI)</div>', '<div class="version">V.02 AUTO CYCLE (HAMMAD & SOMI)</div>', 1)
    s = s.replace('<body>\n', '<body>\n<!-- '+MARK+' -->\n', 1)
    p.write_text(s, encoding="utf-8")

p = Path("web/update-v001.js")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = '// '+MARK+'\n' + s
    old = '''      const r=await fetch('/api/update/start',{method:'POST',cache:'no-store'});
      if(!r.ok)throw new Error((await r.text())||'Update could not start.');
      btn.style.display='none';
      if(!progressTimer){progressTimer=setInterval(pollProgress,250)}
      pollProgress();
'''
    new = '''      const r=await fetch('/api/update/start',{method:'POST',cache:'no-store'});
      if(!r.ok)throw new Error((await r.text())||'Update could not start.');
      const j=await r.json();
      if(j.already_current){
        required=false; verifiedOnce=true;
        if(progressTimer){clearInterval(progressTimer);progressTimer=0}
        wrap.classList.remove('show');btn.style.display='none';retry.classList.remove('show');
        title.textContent='Version Verified';sub.textContent='MH Analysis is up to date.';state.textContent='Opening MH Analysis…';
        setTimeout(()=>hideGate(),250);
        return;
      }
      btn.style.display='none';
      if(!progressTimer){progressTimer=setInterval(pollProgress,250)}
      pollProgress();
'''
    if old not in s:
        raise SystemExit("update JS start anchor missing")
    s = s.replace(old, new, 1)

    # Show current -> latest clearly instead of a misleading static version.
    old2 = "sub.textContent=`${j.latest||'New version'} is required before MH Analysis can continue.`;"
    new2 = "version.textContent=`${j.current||'V.02'} → ${j.latest||'New version'}`;sub.textContent=`${j.latest||'New version'} is required before MH Analysis can continue.`;"
    # Existing script variable is named ver, not version in some builds; detect safely.
    if old2 in s:
        if "const version=" in s:
            s = s.replace(old2, new2, 1)
        elif "const ver=" in s:
            s = s.replace(old2, "ver.textContent=`${j.current||'V.02'} → ${j.latest||'New version'}`;sub.textContent=`${j.latest||'New version'} is required before MH Analysis can continue.`;", 1)
    p.write_text(s, encoding="utf-8")

print(MARK + ": V.02 dedicated update channel, verify-first native lock and stuck-update repair applied")
