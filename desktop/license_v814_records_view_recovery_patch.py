from pathlib import Path

MARK = "MH_RECORDS_VIEW_RECOVERY_V814"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

# Records is a separate Chromium child. Start it only when the user requests the
# Records tab. Until that child is fully attached, keep the current working view
# visible so Records can never produce the blank host screen reported by the user.

anchor = "\tchStopping    bool\n"
replacement = anchor + "\tchRecordsStarting bool // " + MARK + "\n"
if replacement not in s:
    if anchor not in s:
        raise SystemExit("chStopping var anchor missing")
    s = s.replace(anchor, replacement, 1)

insert_anchor = "\nfunc chSwitchView(which int) {"
helper = r'''

func chEnsureRecordsBrowser() bool {
	chMu.Lock()
	if chStopping {
		chMu.Unlock()
		return false
	}
	if chRecordsWnd != 0 {
		chMu.Unlock()
		return true
	}
	if chRecordsStarting {
		chMu.Unlock()
		// Another Records request is already starting it. Wait boundedly without
		// touching the native UI thread.
		for i := 0; i < 260; i++ {
			time.Sleep(100 * time.Millisecond)
			chMu.Lock()
			ready := chRecordsWnd != 0
			starting := chRecordsStarting
			stopping := chStopping
			chMu.Unlock()
			if ready { return true }
			if stopping || !starting { return false }
		}
		return false
	}
	chRecordsStarting = true
	chMu.Unlock()

	defer func() {
		chMu.Lock()
		chRecordsStarting = false
		chMu.Unlock()
	}()

	target := strings.TrimRight(serverURL, "/") + "/records.html"
	for attempt := 0; attempt < 3; attempt++ {
		chMu.Lock()
		stopping := chStopping
		chMu.Unlock()
		if stopping { return false }

		profile := fmt.Sprintf("RecordsRuntime-%d-%d", os.Getpid(), attempt)
		cmd, wnd, err := chLaunchBrowser(profile, target, 0)
		if err != nil || wnd == 0 {
			if cmd != nil && cmd.Process != nil {
				_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Start()
			}
			time.Sleep(time.Duration(250+attempt*250) * time.Millisecond)
			continue
		}

		chMu.Lock()
		if chStopping {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Start()
			return false
		}
		if chRecordsWnd != 0 {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Start()
			return true
		}
		chRecordsCmd, chRecordsWnd = cmd, wnd
		chMu.Unlock()

		// Cross-process window work must never happen while chMu is held.
		chAttachBrowser(wnd)
		chSetEmbeddedVisible(wnd, false)
		chResizeChildren()
		return true
	}
	return false
}
'''
if helper not in s:
    if insert_anchor not in s:
        raise SystemExit("chSwitchView anchor missing")
    s = s.replace(insert_anchor, helper + insert_anchor, 1)

# Records request stays on a worker. Do not call chApplyDesiredBrowserView until a
# real Records child exists. If Chrome cannot start, restore desired view=Analysis
# while leaving the already-visible Analysis surface untouched.
switch_old = '''\tif chSignalLinkBtn != 0 {
\t\tif which == 2 {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWShow)
\t\t} else {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWHide)
\t\t}
\t}

\tchApplyDesiredBrowserView()'''
switch_new = '''\tif chSignalLinkBtn != 0 {
\t\tif which == 2 {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWShow)
\t\t} else {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWHide)
\t\t}
\t}

\tif which == 3 {
\t\tif chEnsureRecordsBrowser() {
\t\t\tchApplyDesiredBrowserView()
\t\t} else {
\t\t\tchViewMu.Lock()
\t\t\tif chDesiredView == 3 { chDesiredView = 1 }
\t\t\tchViewMu.Unlock()
\t\t}
\t\treturn
\t}

\tchApplyDesiredBrowserView()'''
if switch_new not in s:
    if switch_old not in s:
        raise SystemExit("chSwitchView body anchor missing")
    s = s.replace(switch_old, switch_new, 1)

# Native Records button returns instantly; all Chromium startup/focus/resize work
# runs on a worker goroutine.
cmd_old = '''\t\tcase idRecords:
\t\t\tchSwitchView(3)
'''
cmd_new = '''\t\tcase idRecords:
\t\t\tgo chSwitchView(3) // ''' + MARK + ''': never block native UI thread
'''
if cmd_new not in s:
    if cmd_old not in s:
        raise SystemExit("Records WM_COMMAND anchor missing")
    s = s.replace(cmd_old, cmd_new, 1)

# Remove the old eager Records startup completely. Records is launched lazily on the
# first Records click; this eliminates the startup race where desired view=3 could
# hide Analysis before the Records child existed.
start = s.find('''\tgo func() {\n\t\ttime.Sleep(250 * time.Millisecond)\n\t\trecordsDebugPort := 0''')
end_marker = '''\n\t}()\n\n\tvar m chMsg'''
if start >= 0:
    end = s.find(end_marker, start)
    if end < 0:
        raise SystemExit("Records startup block end missing")
    replacement_block = '''\t// ''' + MARK + ''': Records browser is lazy-started by the Records button.\n'''
    s = s[:start] + replacement_block + s[end + len('\n\t}()'):]
else:
    raise SystemExit("original eager Records startup block not found")

p.write_text(s, encoding="utf-8")
print(MARK + ": lazy Records launch + preserve current view + retries + immediate native command")
