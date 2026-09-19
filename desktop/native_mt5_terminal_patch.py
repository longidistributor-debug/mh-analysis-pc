from pathlib import Path

MARK='MH_NATIVE_MT5_TERMINAL_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK in s:
    print('PASS native MT5 patch already applied')
    raise SystemExit(0)

# This patch runs after records_feature_patch.py. It adds a fourth tab backed by
# the locally installed native MetaTrader 5 terminal. No broker web page,
# Exness URL, WebView or browser profile is used for this tab.
s=rep(s,
'''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchRecordsWnd  uintptr
\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchRecordsCmd  *exec.Cmd
\tbtnRecords    uintptr
\tchBrowserPath string
''',
'''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchRecordsWnd  uintptr
\tchMT5Wnd      uintptr // '''+MARK+'''\n\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchRecordsCmd  *exec.Cmd
\tchMT5Cmd      *exec.Cmd
\tbtnRecords    uintptr
\tbtnMT5        uintptr
\tchBrowserPath string
''','mt5 vars')

s=rep(s,
'\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n)',
'\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n\tidMT5           = 1004 // '+MARK+'\n)',
'mt5 id')

s=rep(s,
'''\tif chRecordsWnd != 0 {
\t\tchSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''',
'''\tif chRecordsWnd != 0 {
\t\tchSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
\tif chMT5Wnd != 0 {
\t\tchSetWindowPos.Call(chMT5Wnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''','mt5 resize')

s=rep(s,
'''\tif btnRecords != 0 {
\t\tchMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 452, 7, 145, 30, 1)
\t}
''',
'''\tif btnRecords != 0 {
\t\tchMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
\t}
\tif btnMT5 != 0 {
\t\tchMoveWindow.Call(btnMT5, 452, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
\t}
''','mt5 button layout')

s=rep(s,
'''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\trecords := chRecordsWnd
\tchMu.Unlock()
''',
'''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\trecords := chRecordsWnd
\tmt5 := chMT5Wnd
\tchMu.Unlock()
''','mt5 desired vars')

old='''\tif which == 2 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWShow) }
\t\treturn
\t}
\tif which == 3 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWShow) }
\t\treturn
\t}
\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }
'''
new='''\tif which == 2 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWShow) }
\t\treturn
\t}
\tif which == 3 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWShow) }
\t\treturn
\t}
\tif which == 4 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif mt5 != 0 { chShowWindowAsync.Call(mt5, chSWShow) }
\t\treturn
\t}
\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\tif mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }
'''
s=rep(s,old,new,'mt5 view logic')

s=rep(s,
'''\t\tcase idRecords:
\t\t\tchSwitchView(3)
\t\tcase chIDSignalLink:
''',
'''\t\tcase idRecords:
\t\t\tchSwitchView(3)
\t\tcase idMT5:
\t\t\tchSwitchView(4)
\t\t\tgo func() {
\t\t\t\tif err := chEnsureMT5Terminal(); err != nil {
\t\t\t\t\tmessageBox(hostHWND, err.Error(), "MT5 System", 0x10)
\t\t\t\t}
\t\t\t}()
\t\tcase chIDSignalLink:
''','mt5 command')

s=rep(s,
'''\tbtnRecords, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
\t\tchWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 452, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''',
'''\tbtnRecords, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
\t\tchWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
\t)
\tbtnMT5, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("MT5 System"))),
\t\tchWSChild|chWSVisible, 452, 7, 140, 30, hostHWND, idMT5, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 600, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''','mt5 button create')

s=rep(s,
'''\t\tchSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''',
'''\t\tchSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(btnMT5, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''','mt5 dark theme')

