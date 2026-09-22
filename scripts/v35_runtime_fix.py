from pathlib import Path

p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8-sig')
# Prewarm auxiliary embedded views once after the host is visible. This keeps click handlers show/hide only.
s=s.replace('''\twv2Resize()\n\tb.Focus()\n\n\tvar m chMsg''','''\twv2Resize()\n\tb.Focus()\n\n\t// V35_PREWARM_AUX: create WhatsApp and Records once after first paint.\n\t// User clicks then only switch already-attached children; no repeated launch race.\n\tgo func() {\n\t\ttime.Sleep(300 * time.Millisecond)\n\t\twv2EnsureAuxBrowser(2)\n\t\twv2EnsureAuxBrowser(3)\n\t\twv2SetDesiredView(1)\n\t\tchApplyDesiredBrowserView()\n\t}()\n\n\tvar m chMsg''')
# First click remains authoritative; if prewarm is still completing, one background ensure is enough.
s=s.replace('''\tif which == 2 && chWhatsappWnd == 0 {\n\t\t// V32: create/attach before returning so one click is enough.\n\t\twv2EnsureAuxBrowser(2)\n\t}\n\tif which == 3 && chRecordsWnd == 0 {\n\t\t// V32: Records must be attached and visible on the first click.\n\t\twv2EnsureAuxBrowser(3)\n\t}''','''\tif which == 2 && chWhatsappWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(2)\n\t\treturn\n\t}\n\tif which == 3 && chRecordsWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(3)\n\t\treturn\n\t}''')
p.write_text(s,encoding='utf-8')

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8-sig')
# Native process-image lookup: no PowerShell and no dependence on broker window title.
s=s.replace('''\tchGetCurrentThreadId    = chKernel32.NewProc("GetCurrentThreadId")''','''\tchGetCurrentThreadId    = chKernel32.NewProc("GetCurrentThreadId")\n\tchOpenProcess           = chKernel32.NewProc("OpenProcess")\n\tchCloseHandle           = chKernel32.NewProc("CloseHandle")\n\tchQueryFullProcessImageName = chKernel32.NewProc("QueryFullProcessImageNameW")''')
marker='''// V32: locate an existing MetaTrader 5 top-level window.'''
helper=r'''// V35_MT5_PROCESS_IMAGE: identify broker MT5 by the owning executable, not window title.
func chProcessImageBaseV35(pid uint32) string {
	const processQueryLimitedInformation = 0x1000
	h, _, _ := chOpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
	if h == 0 { return "" }
	defer chCloseHandle.Call(h)
	buf := make([]uint16, 32768)
	n := uint32(len(buf))
	r, _, _ := chQueryFullProcessImageName.Call(h, 0, uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&n)))
	if r == 0 || n == 0 { return "" }
	return strings.ToLower(filepath.Base(syscall.UTF16ToString(buf[:n])))
}

func chFindMT5ByProcessImageV35() uintptr {
	var found uintptr
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		if hwnd == 0 || hwnd == hostHWND { return 1 }
		var pid uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
		name := chProcessImageBaseV35(pid)
		if name == "terminal64.exe" || name == "terminal.exe" {
			found = hwnd
			return 0
		}
		return 1
	})
	chEnumWindows.Call(cb, 0)
	return found
}

'''
s=s.replace(marker,helper+marker)
# Prefer deterministic process-image detection before legacy title fallback.
s=s.replace('''\t// V33: first embed the already installed/running broker terminal. Never deliberately open it externally.\n\tif existing := chFindInstalledMT5WindowV33(); existing != 0 {''','''\t// V35: first locate the real installed/running terminal by process image.\n\tif existing := chFindMT5ByProcessImageV35(); existing != 0 {\n\t\tif chEmbedMT5V33(existing) {\n\t\t\tgo mt5ApplyLatestQueued()\n\t\t\treturn nil\n\t\t}\n\t}\n\t// Legacy broker-title fallback only after process-image detection.\n\tif existing := chFindInstalledMT5WindowV33(); existing != 0 {''')
# If a launch hands off to an existing broker process, detect it by image first.
s=s.replace('''\tif wnd == 0 {\n\t\twnd = chFindInstalledMT5WindowV33()\n\t}''','''\tif wnd == 0 {\n\t\twnd = chFindMT5ByProcessImageV35()\n\t}\n\tif wnd == 0 {\n\t\twnd = chFindInstalledMT5WindowV33()\n\t}''')
p.write_text(s,encoding='utf-8')

# bump canonical version only; no historical patches
for fn,old,new in [('updater.go','V.34','V.35'),('license_auth.go','V.34','V.35')]:
 p=Path(fn); x=p.read_text(encoding='utf-8-sig'); p.write_text(x.replace(old,new),encoding='utf-8')
print('V35 runtime fix applied')
