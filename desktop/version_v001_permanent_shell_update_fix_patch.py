from pathlib import Path

MARK='MH_V001_PERMANENT_SHELL_UPDATE_FIX'

# 1) SINGLE WINDOW FRAME: permanently re-assert content-only framing.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    sleep='\t\tchBrandAndProtectNativeWindowsV816()\n\t\ttime.Sleep(250 * time.Millisecond)'
    if sleep not in s:
        raise SystemExit('protection-loop body anchor missing')
    s=s.replace(sleep,'''\t\tchBrandAndProtectNativeWindowsV816()
\t\t// MH_V001_PERMANENT_SHELL_UPDATE_FIX: Chromium/MT5 may restore a
\t\t// non-client caption after navigation/login. Strip it continuously.
\t\tchMu.Lock()
\t\tchildren := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd}
\t\tchMu.Unlock()
\t\tfor _, child := range children {
\t\t\tif child != 0 { chNormalizeEmbeddedFrame(child) }
\t\t}
\t\ttime.Sleep(250 * time.Millisecond)''',1)
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# 2) UPDATE MUST PRECEDE LOGIN.
# Earlier license patches can rewrite the final auth bootstrap. Locate the final
# bootstrap semantically instead of requiring one exact whitespace/text block.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    end=s.rfind('})();')
    if end < 0:
        raise SystemExit('auth closure missing')
    prefix=s[:end]
    # Remove the existing final bootstrap calls regardless of whitespace variants.
    import re
    patterns=[
        r'\s*build\(\)\s*;\s*show\([\'\"]login_required[\'\"]\)\s*;\s*status\(false\)\s*;\s*setInterval\(\(\)\s*=>\s*status\(false\),\s*4\s*\*\s*60\s*\*\s*1000\)\s*;\s*$',
        r'\s*build\(\)\s*;\s*show\([\'\"]login_required[\'\"]\)\s*;\s*status\(false\)\s*;\s*$'
    ]
    removed=False
    for pat in patterns:
        newer,n=re.subn(pat,'\n',prefix,flags=re.S)
        if n:
            prefix=newer; removed=True; break
    if not removed:
        # Last-resort safe cut: find the last top-level bootstrap build() occurring
        # after MHLicense export. Never touch build() calls inside functions.
        export_pos=prefix.rfind('window.MHLicense')
        boot_pos=prefix.find('\n  build();', export_pos if export_pos >= 0 else 0)
        if boot_pos < 0:
            raise SystemExit('final auth bootstrap not found')
        prefix=prefix[:boot_pos]+'\n'

    injected=r'''
  // MH_V001_PERMANENT_SHELL_UPDATE_FIX
  // Version verification happens BEFORE Account Login becomes visible.
  async function mhPreLoginUpdateCheckV001(){
    try{
      const r=await rawFetch("/api/update/status?preauth=1&t="+Date.now(),{cache:"no-store"});
      const j=await r.json().catch(()=>({}));
      if(!r.ok || j.verified!==true) return {verified:false,required:true};
      return {verified:true,required:j.required===true};
    }catch{
      return {verified:false,required:true};
    }
  }

  async function mhBootAfterVersionV001(){
    const gate=document.getElementById("mhMandatoryUpdateV001");
    if(gate) gate.classList.remove("mhUpdateHiddenV001");
    const v=await mhPreLoginUpdateCheckV001();
    if(!v.verified || v.required){
      if(overlay) overlay.classList.remove("show");
      document.documentElement.classList.remove("mhLicenseLocked");
      return;
    }
    if(gate) gate.classList.add("mhUpdateHiddenV001");
    build();
    show("login_required");
    status(false);
  }

  mhBootAfterVersionV001();
  setInterval(async()=>{
    const v=await mhPreLoginUpdateCheckV001();
    if(v.verified && !v.required && overlay && overlay.classList.contains("show")) status(false);
  },4 * 60 * 1000);
'''
    s=prefix+injected+'})();\n'
    p.write_text(s,encoding='utf-8')

# 3) Keep update surface above every login/auth overlay.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
s=s.replace('z-index:2147483646','z-index:2147483647')
p.write_text(s,encoding='utf-8')

print(MARK+': single outer frame + resilient update-before-login bootstrap applied')
