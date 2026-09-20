from pathlib import Path

MARK = "MH_SINGLE_EXE_CROP_V813"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

# Chrome --app draws its own Aura title strip even after Win32 caption style bits are
# removed. Kiosk hid that strip but broke normal restore/resize behavior. V81.3 keeps
# the good V81.2 responsive non-kiosk mode and clips only Chrome's internal app title
# strip. The web viewport still fills exactly the host content area below the native
# MH Analysis toolbar.

# Win32 helpers for DPI-aware clipping regions.
proc_anchor = '\tchSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")\n'
proc_new = proc_anchor + '\tchGetDpiForWindow        = chUser32.NewProc("GetDpiForWindow") // ' + MARK + '\n\tchSetWindowRgn          = chUser32.NewProc("SetWindowRgn")\n\tchCreateRectRgn         = chGdi32.NewProc("CreateRectRgn")\n'
if proc_new not in s:
    if proc_anchor not in s:
        raise SystemExit("Win32 proc anchor missing")
    s = s.replace(proc_anchor, proc_new, 1)

helper_anchor = '\nfunc chResizeChildren() {'
helper = r'''

// MH_SINGLE_EXE_CROP_V813: Chrome app-mode owns a client-drawn title strip that is
// not governed by WS_CAPTION. Crop that strip instead of using --kiosk. This leaves
// Minimize/Maximize/Close exclusively on the outer MH Analysis EXE while preserving
// normal Windows resize/restore/maximize behavior.
func chChromeAppTitleCrop(hwnd uintptr) int32 {
	if hwnd == 0 { return 0 }
	dpi := uintptr(96)
	if chGetDpiForWindow.Find() == nil {
		if v, _, _ := chGetDpiForWindow.Call(hwnd); v != 0 { dpi = v }
	}
	crop := int32((30*dpi + 48) / 96)
	if crop < 28 { crop = 28 }
	if crop > 52 { crop = 52 }
	return crop
}

func chLayoutChromeCropped(hwnd uintptr, w, h int32) {
	if hwnd == 0 { return }
	chNormalizeEmbeddedFrame(hwnd)
	crop := chChromeAppTitleCrop(hwnd)
	totalH := h + crop
	if totalH < 1 { totalH = 1 }
	// Move the hidden app-title strip upward and expose only the web surface.
	chMoveWindow.Call(hwnd, 0, uintptr(int32(barH)-crop), uintptr(w), uintptr(totalH), 1)
	if chCreateRectRgn.Find() == nil && chSetWindowRgn.Find() == nil {
		rgn, _, _ := chCreateRectRgn.Call(0, uintptr(crop), uintptr(w), uintptr(totalH))
		if rgn != 0 {
			// On success Windows owns the HRGN; do not delete it here.
			chSetWindowRgn.Call(hwnd, rgn, 1)
		}
	}
}
'''
if helper not in s:
    if helper_anchor not in s:
        raise SystemExit("resize helper anchor missing")
    s = s.replace(helper_anchor, helper + helper_anchor, 1)

# Replace only the V80.9 layout closure. Analysis/WhatsApp/Records are Chromium;
# MT5 is native and must keep the normal uncropped rectangle.
old_layout = '''\tlayout := func(child uintptr) {\n\t\tif child != 0 {\n\t\t\tchNormalizeEmbeddedFrame(child) // MH_SINGLE_NATIVE_FRAME_V810\n\t\t\tchMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)\n\t\t}\n\t}\n\tlayout(chAnalysisWnd)\n\tlayout(chWhatsappWnd)\n\tlayout(chRecordsWnd)\n\tlayout(chMT5Wnd)'''
new_layout = '''\t// ''' + MARK + ''': Chromium app title strip is clipped, never shown as a second frame.\n\tchLayoutChromeCropped(chAnalysisWnd, w, h)\n\tchLayoutChromeCropped(chWhatsappWnd, w, h)\n\tchLayoutChromeCropped(chRecordsWnd, w, h)\n\tif chMT5Wnd != 0 {\n\t\tchNormalizeEmbeddedFrame(chMT5Wnd)\n\t\tchMoveWindow.Call(chMT5Wnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1)\n\t}'''
if new_layout not in s:
    if old_layout not in s:
        raise SystemExit("V81.2 layout anchor missing")
    s = s.replace(old_layout, new_layout, 1)

# The initial attach is still tiny/offscreen-ish; immediately apply the crop once so
# no blue app frame flashes before the first resize settles.
old_tail = '''\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n\tchSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)'''
new_tail = '''\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n\tchSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)\n\t// ''' + MARK + ''': first real geometry is applied by chResizeChildren immediately after attach.'''
if old_tail in s and new_tail not in s:
    s = s.replace(old_tail, new_tail, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": Chrome app title strip clipped; only outer EXE owns window controls; V81.2 responsiveness retained")
