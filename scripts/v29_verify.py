from pathlib import Path


def text(path):
    return Path(path).read_text(encoding='utf-8')

idx = text('web/index.html')
wv = text('webview2_host.go')
ch = text('chrome_host.go')
lic = text('license_auth.go')
upd = text('updater.go')

required_arabic = 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ'
if required_arabic not in idx:
    raise SystemExit('Arabic Bismillah regression')
for bad in ('Ø¨Ù', 'â—', 'â€”'):
    if bad in idx:
        raise SystemExit(f'Visible mojibake remains in main UI: {bad!r}')

for marker in (
    'Signal Link',
    'chSignalLinkBtn',
    'case chIDSignalLink:',
    'chShowNativeSettingsDialog(2)',
    'V29: restore the proven V26 Signal Link control',
):
    if marker not in wv:
        raise SystemExit(f'Signal Link regression guard missing: {marker}')
if 'if which == 2' not in wv:
    raise SystemExit('Signal Link WhatsApp-only visibility guard missing')

for marker in ('HideWindow: true', 'CreationFlags: 0x08000000', 'V29: launch auxiliary browser hidden'):
    if marker not in ch:
        raise SystemExit(f'Taskbar flicker guard missing: {marker}')
if 'vis, _, _ := chIsWindowVisible.Call(hwnd)' in ch:
    raise SystemExit('Hidden browser discovery still requires visible top-level window')

if 'registry.LOCAL_MACHINE, `SOFTWARE\\Microsoft\\Cryptography`' not in lic:
    raise SystemExit('V28 MachineGuid fix lost')
if 'V28 recovery: old/broken DPAPI blob' not in lic:
    raise SystemExit('V28 device self-heal lost')
if 'V28: keep the native host hidden until WebView2 gets its first paint.' not in wv:
    raise SystemExit('V28 startup first-paint fix lost')
if 'time.Sleep(700 * time.Millisecond)' in wv or 'time.Sleep(1100 * time.Millisecond)' in wv:
    raise SystemExit('Auxiliary startup prewarm returned')

if 'const mhPublicVersionV001 = "V.29"' not in upd:
    raise SystemExit('Updater V29 stamp missing')
if 'const licAppVersion = "V.29"' not in lic:
    raise SystemExit('License V29 stamp missing')

print('PASS V29 regression guards')
