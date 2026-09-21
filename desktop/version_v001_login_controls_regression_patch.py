from pathlib import Path
import re

MARK='MH_V002_RUNTIME_ACCEPTANCE_FIX'

def replace_go_func(src: str, name: str, body: str) -> str:
    start=src.find('func '+name+'(')
    if start<0:
        raise SystemExit('missing Go function '+name)
    brace=src.find('{',start)
    if brace<0:
        raise SystemExit('missing brace for '+name)
    depth=0
    i=brace
    while i<len(src):
        if src[i]=='{': depth+=1
        elif src[i]=='}':
            depth-=1
            if depth==0:
                return src[:start]+body.rstrip()+src[i+1:]
        i+=1
    raise SystemExit('unterminated Go function '+name)

# ---------------------------------------------------------------------------
# AUTH: saved app/browser/trading state survives, authorization for this EXE
# process does NOT. Every new process must manually submit username/password.
# Existing backend cookies/sessions are never allowed to auto-hide Account Login.
# ---------------------------------------------------------------------------
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Per-process flag starts false after every EXE/browser process start.
anchor='  let lastField = "username";\n'
if 'mhManualLoginV002' not in s:
    if anchor not in s: raise SystemExit('auth state anchor missing')
    s=s.replace(anchor,anchor+'  let mhManualLoginV002 = false; // '+MARK+'\n',1)

# status() is allowed only after THIS process has completed a manual login.
status_anchor='  async function status(reloadAfter = false) {\n'
guard='  async function status(reloadAfter = false) {\n    if (!mhManualLoginV002) { show("login_required"); return; } // '+MARK+'\n'
if guard not in s:
    if status_anchor not in s: raise SystemExit('status function anchor missing')
    s=s.replace(status_anchor,guard,1)

# Successful login marks only this running process authorized; no reload.
login_old='''      passInput.value = "";
      message.textContent = "Access granted. Loading MH Analysis…";
      hide(j);'''
login_new='''      passInput.value = "";
      mhManualLoginV002 = true;
      message.textContent = "Access granted. Loading MH Analysis…";
      hide(j); // '''+MARK
if login_new not in s:
    if login_old in s:
        s=s.replace(login_old,login_new,1)
    else:
        # Flexible fallback around the final successful hide(j).
        m=list(re.finditer(r'(?m)^\s*hide\(j\);\s*$',s))
        if not m: raise SystemExit('successful login hide(j) anchor missing')
        q=m[-1]
        indent=re.match(r'\s*',q.group(0)).group(0)
        repl=indent+'mhManualLoginV002 = true;\n'+indent+'hide(j); // '+MARK
        s=s[:q.start()]+repl+s[q.end():]

# Never reload after successful login.
s=re.sub(r'(?m)^\s*location\.reload\(\);\s*//?[^\n]*$', '', s)
s=re.sub(r'(?m)^\s*location\.reload\(\);\s*$', '', s)

# Any startup/periodic status(false) remains safe because status() itself refuses
# to authorize until manual login in this process. Ensure Account Login is shown
# after update verification when no newer mandatory release is active.
if 'show("login_required")' not in s:
    raise SystemExit('Account Login UI missing')
if MARK not in s:
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# ---------------------------------------------------------------------------
# NATIVE SHELL: one and only one Windows frame. Embedded Chromium/MT5 windows
# are permanent WS_CHILD content surfaces and cannot regain caption/min/max/close.
# ---------------------------------------------------------------------------
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')

normalizer=r'''func chNormalizeEmbeddedFrame(hwnd uintptr) {
	if hwnd == 0 { return }
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSPopup | chWSOverlapped | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
	style |= chWSChild | chWSVisible
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	exStyle |= chEXToolWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)
}'''
s=replace_go_func(s,'chNormalizeEmbeddedFrame',normalizer)

