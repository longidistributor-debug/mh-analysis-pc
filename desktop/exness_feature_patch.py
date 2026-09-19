from pathlib import Path

MARK='MH_EXNESS_V796_PATCH'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# main.go: local bridge routes only.
p=Path('main.go'); s=p.read_text(encoding='utf-8')
if 'registerExnessRoutes(mux)' not in s:
    s=rep(s,'\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n','\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n\tregisterExnessRoutes(mux) // '+MARK+'\n','main exness routes')
p.write_text(s,encoding='utf-8')

# app.js: NEW signal -> local Exness prefill request. No external market API call.
p=Path('web/app.js'); s=p.read_text(encoding='utf-8')
if 'prepareExnessSignalV796' not in s:
    fn=r'''async function prepareExnessSignalV796(d,state='NEW'){
  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW'||symbol!=='XAUUSD')return;
  const arr=candleCache.get(keyFor())||[];
  const market=Number(arr.at(-1)?.c??publicGoldPrice);
  if(!Number.isFinite(market)||market<=0)return;
  try{
    await fetch('/api/exness/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,
      market_price:market,score:sig.score,setup:d.bestFamily||sig.setupReason||''
    })});
  }catch(e){}
}
'''
    s=rep(s,"function addRecent(d,state='NEW'){\n",fn+"function addRecent(d,state='NEW'){\n",'app exness function')
    s=rep(s,"  if(sig&&String(state).toUpperCase()==='NEW')void captureSignalRecordV796(d,state);\n  renderRecentSignals();\n}","  if(sig&&String(state).toUpperCase()==='NEW'){\n    void captureSignalRecordV796(d,state);\n    void prepareExnessSignalV796(d,state);\n  }\n  renderRecentSignals();\n}",'app exness call')
p.write_text(s,encoding='utf-8')

# chrome_host.go: fourth native Exness tab with persistent isolated browser profile.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if 'chExnessWnd' not in s:
    s=rep(s,'''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchRecordsWnd  uintptr
\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchRecordsCmd  *exec.Cmd
\tbtnRecords    uintptr
\tchBrowserPath string
''','''\tchAnalysisWnd uintptr
\tchWhatsappWnd uintptr
\tchRecordsWnd  uintptr
\tchExnessWnd   uintptr
\tchAnalysisCmd *exec.Cmd
\tchWhatsappCmd *exec.Cmd
\tchRecordsCmd  *exec.Cmd
\tchExnessCmd   *exec.Cmd
\tbtnRecords    uintptr
\tbtnExness     uintptr
\tchBrowserPath string
''','chrome exness vars')
    s=rep(s,'\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n)','\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n\tidExness        = 1004 // '+MARK+'\n)','exness id')
    s=rep(s,'''\tif chRecordsWnd != 0 {
\t\tchSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''','''\tif chRecordsWnd != 0 {
\t\tchSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
\tif chExnessWnd != 0 {
\t\tchSetWindowPos.Call(chExnessWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
\t}
''','exness resize')
    s=rep(s,'''\tif btnRecords != 0 {
\t\tchMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 452, 7, 145, 30, 1)
\t}
''','''\tif btnRecords != 0 {
\t\tchMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
\t}
\tif btnExness != 0 {
\t\tchMoveWindow.Call(btnExness, 452, 7, 140, 30, 1)
\t}
\tif chSignalLinkBtn != 0 {
\t\tchMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
\t}
''','exness button layout')
    s=rep(s,'''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\trecords := chRecordsWnd
\tchMu.Unlock()
''','''\tanalysis := chAnalysisWnd
\twhatsapp := chWhatsappWnd
\trecords := chRecordsWnd
\texness := chExnessWnd
\tchMu.Unlock()
''','exness desired vars')
    old='''\tif which == 2 {
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
'''
    new='''\tif which == 2 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif exness != 0 { chShowWindowAsync.Call(exness, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWShow) }
\t\treturn
\t}
\tif which == 3 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif exness != 0 { chShowWindowAsync.Call(exness, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWShow) }
\t\treturn
\t}
\tif which == 4 {
\t\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
\t\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\t\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\t\tif exness != 0 { chShowWindowAsync.Call(exness, chSWShow) }
\t\treturn
\t}
\tif whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
\tif records != 0 { chShowWindowAsync.Call(records, chSWHide) }
\tif exness != 0 { chShowWindowAsync.Call(exness, chSWHide) }
\tif analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }
'''
    s=rep(s,old,new,'exness view logic')
    s=rep(s,'''\t\tcase idRecords:
\t\t\tchSwitchView(3)
\t\tcase chIDSignalLink:
''','''\t\tcase idRecords:
\t\t\tchSwitchView(3)
\t\tcase idExness:
\t\t\tchSwitchView(4)
\t\tcase chIDSignalLink:
''','exness command')
    s=rep(s,'''\tbtnRecords, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
\t\tchWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 452, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''','''\tbtnRecords, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
\t\tchWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
\t)
\tbtnExness, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Exness"))),
\t\tchWSChild|chWSVisible, 452, 7, 140, 30, hostHWND, idExness, inst, 0,
\t)
\tchSignalLinkBtn, _, _ = chCreateWindowEx.Call(
\t\t0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
\t\tchWSChild, 600, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
\t)
''','exness button create')
    s=rep(s,'''\t\tchSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''','''\t\tchSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(btnExness, uintptr(unsafe.Pointer(darkTheme)), 0)
\t\tchSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
''','exness dark theme')
    launch='''\tgo func() {
\t\ttime.Sleep(300 * time.Millisecond)
\t\tcmd, wnd, err := chLaunchBrowser("ExnessProfile", "https://my.exness.global/webtrading/", 17882)
\t\tif err != nil { return }
\t\tchMu.Lock()
\t\tif chStopping {
\t\t\tchMu.Unlock()
\t\t\t_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
\t\t\treturn
\t\t}
\t\tchExnessCmd, chExnessWnd = cmd, wnd
\t\tchAttachBrowser(chExnessWnd)
\t\tchShowWindowAsync.Call(chExnessWnd, chSWHide)
\t\tchMu.Unlock()
\t\tchResizeChildren()
\t\tchApplyDesiredBrowserView()
\t}()

'''
    s=rep(s,'\tvar m chMsg\n',launch+'\tvar m chMsg\n','exness launch')
    s=rep(s,'''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd}
\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd = nil, nil, nil
\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd = 0, 0, 0
''','''\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chExnessCmd}
\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd, chExnessCmd = nil, nil, nil, nil
\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd, chExnessWnd = 0, 0, 0, 0
''','exness shutdown')
p.write_text(s,encoding='utf-8')

print('PASS Exness integration: fourth persistent tab + local signal prefill bridge; no submit action')
