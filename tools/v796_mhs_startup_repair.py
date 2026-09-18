from pathlib import Path

p = Path('main.go')
s = p.read_text(encoding='utf-8')

# Restore the exact historical V79.6 window/WebView2 startup path.
# The prior MH-S build added a GDI stock brush + delayed custom window message;
# remove those startup-only changes because the user's PC closes immediately.
s = s.replace('\nvar gdi32 = syscall.NewLazyDLL("gdi32.dll")', '')
s = s.replace('\nvar pGetStockObject = gdi32.NewProc("GetStockObject")', '')
s = s.replace('\n\twmShowReady      = 0x8005', '')

old = '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\t// The window itself is still hidden here. The local page is tiny and\n\t\t// embedded, so give WebView2 a brief paint window and reveal only then.\n\t\ttime.AfterFunc(450*time.Millisecond, func() { postMessage(hostHWND, wmShowReady, 0, 0) })'''
new = '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)'''
if old not in s:
    raise SystemExit('delayed V79.6 MH-S startup block not found')
s = s.replace(old, new, 1)

old = '''\tbgBrush, _, _ := pGetStockObject.Call(4) // BLACK_BRUSH: no white startup flash\n\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: bgBrush, LpszClassName: cls}'''
new = '''\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: 6, LpszClassName: cls}'''
if old not in s:
    raise SystemExit('custom MH-S background block not found')
s = s.replace(old, new, 1)

old = '''\tcase wmShowReady:\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)\n\t\tresizeWebViews()\n\t\treturn 0\n'''
if old not in s:
    raise SystemExit('custom MH-S show-ready handler not found')
s = s.replace(old, '', 1)

# Keep the requested visible title only; it does not alter the startup mechanism.
s = s.replace('wstr("MH Analysis • V79.6 MH-S")', 'wstr("MH Analysis • V79.6 MH-S")')

# Safety: original V79.6 startup markers must now be back.
required = [
    'wvNavigate(analysisCore, serverURL)',
    'pShowWindow.Call(hostHWND, swMaximize)',
    'pUpdateWindow.Call(hostHWND)',
    'HbrBackground: 6',
    'func processWhatsAppQueue()',
    'time.AfterFunc(4*time.Second, func() { postMessage(hostHWND, wmWhatsAppClick, 0, 0) })',
]
for marker in required:
    if marker not in s:
        raise SystemExit('missing restored V79.6 marker: ' + marker)
for forbidden in ('pGetStockObject', 'wmShowReady', '450*time.Millisecond'):
    if forbidden in s:
        raise SystemExit('startup experiment still present: ' + forbidden)

p.write_text(s, encoding='utf-8')
print('Restored original V79.6 startup path; WhatsApp sender untouched')
