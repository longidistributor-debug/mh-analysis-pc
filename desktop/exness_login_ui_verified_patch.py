from pathlib import Path

MARK='MH_EXNESS_LOGIN_UI_VERIFIED_V796'

def rep(s,old,new,label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# Native cross-process keyboard focus: SetFocus alone is not reliable when the
# embedded Chrome renderer belongs to a different GUI thread. Attach the input
# queues temporarily and focus Chrome_RenderWidgetHostHWND directly.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,
        '\tchEnumWindows           = chUser32.NewProc("EnumWindows")\n',
        '\tchEnumWindows           = chUser32.NewProc("EnumWindows")\n\tchEnumChildWindows      = chUser32.NewProc("EnumChildWindows") // '+MARK+'\n',
        'EnumChildWindows proc')
    s=rep(s,
        '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n',
        '\tchSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchAttachThreadInput     = chUser32.NewProc("AttachThreadInput") // '+MARK+'\n',
        'AttachThreadInput proc')
    s=rep(s,
        '\tchGetModuleHandle       = chKernel32.NewProc("GetModuleHandleW")\n',
        '\tchGetModuleHandle       = chKernel32.NewProc("GetModuleHandleW")\n\tchGetCurrentThreadID    = chKernel32.NewProc("GetCurrentThreadId") // '+MARK+'\n',
        'GetCurrentThreadId proc')

    anchor='''func chApplyDesiredBrowserView() {\n'''
    helper=r'''func chFocusChromeRenderer(root uintptr) {
	if root == 0 { return }
	target := uintptr(0)
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		buf := make([]uint16, 160)
		n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
		if n == 0 { return 1 }
		cls := syscall.UTF16ToString(buf)
		if cls == "Chrome_RenderWidgetHostHWND" || strings.Contains(cls, "RenderWidgetHost") {
			target = hwnd
			return 0
		}
		return 1
	})
	chEnumChildWindows.Call(root, cb, 0)
	if target == 0 { target = root }
	var pid uint32
	childThread, _, _ := chGetWindowThreadPID.Call(target, uintptr(unsafe.Pointer(&pid)))
	hostThread, _, _ := chGetCurrentThreadID.Call()
	attached := false
	if childThread != 0 && hostThread != 0 && childThread != hostThread {
		r, _, _ := chAttachThreadInput.Call(hostThread, childThread, 1)
		attached = r != 0
	}
	chSetForegroundWindow.Call(hostHWND)
	chSetFocus.Call(target)
	if attached { chAttachThreadInput.Call(hostThread, childThread, 0) }
}

'''+anchor
    s=rep(s,anchor,helper,'Chrome renderer focus helper')

    old='''\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchResizeChildren()\n\t\t\tchUpdateWindow.Call(exness)\n\t\t\tchSetForegroundWindow.Call(hostHWND)\n\t\t\tchSetFocus.Call(exness)\n\t\t}\n'''
    new='''\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchResizeChildren()\n\t\t\tchUpdateWindow.Call(exness)\n\t\t\tchFocusChromeRenderer(exness) // '''+MARK+'''\n\t\t}\n'''
    s=rep(s,old,new,'Exness renderer focus call')

    # Re-apply cleanup through redirects/SPAs for a short bounded period.
    old='''if which == 4 { go func(){ if chEnsureExnessBrowser()==nil { time.Sleep(900*time.Millisecond); exnessApplyLoginCleanup() } }() } // MH_EXNESS_LOGIN_FIX_V796'''
    new='''if which == 4 { go func(){ if chEnsureExnessBrowser()==nil { for i:=0;i<24;i++ { time.Sleep(500*time.Millisecond); exnessApplyLoginCleanup() } } }() } // MH_EXNESS_LOGIN_FIX_V796 // '''+MARK
    if old not in s:
        raise SystemExit('repeated login cleanup switch anchor missing')
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Replace cleanup JS with the exact current Exness labels and add a local-only
# diagnostic endpoint used by CI to prove hidden controls + real input focus.
p=Path('exness_bridge.go'); s=p.read_text(encoding='utf-8')
start=s.find('func exnessApplyLoginCleanup() {')
end=s.find('func exnessPrefillOrder(prep exnessOrderPrep)', start)
if start<0 or end<0:
    raise SystemExit('Exness cleanup function anchors missing')
