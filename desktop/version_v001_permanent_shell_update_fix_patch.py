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
# The login is dynamically created by auth.js inside index.html, so gate the auth
# bootstrap itself rather than looking for a separate login.html.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    old='''  build();
  show("login_required");
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);
})();'''
    new=r'''  // MH_V001_PERMANENT_SHELL_UPDATE_FIX
  // Version verification always happens BEFORE Account Login becomes visible.
  // Same version => normal login. New mandatory version => update screen only.
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
      // Keep license/login completely behind the mandatory update surface.
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
    if(v.verified && !v.required){
      if(!overlay || !overlay.classList.contains("show")){
        status(false);
      }
    }
  },4 * 60 * 1000);
})();'''
    if old not in s:
        raise SystemExit('auth bootstrap anchor missing')
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')

# 3) Keep the update surface above every login/auth overlay.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
s=s.replace('z-index:2147483646','z-index:2147483647')
p.write_text(s,encoding='utf-8')

print(MARK+': single outer frame + update-before-login bootstrap applied')
