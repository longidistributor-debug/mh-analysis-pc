from pathlib import Path

# V.04: preserve V.03 behavior, fix cross-process embedded-browser keyboard input,
# and promote all runtime/update identity to V.04.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if 'chAttachThreadInput' not in s:
    s=s.replace('chSetFocus              = chUser32.NewProc("SetFocus")', 'chSetFocus              = chUser32.NewProc("SetFocus")\n\tchAttachThreadInput     = chUser32.NewProc("AttachThreadInput")\n\tchGetCurrentThreadId    = chKernel32.NewProc("GetCurrentThreadId")')
needle='\tchSetParent.Call(hwnd, hostHWND)\n\tchSetFocus.Call(hwnd)'
replacement='''\tchSetParent.Call(hwnd, hostHWND)
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
if needle not in s: raise SystemExit('V.03 browser focus anchor missing')
s=s.replace(needle,replacement,1)
p.write_text(s,encoding='utf-8')

p=Path('updater.go'); s=p.read_text(encoding='utf-8')
s=s.replace('const mhPublicVersionV001 = "V.03"','const mhPublicVersionV001 = "V.04"')
if 'const mhPublicVersionV001 = "V.04"' not in s: raise SystemExit('V.04 updater identity missing')
p.write_text(s,encoding='utf-8')

p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('id="mhUpdateVersionV001">V.03<','id="mhUpdateVersionV001">V.04<')
p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.04\n',encoding='utf-8')
print('PASS V.04 keyboard input + version identity')
