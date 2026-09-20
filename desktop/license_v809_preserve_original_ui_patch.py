from pathlib import Path

MARK = "MH_PRESERVE_ORIGINAL_UI_V809"


def replace_func(src: str, name: str, next_name: str, body: str) -> str:
    start = src.find(f"func {name}(")
    if start < 0:
        raise SystemExit(f"missing function {name}")
    end = src.find(f"\nfunc {next_name}(", start)
    if end < 0:
        raise SystemExit(f"missing next function {next_name} after {name}")
    return src[:start] + body.rstrip() + "\n" + src[end:]

p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

# Keep the original Analysis browser profile. The application stores its own UI
# state (auto-signal preference, candle cache and active signal state) in browser
# localStorage, so a throw-away profile must not be used on every EXE launch.
old_profile = '''\tprofileDir := chProfileDir(profile)
\tif profile == "AnalysisProfile" {
\t\tprofileDir = chAnalysisRuntimeProfileDir()
\t}
'''
new_profile = '''\tprofileDir := chProfileDir(profile) // ''' + MARK + ''': persistent original app state
'''
if old_profile in s:
    s = s.replace(old_profile, new_profile, 1)
elif new_profile not in s:
    raise SystemExit("Analysis profile override anchor missing")

# Chromium app-mode is enough once its window chrome is stripped and reparented.
# Kiosk mode may asynchronously maximize the child back over the native toolbar,
# which is exactly the cut/covered view seen after login.
s = s.replace('\t\t"--kiosk",\n', '')

# Reparent at the correct content origin immediately. The native toolbar owns
# 0..barH and the browser/Records/MT5 content owns barH..client-bottom.
attach_body = r'''func chAttachBrowser(hwnd uintptr) {
	if hwnd == 0 || hostHWND == 0 {
		return
	}
	chShowWindow.Call(hwnd, chSWHide)
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu | chWSVisible
	style |= chWSChild
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	exStyle |= chEXToolWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chSetParent.Call(hwnd, hostHWND)
	// MH_PRESERVE_ORIGINAL_UI_V809: synchronous child geometry; never cover toolbar.
	chMoveWindow.Call(hwnd, 0, uintptr(barH), 1, 1, 1)
}'''
# The V80.2 focus patch inserts chFocusEmbedded/chFocusDesiredEmbedded between
# chAttachBrowser and chResizeChildren. Preserve those helpers exactly.
s = replace_func(s, "chAttachBrowser", "chFocusEmbedded", attach_body)

resize_body = r'''func chResizeChildren() {
	if hostHWND == 0 {
		return
	}
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int32(r.R - r.L)
	clientH := int32(r.B - r.T)
	h := clientH - int32(barH)
	if w < 1 { w = 1 }
	if h < 1 { h = 1 }

	// MH_PRESERVE_ORIGINAL_UI_V809: MoveWindow is deliberately synchronous.
	// Every embedded view gets exactly the same rectangle below the native bar,
	// so the web footer remains reachable and the native tabs can never be covered.
	layout := func(child uintptr) {
		if child != 0 {
			chMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
		}
	}
	layout(chAnalysisWnd)
	layout(chWhatsappWnd)
	layout(chRecordsWnd)
	layout(chMT5Wnd)

	if btnAnalysis != 0 { chMoveWindow.Call(btnAnalysis, 8, 7, 140, 30, 1) }
	if btnWhatsapp != 0 { chMoveWindow.Call(btnWhatsapp, 156, 7, 140, 30, 1) }
	if btnRecords != 0 { chMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1) }
	if btnMT5 != 0 { chMoveWindow.Call(btnMT5, 452, 7, 140, 30, 1) }
	if chSignalLinkBtn != 0 { chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1) }

	// Keep native controls above all reparented child windows without moving them.
	raise := func(child uintptr) {
		if child != 0 {
			chSetWindowPos.Call(child, 0, 0, 0, 0, 0, 0x0001|0x0002|chSWPNoActivate)
		}
	}
	raise(btnAnalysis)
	raise(btnWhatsapp)
	raise(btnRecords)
	raise(btnMT5)
	raise(chSignalLinkBtn)
}'''
s = replace_func(s, "chResizeChildren", "chApplyDesiredBrowserView", resize_body)

