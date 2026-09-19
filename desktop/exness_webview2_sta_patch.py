from pathlib import Path

MARK='MH_EXNESS_WEBVIEW2_STA_V796'
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    old='''func runChromeHost() {\n\truntime.LockOSThread()\n\tdefer runtime.UnlockOSThread()\n'''
    new='''func runChromeHost() {\n\truntime.LockOSThread()\n\tdefer runtime.UnlockOSThread()\n\t// Native WebView2 controllers require the host UI thread to be an STA COM\n\t// apartment. Chrome embedding did not need COM, so initialize it explicitly\n\t// before the Win32 message loop/controller creation. // '''+MARK+'''\n\thrCOM, _, _ := pCoInitializeEx.Call(0, 0x2) // COINIT_APARTMENTTHREADED\n\tif int32(hrCOM) < 0 {\n\t\tmessageBox(0, fmt.Sprintf("Could not initialize Exness WebView2 COM apartment (0x%08X).", uint32(hrCOM)), "MH Analysis", 0x10)\n\t\treturn\n\t}\n'''
    if s.count(old)!=1:
        raise SystemExit(f'runChromeHost STA anchor: expected 1, found {s.count(old)}')
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('PASS Exness WebView2 host UI thread initialized as STA COM')
