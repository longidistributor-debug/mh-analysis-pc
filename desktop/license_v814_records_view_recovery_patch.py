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
# launch, and ensure the native Records tab can recover the child on demand.

# Track one Records launch attempt at a time.
anchor = "\tchStopping    bool\n"
replacement = anchor + "\tchRecordsStarting bool // " + MARK + "\n"
if replacement not in s:
    if anchor not in s:
        raise SystemExit("chStopping var anchor missing")
    s = s.replace(anchor, replacement, 1)

# Insert a robust Records launcher before chSwitchView. It deliberately uses a
# per-process Records browser profile because Records data itself is stored by the
# local Go backend, not browser localStorage. This avoids stale/crashed Chrome state.
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
		// Another path may have completed while this process was starting.
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

# When Records is clicked before its browser is ready, start/retry it. Keep the
# current working view visible until Records has attached instead of showing a blank
# host. chEnsureRecordsBrowser applies the requested Records view as soon as ready.
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
\t\tchMu.Lock()
\t\tready := chRecordsWnd != 0
\t\tchMu.Unlock()
\t\tif !ready {
\t\t\tgo chEnsureRecordsBrowser()
\t\t\treturn
\t\t}
\t}

\tchApplyDesiredBrowserView()'''
if switch_new not in s:
    if switch_old not in s:
        raise SystemExit("chSwitchView body anchor missing")
    s = s.replace(switch_old, switch_new, 1)

# Replace the eager Records launch block with the same recovery helper. The helper
# is also called on click, so a transient startup failure no longer permanently
# breaks Records for the entire EXE session.
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
print(MARK + ": Records browser uses fresh per-run profile, 3 launch retries, and on-demand recovery")