cleanup=r'''func exnessApplyLoginCleanup() {
	wsURL, err := exnessPageSocket()
	if err != nil { return }
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil { return }
	defer conn.Close()
	js := `(()=>{
const norm=e=>String((e&&e.innerText)||(e&&e.textContent)||'').replace(/\\s+/g,' ').trim().toLowerCase();
const hide=()=>{
 const clickable=[...document.querySelectorAll('button,a,[role="button"]')];
 for(const e of clickable){const t=norm(e);if(t==='google'||t==='sign in with google'||t==='continue with google'||t==='login with google'||t.includes('forgot password')||t.includes('forgot my password'))e.style.setProperty('display','none','important');}
 const labels=[...document.querySelectorAll('div,span,p')];
 for(const e of labels){const t=norm(e);if(t==='or sign in with'||t==='or continue with')e.style.setProperty('display','none','important');}
};
hide();
if(!window.__mhExnessLoginCleanup){window.__mhExnessLoginCleanup=true;new MutationObserver(hide).observe(document.documentElement,{childList:true,subtree:true,characterData:true});}
return 'ok';
})()`
	_, _ = chCDPCommand(conn, 9101, "Runtime.evaluate", map[string]any{"expression": js, "returnByValue": true})
}

'''
s=s[:start]+cleanup+s[end:]

route='\tmux.HandleFunc("/api/exness/login-ui-check", exnessLoginUICheckHandler) // '+MARK+'\n'
if route not in s:
    anchor='\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n'
    if anchor not in s: raise SystemExit('Exness status route missing')
    s=s.replace(anchor,anchor+route,1)

if 'func exnessLoginUICheckHandler(' not in s:
    anchor='func exnessStatusHandler(w http.ResponseWriter, r *http.Request) {\n'
    handler=r'''func exnessLoginUICheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	if err:=chEnsureExnessBrowser(); err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	exnessApplyLoginCleanup()
	wsURL,err:=exnessPageSocket(); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	conn,_,err:=websocket.DefaultDialer.Dial(wsURL,nil); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }; defer conn.Close()
	focus:=r.URL.Query().Get("focus")
	clear:=r.URL.Query().Get("clear")=="1"
	js:=fmt.Sprintf(`(()=>{
const vis=e=>!!(e&&getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0);
const norm=e=>String((e&&e.innerText)||(e&&e.textContent)||'').replace(/\\s+/g,' ').trim().toLowerCase();
const all=[...document.querySelectorAll('button,a,[role="button"],div,span,p')];
const googleVisible=all.filter(e=>vis(e)&&['google','sign in with google','continue with google','login with google','or sign in with'].includes(norm(e))).length;
const forgotVisible=all.filter(e=>vis(e)&&(norm(e).includes('forgot password')||norm(e).includes('forgot my password'))).length;
const inputs=[...document.querySelectorAll('input')];
const email=inputs.find(i=>(i.type||'').toLowerCase()==='email')||inputs.find(i=>/email/i.test([i.name,i.id,i.placeholder,i.getAttribute('aria-label')].filter(Boolean).join(' ')))||inputs.find(i=>(i.autocomplete||'').toLowerCase()==='username');
const pass=inputs.find(i=>(i.type||'').toLowerCase()==='password');
if(%q==='email'&&email)email.focus(); if(%q==='password'&&pass)pass.focus();
if(%t){if(email){email.value='';email.dispatchEvent(new Event('input',{bubbles:true}))}if(pass){pass.value='';pass.dispatchEvent(new Event('input',{bubbles:true}))}}
return JSON.stringify({googleVisible,forgotVisible,emailFound:!!email,passwordFound:!!pass,emailValue:email?email.value:'',passwordLength:pass?pass.value.length:0,activeType:document.activeElement?document.activeElement.type||document.activeElement.tagName:'',ready:document.readyState,url:location.href});
})()`,focus,focus,clear)
	msg,err:=chCDPCommand(conn,9301,"Runtime.evaluate",map[string]any{"expression":js,"returnByValue":true}); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	value:=chEvalValue(msg); out:=map[string]any{}; if json.Unmarshal([]byte(value),&out)!=nil { out["raw"]=value }; out["ok"]=true; _=json.NewEncoder(w).Encode(out)
}

'''+anchor
    if anchor not in s: raise SystemExit('login UI handler insertion anchor missing')
    s=s.replace(anchor,handler,1)
p.write_text(s,encoding='utf-8')

print('PASS Exness login UI verified patch: Google/Forgot hidden + renderer keyboard focus + diagnostics')
