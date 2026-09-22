from pathlib import Path
import re


def rw(path):
    return Path(path).read_text(encoding='utf-8')


def ww(path, text):
    Path(path).write_text(text, encoding='utf-8', newline='\n')


# V29 version stamps. V28 fixes are applied first by the build workflow.
u = rw('updater.go')
u = re.sub(r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.29"', u)
ww('updater.go', u)

lic = rw('license_auth.go')
lic = re.sub(r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.29"', lic)
ww('license_auth.go', lic)

# Repair inherited visible mojibake without changing layout/content logic.
idx = rw('web/index.html')
idx = re.sub(r'<div class="version">[^<]*</div>', '<div class="version">V.29 AUTO CYCLE (HAMMAD & SOMI)</div>', idx)
idx = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.29</div>', idx)
replacements = {
    'â—†': '◆', 'â”€': '─', 'â€¢': '•', 'â‚¿': '₿', 'â—Ž': '◎', 'â€”': '—',
    'â‚¬': '€', 'Â¥': '¥', 'Â£': '£', 'â—': '●', 'â†»': '↻', 'â—´': '◴', 'â€¦': '…',
}
for bad, good in replacements.items():
    idx = idx.replace(bad, good)
idx = re.sub(r'<div class="bismillah">.*?</div>', '<div class="bismillah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>', idx, count=1)
ww('web/index.html', idx)

# Restore old proven Signal Link native control in WebView2 host.
p = 'webview2_host.go'
wv = rw(p)
needle = '''\tfor _, child := range []uintptr{chWhatsappWnd, chRecordsWnd, chMT5Wnd} {
\t\tif child != 0 {
\t\t\tchMoveWindow.Call(child, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
\t\t}
\t}
'''
insert = needle + '''\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
\t}
'''
if 'chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)' not in wv:
    if needle not in wv:
        raise SystemExit('V29: WebView2 resize insertion point not found')
    wv = wv.replace(needle, insert, 1)

old = '''func wv2SetDesiredView(which int) {
\tchViewMu.Lock()
\tchDesiredView = which
\tchViewMu.Unlock()
}
'''
new = '''func wv2SetDesiredView(which int) {
\tchViewMu.Lock()
\tchDesiredView = which
\tchViewMu.Unlock()
\t// V29: restore the proven V26 Signal Link control exactly for WhatsApp view.
\tif chSignalLinkBtn != 0 {
\t\tif which == 2 {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWShow)
\t\t} else {
\t\t\tchShowWindow.Call(chSignalLinkBtn, chSWHide)
\t\t}
\t}
}
'''
if 'V29: restore the proven V26 Signal Link control' not in wv:
    if old not in wv:
        raise SystemExit('V29: desired view block not found')
    wv = wv.replace(old, new, 1)

needle = '''\tif id == idMT5 {
\t\tsection = "MT5 System"
\t}
'''
insert = needle + '''\tif id == chIDSignalLink {
\t\tsection = "Signal Link"
\t}
'''
if 'section = "Signal Link"' not in wv:
    if needle not in wv:
        raise SystemExit('V29: button allowed insertion point not found')
    wv = wv.replace(needle, insert, 1)

needle = '''\t\tcase idMT5:
\t\t\twv2ShowMT5()
'''
insert = needle + '''\t\tcase chIDSignalLink:
\t\t\tchShowNativeSettingsDialog(2)
'''
if 'case chIDSignalLink:' not in wv:
    if needle not in wv:
        raise SystemExit('V29: Signal Link command insertion point not found')
    wv = wv.replace(needle, insert, 1)

needle = '''\tbtnMT5, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("MT5 System"))), chWSChild|chWSVisible, 452, 7, 140, 30, hostHWND, idMT5, inst, 0)
'''
insert = needle + '''\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))), chWSChild, 600, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0)
'''
if 'uintptr(unsafe.Pointer(chWstr("Signal Link")))' not in wv:
    if needle not in wv:
        raise SystemExit('V29: Signal Link creation point not found')
    wv = wv.replace(needle, insert, 1)
ww(p, wv)

# Taskbar flicker hardfix: Chrome/Edge starts hidden, and hidden top-level browser
# windows are discoverable/re-parented without first becoming visible.
p = 'chrome_host.go'
ch = rw(p)
needle = '''\tcmd := exec.Command(chBrowserPath, args...)
\tif err := cmd.Start(); err != nil {
'''
insert = '''\tcmd := exec.Command(chBrowserPath, args...)
\t// V29: launch auxiliary browser hidden. It becomes visible only after re-parenting.
\tcmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
\tif err := cmd.Start(); err != nil {
'''
if 'V29: launch auxiliary browser hidden' not in ch:
    if needle not in ch:
        raise SystemExit('V29: browser launch insertion point not found')
    ch = ch.replace(needle, insert, 1)

# Robustly remove old visibility gate regardless of CRLF/gofmt whitespace.
ch, n = re.subn(
    r'\s*vis,\s*_,\s*_\s*:=\s*chIsWindowVisible\.Call\(hwnd\)\s*\n\s*if\s+vis\s*==\s*0\s*\{\s*\n\s*return\s+1\s*\n\s*\}\s*\n',
    '\n', ch, count=1,
)
if n != 1 and 'vis, _, _ := chIsWindowVisible.Call(hwnd)' in ch:
    raise SystemExit('V29: could not remove visible-window discovery gate')
ww(p, ch)

print('V29 regression recovery patch applied')
