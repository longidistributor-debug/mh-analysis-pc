from pathlib import Path

MARK = "MH_ANALYSIS_REPAINT_V808"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

# A per-run Analysis profile is already unique, so deleting every sibling profile
# at the next startup is unnecessary and can race a previous Chromium process that
# is still finishing its graceful shutdown. Keep only this process's cleanup.
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
\t// '''+MARK+''': each run already has a unique directory. Never delete another
\t// process's Chromium profile while it may still be shutting down.
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

# Patch only the Analysis branch inside chApplyDesiredBrowserView, accepting either
# the synchronous or asynchronous ShowWindow variant produced by retained patches.
fn_start = s.find('func chApplyDesiredBrowserView() {')
fn_end = s.find('\nfunc chSwitchView(', fn_start)
if fn_start < 0 or fn_end < 0:
    raise SystemExit("chApplyDesiredBrowserView boundaries missing")
block = s[fn_start:fn_end]
if MARK not in block:
    show_call = None
    for candidate in (
        'chShowWindowAsync.Call(analysis, chSWShow)',
        'chShowWindow.Call(analysis, chSWShow)',
    ):
        if candidate in block:
            show_call = candidate
            break
    if not show_call:
        raise SystemExit("Analysis show call missing")
    replacement = show_call + r'''
		chResizeChildren()
		chUpdateWindow.Call(analysis)
		chRedrawWindow.Call(analysis, 0, 0, 0x0085) // MH_ANALYSIS_REPAINT_V808
		go func(hwnd uintptr) {
			for _, delay := range []time.Duration{80 * time.Millisecond, 260 * time.Millisecond, 650 * time.Millisecond} {
				time.Sleep(delay)
				if hwnd == 0 || chStopping { return }
				chResizeChildren()
				chUpdateWindow.Call(hwnd)
				chRedrawWindow.Call(hwnd, 0, 0, 0x0085)
			}
		}(analysis)'''
    block = block.replace(show_call, replacement, 1)
    s = s[:fn_start] + block + s[fn_end:]

p.write_text(s, encoding="utf-8")
print(MARK + ": unique profile no cross-process deletion + forced Analysis compositor repaint applied")
