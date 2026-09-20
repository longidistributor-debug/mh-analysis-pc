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
# launch, and make native tab switching non-blocking so the EXE UI never freezes.

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
		chAttachBrowser(chRecordsWnd)
		chSetEmbeddedVisible(chRecordsWnd, false)
		chMu.Unlock()

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

# V80.9 made chApplyDesiredBrowserView synchronous. That can block WM_COMMAND while
# Chromium is being reframed/focused, which makes the Records button appear dead and
# can show Windows Not Responding. Restore the original non-blocking native-tab rule.
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
\t\t// Never block the host message thread while Records Chromium starts or
\t\t// reframes. Keep the current view visible until Records is actually ready.
\t\tgo func() {
\t\t\tchEnsureRecordsBrowser()
\t\t\tfor i := 0; i < 220; i++ {
\t\t\t\tchMu.Lock()
\t\t\t\tready := chRecordsWnd != 0
\t\t\t\tstarting := chRecordsStarting
\t\t\t\tstopping := chStopping
\t\t\t\tchMu.Unlock()
\t\t\t\tif stopping { return }
\t\t\t\tif ready { chApplyDesiredBrowserView(); return }
\t\t\t\tif !starting { return }
\t\t\t\ttime.Sleep(100 * time.Millisecond)
\t\t\t}
\t\t}()
\t\treturn
\t}

\tgo chApplyDesiredBrowserView()'''
if switch_new not in s:
    if switch_old not in s:
        raise SystemExit("chSwitchView body anchor missing")
    s = s.replace(switch_old, switch_new, 1)

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
print(MARK + ": fresh Records runtime + retries + non-blocking native Records tab recovery")
