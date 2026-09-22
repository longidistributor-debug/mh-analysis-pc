from pathlib import Path

# MH Analysis V.27.1 hotfix
# 1) Fix Windows MachineGuid registry path used for secure device identity.
# 2) Serialize device identity creation inside one process.
# 3) Stop pre-warming external WhatsApp/Records browser windows at app startup.

lic = Path('license_auth.go')
s = lic.read_text(encoding='utf-8-sig')
old = r'registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\\Microsoft\\Cryptography`, registry.QUERY_VALUE)'
new = r'registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Cryptography`, registry.QUERY_VALUE)'
if old not in s:
    raise SystemExit('V271: malformed MachineGuid registry path marker not found')
s = s.replace(old, new, 1)

old_var = '''\tlicMu                    sync.Mutex
\tlicSessionMem            *licSession'''
new_var = '''\tlicMu                    sync.Mutex
\tlicDeviceMu              sync.Mutex // V.27.1: prevent concurrent device-key creation races
\tlicSessionMem            *licSession'''
if old_var not in s:
    raise SystemExit('V271: license mutex marker not found')
s = s.replace(old_var, new_var, 1)

old_func = '''func licEnsureDevice() (*licDevice, error) {
\tmachineID, err := licStableMachineID()'''
new_func = '''func licEnsureDevice() (*licDevice, error) {
\tlicDeviceMu.Lock()
\tdefer licDeviceMu.Unlock()

\tmachineID, err := licStableMachineID()'''
if old_func not in s:
    raise SystemExit('V271: licEnsureDevice marker not found')
s = s.replace(old_func, new_func, 1)
lic.write_text(s, encoding='utf-8', newline='\n')

wv = Path('webview2_host.go')
w = wv.read_text(encoding='utf-8-sig')
# Remove time import because startup prewarm is removed.
w = w.replace('\t"time"\n', '', 1)
prewarm = '''\n\t// Keep WhatsApp CDP and Records ready in their own hidden embedded windows.
\t// They no longer replace/unload the MH Analysis page.
\tgo func() {
\t\ttime.Sleep(700 * time.Millisecond)
\t\twv2EnsureAuxBrowser(2)
\t}()
\tgo func() {
\t\ttime.Sleep(1100 * time.Millisecond)
\t\twv2EnsureAuxBrowser(3)
\t}()
'''
if prewarm not in w:
    raise SystemExit('V271: auxiliary browser prewarm block not found')
w = w.replace(prewarm, '''\n\t// V.27.1: do not pre-launch WhatsApp/Records at startup. External Chromium
\t// windows are created only when the user opens those tabs, eliminating
\t// visible startup flashes while keeping MH Analysis itself persistent.\n''', 1)
wv.write_text(w, encoding='utf-8', newline='\n')

print('PASS V27.1 hotfix applied')
