from pathlib import Path

MARK='MH_V002_TRUE_SINGLE_FRAME'
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Root cause: Chromium is re-parented after its style is stripped. Windows/Chromium
    # can recreate/restore the non-client frame during SetParent/navigation. Force the
    # CHILD-only style AFTER SetParent and again whenever children are resized.
    anchor='\tchSetParent.Call(hwnd, hostHWND)\n'
    if anchor not in s: raise SystemExit('SetParent anchor missing')
    force=r'''
	// MH_V002_TRUE_SINGLE_FRAME: after re-parenting, force the browser root to be
	// a plain WS_CHILD. It must never own caption/min/max/close controls.
	style, _, _ = chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSPopup | chWSOverlapped | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
	style |= chWSChild | chWSVisible
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ = chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), 1, 1, chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
'''
    s=s.replace(anchor,anchor+force,1)

    # Every resize reasserts root style before sizing. This prevents Chrome from
    # restoring a second caption after login/navigation/maximize.
    needle='''\tif chAnalysisWnd != 0 {
\t\tchSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}'''
    repl='''\tif chAnalysisWnd != 0 {
\t\tchNormalizeEmbeddedTreeV001Final(chAnalysisWnd)
\t\tchSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
\t}'''
    if needle not in s: raise SystemExit('analysis resize anchor missing')
    s=s.replace(needle,repl,1)
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# V.02 is the new release. Old V.01 clients should see this as a genuine newer update.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('mhPublicVersionV001 = "V.01"','mhPublicVersionV001 = "V.02"')
p.write_text(s,encoding='utf-8')

print(MARK+': browser forced to true child-only frame; release V.02')
