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

# Add TOOLWINDOW so embedded Chromium windows never get their own taskbar slot.
s=rep(s,
    '\tchEXAppWindow   = 0x00040000\n',
    '\tchEXAppWindow   = 0x00040000\n\tchEXToolWindow  = 0x00000080 // '+MARK+'\n',
    'toolwindow constant')

# One-time reveal: keep the native host hidden until the Analysis child is already attached.
s=rep(s,
    '\tchStopping    bool\n)',
    '\tchStopping    bool\n\tchHostShowOnce sync.Once // '+MARK+'\n)',
    'host reveal state')

insert='''\nfunc chRevealHostOnce(){\n\tchHostShowOnce.Do(func(){\n\t\tif hostHWND!=0 {\n\t\t\tchShowWindowAsync.Call(hostHWND, chSWMaximize)\n\t\t\tchUpdateWindow.Call(hostHWND)\n\t\t}\n\t})\n}\n\nfunc chPrepareBrowserWindowsForShutdown(){\n\tchMu.Lock()\n\twindows:=[]uintptr{chAnalysisWnd,chWhatsappWnd,chRecordsWnd}\n\tchMu.Unlock()\n\tfor _,hwnd:=range windows {\n\t\tif hwnd==0 { continue }\n\t\tchShowWindow.Call(hwnd,chSWHide)\n\t\texStyle,_,_:=chGetWindowLongPtr.Call(hwnd,^uintptr(19))\n\t\texStyle &^= chEXAppWindow\n\t\texStyle |= chEXToolWindow\n\t\tchSetWindowLongPtr.Call(hwnd,^uintptr(19),exStyle)\n\t}\n}\n'''
s=rep(s,
    '\nfunc chBrowserExecutable() (string, error) {',
    insert+'\nfunc chBrowserExecutable() (string, error) {',
    'helper functions')

# STARTUPINFO hidden helps suppress Chrome/Edge's initial top-level flash.
s=rep(s,
    '\tcmd := exec.Command(chBrowserPath, args...)\n\tif err := cmd.Start(); err != nil {',
    '\tcmd := exec.Command(chBrowserPath, args...)\n\tcmd.SysProcAttr=&syscall.SysProcAttr{HideWindow:true}\n\tif err := cmd.Start(); err != nil {',
    'hidden browser process startup')

# Detect the real large Chromium app window before it becomes visible. Small hidden
# Chrome helper windows are ignored so the actual page window is what gets reparented.
old='''\t\tvis, _, _ := chIsWindowVisible.Call(hwnd)\n\t\tif vis == 0 {\n\t\t\treturn 1\n\t\t}\n\t\tbuf := make([]uint16, 128)'''
new='''\t\tbuf := make([]uint16, 128)'''
s=rep(s,old,new,'early hidden browser detection')
s=rep(s,
    '''\t\tcls := syscall.UTF16ToString(buf)\n\t\tif strings.HasPrefix(cls, "Chrome_WidgetWin") {''',
    '''\t\tcls := syscall.UTF16ToString(buf)\n\t\tvar wr chRect\n\t\tchGetClientRect.Call(hwnd, uintptr(unsafe.Pointer(&wr)))\n\t\tww, wh := wr.R-wr.L, wr.B-wr.T\n\t\tif strings.HasPrefix(cls, "Chrome_WidgetWin") && ww >= 600 && wh >= 400 {''',
    'large chromium app window filter')

# Keep WS_VISIBLE off while converting the external browser into a child window,
# and force TOOLWINDOW in case Windows cached an app/taskbar representation.
s=rep(s,
    '\tstyle &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu\n\tstyle |= chWSChild | chWSVisible\n',
    '\tstyle &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu | chWSVisible\n\tstyle |= chWSChild\n',
    'attach without visible flash')
s=rep(s,
    '\texStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow\n\tchSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)\n',
    '\texStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow\n\texStyle |= chEXToolWindow\n\tchSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)\n',
    'force toolwindow')

# Do not paint/maximize the host before the Analysis browser is attached.
s=rep(s,
    '\tchShowWindow.Call(hostHWND, chSWMaximize)\n\tchUpdateWindow.Call(hostHWND)\n\n\t// Start browsers asynchronously so host message handling never blocks.\n',
    '\t// Host is intentionally kept hidden until Analysis is attached. // '+MARK+'\n\tgo func(){ time.Sleep(7*time.Second); chRevealHostOnce() }()\n\n\t// Start browsers asynchronously so host message handling never blocks.\n',
    'defer native host reveal')

# Reveal exactly once after Analysis has been parented/resized and the desired view is applied.
s=rep(s,
    '''\t\tchAnalysisCmd, chAnalysisWnd = cmd, wnd\n\t\tchAttachBrowser(chAnalysisWnd)\n\t\tchMu.Unlock()\n\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t}()''',
    '''\t\tchAnalysisCmd, chAnalysisWnd = cmd, wnd\n\t\tchAttachBrowser(chAnalysisWnd)\n\t\tchMu.Unlock()\n\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t\tchRevealHostOnce()\n\t}()''',
    'clean reveal after analysis attach')

# On close, hide everything first and kill browser trees while the native parent still exists.
# This prevents the child Chromium windows briefly becoming top-level/taskbar windows again.
s=rep(s,
    '''\tcase chWMClose:\n\t\tchDestroyWindow.Call(hwnd)\n\t\treturn 0''',
    '''\tcase chWMClose:\n\t\tchShowWindow.Call(hwnd,chSWHide)\n\t\tchPrepareBrowserWindowsForShutdown()\n\t\tchStopBrowsers()\n\t\tchDestroyWindow.Call(hwnd)\n\t\treturn 0''',
    'clean shutdown before destroy')

p.write_text(s,encoding='utf-8')
print('PASS '+MARK+': hidden attach, no browser taskbar slot, clean shutdown')
