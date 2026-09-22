from pathlib import Path
import re


def rw(path):
    return Path(path).read_text(encoding='utf-8')

def ww(path, text):
    Path(path).write_text(text, encoding='utf-8', newline='\n')

# updater version
u = rw('updater.go')
u = re.sub(r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.28"', u)
ww('updater.go', u)

# UI version
idx = rw('web/index.html')
idx = re.sub(r'<div class="version">[^<]*</div>', '<div class="version">V.28 AUTO CYCLE (HAMMAD & SOMI)</div>', idx)
idx = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.28</div>', idx)
ww('web/index.html', idx)

# license fixes
p = 'license_auth.go'
lic = rw(p)
lic = re.sub(r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.28"', lic)
lic = lic.replace(r'`SOFTWARE\\Microsoft\\Cryptography`', r'`SOFTWARE\Microsoft\Cryptography`')

if 'licDeviceMu              sync.Mutex' not in lic:
    lic = lic.replace('licMu                    sync.Mutex', 'licMu                    sync.Mutex\n\tlicDeviceMu              sync.Mutex')
if 'licDeviceMu.Lock()' not in lic:
    lic = lic.replace('func licEnsureDevice() (*licDevice, error) {\n', 'func licEnsureDevice() (*licDevice, error) {\n\tlicDeviceMu.Lock()\n\tdefer licDeviceMu.Unlock()\n', 1)

old = '''\tif _, statErr := os.Stat(path); statErr == nil {
\t\tif err := licReadProtected(path, &disk); err != nil {
\t\t\treturn nil, fmt.Errorf("existing device identity cannot be read: %w", err)
\t\t}
\t\traw, err := base64.StdEncoding.DecodeString(disk.PrivateKey)
\t\tif err != nil || len(raw) != ed25519.PrivateKeySize {
\t\t\treturn nil, errors.New("existing device identity is invalid")
\t\t}
\t\tpriv := ed25519.PrivateKey(raw)
\t\tpub := priv.Public().(ed25519.PublicKey)
\t\tder, err := x509.MarshalPKIXPublicKey(pub)
\t\tif err != nil {
\t\t\treturn nil, err
\t\t}
\t\treturn &licDevice{Private: priv, Public: pub, DER: der, ID: machineID}, nil
\t} else if !os.IsNotExist(statErr) {
\t\treturn nil, statErr
\t}
'''
new = '''\tif _, statErr := os.Stat(path); statErr == nil {
\t\treadErr := licReadProtected(path, &disk)
\t\tif readErr == nil {
\t\t\traw, decErr := base64.StdEncoding.DecodeString(disk.PrivateKey)
\t\t\tif decErr == nil && len(raw) == ed25519.PrivateKeySize {
\t\t\t\tpriv := ed25519.PrivateKey(raw)
\t\t\t\tpub := priv.Public().(ed25519.PublicKey)
\t\t\t\tder, marshalErr := x509.MarshalPKIXPublicKey(pub)
\t\t\t\tif marshalErr == nil {
\t\t\t\t\treturn &licDevice{Private: priv, Public: pub, DER: der, ID: machineID}, nil
\t\t\t\t}
\t\t\t}
\t\t}
\t\t// V28 recovery: old/broken DPAPI blob must not brick this Windows device forever.
\t\t_ = os.Remove(path + ".tmp")
\t\t_ = os.Remove(path)
\t} else if !os.IsNotExist(statErr) {
\t\treturn nil, fmt.Errorf("device identity file unavailable: %w", statErr)
\t}
'''
if old in lic:
    lic = lic.replace(old, new, 1)
elif 'V28 recovery: old/broken DPAPI blob' not in lic:
    raise SystemExit('old identity block not found')

lic = lic.replace('"message": "Could not create secure device identity."', '"message": "Could not create secure device identity: " + err.Error()')
ww(p, lic)

# Startup flicker: remove hidden auxiliary browser prewarm and reveal host after first paint delay.
p = 'webview2_host.go'
wv = rw(p)
prewarm = '''\t// Keep WhatsApp CDP and Records ready in their own hidden embedded windows.
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
wv = wv.replace(prewarm, '')
old_show = '''\tb.Navigate(serverURL)
\tb.Focus()
\twv2SetDesiredView(1)
\tchShowWindow.Call(hostHWND, chSWMaximize)
'''
new_show = '''\tb.Navigate(serverURL)
\twv2SetDesiredView(1)
\t// V28: keep the native host hidden until WebView2 gets its first paint.
\ttime.Sleep(450 * time.Millisecond)
\tchShowWindow.Call(hostHWND, chSWMaximize)
'''
if old_show in wv:
    wv = wv.replace(old_show, new_show, 1)
elif 'V28: keep the native host hidden until WebView2 gets its first paint.' not in wv:
    raise SystemExit('startup show block not found')
ww(p, wv)

print('V28 patch applied')
