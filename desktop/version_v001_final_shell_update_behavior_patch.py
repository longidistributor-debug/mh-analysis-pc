from pathlib import Path
import re

MARK='MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR'

# ------------------------------------------------------------------
# A) ONE visible Windows frame only.
# Strip non-client frame from the embedded browser AND all descendants.
# ------------------------------------------------------------------
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    proc_anchor='\tchEnumWindows            = chUser32.NewProc("EnumWindows")\n'
    if proc_anchor not in s: raise SystemExit('EnumWindows anchor missing')
    s=s.replace(proc_anchor,proc_anchor+'\tchEnumChildWindowsV001Final = chUser32.NewProc("EnumChildWindows") // '+MARK+'\n',1)

    helper_anchor='\nfunc chNormalizeEmbeddedFrame(hwnd uintptr) {'
    if helper_anchor not in s: raise SystemExit('normalize helper anchor missing')
    helper=r'''

// MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR: Chromium can create a nested native child
// after navigation/login. Removing styles only from the first browser HWND leaves
// a second Min/Max/Close bar. Normalize the complete embedded HWND tree.
func chNormalizeEmbeddedTreeV001Final(root uintptr) {
	if root == 0 { return }
	chNormalizeEmbeddedFrame(root)
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		chSetWindowText.Call(hwnd, uintptr(unsafe.Pointer(chWstr("MH Analysis"))))
		chNormalizeEmbeddedFrame(hwnd)
		return 1
	})
	chEnumChildWindowsV001Final.Call(root, cb, 0)
}
'''
    s=s.replace(helper_anchor,helper+helper_anchor,1)

    # Permanent loop: normalize full trees, not only root browser handles.
    s=s.replace('chNormalizeEmbeddedFrame(child)\n\t\t\t}', 'chNormalizeEmbeddedTreeV001Final(child)\n\t\t\t}',1)
    # Also normalize full tree whenever resize/reparent normalization is called.
    # Keep original helper for callback safety; tree pass runs from protection loop.
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# ------------------------------------------------------------------
# B) UPDATE UX: update surface appears ONLY for a positively verified newer
# mandatory version. No update => login immediately. Network/check failure =>
# normal login; background checks continue. Update is always detected pre-login
# when server positively reports a newer version.
# ------------------------------------------------------------------
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Existing function currently treats unverified/error as required. Change that.
    s=s.replace('if(!r.ok || j.verified!==true) return {verified:false,required:true};','if(!r.ok || j.verified!==true) return {verified:false,required:false};')
    s=s.replace('return {verified:false,required:true};\n    }catch{\n      return {verified:false,required:true};','return {verified:false,required:false};\n    }catch{\n      return {verified:false,required:false};')
    s=s.replace('}catch{\n      return {verified:false,required:true};\n    }','}catch{\n      return {verified:false,required:false};\n    }')
    # Gate only on verified + required. Otherwise hide gate and continue login.
    s=s.replace('if(!v.verified || v.required){','if(v.verified && v.required){')
    p.write_text(s,encoding='utf-8')

# updater UI itself: never show update screen for check errors/current version.
p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s='// '+MARK+'\n'+s
    # Force gate hidden initially. It is displayed only after required===true.
    s += r'''

// MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR
// Safety net: a current/no-update response must never leave the update surface up.
(function(){
  async function enforceRealUpdateOnly(){
    const gate=document.getElementById('mhMandatoryUpdateV001');
    if(!gate)return;
    try{
      const r=await fetch('/api/update/status?realupdate=1&t='+Date.now(),{cache:'no-store'});
      const j=await r.json();
      if(r.ok && j.verified===true && j.required===true){
        gate.classList.remove('mhUpdateHiddenV001');
      }else{
        gate.classList.add('mhUpdateHiddenV001');
      }
    }catch(e){
      // Check failure is not proof that an update exists.
      gate.classList.add('mhUpdateHiddenV001');
    }
  }
  enforceRealUpdateOnly();
  setInterval(enforceRealUpdateOnly,30000);
})();
'''
    p.write_text(s,encoding='utf-8')

# Backend: a manifest fetch failure is NOT an available update.
p=Path('desktop/version_v001_mandatory_updater_patch.py')
s=p.read_text(encoding='utf-8')
# This patch generates updater.go during build, so correct the generated source.
s=s.replace('"ok": false, "verified": false, "required": true,','"ok": false, "verified": false, "required": false,')
p.write_text(s,encoding='utf-8')

print(MARK+': one native frame tree + real-update-only pre-login behavior applied')
