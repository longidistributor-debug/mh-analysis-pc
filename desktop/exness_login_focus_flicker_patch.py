from pathlib import Path

MARK='MH_EXNESS_LOGIN_FIX_V796'

def rep(s,old,new,label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,'\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n','\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchSetFocus              = chUser32.NewProc("SetFocus") // '+MARK+'\n','setfocus proc')
    s=rep(s,'\tchStopping    bool\n)','\tchStopping    bool\n\tchExnessStarting bool // '+MARK+'\n)','exness starting var')
    anchor='''func chWaitForBrowserWindow(pid uint32, timeout time.Duration) uintptr {\n\tdeadline := time.Now().Add(timeout)\n\tfor time.Now().Before(deadline) {\n\t\tif h := chFindBrowserWindow(pid); h != 0 {\n\t\t\treturn h\n\t\t}\n\t\ttime.Sleep(100 * time.Millisecond)\n\t}\n\treturn 0\n}\n'''
    insert=anchor+'''\nfunc chFindBrowserWindowAny(pid uint32) uintptr {\n\tvar found uintptr\n\tcb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {\n\t\tvar wp uint32\n\t\tchGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))\n\t\tif wp != pid { return 1 }\n\t\tbuf := make([]uint16, 128)\n\t\tn, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))\n\t\tif n == 0 { return 1 }\n\t\tif strings.HasPrefix(syscall.UTF16ToString(buf), "Chrome_WidgetWin") { found = hwnd; return 0 }\n\t\treturn 1\n\t})\n\tchEnumWindows.Call(cb, 0)\n\treturn found\n}\n\nfunc chLaunchBrowserQuiet(profile, target string, debugPort int) (*exec.Cmd, uintptr, error) {\n\tif chBrowserPath == "" { p, err := chBrowserExecutable(); if err != nil { return nil, 0, err }; chBrowserPath = p }\n\targs := []string{"--user-data-dir=" + chProfileDir(profile), "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble", "--disable-background-mode", "--disable-infobars", "--disable-translate", "--disable-features=TranslateUI", "--window-position=-32000,-32000", "--window-size=1280,820", "--kiosk", "--new-window"}\n\tif debugPort > 0 { args = append(args, fmt.Sprintf("--remote-debugging-port=%d", debugPort)) }\n\targs = append(args, "--app="+target)\n\tcmd := exec.Command(chBrowserPath, args...)\n\tcmd.SysProcAttr = &syscall.SysProcAttr{HideWindow:true}\n\tif err := cmd.Start(); err != nil { return nil, 0, err }\n\tdeadline := time.Now().Add(20*time.Second); var wnd uintptr\n\tfor time.Now().Before(deadline) { if wnd=chFindBrowserWindowAny(uint32(cmd.Process.Pid)); wnd!=0 { break }; time.Sleep(100*time.Millisecond) }\n\tif wnd==0 { _=cmd.Process.Kill(); return nil,0,errors.New("quiet browser window did not appear") }\n\tchShowWindow.Call(wnd, chSWHide)\n\treturn cmd,wnd,nil\n}\n'''
    s=rep(s,anchor,insert,'quiet launch helpers')
    apply_anchor='''func chApplyDesiredBrowserView() {\n'''
    helper='''func chEnsureExnessBrowser() error {\n\tchMu.Lock()\n\tif chExnessWnd != 0 { chMu.Unlock(); return nil }\n\tif chExnessStarting { chMu.Unlock(); for i:=0;i<100;i++ { time.Sleep(100*time.Millisecond); chMu.Lock(); ready:=chExnessWnd!=0; starting:=chExnessStarting; chMu.Unlock(); if ready { return nil }; if !starting { break } }; return errors.New("Exness browser is still starting") }\n\tif chStopping { chMu.Unlock(); return errors.New("app is stopping") }\n\tchExnessStarting=true\n\tchMu.Unlock()\n\tcmd,wnd,err:=chLaunchBrowserQuiet("ExnessProfile", "https://my.exness.global/webtrading/", 17882)\n\tchMu.Lock()\n\tchExnessStarting=false\n\tif err!=nil { chMu.Unlock(); return err }\n\tif chStopping { chMu.Unlock(); _=exec.Command("taskkill.exe","/PID",strconv.Itoa(cmd.Process.Pid),"/T","/F").Run(); return errors.New("app is stopping") }\n\tchExnessCmd,chExnessWnd=cmd,wnd\n\tchAttachBrowser(chExnessWnd)\n\tchMu.Unlock()\n\tchResizeChildren(); chApplyDesiredBrowserView()\n\tgo func(){ time.Sleep(500*time.Millisecond); exnessApplyLoginCleanup() }()\n\treturn nil\n}\n\n'''+apply_anchor
    s=rep(s,apply_anchor,helper,'ensure exness helper')
    old='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tif exness != 0 { chShowWindowAsync.Call(exness, chSWShow) }\n\t\treturn\n\t}\n'''
    new='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tif exness != 0 { chShowWindowAsync.Call(exness, chSWShow); chSetForegroundWindow.Call(hostHWND); chSetFocus.Call(exness) }\n\t\treturn\n\t}\n'''
    s=rep(s,old,new,'exness focus view')
    old='''func chSwitchView(which int) {\n\tchViewMu.Lock()\n\tchDesiredView = which\n\tchViewMu.Unlock()\n'''
    new='''func chSwitchView(which int) {\n\tchViewMu.Lock()\n\tchDesiredView = which\n\tchViewMu.Unlock()\n\tif which == 4 { go func(){ _ = chEnsureExnessBrowser() }() } // '''+MARK+'''\n'''
    s=rep(s,old,new,'lazy exness switch')
    startup='''\tgo func() {\n\t\ttime.Sleep(300 * time.Millisecond)\n\t\tcmd, wnd, err := chLaunchBrowser("ExnessProfile", "https://my.exness.global/webtrading/", 17882)\n\t\tif err != nil { return }\n\t\tchMu.Lock()\n\t\tif chStopping {\n\t\t\tchMu.Unlock()\n\t\t\t_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()\n\t\t\treturn\n\t\t}\n\t\tchExnessCmd, chExnessWnd = cmd, wnd\n\t\tchAttachBrowser(chExnessWnd)\n\t\tchShowWindowAsync.Call(chExnessWnd, chSWHide)\n\t\tchMu.Unlock()\n\t\tchResizeChildren()\n\t\tchApplyDesiredBrowserView()\n\t}()\n\n'''
    if startup not in s: raise SystemExit('startup exness launch anchor missing')
    s=s.replace(startup,'',1)
    s=s.replace('\tchStopping = true\n','\tchStopping = true\n\tchExnessStarting = false\n',1)