resize=r'''func chResizeChildren() {
	if hostHWND == 0 { return }
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int32(r.R-r.L)
	h := int32(r.B-r.T)-int32(barH)
	if w < 1 { w = 1 }
	if h < 1 { h = 1 }
	layout := func(child uintptr) {
		if child == 0 { return }
		chNormalizeEmbeddedTreeV001Final(child)
		chMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
		chSetWindowPos.Call(child, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPFrame)
	}
	layout(chAnalysisWnd)
	layout(chWhatsappWnd)
	layout(chRecordsWnd)
	layout(chMT5Wnd)
	if btnAnalysis!=0 { chMoveWindow.Call(btnAnalysis,8,7,140,30,1); chShowWindow.Call(btnAnalysis,chSWShow) }
	if btnWhatsapp!=0 { chMoveWindow.Call(btnWhatsapp,156,7,140,30,1); chShowWindow.Call(btnWhatsapp,chSWShow) }
	if btnRecords!=0 { chMoveWindow.Call(btnRecords,304,7,140,30,1); chShowWindow.Call(btnRecords,chSWShow) }
	if btnMT5!=0 { chMoveWindow.Call(btnMT5,452,7,140,30,1); chShowWindow.Call(btnMT5,chSWShow) }
	chViewMu.Lock(); which:=chDesiredView; chViewMu.Unlock()
	if chSignalLinkBtn!=0 {
		chMoveWindow.Call(chSignalLinkBtn,600,7,145,30,1)
		if which==2 { chShowWindow.Call(chSignalLinkBtn,chSWShow) } else { chShowWindow.Call(chSignalLinkBtn,chSWHide) }
	}
}'''
s=replace_go_func(s,'chResizeChildren',resize)

apply=r'''func chApplyDesiredBrowserView() {
	chMu.Lock()
	analysis:=chAnalysisWnd
	whatsapp:=chWhatsappWnd
	records:=chRecordsWnd
	mt5:=chMT5Wnd
	chMu.Unlock()
	chViewMu.Lock(); which:=chDesiredView; chViewMu.Unlock()
	chResizeChildren()
	// Records is the authorized inline Records surface inside Analysis in V81.5+.
	chSetEmbeddedVisible(analysis, which==1 || which==3)
	chSetEmbeddedVisible(whatsapp, which==2)
	chSetEmbeddedVisible(records, false)
	chSetEmbeddedVisible(mt5, which==4)
	chResizeChildren()
	if which==3 {
		if analysis!=0 { chFocusEmbedded(analysis) }
	} else {
		chFocusDesiredEmbedded()
	}
}'''
s=replace_go_func(s,'chApplyDesiredBrowserView',apply)

switch=r'''func chSwitchView(which int) {
	if which < 1 || which > 4 { which = 1 }
	chViewMu.Lock(); chDesiredView=which; chViewMu.Unlock()
	if chSignalLinkBtn!=0 {
		if which==2 { chShowWindow.Call(chSignalLinkBtn,chSWShow) } else { chShowWindow.Call(chSignalLinkBtn,chSWHide) }
	}
	chApplyDesiredBrowserView()
	go func(){
		for _,d:=range []time.Duration{30*time.Millisecond,120*time.Millisecond,320*time.Millisecond,700*time.Millisecond}{
			time.Sleep(d)
			chMu.Lock(); stop:=chStopping; chMu.Unlock()
			if stop { return }
			chApplyDesiredBrowserView()
		}
	}()
}'''
s=replace_go_func(s,'chSwitchView',switch)

# Do not use the negative-title crop helper anywhere. If later code calls it,
# make it a normal content-only layout beneath the native toolbar.
if 'func chLayoutUpdateChromeV001Final(' in s:
    layout=r'''func chLayoutUpdateChromeV001Final(hwnd uintptr, w, h int32) {
	if hwnd==0 { return }
	chNormalizeEmbeddedTreeV001Final(hwnd)
	chMoveWindow.Call(hwnd,0,uintptr(barH),uintptr(w),uintptr(h),1)
	chSetWindowPos.Call(hwnd,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoZOrder|chSWPNoActivate|chSWPFrame)
}'''
    s=replace_go_func(s,'chLayoutUpdateChromeV001Final',layout)

if MARK not in s:
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
p.write_text(s,encoding='utf-8')

# Hidden update UI must occupy no space when current.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s+='''\n/* MH_V002_RUNTIME_ACCEPTANCE_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;width:0!important;height:0!important;overflow:hidden!important;}
'''
p.write_text(s,encoding='utf-8')

# Release is now V.02. V.01 clients see this manifest as a newer mandatory update.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=re.sub(r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.02"',s)
p.write_text(s,encoding='utf-8')

print(MARK+': V.02 final runtime contract: fresh login every process, preserved data, working views, single outer frame')
