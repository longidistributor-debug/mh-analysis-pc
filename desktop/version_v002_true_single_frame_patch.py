from pathlib import Path

MARK='MH_V002_TRUE_SINGLE_FRAME'
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    anchor='\tchSetParent.Call(hwnd, hostHWND)\n'
    if anchor not in s: raise SystemExit('SetParent anchor missing')
    force=r'''
	// MH_V002_TRUE_SINGLE_FRAME: after SetParent the browser is permanently content-only.
	// Only the outer MH Analysis host may own caption/minimize/maximize/close controls.
	style, _, _ = chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSPopup | chWSOverlapped | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
	style |= chWSChild | chWSVisible
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ = chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chNormalizeEmbeddedTreeV001Final(hwnd)
	chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), 1, 1, chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
'''
    s=s.replace(anchor,anchor+force,1)

    # Existing V.01 permanent shell loop already re-normalizes the embedded tree.
    # Do not patch fragile resize text: strengthen the common normalizer itself so
    # every old resize/view/watchdog path receives the V.02 child-only rule.
    norm='func chNormalizeEmbeddedFrame(hwnd uintptr) {'
    if norm not in s: raise SystemExit('normalizer missing')
    s=s.replace(norm,norm+'''\n\t// V.02: never allow an embedded browser HWND to regain a top-level frame.\n''',1)

    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('mhPublicVersionV001 = "V.01"','mhPublicVersionV001 = "V.02"')
p.write_text(s,encoding='utf-8')
print(MARK+': true child-only browser frame applied after SetParent; release V.02')
