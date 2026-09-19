from pathlib import Path
import re

MARK='MH_EXNESS_LOGIN_FOCUS_FIX_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# chrome_host.go is patched AFTER records_feature_patch.py + exness_feature_patch.py.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')

if MARK not in s:
    s=rep(s,
'''\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")
\tchLoadIcon              = chUser32.NewProc("LoadIconW")
''',
'''\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")
\tchSetFocus              = chUser32.NewProc("SetFocus")
\tchAttachThreadInput     = chUser32.NewProc("AttachThreadInput")
\tchGetWindowRect         = chUser32.NewProc("GetWindowRect")
\tchGetCurrentThreadID    = chKernel32.NewProc("GetCurrentThreadId")
\tchLoadIcon              = chUser32.NewProc("LoadIconW")
''','focus procs')

    s=rep(s,
'''\tcmd := exec.Command(chBrowserPath, args...)
\tif err := cmd.Start(); err != nil {
''',
'''\tcmd := exec.Command(chBrowserPath, args...)
\t// '''+MARK+''': start embedded Chromium hidden from the first frame so it never flashes as a taskbar/top-level app.
\tcmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
\tif err := cmd.Start(); err != nil {
''','hidden startup')

    pattern=r'''func chFindBrowserWindow\(pid uint32\) uintptr \{.*?\n\}\n\nfunc chAttachBrowser'''
    m=re.search(pattern,s,re.S)
    if not m:
        raise SystemExit('browser finder anchor missing')
    finder='''func chFindBrowserWindow(pid uint32) uintptr {
\tvar found uintptr
\tvar bestScore int64 = -1
\tcb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
\t\tvar wp uint32
\t\tchGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))
\t\tif wp != pid { return 1 }
\t\tbuf := make([]uint16, 128)
\t\tn, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
\t\tif n == 0 { return 1 }
\t\tcls := syscall.UTF16ToString(buf)
\t\tif !strings.HasPrefix(cls, "Chrome_WidgetWin") { return 1 }
\t\tvar r chRect
\t\tchGetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&r)))
\t\tw := int64(r.R-r.L); h := int64(r.B-r.T)
\t\tarea := int64(1)
\t\tif w > 0 && h > 0 { area = w*h }
\t\tvis, _, _ := chIsWindowVisible.Call(hwnd)
\t\tscore := area
\t\tif vis != 0 { score += 1 << 50 }
\t\tif score > bestScore { bestScore = score; found = hwnd }
\t\treturn 1
\t})
\tchEnumWindows.Call(cb, 0)
\treturn found
}

func chAttachBrowser'''
    s=s[:m.start()]+finder+s[m.end():]

    anchor='''func chSwitchView(which int) {
'''
    focus='''func chFocusExnessBrowser() {
\tchMu.Lock()
\texness := chExnessWnd
\tchMu.Unlock()
\tif exness == 0 || hostHWND == 0 { return }
\tcur, _, _ := chGetCurrentThreadID.Call()
\ttarget, _, _ := chGetWindowThreadPID.Call(exness, 0)
\tattached := false
\tif cur != 0 && target != 0 && cur != target {
\t\tr, _, _ := chAttachThreadInput.Call(cur, target, 1)
\t\tattached = r != 0
\t}
\tchSetForegroundWindow.Call(hostHWND)
\tchSetFocus.Call(exness)
\tif attached { chAttachThreadInput.Call(cur, target, 0) }
}

'''
    s=rep(s,anchor,focus+anchor,'focus helper')

    s=rep(s,
'''\tchIDCArrow      = 32512
''',
'''\tchIDCArrow      = 32512
\tchWMFocusExness = 0x8054 // '''+MARK+'''
''','focus message const')

    s=rep(s,
'''\t\tcase idExness:
\t\t\tchSwitchView(4)
\t\tcase chIDSignalLink:
''',
'''\t\tcase idExness:
\t\t\tchSwitchView(4)
\t\t\tgo func(){ time.Sleep(40*time.Millisecond); postMessage(hostHWND, chWMFocusExness, 0, 0) }()
\t\tcase chIDSignalLink:
''','exness click focus')

    s=rep(s,
'''\tcase chWMOpenAPISettings:
''',
'''\tcase chWMFocusExness:
\t\tchFocusExnessBrowser()
\t\treturn 0
\tcase chWMOpenAPISettings:
''','focus message handler')

    s=rep(s,
'''\t\tchResizeChildren()
\t\tchApplyDesiredBrowserView()
\t}()

\tvar m chMsg
''',
'''\t\tchResizeChildren()
\t\tchApplyDesiredBrowserView()
\t\tgo exnessInstallLoginUIFixes()
\t\tchViewMu.Lock(); selected := chDesiredView == 4; chViewMu.Unlock()
\t\tif selected { postMessage(hostHWND, chWMFocusExness, 0, 0) }
\t}()

\tvar m chMsg
''','exness post-launch fixes')

