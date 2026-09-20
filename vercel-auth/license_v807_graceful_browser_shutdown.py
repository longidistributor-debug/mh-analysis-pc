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

# Replace the whole function rather than depending on a pre-MT5 exact text block.
# Native MT5 is NOT a Chromium window, so it keeps the existing bounded forced-kill
# behavior while the three Chromium profile windows get a graceful close first.
start = s.find('func chStopBrowsers() {')
end = s.find('\ntype chCDPPage struct {', start)
if start < 0 or end < 0:
    raise SystemExit("chStopBrowsers function boundaries missing")
new_func = r'''func chStopBrowsers() {
	// Mark shutdown first so browser goroutines that finish late cannot escape cleanup.
	chMu.Lock()
	chStopping = true
	browserCmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
	browserWindows := []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd}
	mt5Cmd := chMT5Cmd
	chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil
	chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0
	chMu.Unlock()

	// Close Chromium normally first so its persistent profiles are not marked as
	// crashed. This is especially important for AnalysisProfile on the next EXE run.
	for _, hwnd := range browserWindows {
		if hwnd != 0 {
			chPostMessageW.Call(hwnd, chWMClose, 0, 0)
		}
	}

	// Never hold the UI mutex while waiting. Give each browser a short grace period;
	// stubborn processes are still terminated so EXIT cannot hang indefinitely.
	for _, cmd := range browserCmds {
		if cmd == nil || cmd.Process == nil {
			continue
		}
		if chWaitBrowserExit(cmd, 900*time.Millisecond) {
			continue
		}
		_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
	}

	// MT5 is not Chromium and has no browser profile to flush. Preserve the existing
	// deterministic process-tree cleanup for the embedded terminal.
	if mt5Cmd != nil && mt5Cmd.Process != nil {
		_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(mt5Cmd.Process.Pid), "/T", "/F").Run()
	}
}
'''
s = s[:start] + new_func + s[end:]

p.write_text(s, encoding="utf-8")
print(MARK + ": graceful Chromium close + MT5-safe bounded cleanup applied")
