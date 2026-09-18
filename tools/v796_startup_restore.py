from pathlib import Path

p = Path('main.go')
s = p.read_text(encoding='utf-8')

# Revert ONLY the startup-window experiment introduced by v796_mhs_patch.py.
# Keep the V79.6 analysis engine and original WhatsApp sender untouched.
s = s.replace('\nvar gdi32 = syscall.NewLazyDLL("gdi32.dll")', '', 1)
s = s.replace('\nvar pGetStockObject = gdi32.NewProc("GetStockObject")', '', 1)
s = s.replace('\n\twmShowReady      = 0x8005', '', 1)

old = '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\t// The window itself is still hidden here. The local page is tiny and\n\t\t// embedded, so give WebView2 a brief paint window and reveal only then.\n\t\ttime.AfterFunc(450*time.Millisecond, func() { postMessage(hostHWND, wmShowReady, 0, 0) })'''
new = '''\t\twvNavigate(analysisCore, serverURL)\n\t\twvVisible(analysisCtl, true)\n\t\tresizeWebViews()\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)'''
if old not in s:
    raise SystemExit('delayed startup block not found')
s = s.replace(old, new, 1)

old = '''\tbgBrush, _, _ := pGetStockObject.Call(4) // BLACK_BRUSH: no white startup flash\n\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: bgBrush, LpszClassName: cls}'''
new = '''\twc := wndClassEx{CbSize: uint32(unsafe.Sizeof(wndClassEx{})), LpfnWndProc: syscall.NewCallback(wndProc), HInstance: hinst, HIcon: icon, HIconSm: icon, HCursor: cursor, HbrBackground: 6, LpszClassName: cls}'''
if old not in s:
    raise SystemExit('dark startup brush block not found')
s = s.replace(old, new, 1)

old = '''\tcase wmShowReady:\n\t\tpShowWindow.Call(hostHWND, swMaximize)\n\t\tpUpdateWindow.Call(hostHWND)\n\t\tresizeWebViews()\n\t\treturn 0\n'''
if old not in s:
    raise SystemExit('delayed reveal handler not found')
s = s.replace(old, '', 1)

# Keep the requested visible title but verify original immediate startup is back.
required = [
    'pShowWindow.Call(hostHWND, swMaximize)',
    'pUpdateWindow.Call(hostHWND)',
    'HbrBackground: 6',
    'MH Analysis • V79.6 MH-S',
]
for x in required:
    if x not in s:
        raise SystemExit(f'missing restored startup marker: {x}')
for x in ('wmShowReady', 'pGetStockObject', '450*time.Millisecond', 'gdi32'):
    if x in s:
        raise SystemExit(f'startup experiment still present: {x}')

p.write_text(s, encoding='utf-8')
print('Restored original V79.6 immediate startup sequence')
