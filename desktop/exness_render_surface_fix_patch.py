from pathlib import Path

MARK='MH_EXNESS_RENDER_SURFACE_V796'

def rep(s,old,new,label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,
        '\tchSetFocus              = chUser32.NewProc("SetFocus") // MH_EXNESS_LOGIN_FIX_V796\n',
        '\tchSetFocus              = chUser32.NewProc("SetFocus") // MH_EXNESS_LOGIN_FIX_V796\n\tchInvalidateRect         = chUser32.NewProc("InvalidateRect") // '+MARK+'\n\tchRedrawWindow           = chUser32.NewProc("RedrawWindow") // '+MARK+'\n',
        'render user32 procs')

    anchor='func chEnsureExnessBrowser() error {\n'
    helper=r'''func chForceExnessRender(hwnd uintptr) {
	if hwnd == 0 || hostHWND == 0 { return }
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int32(r.R-r.L)
	h := int32(r.B-r.T-int32(barH))
	if w < 2 { w = 2 }
	if h < 2 { h = 2 }
	// Chromium can keep a stale/black compositor surface after an off-screen
	// top-level window is reparented.  A synchronous size nudge + explicit
	// invalidation forces the child surface to bind to the MH host immediately.
	chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), uintptr(w-1), uintptr(h), chSWPNoZOrder|chSWPFrame)
	chShowWindow.Call(hwnd, chSWShow)
	chUpdateWindow.Call(hwnd)
	chInvalidateRect.Call(hwnd, 0, 1)
	chRedrawWindow.Call(hwnd, 0, 0, 0x0581) // INVALIDATE|ALLCHILDREN|UPDATENOW|FRAME
	time.Sleep(70*time.Millisecond)
	chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPFrame)
	chUpdateWindow.Call(hwnd)
	chInvalidateRect.Call(hwnd, 0, 1)
	chRedrawWindow.Call(hwnd, 0, 0, 0x0581)
	chSetForegroundWindow.Call(hostHWND)
	chSetFocus.Call(hwnd)
}

'''+anchor
    s=rep(s,anchor,helper,'render helper')

    old='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchSetForegroundWindow.Call(hostHWND)\n\t\t\tchSetFocus.Call(exness)\n\t\t}\n\t\treturn\n\t}\n'''
    new='''\tif which == 4 {\n\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }\n\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }\n\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }\n\t\tif exness != 0 { chForceExnessRender(exness) }\n\t\treturn\n\t}\n'''
    s=rep(s,old,new,'view 4 render')

    old='''\tchResizeChildren(); chApplyDesiredBrowserView()\n\treturn nil\n}\n'''
    new='''\tchResizeChildren()\n\tchApplyDesiredBrowserView()\n\tchViewMu.Lock(); selected := chDesiredView == 4; chViewMu.Unlock()\n\tif selected {\n\t\tchForceExnessRender(wnd)\n\t\tgo func(h uintptr){ time.Sleep(450*time.Millisecond); chViewMu.Lock(); still := chDesiredView == 4; chViewMu.Unlock(); if still { chForceExnessRender(h) } }(wnd)\n\t}\n\treturn nil\n}\n'''
    s=rep(s,old,new,'ensure final render')
p.write_text(s,encoding='utf-8')

p=Path('exness_bridge.go')
s=p.read_text(encoding='utf-8')
if 'exnessRenderCheckHandler' not in s:
    s=rep(s,
        '\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n',
        '\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n\tmux.HandleFunc("/api/exness/render-check", exnessRenderCheckHandler) // '+MARK+'\n',
        'render-check route')
    anchor='func exnessStatusHandler(w http.ResponseWriter, r *http.Request) {\n'
    handler=r'''func exnessRenderCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	if err:=chEnsureExnessBrowser(); err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	wsURL,err:=exnessPageSocket(); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	conn,_,err:=websocket.DefaultDialer.Dial(wsURL,nil); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }; defer conn.Close()
	expr:=`JSON.stringify({ready:document.readyState,title:document.title||'',url:location.href||'',bodyLength:document.body?document.body.innerText.length:0,htmlLength:document.documentElement?document.documentElement.outerHTML.length:0})`
	msg,err:=chCDPCommand(conn,9201,"Runtime.evaluate",map[string]any{"expression":expr,"returnByValue":true}); if err!=nil { w.WriteHeader(http.StatusServiceUnavailable); _=json.NewEncoder(w).Encode(map[string]any{"ok":false,"error":err.Error()}); return }
	value:=chEvalValue(msg)
	var detail map[string]any
	if json.Unmarshal([]byte(value),&detail)!=nil { detail=map[string]any{"raw":value} }
	detail["ok"]=true
	_ = json.NewEncoder(w).Encode(detail)
}

'''+anchor
    s=rep(s,anchor,handler,'render-check handler')
p.write_text(s,encoding='utf-8')

print('PASS Exness render surface fix: synchronous compositor refresh + DOM render-check endpoint')
