from pathlib import Path

MARK='MH_EXNESS_WEBVIEW2_V796'

def rep(s,old,new,label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# Build a dedicated Exness WebView2 controller implementation from the already
# verified WhatsApp controller implementation. This keeps separate COM state and
# a separate persistent user-data folder while reusing the proven ABI code.
src=Path('native_whatsapp_bridge_windows.go').read_text(encoding='utf-8')
ex=src.replace('desktopNativeWhatsApp','desktopNativeExness')
ex=ex.replace('desktopNativeWa','desktopNativeEx')
ex=ex.replace('WhatsApp','Exness')
ex=ex.replace('https://web.whatsapp.com/','https://my.exness.global/webtrading/')
# Add explicit controller focus so clicks/typing in email/password work normally.
needle='func desktopNativeExnessDestroy() {'
focus=r'''func desktopNativeExnessFocus() {
	desktopNativeExMu.RLock()
	dispatch := desktopNativeExDispatch
	ctl := desktopNativeExCtl
	desktopNativeExMu.RUnlock()
	if dispatch != nil && ctl != 0 {
		dispatch(func() { _ = comCall(ctl, 12, 0) }) // ICoreWebView2Controller::MoveFocus(PROGRAMMATIC)
	}
}

'''+needle
if needle not in ex:
    raise SystemExit('Exness WebView2 focus anchor missing')
ex=ex.replace(needle,focus,1)
Path('native_exness_bridge_windows.go').write_text(ex,encoding='utf-8')

# Replace the Chrome-reparent Exness startup path with the dedicated WebView2
# controller. Analysis/WhatsApp/Records Chrome children remain untouched.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    # UI task marshal used by WebView2 callbacks/layout calls from worker goroutines.
    s=rep(s,'\tchIDCArrow      = 32512\n)', '\tchIDCArrow      = 32512\n\tchWMExnessUITask = 0x8079 // '+MARK+'\n)', 'Exness UI message')
    s=rep(s,'\tchStopping    bool\n', '\tchStopping    bool\n\tchExnessUITasks = make(chan func(), 128) // '+MARK+'\n', 'Exness UI queue')

    ensure_start=s.find('func chEnsureExnessBrowser() error {')
    apply_start=s.find('func chApplyDesiredBrowserView() {', ensure_start)
    if ensure_start<0 or apply_start<0:
        raise SystemExit('generated Exness ensure/apply anchors missing')
    replacement=r'''func chDispatchExnessUI(fn func()) {
	if fn == nil || hostHWND == 0 { return }
	select { case chExnessUITasks <- fn: default: go func(){ chExnessUITasks <- fn }() }
	postMessage(hostHWND, chWMExnessUITask, 0, 0)
}

func chLayoutExnessWebView() {
	if hostHWND == 0 { return }
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int(r.R-r.L); h := int(r.B-r.T)-barH
	if w < 1 { w = 1 }; if h < 1 { h = 1 }
	chViewMu.Lock(); visible := chDesiredView == 4; chViewMu.Unlock()
	desktopNativeExnessSetLayout(0, barH, w, h, visible)
	if visible { desktopNativeExnessFocus() }
}

func chStartExnessWebViewUI() error {
	profile := chProfileDir("ExnessWebView2Profile")
	if err := desktopNativeExnessStart(hostHWND, chDispatchExnessUI, profile); err != nil { return err }
	chLayoutExnessWebView()
	go func(){
		if desktopNativeExnessWaitReady(15*time.Second)==nil {
			chLayoutExnessWebView()
			desktopNativeExnessFocus()
			exnessApplyLoginCleanup()
		}
	}()
	return nil
}

// Kept under the historical name because the signal bridge already calls it.
// It now guarantees a native WebView2 controller, not a reparented Chrome HWND.
func chEnsureExnessBrowser() error {
	if desktopNativeExnessWaitReady(1*time.Millisecond)==nil { return nil }
	done:=make(chan error,1)
	chDispatchExnessUI(func(){ done <- chStartExnessWebViewUI() })
	select {
	case err:=<-done:
		if err!=nil { return err }
	case <-time.After(3*time.Second):
		return errors.New("Exness WebView2 start dispatch timed out")
	}
	return desktopNativeExnessWaitReady(15*time.Second)
}

'''
    s=s[:ensure_start]+replacement+s[apply_start:]

    # Current generated view-4 block still references the Chrome child. Replace it.
    old='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchSetForegroundWindow.Call(hostHWND)\n\t\t\tchSetFocus.Call(exness)\n\t\t}\n\t\treturn\n\t}\n'''
    new='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tchLayoutExnessWebView()\n\t\treturn\n\t}\n'''
    s=rep(s,old,new,'view 4 WebView2 switch')

    # Always hide/show native Exness controller alongside the selected native tab.
    tail='''\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\tif exness != 0 { chShowWindowAsync.Call(exness, chSWHide) }\n\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }\n'''
    tail_new='''\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\tif exness != 0 { chShowWindowAsync.Call(exness, chSWHide) }\n\tchLayoutExnessWebView()\n\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }\n'''
    s=rep(s,tail,tail_new,'hide native Exness on non-Exness views')

    # Exness button is handled on the UI thread: start native controller immediately,
    # then normal view application hides the three Chrome children.
    old='''\tif which == 4 { go func(){ _ = chEnsureExnessBrowser() }() } // MH_EXNESS_LOGIN_FIX_V796\n'''
    new='''\tif which == 4 { _ = chStartExnessWebViewUI() } // '''+MARK+'''\n'''
    s=rep(s,old,new,'Exness UI-thread start')

    # Keep native controller bounds in sync with host DPI/resize.
    resize_anchor='''\tif chExnessWnd != 0 {\n\t\tchSetWindowPos.Call(chExnessWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)\n\t}\n'''
    s=rep(s,resize_anchor,resize_anchor+'\tchLayoutExnessWebView()\n','Exness WebView2 resize')

    # UI task message executes COM/controller operations on the host thread.
    cmd_anchor='''\tcase chWMCommand:\n'''
    task_case='''\tcase chWMExnessUITask:\n\t\tfor {\n\t\t\tselect { case fn:=<-chExnessUITasks: if fn!=nil { fn() }; default: return 0 }\n\t\t}\n'''+cmd_anchor
    s=rep(s,cmd_anchor,task_case,'Exness UI task wndproc')

    # Close native controller during app shutdown; no external Exness browser process exists.
    stop_anchor='''func chStopBrowsers() {\n'''
    s=rep(s,stop_anchor,stop_anchor+'\tdesktopNativeExnessDestroy() // '+MARK+'\n','Exness WebView2 shutdown')
p.write_text(s,encoding='utf-8')

# Switch Exness DOM automation from Chrome remote-debug CDP to the native WebView2
# ExecuteScript path. No password/email values are read or stored by MH Analysis.
p=Path('exness_bridge.go'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,'\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n', '\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n\tmux.HandleFunc("/api/exness/render-check", exnessRenderCheckHandler) // '+MARK+'\n','WebView2 render route')

    cleanup_start=s.find('func exnessApplyLoginCleanup() {')
    prefill_start=s.find('func exnessPrefillOrder(prep exnessOrderPrep)', cleanup_start)
    if cleanup_start<0 or prefill_start<0:
        raise SystemExit('cleanup/prefill anchors missing after prior patches')
    cleanup=r'''func exnessWVValue(raw string) string {
	raw=strings.TrimSpace(raw)
	var decoded string
	if json.Unmarshal([]byte(raw),&decoded)==nil { return decoded }
	return raw
}

func exnessApplyLoginCleanup() {
	if err:=chEnsureExnessBrowser(); err!=nil { return }
	js := `(()=>{
const hide=()=>{
 const els=[...document.querySelectorAll('button,a,[role="button"]')];
 for(const e of els){const t=String(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim().toLowerCase();
  if(t==='sign in with google'||t==='continue with google'||t==='login with google'||t.includes('forgot password')||t.includes('forgot my password')){e.style.setProperty('display','none','important');}
 }
}; hide();
if(!window.__mhExnessLoginCleanup){window.__mhExnessLoginCleanup=true;new MutationObserver(hide).observe(document.documentElement,{childList:true,subtree:true});}
return 'ok';
})()`
	_, _ = desktopNativeExnessEval(js, 5*time.Second)
}

func exnessRenderCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type","application/json")
	if r.Method!=http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	if err:=chEnsureExnessBrowser(); err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	raw,err:=desktopNativeExnessEval(`JSON.stringify({ready:document.readyState,title:document.title||'',url:location.href||'',bodyLength:document.body?document.body.innerText.length:0,htmlLength:document.documentElement?document.documentElement.outerHTML.length:0})`,5*time.Second)
	if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	value:=exnessWVValue(raw); detail:=map[string]any{}
	if json.Unmarshal([]byte(value),&detail)!=nil { detail["raw"]=value }
	detail["ok"]=true; _=json.NewEncoder(w).Encode(detail)
}

'''
    s=s[:cleanup_start]+cleanup+s[prefill_start:]

    # Replace CDP connection setup with native WebView2 readiness.
    old='''func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {\n\tif err := chEnsureExnessBrowser(); err != nil { return "", err }\n\texnessApplyLoginCleanup()\n\twsURL, err := exnessPageSocket()\n\tif err != nil {\n\t\treturn "", err\n\t}\n\tconn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)\n\tif err != nil {\n\t\treturn "", err\n\t}\n\tdefer conn.Close()\n'''
    new='''func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {\n\tif err := chEnsureExnessBrowser(); err != nil { return "", err }\n\texnessApplyLoginCleanup()\n'''
    s=rep(s,old,new,'prefill WebView2 setup')

    old='''\tmsg, err := chCDPCommand(conn, 1, "Runtime.evaluate", map[string]any{"expression": js, "returnByValue": true, "awaitPromise": true})\n\tif err != nil {\n\t\treturn "", err\n\t}\n\tvalue := chEvalValue(msg)\n'''
    new='''\traw, err := desktopNativeExnessEval(js, 8*time.Second)\n\tif err != nil { return "", err }\n\tvalue := exnessWVValue(raw)\n'''
    s=rep(s,old,new,'prefill WebView2 evaluate')
p.write_text(s,encoding='utf-8')

print('PASS Exness switched from reparented Chrome to native persistent WebView2')
