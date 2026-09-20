from pathlib import Path

MARK = "MH_ANALYSIS_REPAINT_V808"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

# Every Analysis run already has a unique Chromium profile. Do not delete sibling
# runtime profiles at startup because another EXE/browser may still be shutting down.
old_cleanup = '''\troot := filepath.Join(base, "MHAnalysis", "AnalysisRuntime")
\t_ = os.MkdirAll(root, 0755)
\t// Best-effort cleanup of abandoned runtime profiles from older EXE processes.
\tif entries, err := os.ReadDir(root); err == nil {
\t\tfor _, e := range entries {
\t\t\tif e.IsDir() {
\t\t\t\t_ = os.RemoveAll(filepath.Join(root, e.Name()))
\t\t\t}
\t\t}
\t}
\tchAnalysisRuntimeDir = filepath.Join(root, fmt.Sprintf("run-%d-%d", os.Getpid(), time.Now().UnixNano()))'''
new_cleanup = '''\troot := filepath.Join(base, "MHAnalysis", "AnalysisRuntime")
\t_ = os.MkdirAll(root, 0755)
\t// '''+MARK+''': each process owns only its own unique runtime profile.
\tchAnalysisRuntimeDir = filepath.Join(root, fmt.Sprintf("run-%d-%d", os.Getpid(), time.Now().UnixNano()))'''
if new_cleanup not in s:
    if old_cleanup not in s:
        raise SystemExit("V807 AnalysisRuntime cleanup anchor missing")
    s = s.replace(old_cleanup, new_cleanup, 1)

proc_anchor = '\tchUpdateWindow          = chUser32.NewProc("UpdateWindow")\n'
proc_new = '\tchUpdateWindow          = chUser32.NewProc("UpdateWindow")\n\tchRedrawWindow          = chUser32.NewProc("RedrawWindow") // '+MARK+'\n'
if proc_new not in s:
    if proc_anchor not in s:
        raise SystemExit("UpdateWindow proc anchor missing")
    s = s.replace(proc_anchor, proc_new, 1)

# Force Analysis to show/resize/repaint from the native switch path itself. This is
# independent of how retained patches implement chApplyDesiredBrowserView.
switch_anchor = '''func chSwitchView(which int) {
\tchViewMu.Lock()
\tchDesiredView = which
\tchViewMu.Unlock()
'''
switch_new = '''func chSwitchView(which int) {
\tchViewMu.Lock()
\tchDesiredView = which
\tchViewMu.Unlock()

\t// '''+MARK+''': eliminate stale white Chromium backing frames after login/restart.
\tif which == 1 {
\t\tgo func() {
\t\t\tfor _, delay := range []time.Duration{20 * time.Millisecond, 100 * time.Millisecond, 260 * time.Millisecond, 650 * time.Millisecond} {
\t\t\t\ttime.Sleep(delay)
\t\t\t\tchMu.Lock()
\t\t\t\thwnd := chAnalysisWnd
\t\t\t\tstopping := chStopping
\t\t\t\tchMu.Unlock()
\t\t\t\tif stopping || hwnd == 0 { continue }
\t\t\t\tchShowWindowAsync.Call(hwnd, chSWShow)
\t\t\t\tchResizeChildren()
\t\t\t\tchUpdateWindow.Call(hwnd)
\t\t\t\tchRedrawWindow.Call(hwnd, 0, 0, 0x0085)
\t\t\t}
\t\t}()
\t}
'''
if switch_new not in s:
    if switch_anchor not in s:
        raise SystemExit("chSwitchView anchor missing")
    s = s.replace(switch_anchor, switch_new, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": unique runtime profile + Analysis switch repaint hardening applied")
