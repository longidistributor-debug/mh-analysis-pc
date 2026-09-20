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

# When returning from WhatsApp/login to Analysis, force Chromium's compositor to
# resize/repaint more than once. This prevents a stale white backing surface from
# being the first visible frame after a fast restart/view switch.
old_show = '''\tif analysis != 0 {
\t\tchShowWindowAsync.Call(analysis, chSWShow)
\t}
}'''
new_show = '''\tif analysis != 0 {
\t\tchShowWindowAsync.Call(analysis, chSWShow)
\t\tchResizeChildren()
\t\tchUpdateWindow.Call(analysis)
\t\tchRedrawWindow.Call(analysis, 0, 0, 0x0085) // RDW_INVALIDATE|RDW_UPDATENOW|RDW_ALLCHILDREN
\t\tgo func(hwnd uintptr) {
\t\t\tfor _, delay := range []time.Duration{80 * time.Millisecond, 260 * time.Millisecond, 650 * time.Millisecond} {
\t\t\t\ttime.Sleep(delay)
\t\t\t\tif hwnd == 0 || chStopping { return }
\t\t\t\tchResizeChildren()
\t\t\t\tchUpdateWindow.Call(hwnd)
\t\t\t\tchRedrawWindow.Call(hwnd, 0, 0, 0x0085)
\t\t\t}
\t\t}(analysis)
\t}
}'''
if new_show not in s:
    if old_show not in s:
        raise SystemExit("Analysis show anchor missing")
    s = s.replace(old_show, new_show, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": unique profile no cross-process deletion + forced Analysis compositor repaint applied")
