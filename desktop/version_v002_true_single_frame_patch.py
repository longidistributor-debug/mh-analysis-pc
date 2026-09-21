from pathlib import Path

MARK='MH_V002_TRUE_SINGLE_FRAME'
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Chromium may restore its top-level non-client frame after SetParent.
    # Force the embedded root to WS_CHILD only AFTER re-parenting.
    anchor='\tchSetParent.Call(hwnd, hostHWND)\n'
    if anchor not in s: raise SystemExit('SetParent anchor missing')
    force=r'''
	// MH_V002_TRUE_SINGLE_FRAME: embedded Chromium is content only.
	// The outer MH Analysis host is the only window allowed to own Min/Max/Close.
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

    # Match the CURRENT generated source rather than an obsolete escaped anchor.
    analysis='''\tif chAnalysisWnd != 0 {
\t\tchSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}'''
    analysis_repl='''\tif chAnalysisWnd != 0 {
\t\tchNormalizeEmbeddedTreeV001Final(chAnalysisWnd)
\t\tchSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
\t}'''
    if analysis not in s: raise SystemExit('current analysis resize block missing')
    s=s.replace(analysis,analysis_repl,1)

    whatsapp='''\tif chWhatsappWnd != 0 {
\t\tchSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}'''
    whatsapp_repl='''\tif chWhatsappWnd != 0 {
\t\tchNormalizeEmbeddedTreeV001Final(chWhatsappWnd)
\t\tchSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
\t}'''
    if whatsapp not in s: raise SystemExit('current whatsapp resize block missing')
    s=s.replace(whatsapp,whatsapp_repl,1)

    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

# V.02 is the new release. Existing V.01 installations must detect it as newer.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('mhPublicVersionV001 = "V.01"','mhPublicVersionV001 = "V.02"')
p.write_text(s,encoding='utf-8')

print(MARK+': post-SetParent child-only browser frame + resize reassertion; release V.02')
