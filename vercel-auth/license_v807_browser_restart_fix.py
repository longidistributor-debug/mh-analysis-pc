from pathlib import Path

MARK = "MH_ANALYSIS_BROWSER_RESTART_V807"

p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

helper = r'''

// MH_ANALYSIS_BROWSER_RESTART_V807: Chrome/Edge app-mode can preserve a crashed
// tab/session for an app-specific profile after a forced child-process shutdown.
// Clear only transient window/session-restore state before launching Analysis.
// Persistent Local Storage, cookies and normal MH settings are intentionally kept.
func chPrepareAnalysisProfileRuntime(dir string) {
	for _, name := range []string{"SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"} {
		_ = os.Remove(filepath.Join(dir, name))
	}
	def := filepath.Join(dir, "Default")
	_ = os.RemoveAll(filepath.Join(def, "Sessions"))
	for _, name := range []string{"Last Session", "Last Tabs", "Current Session", "Current Tabs"} {
		_ = os.Remove(filepath.Join(def, name))
	}
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
\t\tchPrepareAnalysisProfileRuntime(profileDir)
\t}
\targs := []string{
\t\t"--user-data-dir=" + profileDir,
'''
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit("analysis profile launch anchor missing")

flag_anchor = '\t\t"--disable-session-crashed-bubble",\n'
flag_new = '\t\t"--disable-session-crashed-bubble",\n\t\t"--noerrdialogs",\n'
if flag_new not in s:
    if flag_anchor not in s:
        raise SystemExit("session crash flag anchor missing")
    s = s.replace(flag_anchor, flag_new, 1)

p.write_text(s, encoding="utf-8")

# Graceful Chromium shutdown is paired with launch cleanup. Without it Chrome can
# mark the persistent Analysis profile as crashed again on every EXIT.
gracious = Path("vercel-auth/license_v807_graceful_browser_shutdown.py").read_text(encoding="utf-8")
exec(compile(gracious, "vercel-auth/license_v807_graceful_browser_shutdown.py", "exec"), {"__name__": "__main__"})

print(MARK + ": transient Analysis browser state cleanup + graceful shutdown chained")