helper='''

// MH_NATIVE_MT5_TERMINAL_V796
func chMT5Executable() (string, error) {
\tif p := strings.TrimSpace(os.Getenv("MH_MT5_PATH")); p != "" {
\t\tif st, err := os.Stat(p); err == nil && !st.IsDir() { return p, nil }
\t\treturn "", fmt.Errorf("MH_MT5_PATH does not point to a valid terminal executable: %s", p)
\t}
\tvar roots []string
\tfor _, e := range []string{"PROGRAMFILES", "PROGRAMFILES(X86)"} {
\t\tif p := strings.TrimSpace(os.Getenv(e)); p != "" { roots = append(roots, p) }
\t}
\tif p := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); p != "" { roots = append(roots, filepath.Join(p, "Programs")) }
\tcandidates := []string{}
\tseen := map[string]bool{}
\tadd := func(p string) {
\t\tkey := strings.ToLower(filepath.Clean(p)); if seen[key] { return }; seen[key] = true; candidates = append(candidates, p)
\t}
\tfor _, root := range roots {
\t\tadd(filepath.Join(root, "MetaTrader 5", "terminal64.exe"))
\t\tadd(filepath.Join(root, "MetaTrader 5", "terminal.exe"))
\t\tentries, _ := os.ReadDir(root)
\t\tfor _, e := range entries {
\t\t\tif !e.IsDir() { continue }
\t\t\td1 := filepath.Join(root, e.Name())
\t\t\tadd(filepath.Join(d1, "terminal64.exe")); add(filepath.Join(d1, "terminal.exe"))
\t\t\tsubs, _ := os.ReadDir(d1)
\t\t\tfor _, se := range subs {
\t\t\t\tif !se.IsDir() { continue }
\t\t\t\td2 := filepath.Join(d1, se.Name())
\t\t\t\tadd(filepath.Join(d2, "terminal64.exe")); add(filepath.Join(d2, "terminal.exe"))
\t\t\t}
\t\t}
\t}
\tif p, err := exec.LookPath("terminal64.exe"); err == nil { add(p) }
\tif p, err := exec.LookPath("terminal.exe"); err == nil { add(p) }
\tfor _, p := range candidates {
\t\tif st, err := os.Stat(p); err == nil && !st.IsDir() { return p, nil }
\t}
\treturn "", errors.New("MetaTrader 5 terminal64.exe was not found. Install your broker's MT5 terminal, then reopen MH Analysis. If you have more than one MT5 installation, set MH_MT5_PATH to the terminal64.exe you want to use.")
}

func chFindProcessWindow(pid uint32) uintptr {
\tvar found uintptr
\tcb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
\t\tvar wp uint32
\t\tchGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))
\t\tif wp != pid { return 1 }
\t\tvis, _, _ := chIsWindowVisible.Call(hwnd)
\t\tif vis == 0 { return 1 }
\t\tfound = hwnd
\t\treturn 0
\t})
\tchEnumWindows.Call(cb, 0)
\treturn found
}

func chWaitForProcessWindow(pid uint32, timeout time.Duration) uintptr {
\tdeadline := time.Now().Add(timeout)
\tfor time.Now().Before(deadline) {
\t\tif h := chFindProcessWindow(pid); h != 0 { return h }
\t\ttime.Sleep(120 * time.Millisecond)
\t}
\treturn 0
}

func chEnsureMT5Terminal() error {
\tchMu.Lock()
\tif chMT5Wnd != 0 {
\t\tchMu.Unlock(); chApplyDesiredBrowserView(); return nil
\t}
\tif chMT5Cmd != nil {
\t\tchMu.Unlock(); return nil
\t}
\tchMu.Unlock()

\tpath, err := chMT5Executable()
\tif err != nil { return err }
\tcmd := exec.Command(path)
\tif err := cmd.Start(); err != nil { return fmt.Errorf("Could not start MT5: %w", err) }

\tchMu.Lock()
\tif chStopping {
\t\tchMu.Unlock(); _ = cmd.Process.Kill(); return errors.New("MH Analysis is closing")
\t}
\tchMT5Cmd = cmd
\tchMu.Unlock()

\twnd := chWaitForProcessWindow(uint32(cmd.Process.Pid), 35*time.Second)
\tif wnd == 0 {
\t\tchMu.Lock(); if chMT5Cmd == cmd { chMT5Cmd = nil }; chMu.Unlock()
\t\treturn errors.New("MT5 started but its main window could not be embedded. Close any separately running MT5 instance and try again.")
\t}
\tchShowWindow.Call(wnd, chSWHide)
\tchAttachBrowser(wnd)
\tchMu.Lock()
\tif chStopping {
\t\tchMu.Unlock(); _ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run(); return errors.New("MH Analysis is closing")
\t}
\tchMT5Wnd = wnd
\tchMu.Unlock()
\tchResizeChildren()
\tchApplyDesiredBrowserView()
\treturn nil
}
'''

s=rep(s,'\nfunc runChromeHost() {',helper+'\nfunc runChromeHost() {','mt5 helpers')

s=rep(s,
'''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd = nil, nil, nil
\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd = 0, 0, 0
''',
'''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd}
\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil
\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0
''','mt5 shutdown')

p.write_text(s,encoding='utf-8')
print('PASS native MT5 terminal: fourth embedded native tab; no browser broker dependency')