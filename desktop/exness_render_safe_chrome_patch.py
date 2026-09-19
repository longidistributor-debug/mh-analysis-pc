from pathlib import Path

MARK='MH_EXNESS_RENDER_SAFE_CHROME_V796'

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
old='cmd,wnd,err:=chLaunchBrowserQuiet("ExnessProfile", "https://my.exness.global/webtrading/", 17882)'
new='cmd,wnd,err:=chLaunchBrowser("ExnessProfile", "https://my.exness.global/webtrading/", 17882) // '+MARK
if new not in s:
    if old not in s:
        raise SystemExit('Exness quiet-launch anchor missing')
    s=s.replace(old,new,1)

# Force a real repaint when Exness becomes the visible child.
old_view='''\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchSetForegroundWindow.Call(hostHWND)\n\t\t\tchSetFocus.Call(exness)\n\t\t}\n'''
new_view='''\t\tif exness != 0 {\n\t\t\tchShowWindowAsync.Call(exness, chSWShow)\n\t\t\tchResizeChildren()\n\t\t\tchUpdateWindow.Call(exness)\n\t\t\tchSetForegroundWindow.Call(hostHWND)\n\t\t\tchSetFocus.Call(exness)\n\t\t}\n'''
if new_view not in s:
    if old_view not in s:
        raise SystemExit('Exness visible-view anchor missing')
    s=s.replace(old_view,new_view,1)
p.write_text(s,encoding='utf-8')

p=Path('exness_bridge.go')
s=p.read_text(encoding='utf-8')
route='\tmux.HandleFunc("/api/exness/render-check", exnessRenderCheckHandler) // '+MARK+'\n'
if route not in s:
    anchor='\tmux.HandleFunc("/api/exness/status", exnessStatusHandler)\n'
    if anchor not in s:
        raise SystemExit('Exness status route anchor missing')
    s=s.replace(anchor,anchor+route,1)

if 'func exnessRenderCheckHandler(' not in s:
    anchor='func derivePendingType(direction string, entry, market float64) string {\n'
    handler=r'''func exnessRenderCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	if err := chEnsureExnessBrowser(); err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
		return
	}
	wsURL, err := exnessPageSocket()
	if err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
		return
	}
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
		return
	}
	defer conn.Close()
	js := `JSON.stringify({ready:document.readyState,title:document.title||'',url:location.href||'',bodyLength:document.body?document.body.innerText.length:0,htmlLength:document.documentElement?document.documentElement.outerHTML.length:0})`
	msg, err := chCDPCommand(conn, 7001, "Runtime.evaluate", map[string]any{"expression": js, "returnByValue": true})
	if err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": err.Error()})
		return
	}
	value := chEvalValue(msg)
	out := map[string]any{}
	if err := json.Unmarshal([]byte(value), &out); err != nil {
		out["raw"] = value
	}
	out["ok"] = true
	_ = json.NewEncoder(w).Encode(out)
}

'''+anchor
    if anchor not in s:
        raise SystemExit('pending-type anchor missing')
    s=s.replace(anchor,handler,1)
p.write_text(s,encoding='utf-8')

print('PASS Exness render-safe Chrome: normal renderer launch + repaint + DOM render-check')
