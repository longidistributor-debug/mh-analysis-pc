from pathlib import Path

MARK='MH_WINDOW_FLICKER_FIX_V798'


def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')

# Embedded Chromium windows are child/tool windows, never separate taskbar apps.
s=rep(s,
    '\tchEXAppWindow   = 0x00040000\n',
    '\tchEXAppWindow   = 0x00040000\n\tchEXToolWindow  = 0x00000080 // '+MARK+'\n',
    'toolwindow constant')

# Reveal native shell exactly once after the first real page is already embedded.
s=rep(s,
    '\tchStopping    bool\n)',
    '\tchStopping    bool\n\tchHostShowOnce sync.Once // '+MARK+'\n)',
    'host reveal state')

insert='''\nfunc chRevealHostOnce(){\n\tchHostShowOnce.Do(func(){\n\t\tif hostHWND!=0 {\n\t\t\tchShowWindowAsync.Call(hostHWND, chSWMaximize)\n\t\t\tchUpdateWindow.Call(hostHWND)\n\t\t}\n\t})\n}\n\nfunc chSetEmbeddedVisible(hwnd uintptr, show bool){\n\tif hwnd==0 { return }\n\tvis,_,_:=chIsWindowVisible.Call(hwnd)\n\twant:=uintptr(0)\n\tif show { want=1 }\n\tif vis==want { return }\n\tif show { chShowWindowAsync.Call(hwnd,chSWShow) } else { chShowWindowAsync.Call(hwnd,chSWHide) }\n}\n\nfunc chPrepareBrowserWindowsForShutdown(){\n\tchMu.Lock()\n\twindows:=[]uintptr{chAnalysisWnd,chWhatsappWnd,chRecordsWnd}\n\tchMu.Unlock()\n\tfor _,hwnd:=range windows {\n\t\tif hwnd==0 { continue }\n\t\tchShowWindow.Call(hwnd,chSWHide)\n\t\texStyle,_,_:=chGetWindowLongPtr.Call(hwnd,^uintptr(19))\n\t\texStyle &^= chEXAppWindow\n\t\texStyle |= chEXToolWindow\n\t\tchSetWindowLongPtr.Call(hwnd,^uintptr(19),exStyle)\n\t}\n}\n'''
s=rep(s,
    '\nfunc chBrowserExecutable() (string, error) {',
    insert+'\nfunc chBrowserExecutable() (string, error) {',
    'helper functions')

# The window is launched far off-screen. Poll much faster so Windows has almost no
# time to create a transient browser/profile taskbar button before we reparent it.
s=rep(s,
    '\t\ttime.Sleep(100 * time.Millisecond)\n',
    '\t\ttime.Sleep(20 * time.Millisecond) // '+MARK+' fast off-screen attach\n',
    'fast browser attach polling')

# Keep WS_VISIBLE off while converting the external browser into a child and mark it
# TOOLWINDOW. The selected embedded view is shown only after parenting/resizing.
s=rep(s,
    '\tstyle &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu\n\tstyle |= chWSChild | chWSVisible\n',
    '\tstyle &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu | chWSVisible\n\tstyle |= chWSChild\n',
    'attach without visible flash')
s=rep(s,
    '\texStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow\n\tchSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)\n',
    '\texStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow\n\texStyle |= chEXToolWindow\n\tchSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)\n',
    'force toolwindow')

# Avoid redundant ShowWindow calls every time another hidden embedded browser finishes
# loading. Only the actual visibility transition is applied.
for old,new in [
    ('chShowWindowAsync.Call(analysis, chSWHide)','chSetEmbeddedVisible(analysis,false)'),
    ('chShowWindowAsync.Call(analysis, chSWShow)','chSetEmbeddedVisible(analysis,true)'),
    ('chShowWindowAsync.Call(whatsapp, chSWHide)','chSetEmbeddedVisible(whatsapp,false)'),
    ('chShowWindowAsync.Call(whatsapp, chSWShow)','chSetEmbeddedVisible(whatsapp,true)'),
    ('chShowWindowAsync.Call(records, chSWHide)','chSetEmbeddedVisible(records,false)'),
    ('chShowWindowAsync.Call(records, chSWShow)','chSetEmbeddedVisible(records,true)'),
]:
    s=s.replace(old,new)

# Do not show/maximize an empty shell first. Paint it once the Analysis child is ready.
s=rep(s,
    '\tchShowWindow.Call(hostHWND, chSWMaximize)\n\tchUpdateWindow.Call(hostHWND)\n\n\t// Start browsers asynchronously so host message handling never blocks.\n',
    '\t// Host remains hidden until Analysis is embedded. // '+MARK+'\n\tgo func(){ time.Sleep(7*time.Second); chRevealHostOnce() }()\n\n\t// Start browsers asynchronously so host message handling never blocks.\n',
    'defer native host reveal')

s=rep(s,
    '''\t\tchAnalysisCmd, chAnalysisWnd = cmd, wnd\n\t\tchAttachBrowser(chAnalysisWnd)\n\t\tchMu.Unlock()\n\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t}()''',
    '''\t\tchAnalysisCmd, chAnalysisWnd = cmd, wnd\n\t\tchAttachBrowser(chAnalysisWnd)\n\t\tchMu.Unlock()\n\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t\tchRevealHostOnce()\n\t}()''',
    'clean reveal after analysis attach')

# Close cleanly: remove all embedded Chromium windows from view/taskbar before the
# native parent is destroyed, then terminate the browser process trees.
s=rep(s,
    '''\tcase chWMClose:\n\t\tchDestroyWindow.Call(hwnd)\n\t\treturn 0''',
    '''\tcase chWMClose:\n\t\tchShowWindow.Call(hwnd,chSWHide)\n\t\tchPrepareBrowserWindowsForShutdown()\n\t\tchStopBrowsers()\n\t\tchDestroyWindow.Call(hwnd)\n\t\treturn 0''',
    'clean shutdown before destroy')

p.write_text(s,encoding='utf-8')
print('PASS '+MARK+': fast off-screen attach, toolwindow taskbar cleanup, single-paint host, clean shutdown')
