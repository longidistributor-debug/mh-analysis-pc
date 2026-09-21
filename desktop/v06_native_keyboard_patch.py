from pathlib import Path

# V.06: fix the actual native focus path for the cross-process embedded Chromium child.
# Keep V.05 UI/update behavior otherwise unchanged.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')

if 'chGetForegroundWindow' not in s:
    s=s.replace('chSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")', 'chSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchGetForegroundWindow   = chUser32.NewProc("GetForegroundWindow")')
if 'chBringWindowToTop' not in s:
    s=s.replace('chGetForegroundWindow   = chUser32.NewProc("GetForegroundWindow")', 'chGetForegroundWindow   = chUser32.NewProc("GetForegroundWindow")\n\tchBringWindowToTop      = chUser32.NewProc("BringWindowToTop")')

marker='func chFocusEmbeddedBrowser(hwnd uintptr) {'
if marker not in s:
    insert='''
func chFocusEmbeddedBrowser(hwnd uintptr) {
\tif hwnd == 0 || hostHWND == 0 { return }
\t// The browser is a separate process/thread. Windows keyboard focus must be
\t// transferred while the host and browser input queues are temporarily attached.
\tvar browserPID uint32
\tbrowserThread, _, _ := chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&browserPID)))
\thostThread, _, _ := chGetWindowThreadPID.Call(hostHWND, 0)
\tfg, _, _ := chGetForegroundWindow.Call()
\tfgThread := uintptr(0)
\tif fg != 0 { fgThread, _, _ = chGetWindowThreadPID.Call(fg, 0) }
\tif hostThread != 0 && browserThread != 0 && hostThread != browserThread { chAttachThreadInput.Call(hostThread, browserThread, 1) }
\tif fgThread != 0 && browserThread != 0 && fgThread != browserThread { chAttachThreadInput.Call(fgThread, browserThread, 1) }
\tchSetForegroundWindow.Call(hostHWND)
\tchBringWindowToTop.Call(hostHWND)
\tchSetFocus.Call(hwnd)
\tif fgThread != 0 && browserThread != 0 && fgThread != browserThread { chAttachThreadInput.Call(fgThread, browserThread, 0) }
\tif hostThread != 0 && browserThread != 0 && hostThread != browserThread { chAttachThreadInput.Call(hostThread, browserThread, 0) }
}

'''
    anchor='func chResizeChildren() {'
    if anchor not in s: raise SystemExit('resize anchor missing')
    s=s.replace(anchor,insert+anchor,1)

# Do not permanently attach input queues. Replace V.04 attach block with one-shot focus helper.
old='''\tchSetParent.Call(hwnd, hostHWND)
\t// Chrome/Edge runs on a different GUI thread. Attach its input queue to the
\t// MH Analysis host thread so focused HTML inputs receive real keyboard input.
\tvar browserPID uint32
\tbrowserThread, _, _ := chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&browserPID)))
\thostThread, _, _ := chGetWindowThreadPID.Call(hostHWND, 0)
\tif hostThread == 0 { hostThread, _, _ = chGetCurrentThreadId.Call() }
\tif browserThread != 0 && hostThread != 0 && browserThread != hostThread {
\t\tchAttachThreadInput.Call(hostThread, browserThread, 1)
\t}
\tchSetFocus.Call(hwnd)'''
new='''\tchSetParent.Call(hwnd, hostHWND)
\tchFocusEmbeddedBrowser(hwnd)'''
if old in s: s=s.replace(old,new,1)
else:
    s=s.replace('\tchSetParent.Call(hwnd, hostHWND)\n\tchSetFocus.Call(hwnd)','\tchSetParent.Call(hwnd, hostHWND)\n\tchFocusEmbeddedBrowser(hwnd)',1)

# Whenever Analysis becomes visible, explicitly transfer native keyboard focus to it.
oldshow='\t\tchShowWindowAsync.Call(analysis, chSWShow)\n\t}'
newshow='\t\tchShowWindowAsync.Call(analysis, chSWShow)\n\t\tchFocusEmbeddedBrowser(analysis)\n\t}'
if oldshow in s: s=s.replace(oldshow,newshow,1)

p.write_text(s,encoding='utf-8')

p=Path('updater.go'); s=p.read_text(encoding='utf-8')
s=s.replace('const mhPublicVersionV001 = "V.05"','const mhPublicVersionV001 = "V.06"')
if 'const mhPublicVersionV001 = "V.06"' not in s: raise SystemExit('V.06 updater identity missing')
p.write_text(s,encoding='utf-8')

p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('id="mhUpdateVersionV001">V.05<','id="mhUpdateVersionV001">V.06<')
p.write_text(s,encoding='utf-8')
Path('VERSION').write_text('V.06\n',encoding='utf-8')
print('PASS V.06 native keyboard focus + version identity')
