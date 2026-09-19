from pathlib import Path

MARK = 'MH_RECORDS_V796_PATCH'

def replace_once(text, old, new, label):
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly 1 anchor, found {n}')
    return text.replace(old, new, 1)

# main.go: register local-only records routes.
p = Path('main.go')
s = p.read_text(encoding='utf-8')
if 'registerRecordsRoutes(mux)' not in s:
    s = replace_once(
        s,
        '\tmux.HandleFunc("/api/send-whatsapp", sendWhatsappHandler)\n',
        '\tregisterRecordsRoutes(mux) // '+MARK+'\n\tmux.HandleFunc("/api/send-whatsapp", sendWhatsappHandler)\n',
        'main records route',
    )
p.write_text(s, encoding='utf-8')

# app.js: save only fresh NEW signals; RE-EVALUATE does not create duplicate trades.
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')
if 'captureSignalRecordV796' not in s:
    capture = r'''async function captureSignalRecordV796(d,state='NEW'){
  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW')return;
  try{
    await fetch('/api/records/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,
      score:sig.score,setup:d.bestFamily||sig.setupReason||'',action:'NEW'
    })});
  }catch(e){}
}
'''
    s = replace_once(s, "function addRecent(d,state='NEW'){\n", capture+"function addRecent(d,state='NEW'){\n", 'app capture function')
    s = replace_once(
        s,
        "  if(recentSession.length>6)recentSession.length=6;\n  renderRecentSignals();\n}",
        "  if(recentSession.length>6)recentSession.length=6;\n  if(sig&&String(state).toUpperCase()==='NEW')void captureSignalRecordV796(d,state);\n  renderRecentSignals();\n}",
        'app capture call',
    )
p.write_text(s, encoding='utf-8')

# chrome_host.go: third native tab + isolated embedded Records browser.
p = Path('chrome_host.go')
s = p.read_text(encoding='utf-8')
if 'chRecordsWnd' not in s:
    s = replace_once(
        s,
        '''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchBrowserPath string
''',
        '''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchRecordsWnd  uintptr
\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchRecordsCmd  *exec.Cmd
\tbtnRecords    uintptr
\tchBrowserPath string
''',
        'chrome vars',
    )
    s = replace_once(
        s,
        '\tchIDCArrow      = 32512\n)',
        '\tchIDCArrow      = 32512\n\tidRecords       = 1003 // '+MARK+'\n)',
        'records command id',
    )
    s = replace_once(
        s,
        '''\tif chWhatsappWnd != 0 {
\t\tchSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''',
        '''\tif chWhatsappWnd != 0 {
\t\tchSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
\tif chRecordsWnd != 0 {
\t\tchSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''',
        'records resize child',
    )
    s = replace_once(
        s,
        '''\tif btnWhatsapp != 0 {
\t\tchMoveWindow.Call(btnWhatsapp, 156, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 304, 7, 145, 30, 1)
\t}
''',
        '''\tif btnWhatsapp != 0 {
\t\tchMoveWindow.Call(btnWhatsapp, 156, 7, 140, 30, 1)
\t}
\tif btnRecords != 0 {
\t\tchMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 452, 7, 145, 30, 1)
\t}
''',
        'records button resize',
    )
    s = replace_once(
        s,
        '''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\tchMu.Unlock()
''',
        '''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\trecords := chRecordsWnd
\tchMu.Unlock()
''',
        'desired view vars',
    )
    s = replace_once(
        s,
        '''\tif which == 2 {
\t\tif analysis != 0 {
\t\t\tchShowWindowAsync.Call(analysis, chSWHide)
\t\t}
\t\tif whatsapp != 0 {
\t\t\tchShowWindowAsync.Call(whatsapp, chSWShow)
\t\t}
\t\treturn
\t}
\tif whatsapp != 0 {
\t\tchShowWindowAsync.Call(whatsapp, chSWHide)
\t}
\tif analysis != 0 {
\t\tchShowWindowAsync.Call(analysis, chSWShow)
\t}
''',
        '''\tif which == 2 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWShow) }
\t\treturn
\t}
\tif which == 3 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWShow) }
\t\treturn
\t}
\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }
''',
        'desired view logic',
    )
    s = replace_once(
        s,
        '''\t\tcase idWhatsapp:
\t\t\tchSwitchView(2)
\t\tcase chIDSignalLink:
''',
        '''\t\tcase idWhatsapp:
\t\t\tchSwitchView(2)
\t\tcase idRecords:
\t\t\tchSwitchView(3)
\t\tcase chIDSignalLink:
''',
        'records command switch',
    )
    s = replace_once(
        s,
        '''\tbtnWhatsapp, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("WhatsApp"))),
\t\tchWSChild|chWSVisible, 156, 7, 140, 30, hostHWND, idWhatsapp, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 304, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''',
        '''\tbtnWhatsapp, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("WhatsApp"))),
\t\tchWSChild|chWSVisible, 156, 7, 140, 30, hostHWND, idWhatsapp, inst, 0,
\t)
\tbtnRecords, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
\t\tchWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 452, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''',
        'records button create',
    )
    s = replace_once(
        s,
        '''\t\tchSetWindowTheme.Call(btnAnalysis, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(btnWhatsapp, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''',
        '''\t\tchSetWindowTheme.Call(btnAnalysis, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(btnWhatsapp, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''',
        'records dark theme',
    )
    # Respect the currently selected native tab when browsers finish asynchronously.
    s = replace_once(s, '\t\tchShowWindowAsync.Call(chAnalysisWnd, chSWShow)\n\t}()\n', '\t\tchApplyDesiredBrowserView()\n\t}()\n', 'analysis async desired view')
    s = replace_once(s, '\t\tchResizeChildren()\n\t}()\n\n\tvar m chMsg\n', '''\t\tchResizeChildren()
\t\tchApplyDesiredBrowserView()
\t}()

\tgo func() {
\t\ttime.Sleep(250 * time.Millisecond)
\t\trecordsDebugPort := 0
\t\tif os.Getenv("MH_SMOKE_TEST") == "1" { recordsDebugPort = 17881 }
\t\tcmd, wnd, err := chLaunchBrowser("RecordsProfile", serverURL+"records.html", recordsDebugPort)
\t\tif err != nil { return }
\t\tchMu.Lock()
\t\tif chStopping {
\t\t\tchMu.Unlock()
\t\t\t_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
\t\t\treturn
\t\t}
\t\tchRecordsCmd, chRecordsWnd = cmd, wnd
\t\tchAttachBrowser(chRecordsWnd)
\t\tchShowWindowAsync.Call(chRecordsWnd, chSWHide)
\t\tchMu.Unlock()
\t\tchResizeChildren()
\t\tchApplyDesiredBrowserView()
\t}()

\tvar m chMsg
''', 'records browser launch')
    s = replace_once(
        s,
        '''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd}
\tchAnalysisCmd, chWhatsappCmd = nil, nil
\tchAnalysisWnd, chWhatsappWnd = 0, 0
''',
        '''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd = nil, nil, nil
\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd = 0, 0, 0
''',
        'records shutdown',
    )
p.write_text(s, encoding='utf-8')

print('PASS records integration patch: native Records tab + local capture + routes')
