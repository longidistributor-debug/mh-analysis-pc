from pathlib import Path

MARK='MH_V001_CLEAN_BROWSER_TITLE'
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK in s:
    print(MARK+': already applied')
    raise SystemExit(0)

# Chromium derives its native app-window title from --app=<URL>. Our local URL can
# contain an encoded name/build timestamp, producing titles such as
# MH%20Analysis(20260921-095153). Force a clean native caption before and after
# re-parenting. The inner caption remains stripped; this also prevents the ugly
# text from appearing during startup/transition flashes.
proc='\tchSetWindowText          = chUser32.NewProc("SetWindowTextW") // '+MARK+'\n'
anchor='\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n'
if proc not in s:
    if anchor not in s: raise SystemExit('SetWindowText proc anchor missing')
    s=s.replace(anchor,anchor+proc,1)

# Clean the browser window immediately when it is discovered, before it is shown.
old='''\tchShowWindow.Call(wnd, chSWHide)\n\treturn cmd, wnd, nil'''
new='''\tchShowWindow.Call(wnd, chSWHide)\n\tchSetWindowText.Call(wnd, uintptr(unsafe.Pointer(chWstr("MH Analysis")))) // '''+MARK+'''\n\treturn cmd, wnd, nil'''
if old not in s: raise SystemExit('browser discovery return anchor missing')
s=s.replace(old,new,1)

# Re-assert after SetParent because Chromium can restore its URL-derived title.
anchor='\tchSetParent.Call(hwnd, hostHWND)\n'
repl=anchor+'\tchSetWindowText.Call(hwnd, uintptr(unsafe.Pointer(chWstr("MH Analysis")))) // '+MARK+'\n'
if anchor not in s: raise SystemExit('SetParent anchor missing')
s=s.replace(anchor,repl,1)

# Continuous shell protection loop also keeps every embedded browser caption clean
# if Chromium changes it after navigation/login.
needle='''\t\tfor _, child := range children {
\t\t\tif child != 0 { chNormalizeEmbeddedFrame(child) }
\t\t}'''
replacement='''\t\tfor _, child := range children {
\t\t\tif child != 0 {
\t\t\t\tchSetWindowText.Call(child, uintptr(unsafe.Pointer(chWstr("MH Analysis"))))
\t\t\t\tchNormalizeEmbeddedFrame(child)
\t\t\t}
\t\t}'''
if needle in s:
    s=s.replace(needle,replacement,1)
else:
    raise SystemExit('permanent shell loop anchor missing')

s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
p.write_text(s,encoding='utf-8')
print(MARK+': embedded browser native title forced to MH Analysis')
