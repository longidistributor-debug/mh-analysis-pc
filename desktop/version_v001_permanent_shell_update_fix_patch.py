from pathlib import Path

MARK='MH_V001_PERMANENT_SHELL_UPDATE_FIX'

# 1) SINGLE WINDOW FRAME: re-assert content-only Chromium framing continuously.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Ensure embedded child normalization happens not only on resize but also after
    # Chromium navigation/login can recreate its non-client frame.
    anchor='func chProtectionLoopV816() {\n\tfor {'
    if anchor in s:
        repl='''func chProtectionLoopV816() {\n\tfor {'''
        s=s.replace(anchor,repl,1)
        sleep='\t\tchBrandAndProtectNativeWindowsV816()\n\t\ttime.Sleep(250 * time.Millisecond)'
        if sleep in s:
            s=s.replace(sleep,'''\t\tchBrandAndProtectNativeWindowsV816()\n\t\t// '''+MARK+''': Chromium may restore a caption after navigation/login.\n\t\t// Strip it again so only the outer MH Analysis host owns Min/Max/Close.\n\t\tchMu.Lock()\n\t\tchildren := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd}\n\t\tchMu.Unlock()\n\t\tfor _, child := range children { if child != 0 { chNormalizeEmbeddedFrame(child) } }\n\t\ttime.Sleep(250 * time.Millisecond)''',1)
        else:
            raise SystemExit('protection-loop body anchor missing')
    else:
        raise SystemExit('protection loop missing')
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# 2) UPDATE GATE BEFORE LOGIN: updater JS is loaded in the login page too.
p=Path('web/login.html')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Reuse the exact mandatory-update UI/CSS already defined by the main page by
    # loading a compact gate shell before auth becomes usable.
    gate='''\n<!-- '''+MARK+''' -->\n<div id="mhUpdateGateV001" class="mhUpdateGateV001" style="display:none;position:fixed;inset:0;z-index:2147483647;background:#07101b;color:#fff;align-items:center;justify-content:center;font-family:Segoe UI,Arial,sans-serif">\n  <div style="width:min(560px,92vw);text-align:center">\n    <img src="/mh-logo.png" alt="MH" style="width:78px;height:78px;object-fit:contain">\n    <h1 style="margin:16px 0 4px">MH ANALYSIS</h1>\n    <div id="mhUpdateVersionV001" style="font-weight:700">V.01</div>\n    <h2 id="mhUpdateTitleV001">Checking required version…</h2>\n    <p id="mhUpdateSubV001">Please wait.</p>\n    <div id="mhUpdateStateV001"></div>\n    <div id="mhUpdateBarV001" style="height:8px;background:#253244;margin:16px 0"><i style="display:block;height:100%;width:0;background:#fff"></i></div>\n    <button id="mhUpdateBtnV001" type="button" style="display:none;width:100%;height:52px">Update Now - To Access</button>\n    <button id="mhUpdateRetryV001" type="button" style="display:none;width:100%;height:44px;margin-top:10px">Retry</button>\n  </div>\n</div>\n<script src="/update-v001.js"></script>\n'''
    if '</body>' not in s: raise SystemExit('login body close missing')
    s=s.replace('</body>',gate+'</body>',1)
    p.write_text(s,encoding='utf-8')

# 3) Login controls stay unusable until authoritative version verification says
# current. If newer version exists, update gate remains and login never proceeds.
p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s='// '+MARK+'\n'+s
    s += r'''

// MH_V001_PERMANENT_SHELL_UPDATE_FIX
// Works on login.html and index.html. Authentication is not allowed to become
// interactive until update status is positively verified.
(function(){
  const gate=document.getElementById('mhUpdateGateV001');
  if(!gate)return;
  const loginControls=()=>Array.from(document.querySelectorAll('input,button,select,textarea')).filter(x=>!x.id.startsWith('mhUpdate'));
  function lockLogin(v){loginControls().forEach(x=>{x.disabled=!!v});}
  async function preAuthVersionCheck(){
    lockLogin(true); gate.style.display='flex';
    try{
      const r=await fetch('/api/update/status?preauth=1&t='+Date.now(),{cache:'no-store'});
      if(!r.ok)throw new Error('version status '+r.status);
      const j=await r.json();
      if(!j || j.verified!==true)throw new Error('version not verified');
      if(j.required===true){ gate.style.display='flex'; lockLogin(true); return; }
      gate.style.display='none'; lockLogin(false);
    }catch(e){ gate.style.display='flex'; lockLogin(true); }
  }
  preAuthVersionCheck();
  setInterval(preAuthVersionCheck,5000);
})();
'''
    p.write_text(s,encoding='utf-8')

print(MARK+': permanent single native frame + update-before-login gate applied')