p.write_text(s,encoding='utf-8')

# exness_bridge.go: hide alternate-login/recovery controls visually and keep email/password inputs focusable.
p=Path('exness_bridge.go'); s=p.read_text(encoding='utf-8')
if 'exnessInstallLoginUIFixes' not in s:
    add='''

const exnessLoginUIFixJS = `(function(){
  if(window.__mhExnessLoginFixV796)return;
  window.__mhExnessLoginFixV796=true;
  const norm=x=>String(x||'').replace(/\\s+/g,' ').trim().toLowerCase();
  const hide=e=>{if(e&&e.style)e.style.setProperty('display','none','important')};
  const clean=()=>{
    try{
      document.querySelectorAll('button,a,[role="button"],iframe').forEach(el=>{
        const tag=(el.tagName||'').toLowerCase();
        const t=norm((el.innerText||el.textContent||'')+' '+(el.getAttribute&&el.getAttribute('aria-label')||'')+' '+(el.getAttribute&&el.getAttribute('title')||''));
        const src=norm(el.getAttribute&&el.getAttribute('src'));
        const isGoogle=(t.includes('sign in with google')||t.includes('continue with google')||t==='google'||(tag==='iframe'&&src.includes('google')));
        const isForgot=(t.includes('forgot password')||t.includes('forgot your password'));
        if(isGoogle){
          const wrap=el.closest&&el.closest('[data-provider],[class*="social"],[class*="oauth"],[class*="google"]');
          hide(wrap||el);
        }
        if(isForgot)hide(el);
      });
      document.querySelectorAll('input').forEach(i=>{
        i.style.setProperty('pointer-events','auto','important');
        i.style.setProperty('user-select','text','important');
      });
    }catch(e){}
  };
  document.addEventListener('pointerdown',e=>{
    const i=e.target&&e.target.closest&&e.target.closest('input');
    if(i)setTimeout(()=>{try{i.focus({preventScroll:true})}catch(_){try{i.focus()}catch(__){}}},0);
  },true);
  new MutationObserver(clean).observe(document.documentElement,{childList:true,subtree:true,attributes:false});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean,{once:true});else clean();
})();`

func exnessInstallLoginUIFixes() {
\twsURL, err := exnessPageSocket()
\tif err != nil { return }
\tconn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
\tif err != nil { return }
\tdefer conn.Close()
\t_, _ = chCDPCommand(conn, 1, "Page.enable", map[string]any{})
\t_, _ = chCDPCommand(conn, 2, "Page.addScriptToEvaluateOnNewDocument", map[string]any{"source": exnessLoginUIFixJS})
\t_, _ = chCDPCommand(conn, 3, "Runtime.evaluate", map[string]any{"expression": exnessLoginUIFixJS, "returnByValue": true})
}
'''
    s=s+add
p.write_text(s,encoding='utf-8')

print('PASS Exness login focus + hidden startup + login UI cleanup patch')
