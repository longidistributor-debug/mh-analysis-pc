from pathlib import Path
import re

MARK='MH_V001_FINAL_EXACT_BEHAVIOR'

# 1) Release is reset to V.01. Future V.02+ is what must trigger the updater.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=re.sub(r'const mhPublicVersionV001 = "V\.[0-9]+"','const mhPublicVersionV001 = "V.01"',s)
p.write_text(s,encoding='utf-8')

# 2) Update UI must NEVER be visible merely because the app is checking.
# It is hidden in the HTML from the first paint and is shown only after a
# positively verified response says required=true.
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('id="mhMandatoryUpdateV001" class="mhUpdateGateV001"','id="mhMandatoryUpdateV001" class="mhUpdateGateV001 mhUpdateHiddenV001"')
s=s.replace('<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.02</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.01</div>')
s=s.replace('<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.01</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.01</div>')
p.write_text(s,encoding='utf-8')

# 3) No scrollbar on the update surface.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '\n/* '+MARK+' */\nhtml:has(#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001)),body:has(#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001)){overflow:hidden!important;width:100%!important;height:100%!important;}\n#mhMandatoryUpdateV001{overflow:hidden!important;overscroll-behavior:none!important;}\n'
p.write_text(s,encoding='utf-8')

# 4) Rewrite updater front-end contract:
# - hidden while checking
# - current V.01 => remain hidden
# - only verified newer mandatory version => show update screen
# - check failure is NOT represented as 'Update Required'
p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
s=s.replace("function checkError(msg){showGate();title.textContent='Update Check Required';sub.textContent=msg||'Internet is required to verify the latest MH Analysis version.';btn.style.display='none';retry.classList.add('show');state.textContent='Access remains locked until the version check succeeds.'}",
"function checkError(msg){hideGate();title.textContent='Checking required version…';sub.textContent=msg||'Unable to verify version.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}")
s=s.replace("if(initial){showGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}",
"if(initial){hideGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}")
# Remove later add-on logic that could independently re-show the gate on mere verification checks.
addon=s.find('// MH_V001_FINAL_SHELL_UPDATE_BEHAVIOR')
if addon>=0:
    s=s[:addon].rstrip()+"\n"
    # preserve closure if truncation removed it
    if not s.rstrip().endswith('})();'):
        s += '\n'
p.write_text(s,encoding='utf-8')

# 5) Auth/login is still withheld until version status is verified, but it never
# forces the update gate visible. The update script alone shows it for required=true.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
s=s.replace('if(gate) gate.classList.remove("mhUpdateHiddenV001");\n    const v=await mhPreLoginUpdateCheckV001();',
            'if(gate) gate.classList.add("mhUpdateHiddenV001");\n    const v=await mhPreLoginUpdateCheckV001();')
# On verified required update, updater JS owns visibility. On unverified, keep login hidden without fake update screen.
s=s.replace('if(!v.verified || v.required){\n      if(overlay) overlay.classList.remove("show");',
            'if(!v.verified || v.required){\n      if(gate && !v.required) gate.classList.add("mhUpdateHiddenV001");\n      if(overlay) overlay.classList.remove("show");')
p.write_text(s,encoding='utf-8')

# 6) Native update-lock layout must also crop Chrome's app/Aura title strip.
# The old mandatory branch used SetWindowPos at y=0, which exposed Chrome's own
# Minimize/Maximize/Close underneath the real MH Analysis frame.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    helper_anchor='\nfunc chResizeChildren() {'
    helper=r'''

// MH_V001_FINAL_EXACT_BEHAVIOR: full update surface with Chrome's own app-title
// strip physically outside the visible host client. Only MH Analysis owns window controls.
func chLayoutUpdateChromeV001Final(hwnd uintptr, w, h int32) {
	if hwnd == 0 { return }
	chNormalizeEmbeddedTreeV001Final(hwnd)
	crop := chChromeAppTitleCrop(hwnd)
	totalH := h + crop
	if totalH < 1 { totalH = 1 }
	chMoveWindow.Call(hwnd, 0, uintptr(-crop), uintptr(w), uintptr(totalH), 1)
	if chCreateRectRgn.Find() == nil && chSetWindowRgn.Find() == nil {
		rgn, _, _ := chCreateRectRgn.Call(0, uintptr(crop), uintptr(w), uintptr(totalH))
		if rgn != 0 { chSetWindowRgn.Call(hwnd, rgn, 1) }
	}
}
'''
    if helper_anchor not in s: raise SystemExit('resize helper anchor missing')
    s=s.replace(helper_anchor,helper+helper_anchor,1)

    old='''\t\tif chAnalysisWnd != 0 {
\t\t\tchSetWindowPos.Call(chAnalysisWnd, 0, 0, 0, uintptr(w), uintptr(fullH), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t\t\tchShowWindowAsync.Call(chAnalysisWnd, chSWShow)
\t\t}'''
    new='''\t\tif chAnalysisWnd != 0 {
\t\t\tchLayoutUpdateChromeV001Final(chAnalysisWnd, w, fullH)
\t\t\tchShowWindowAsync.Call(chAnalysisWnd, chSWShow)
\t\t}'''
    if old not in s: raise SystemExit('mandatory update layout anchor missing')
    s=s.replace(old,new,1)

    # Permanent protection loop: if Chromium/Aura tries to restore its app title,
    # normalize the full tree, not just the root.
    s=s.replace('if child != 0 { chNormalizeEmbeddedFrame(child) }','if child != 0 { chNormalizeEmbeddedTreeV001Final(child) }')
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
p.write_text(s,encoding='utf-8')

print(MARK+': V.01 reset; update only for verified newer version; no update scrollbar; single outer window frame')
