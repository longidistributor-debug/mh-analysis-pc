from pathlib import Path

MARK = "MH_SINGLE_NATIVE_FRAME_V810"

p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

helper = r'''
// MH_SINGLE_NATIVE_FRAME_V810
// Every re-parented browser/MT5 window is content only. The native MH Analysis
// host remains the one and only Windows frame with Minimize/Maximize/Close.
func chNormalizeEmbeddedFrame(hwnd uintptr) {
	if hwnd == 0 { return }
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	wanted := style
	wanted &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
	wanted |= chWSChild
	if wanted != style {
		chSetWindowLongPtr.Call(hwnd, ^uintptr(15), wanted)
	}
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exWanted := exStyle
	exWanted &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	exWanted |= chEXToolWindow
	if exWanted != exStyle {
		chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exWanted)
	}
	// Force Windows to recalculate the non-client area immediately. Without
	// SWP_FRAMECHANGED Chromium can keep drawing its old inner title bar even
	// though the style bits have already been removed.
	chSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)
}
'''

anchor = '\nfunc chAttachBrowser(hwnd uintptr) {'
if anchor not in s:
    raise SystemExit('chAttachBrowser anchor missing')
s = s.replace(anchor, '\n' + helper + anchor, 1)

# V80.9 already reparents correctly; normalize after SetParent and force a frame
# recalculation so no nested Chromium caption/min/max/close survives.
old_attach_tail = '''\tchSetParent.Call(hwnd, hostHWND)\n\t// MH_PRESERVE_ORIGINAL_UI_V809: synchronous child geometry; never cover toolbar.\n\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n}'''
new_attach_tail = '''\tchSetParent.Call(hwnd, hostHWND)\n\tchNormalizeEmbeddedFrame(hwnd) // ''' + MARK + '''\n\t// MH_PRESERVE_ORIGINAL_UI_V809: synchronous child geometry; never cover toolbar.\n\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n\tchSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)\n}'''
if old_attach_tail not in s:
    raise SystemExit('V80.9 attach tail missing')
s = s.replace(old_attach_tail, new_attach_tail, 1)

# Re-assert content-only framing on every native resize. This catches Chromium or
# MT5 recreating/restoring its top-level frame after navigation/login/compositor
# changes. It does not touch the MH Analysis host frame.
old_layout = '''\tlayout := func(child uintptr) {\n\t\tif child != 0 {\n\t\t\tchMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)\n\t\t}\n\t}'''
new_layout = '''\tlayout := func(child uintptr) {\n\t\tif child != 0 {\n\t\t\tchNormalizeEmbeddedFrame(child) // ''' + MARK + '''\n\t\t\tchMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)\n\t\t}\n\t}'''
if old_layout not in s:
    raise SystemExit('V80.9 layout anchor missing')
s = s.replace(old_layout, new_layout, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": inner browser/MT5 title bars removed; only EXE frame keeps window controls")
