from pathlib import Path
import re

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')

# V.08: restore the V.04 native keyboard model that was the last build where
# the username field demonstrably accepted real keyboard input. Password is
# already a normal text input with CSS masking, so the same native focus path
# now serves both fields.
start=s.index('func chFocusEmbeddedBrowser(hwnd uintptr) {')
end=s.index('\n}\n\nfunc chResizeChildren()', start)+2
focus='''func chFocusEmbeddedBrowser(hwnd uintptr) {
\tif hwnd == 0 || hostHWND == 0 { return }
\tvar browserPID uint32
\tbrowserThread, _, _ := chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&browserPID)))
\thostThread, _, _ := chGetWindowThreadPID.Call(hostHWND, 0)
\tif hostThread == 0 { hostThread, _, _ = chGetCurrentThreadId.Call() }
\t// V.08: keep the host/browser input queues attached for the lifetime of the
\t// embedded child. This is the proven V.04 behavior where username typing worked.
\tif browserThread != 0 && hostThread != 0 && browserThread != hostThread {
\t\tchAttachThreadInput.Call(hostThread, browserThread, 1)
\t}
\tchSetForegroundWindow.Call(hostHWND)
\tchSetFocus.Call(hwnd)
}'''
s=s[:start]+focus+s[end:]

# Restore the known-good V.06 presentation geometry. Do NOT use V.07's 1x1 /
# start-minimized browser window, which distorted the embedded viewport.
s=s.replace('"--window-size=1,1",\n\t\t"--start-minimized",','"--window-size=1280,820",')

# Keep the host presentation behavior that produced the correct full viewport.
if '\tchShowWindow.Call(hostHWND, chSWMaximize)\n\tchUpdateWindow.Call(hostHWND)' not in s:
    anchor='\t// Start browsers asynchronously so host message handling never blocks.'
    s=s.replace(anchor,'\tchShowWindow.Call(hostHWND, chSWMaximize)\n\tchUpdateWindow.Call(hostHWND)\n\n'+anchor,1)

# Secondary embedded apps start after the primary Analysis view is stable.
# This reduces transient taskbar/process-window flashes without changing layout.
s=s.replace('time.Sleep(150 * time.Millisecond)\n\t\tcmd, wnd, err := chLaunchBrowser("WhatsAppProfile"','time.Sleep(1000 * time.Millisecond)\n\t\tcmd, wnd, err := chLaunchBrowser("WhatsAppProfile"',1)
s=s.replace('time.Sleep(250 * time.Millisecond)\n\t\trecordsDebugPort := 0','time.Sleep(1300 * time.Millisecond)\n\t\trecordsDebugPort := 0',1)

# Hide every embedded child before the host is destroyed, preventing child
# windows becoming briefly visible/taskbar-visible during shutdown.
old='''\tcase chWMClose:
\t\tchDestroyWindow.Call(hwnd)
\t\treturn 0'''
new='''\tcase chWMClose:
\t\tchMu.Lock()
\t\tfor _, w := range []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd} {
\t\t\tif w != 0 { chShowWindow.Call(w, chSWHide) }
\t\t}
\t\tchMu.Unlock()
\t\tchDestroyWindow.Call(hwnd)
\t\treturn 0'''
if old in s: s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')

# Promote the committed runtime itself, not only the CI artifact.
p=Path('updater.go'); s=p.read_text(encoding='utf-8')
s=re.sub(r'const mhPublicVersionV001 = "V\.\d+"','const mhPublicVersionV001 = "V.08"',s)
p.write_text(s,encoding='utf-8')
Path('VERSION').write_text('V.08\n',encoding='utf-8')
p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=re.sub(r'id="mhUpdateVersionV001">V\.\d+<','id="mhUpdateVersionV001">V.08<',s)
p.write_text(s,encoding='utf-8')
print('PASS V.08: restored viewport + proven native keyboard path + shutdown hiding + version')
