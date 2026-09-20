from pathlib import Path

MARK = "MH_GRACEFUL_BROWSER_SHUTDOWN_V807"

p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

# Native PostMessage for gracefully asking embedded Chromium app windows to close.
proc_anchor = '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n'
proc_new = '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchPostMessageW          = chUser32.NewProc("PostMessageW") // '+MARK+'\n'
if proc_new not in s:
    if proc_anchor not in s:
        raise SystemExit("PostMessage proc anchor missing")
    s = s.replace(proc_anchor, proc_new, 1)

helper = r'''

// MH_GRACEFUL_BROWSER_SHUTDOWN_V807: give Chromium a short chance to flush its
// profile/session metadata normally. Forced taskkill remains the fallback only.
func chWaitBrowserExit(cmd *exec.Cmd, timeout time.Duration) bool {
	if cmd == nil || cmd.Process == nil {
		return true
	}
	done := make(chan struct{}, 1)
	go func() {
		_ = cmd.Wait()
		done <- struct{}{}
	}()
	select {
	case <-done:
		return true
	case <-time.After(timeout):
		return false
	}
}
'''
anchor = '\nfunc chStopBrowsers() {'
if helper not in s:
    if anchor not in s:
        raise SystemExit("chStopBrowsers anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

old = '''func chStopBrowsers() {
	// Mark shutdown first so browser goroutines that finish late cannot escape cleanup.
	chMu.Lock()
	chStopping = true
	cmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
	chAnalysisCmd, chWhatsappCmd, chRecordsCmd = nil, nil, nil
	chAnalysisWnd, chWhatsappWnd, chRecordsWnd = 0, 0, 0
	chMu.Unlock()

	// Never hold the UI mutex while waiting for taskkill.
	for _, cmd := range cmds {
		if cmd != nil && cmd.Process != nil {
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
		}
	}
}'''
new = '''func chStopBrowsers() {
	// Mark shutdown first so browser goroutines that finish late cannot escape cleanup.
	chMu.Lock()
	chStopping = true
	cmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
	windows := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd}
	chAnalysisCmd, chWhatsappCmd, chRecordsCmd = nil, nil, nil
	chAnalysisWnd, chWhatsappWnd, chRecordsWnd = 0, 0, 0
	chMu.Unlock()

	// Ask every embedded Chromium window to close normally first. This prevents the
	// persistent Analysis profile from being marked as crashed, which previously
	// produced an all-white second launch.
	for _, hwnd := range windows {
		if hwnd != 0 {
			chPostMessageW.Call(hwnd, chWMClose, 0, 0)
		}
	}

	// Never hold the UI mutex while waiting. Give each browser a short grace period;
	// stubborn processes are still terminated so EXIT cannot hang indefinitely.
	for _, cmd := range cmds {
		if cmd == nil || cmd.Process == nil {
			continue
		}
		if chWaitBrowserExit(cmd, 900*time.Millisecond) {
			continue
		}
		_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
	}
}'''
if old in s:
    s = s.replace(old, new, 1)
elif MARK not in s or 'windows := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd}' not in s:
    raise SystemExit("expected browser shutdown block not found")

p.write_text(s, encoding="utf-8")
print(MARK + ": graceful Chromium close with bounded forced-kill fallback applied")
