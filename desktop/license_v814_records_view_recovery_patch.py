from pathlib import Path

MARK = "MH_RECORDS_VIEW_RECOVERY_V814"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

# Records is a separate Chromium child. If that browser starts late or a stale
# RecordsProfile prevents Chrome from producing a window, selecting Records leaves
# only the host background visible. Give Records a fresh per-run profile, retry its
# launch, and keep all Records browser/focus work off the native Win32 UI thread.

anchor = "\tchStopping    bool\n"
replacement = anchor + "\tchRecordsStarting bool // " + MARK + "\n"
if replacement not in s:
    if anchor not in s:
        raise SystemExit("chStopping var anchor missing")
    s = s.replace(anchor, replacement, 1)

insert_anchor = "\nfunc chSwitchView(which int) {"
helper = r'''

func chEnsureRecordsBrowser() {
	chMu.Lock()
	if chStopping || chRecordsWnd != 0 || chRecordsStarting {
		chMu.Unlock()
		return
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
		if stopping { return }

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
			return
		}
		if chRecordsWnd != 0 {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Start()
			return
		}
		chRecordsCmd, chRecordsWnd = cmd, wnd
		chMu.Unlock()

		// Cross-process window work must never happen while chMu is held.
		chAttachBrowser(wnd)
		chSetEmbeddedVisible(wnd, false)
		chResizeChildren()
		chApplyDesiredBrowserView()
		return
	}
}
'''
if helper not in s:
    if insert_anchor not in s:
        raise SystemExit("chSwitchView anchor missing")
    s = s.replace(insert_anchor, helper + insert_anchor, 1)

# V80.9 made chApplyDesiredBrowserView synchronous. Records launch/reframe/focus can
# involve another process, so keep it away from the native message thread.
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
\t\tchEnsureRecordsBrowser()
\t\tchApplyDesiredBrowserView()
\t\treturn
\t}

\tchApplyDesiredBrowserView()'''
if switch_new not in s:
    if switch_old not in s:
        raise SystemExit("chSwitchView body anchor missing")
    s = s.replace(switch_old, switch_new, 1)

# Most important: the actual Records WM_COMMAND returns immediately. The worker
# performs chSwitchView(3), so even a slow/crashed Chromium child can never freeze
# the outer MH Analysis EXE or make the Records button look dead.
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

# Use the same recovery helper during startup. A transient startup failure is no
# longer permanent because clicking Records invokes the helper again.
start = s.find('''\tgo func() {\n\t\ttime.Sleep(250 * time.Millisecond)\n\t\trecordsDebugPort := 0''')
end_marker = '''\n\t}()\n\n\tvar m chMsg'''
if start >= 0:
    end = s.find(end_marker, start)
    if end < 0:
        raise SystemExit("Records startup block end missing")
    new_block = '''\tgo func() {\n\t\ttime.Sleep(250 * time.Millisecond)\n\t\tchEnsureRecordsBrowser()\n\t}()'''
    s = s[:start] + new_block + s[end + len('\n\t}()'):]
elif 'chEnsureRecordsBrowser()\n\t}()\n\n\tvar m chMsg' not in s:
    raise SystemExit("Records startup block not found")

p.write_text(s, encoding="utf-8")
print(MARK + ": fresh Records runtime + retries + immediate native command + no cross-process work under mutex")
