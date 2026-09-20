from pathlib import Path

MARK = "MH_ANALYSIS_BROWSER_RESTART_V807"

p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

# The Analysis web app runs on a dynamic localhost port and does not need a shared
# Chromium profile. Reusing one app-mode profile across EXE processes allowed a
# previous Chrome process/crash state to own the next launch and render white.
# Give every MH Analysis process its own browser runtime profile instead.
var_anchor = '\tchBrowserPath string\n'
var_new = '\tchBrowserPath string\n\tchAnalysisRuntimeDir string // '+MARK+'\n'
if var_new not in s:
    if var_anchor not in s:
        raise SystemExit("analysis runtime profile var anchor missing")
    s = s.replace(var_anchor, var_new, 1)

helper = r'''

// MH_ANALYSIS_BROWSER_RESTART_V807: Analysis Chromium gets an isolated runtime
// profile for this EXE process only. WhatsApp keeps its persistent profile so its
// QR/login session is not affected. Dynamic localhost app state is server/local
// app state, not browser-account state, so cross-run Chromium profile reuse is
// unnecessary and was the source of the restart-white regression.
func chAnalysisRuntimeProfileDir() string {
	if chAnalysisRuntimeDir != "" {
		return chAnalysisRuntimeDir
	}
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	root := filepath.Join(base, "MHAnalysis", "AnalysisRuntime")
	_ = os.MkdirAll(root, 0755)
	// Best-effort cleanup of abandoned runtime profiles from older EXE processes.
	if entries, err := os.ReadDir(root); err == nil {
		for _, e := range entries {
			if e.IsDir() {
				_ = os.RemoveAll(filepath.Join(root, e.Name()))
			}
		}
	}
	chAnalysisRuntimeDir = filepath.Join(root, fmt.Sprintf("run-%d-%d", os.Getpid(), time.Now().UnixNano()))
	_ = os.MkdirAll(chAnalysisRuntimeDir, 0755)
	return chAnalysisRuntimeDir
}
'''
anchor = '\nfunc chLaunchBrowser(profile, target string, debugPort int) (*exec.Cmd, uintptr, error) {'
if helper not in s:
    if anchor not in s:
        raise SystemExit("chLaunchBrowser anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

old = '''\targs := []string{
\t\t"--user-data-dir=" + chProfileDir(profile),
'''
new = '''\tprofileDir := chProfileDir(profile)
\tif profile == "AnalysisProfile" {
\t\tprofileDir = chAnalysisRuntimeProfileDir()
\t}
\targs := []string{
\t\t"--user-data-dir=" + profileDir,
'''
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    # A previous V80.7 patch form may already have a profileDir block. Normalize it.
    old2 = '''\tprofileDir := chProfileDir(profile)
\tif profile == "AnalysisProfile" {
\t\tchPrepareAnalysisProfileRuntime(profileDir)
\t}
\targs := []string{
\t\t"--user-data-dir=" + profileDir,
'''
    if old2 in s:
        s = s.replace(old2, new, 1)
    elif new not in s:
        raise SystemExit("analysis profile launch anchor missing")

flag_anchor = '\t\t"--disable-session-crashed-bubble",\n'
flag_new = '\t\t"--disable-session-crashed-bubble",\n\t\t"--noerrdialogs",\n'
if flag_new not in s:
    if flag_anchor not in s:
        raise SystemExit("session crash flag anchor missing")
    s = s.replace(flag_anchor, flag_new, 1)

p.write_text(s, encoding="utf-8")

# Graceful Chromium shutdown is still retained to avoid orphan processes. It is a
# fallback hygiene layer; profile isolation is what guarantees the next run cannot
# be hijacked by stale Analysis Chrome state.
gracious = Path("vercel-auth/license_v807_graceful_browser_shutdown.py").read_text(encoding="utf-8")
exec(compile(gracious, "vercel-auth/license_v807_graceful_browser_shutdown.py", "exec"), {"__name__": "__main__"})

# Remove the runtime directory after browser cleanup. This is intentionally after
# chStopBrowsers so Chrome is no longer using its files.
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
cleanup_anchor = '''\tif mt5Cmd != nil && mt5Cmd.Process != nil {
\t\t_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(mt5Cmd.Process.Pid), "/T", "/F").Run()
\t}
}'''
cleanup_new = '''\tif mt5Cmd != nil && mt5Cmd.Process != nil {
\t\t_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(mt5Cmd.Process.Pid), "/T", "/F").Run()
\t}
\tif chAnalysisRuntimeDir != "" {
\t\t_ = os.RemoveAll(chAnalysisRuntimeDir)
\t\tchAnalysisRuntimeDir = ""
\t}
}'''
if cleanup_new not in s:
    if cleanup_anchor not in s:
        raise SystemExit("analysis runtime cleanup anchor missing")
    s = s.replace(cleanup_anchor, cleanup_new, 1)
p.write_text(s, encoding="utf-8")

print(MARK + ": isolated per-process Analysis Chromium profile + graceful cleanup applied")
