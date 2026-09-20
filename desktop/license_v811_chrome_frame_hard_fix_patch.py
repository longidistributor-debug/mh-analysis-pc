from pathlib import Path

MARK = "MH_SINGLE_NATIVE_FRAME_HARD_V811"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

# Chromium app-mode may keep/draw a nested Windows caption even after WS_CAPTION
# is cleared. Kiosk removes Chrome's own frame/chrome; the parent MH window still
# owns all Minimize/Maximize/Close controls. V80.9/V81.0 already constrain the
# child to the exact content rectangle below the native toolbar.
needle = '\t\t"--disable-features=TranslateUI",\n'
if needle not in s:
    raise SystemExit("browser args anchor missing")
if '\t\t"--kiosk",\n' not in s:
    s = s.replace(needle, needle + '\t\t"--kiosk", // ' + MARK + ': no nested Chromium title bar\n', 1)

# Make frame stripping authoritative instead of preserving unrelated top-level
# frame bits. Preserve only current visibility, then force child/clipping styles.
start = s.find('func chNormalizeEmbeddedFrame(hwnd uintptr) {')
end = s.find('\nfunc chAttachBrowser(', start)
if start < 0 or end < 0:
    raise SystemExit("V81.0 normalize function missing")
new_func = r'''func chNormalizeEmbeddedFrame(hwnd uintptr) {
	if hwnd == 0 { return }
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	visible := style & chWSVisible
	// MH_SINGLE_NATIVE_FRAME_HARD_V811: exact embedded style. Never allow a
	// caption/system-menu/min/max/thick-frame to survive Chromium state changes.
	wanted := uintptr(chWSChild|0x02000000|0x04000000) | visible // WS_CLIPCHILDREN | WS_CLIPSIBLINGS
	if style != wanted {
		chSetWindowLongPtr.Call(hwnd, ^uintptr(15), wanted)
	}
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exWanted := exStyle
	exWanted &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	exWanted |= chEXToolWindow
	if exWanted != exStyle {
		chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exWanted)
	}
	chSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)
}'''
s = s[:start] + new_func + s[end:]

# Chromium can perform one late fullscreen/frame transition after the app page is
# attached. Re-assert the child frame/bounds for a short bounded settle period.
attach_tail = '''\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n\tchSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)\n}'''
replacement = '''\tchMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)\n\tchSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate|chSWPFrame)\n\tgo func(child uintptr) {\n\t\tfor _, d := range []time.Duration{40*time.Millisecond, 120*time.Millisecond, 280*time.Millisecond, 600*time.Millisecond, 1200*time.Millisecond, 2200*time.Millisecond} {\n\t\t\ttime.Sleep(d)\n\t\t\tchMu.Lock(); stopping := chStopping; chMu.Unlock()\n\t\t\tif stopping { return }\n\t\t\tchNormalizeEmbeddedFrame(child)\n\t\t\tchResizeChildren()\n\t\t}\n\t}(hwnd)\n}'''
if attach_tail not in s:
    raise SystemExit("V81.0 attach tail anchor missing")
s = s.replace(attach_tail, replacement, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": kiosk content-only Chromium + exact child frame + bounded late-frame suppression")
