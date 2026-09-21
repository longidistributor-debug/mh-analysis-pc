from pathlib import Path
import re

MARK='MH_V001_FINAL_EXACT_BEHAVIOR'

p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=re.sub(r'const mhPublicVersionV001 = "V\.[0-9]+"','const mhPublicVersionV001 = "V.01"',s)
p.write_text(s,encoding='utf-8')

p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('id="mhMandatoryUpdateV001" class="mhUpdateGateV001"','id="mhMandatoryUpdateV001" class="mhUpdateGateV001 mhUpdateHiddenV001"')
s=s.replace('<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.02</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.01</div>')
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '\n/* '+MARK+' */\nhtml:has(#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001)),body:has(#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001)){overflow:hidden!important;width:100%!important;height:100%!important;}\n#mhMandatoryUpdateV001{overflow:hidden!important;overscroll-behavior:none!important;}\n'
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
s=s.replace("function checkError(msg){showGate();title.textContent='Update Check Required';sub.textContent=msg||'Internet is required to verify the latest MH Analysis version.';btn.style.display='none';retry.classList.add('show');state.textContent='Access remains locked until the version check succeeds.'}",
"function checkError(msg){hideGate();title.textContent='Checking required version…';sub.textContent=msg||'Unable to verify version.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}")
s=s.replace("if(initial){showGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}",
"if(initial){hideGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}")
# Any later verification helper must obey exactly the same rule: show only verified+required.
s=s.replace("if(r.ok && j.verified===true && j.required===true) gate.classList.remove('mhUpdateHiddenV001');\n      else gate.classList.add('mhUpdateHiddenV001');",
            "if(r.ok && j.verified===true && j.required===true) gate.classList.remove('mhUpdateHiddenV001');\n      else gate.classList.add('mhUpdateHiddenV001');")
p.write_text(s,encoding='utf-8')

p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
s=s.replace('if(gate) gate.classList.remove("mhUpdateHiddenV001");\n    const v=await mhPreLoginUpdateCheckV001();',
            'if(gate) gate.classList.add("mhUpdateHiddenV001");\n    const v=await mhPreLoginUpdateCheckV001();')
s=s.replace('if(!v.verified || v.required){\n      if(overlay) overlay.classList.remove("show");',
            'if(!v.verified || v.required){\n      if(gate && !v.required) gate.classList.add("mhUpdateHiddenV001");\n      if(overlay) overlay.classList.remove("show");')
p.write_text(s,encoding='utf-8')

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    helper_anchor='\nfunc chResizeChildren() {'
    helper=r'''

// MH_V001_FINAL_EXACT_BEHAVIOR: Chrome's internal app title is always outside
// the visible host. Only the outer MH Analysis window owns Min/Max/Close.
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
    s=s.replace('if child != 0 { chNormalizeEmbeddedFrame(child) }','if child != 0 { chNormalizeEmbeddedTreeV001Final(child) }')
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
p.write_text(s,encoding='utf-8')

print(MARK+': V.01 reset; gate hidden unless verified newer; scrollbar suppressed; one outer native frame')
