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

# Repair the visible mojibake that existed in the inherited HTML source.
# Do not rewrite layout or wording: restore only the intended Unicode characters.
idx = rw('web/index.html')
idx = re.sub(r'<div class="version">[^<]*</div>', '<div class="version">V.29 AUTO CYCLE (HAMMAD & SOMI)</div>', idx)
idx = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.29</div>', idx)
replacements = {
    'Ø¨Ù\x90Ø³Ù’Ù…Ù\x90 Ø§Ù„Ù„ÙŽÙ‘Ù‡Ù\x90 Ø§Ù„Ø±ÙŽÙ‘Ø\xadÙ’Ù…ÙŽÙ°Ù†Ù\x90 Ø§Ù„Ø±ÙŽÙ‘Ø\xadÙ\x90ÙŠÙ…Ù\x90': 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
    'Ø¨ÙØ³Ù’Ù…Ù Ø§Ù„Ù„ÙŽÙ‘Ù‡Ù Ø§Ù„Ø±ÙŽÙ‘Ø­Ù’Ù…ÙŽÙ°Ù†Ù Ø§Ù„Ø±ÙŽÙ‘Ø­ÙÙŠÙ…Ù': 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
    'â—†': '◆',
    'â”€': '─',
    'â€¢': '•',
    'â‚¿': '₿',
    'â—Ž': '◎',
    'â€”': '—',
    'â‚¬': '€',
    'Â¥': '¥',
    'Â£': '£',
    'â—': '●',
    'â†»': '↻',
    'â—´': '◴',
    'â€¦': '…',
}
for bad, good in replacements.items():
    idx = idx.replace(bad, good)
# The Arabic line is a hard requirement; if an unexpected encoding variant survives,
# replace the bismillah element itself instead of risking another broken release.
idx = re.sub(r'<div class="bismillah">.*?</div>', '<div class="bismillah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>', idx, count=1)
ww('web/index.html', idx)

# Restore the exact old Signal Link native control in the WebView2 host.
p = 'webview2_host.go'
wv = rw(p)

# Keep the button aligned in the old 600px slot.
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

# Old behavior: Signal Link is shown only while WhatsApp is selected.
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

# License/navigation label for Signal Link.
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

# Restore old click action: open WhatsApp destination/settings dialog.
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

# Create the button hidden by default, same position/label as the old working host.
needle = '''\tbtnMT5, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("MT5 System"))), chWSChild|chWSVisible, 452, 7, 140, 30, hostHWND, idMT5, inst, 0)
'''
insert = needle + '''\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))), chWSChild, 600, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0)
'''
if 'uintptr(unsafe.Pointer(chWstr("Signal Link")))' not in wv:
    if needle not in wv:
        raise SystemExit('V29: Signal Link creation point not found')
    wv = wv.replace(needle, insert, 1)

ww(p, wv)

# Stop auxiliary Chrome/Edge from ever becoming a visible top-level taskbar window
# before it is re-parented into MH Analysis. This is the taskbar flash root cause.
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

# Hidden browser windows must still be discoverable so they can be re-parented.
visible_filter = '''\t\tvis, _, _ := chIsWindowVisible.Call(hwnd)
\t\tif vis == 0 {
\t\t\treturn 1
\t\t}
'''
ch = ch.replace(visible_filter, '')
ww(p, ch)

print('V29 regression recovery patch applied')
