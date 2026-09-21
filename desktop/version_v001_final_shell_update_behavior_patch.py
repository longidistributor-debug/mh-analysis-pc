from pathlib import Path
import re

MARK='MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR'

# A) ONE visible Windows frame only: normalize browser root + every nested child.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    proc='\tchEnumChildWindowsV001Final = chUser32.NewProc("EnumChildWindows") // '+MARK+'\n'
    if 'chEnumChildWindowsV001Final' not in s:
        anchors=['\tchSetWindowText          = chUser32.NewProc("SetWindowTextW")','\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")','\tchSetParent             = chUser32.NewProc("SetParent")']
        inserted=False
        for a in anchors:
            pos=s.find(a)
            if pos>=0:
                e=s.find('\n',pos); s=s[:e+1]+proc+s[e+1:]; inserted=True; break
        if not inserted: raise SystemExit('stable user32 proc anchor missing')
    helper_anchor='\nfunc chNormalizeEmbeddedFrame(hwnd uintptr) {'
    if helper_anchor not in s: raise SystemExit('normalize helper anchor missing')
    helper=r'''

// MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR: strip any nested Chromium native caption.
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
    old='chNormalizeEmbeddedFrame(child)\n\t\t\t}'
    if old not in s: raise SystemExit('permanent child normalize call missing')
    s=s.replace(old,'chNormalizeEmbeddedTreeV001Final(child)\n\t\t\t}',1)
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# B) PRE-LOGIN UPDATE CONTRACT:
# Login is NEVER shown until version status is positively verified.
# verified+required => mandatory update UI.
# verified+current  => hide update gate, then show login.
# unverified/network error => stay on version gate/retry; do not call it an available update.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Keep verification failure distinct from a real update, but still block login.
    s=s.replace('if(!r.ok || j.verified!==true) return {verified:false,required:true};','if(!r.ok || j.verified!==true) return {verified:false,required:false};')
    s=s.replace('}catch{\n      return {verified:false,required:true};\n    }','}catch{\n      return {verified:false,required:false};\n    }')
    # Critical: both unverified and real-update states block login.
    s=s.replace('if(v.verified && v.required){','if(!v.verified || v.required){')
    s='// '+MARK+'\n'+s
    p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s='// '+MARK+'\n'+s+r'''

(function(){
  async function enforceVerifiedPreLoginGate(){
    const gate=document.getElementById('mhMandatoryUpdateV001');
    if(!gate)return;
    try{
      const r=await fetch('/api/update/status?realupdate=1&t='+Date.now(),{cache:'no-store'});
      const j=await r.json();
      if(r.ok && j.verified===true){
        if(j.required===true) gate.classList.remove('mhUpdateHiddenV001');
        else gate.classList.add('mhUpdateHiddenV001');
      }else{
        gate.classList.remove('mhUpdateHiddenV001');
      }
    }catch(e){
      gate.classList.remove('mhUpdateHiddenV001');
    }
  }
  enforceVerifiedPreLoginGate();
  setInterval(enforceVerifiedPreLoginGate,5000);
})();
'''
    p.write_text(s,encoding='utf-8')

# C) Backend errors are UNVERIFIED, not a fake available update. Auth still blocks
# login because verified=false. Apply to the generated updater.go (not patch source).
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('"ok": false, "verified": false, "required": true,','"ok": false, "verified": false, "required": false,')
p.write_text(s,encoding='utf-8')

print(MARK+': nested frame stripping + verified-before-login update contract applied')