apply_body = r'''func chApplyDesiredBrowserView() {
	chMu.Lock()
	analysis := chAnalysisWnd
	whatsapp := chWhatsappWnd
	records := chRecordsWnd
	mt5 := chMT5Wnd
	chMu.Unlock()

	chViewMu.Lock()
	which := chDesiredView
	chViewMu.Unlock()

	// Always settle geometry first; visibility changes never alter the rectangle.
	chResizeChildren()
	chSetEmbeddedVisible(analysis, which == 1)
	chSetEmbeddedVisible(whatsapp, which == 2)
	chSetEmbeddedVisible(records, which == 3)
	chSetEmbeddedVisible(mt5, which == 4)
	chResizeChildren()
	chFocusDesiredEmbedded()
}'''
s = replace_func(s, "chApplyDesiredBrowserView", "chSwitchView", apply_body)

switch_body = r'''func chSwitchView(which int) {
	chViewMu.Lock()
	chDesiredView = which
	chViewMu.Unlock()

	// Preserve the original behavior: Signal Link appears only inside WhatsApp.
	if chSignalLinkBtn != 0 {
		if which == 2 {
			chShowWindow.Call(chSignalLinkBtn, chSWShow)
		} else {
			chShowWindow.Call(chSignalLinkBtn, chSWHide)
		}
	}

	chApplyDesiredBrowserView()
	// A few cheap geometry settles handle late Chromium/MT5 compositor frames
	// without changing any HTML/CSS/JS layout.
	go func() {
		for _, d := range []time.Duration{40 * time.Millisecond, 140 * time.Millisecond, 360 * time.Millisecond} {
			time.Sleep(d)
			chMu.Lock(); stopping := chStopping; chMu.Unlock()
			if stopping { return }
			chResizeChildren()
		}
	}()
}'''
s = replace_func(s, "chSwitchView", "chPopWhatsAppTask", switch_body)

# Replace the asynchronous wait-for-cleanup EXIT path. The host disappears and is
# destroyed immediately; taskkill helpers are started detached and never waited on
# by the Win32 UI thread. This prevents both the blank four-button shell and the
# Windows "Not Responding" title during exit.
old_close_start = s.find('\tcase chWMClose:')
old_close_end = s.find('\n\t}\n\tr, _, _ := chDefWindowProc.Call', old_close_start)
if old_close_start < 0 or old_close_end < 0:
    raise SystemExit("window close switch block missing")
close_block = r'''	case chWMClose:
		// MH_PRESERVE_ORIGINAL_UI_V809: instant visual exit, zero cleanup waits.
		chShowWindow.Call(hwnd, chSWHide)
		chMu.Lock()
		if !chStopping {
			chStopping = true
			cmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd}
			windows := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd}
			chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil
			chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0
			chMu.Unlock()
			for _, child := range windows {
				if child != 0 { chShowWindow.Call(child, chSWHide) }
			}
			// Start cleanup processes and do not wait for them on this app's UI thread.
			for _, cmd := range cmds {
				if cmd != nil && cmd.Process != nil {
					_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Start()
				}
			}
		} else {
			chMu.Unlock()
		}
		chDestroyWindow.Call(hwnd)
		return 0
	case chWMShutdownDone:
		// Compatibility only; V80.9 no longer waits for this message.
		chDestroyWindow.Call(hwnd)
		return 0
	case chWMDestroy:
		chPostQuitMessage.Call(0)
		return 0'''
s = s[:old_close_start] + close_block + s[old_close_end:]

p.write_text(s, encoding="utf-8")

# Do not modify the original MH Analysis web layout. Auth remains an overlay/gate;
# the existing app.js, styles.css, Records, WhatsApp and MT5 behavior are retained.
print(MARK + ": persistent app state + native toolbar bounds + reachable footer + instant nonblocking exit")