p.write_text(s,encoding='utf-8')

p=Path('exness_bridge.go'); s=p.read_text(encoding='utf-8')
if 'exnessApplyLoginCleanup' not in s:
    anchor='''func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {\n'''
    helper=r'''func exnessApplyLoginCleanup() {\n\twsURL, err := exnessPageSocket(); if err != nil { return }\n\tconn, _, err := websocket.DefaultDialer.Dial(wsURL, nil); if err != nil { return }; defer conn.Close()\n\tjs := `(()=>{const hide=()=>{const els=[...document.querySelectorAll('button,a,[role="button"]')];for(const e of els){const t=String(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim().toLowerCase();if(t==='sign in with google'||t==='continue with google'||t==='login with google'||t.includes('forgot password')||t.includes('forgot my password')){e.style.setProperty('display','none','important');}}};hide();if(!window.__mhExnessLoginCleanup){window.__mhExnessLoginCleanup=true;new MutationObserver(hide).observe(document.documentElement,{childList:true,subtree:true});}return 'ok';})()`\n\t_, _ = chCDPCommand(conn, 9101, "Runtime.evaluate", map[string]any{"expression":js,"returnByValue":true})\n}\n\n'''+anchor
    s=rep(s,anchor,helper,'login cleanup helper')
    s=rep(s,'''func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {\n\twsURL, err := exnessPageSocket()\n''','''func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {\n\tif err := chEnsureExnessBrowser(); err != nil { return "", err }\n\texnessApplyLoginCleanup()\n\twsURL, err := exnessPageSocket()\n''','ensure browser before prefill')
p.write_text(s,encoding='utf-8')
print('PASS Exness login fix: lazy quiet launch + keyboard focus + immediate alternative-login cleanup')
