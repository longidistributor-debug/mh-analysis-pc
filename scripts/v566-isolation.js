const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,needle,label){if(!s.includes(needle))throw new Error(label+' marker not found')}

// Persist exact selected MT5 executable in the existing settings file.
{
  const p='main.go'; let s=read(p);
  if(!s.includes('MT5Path')){
    const re=/(\tWhatsAppLink2\s+string\s+`json:"whatsapp_link2"`\n)/;
    if(!re.test(s))throw new Error('settings struct marker not found');
    s=s.replace(re,'$1\tMT5Path       string `json:"mt5_path"`\n');
  }
  write(p,s);
}

// Force all legacy MT5 entry points to the exact user-selected executable and
// restore a pre-existing selected terminal on MH Analysis shutdown.
{
  const p='chrome_host.go'; let s=read(p);
  let a=s.indexOf('func chMT5Executable() (string, error) {');
  let b=s.indexOf('\nfunc chFindProcessWindow(',a);
  if(a<0||b<0)throw new Error('chMT5Executable block not found');
  s=s.slice(0,a)+`func chMT5Executable() (string, error) {\n\treturn v566SelectedMT5Path()\n}\n`+s.slice(b+1);

  a=s.indexOf('func chEnsureMT5Terminal() error {');
  b=s.indexOf('\nfunc runChromeHost()',a);
  if(a<0||b<0)throw new Error('legacy chEnsureMT5Terminal block not found');
  s=s.slice(0,a)+`func chEnsureMT5Terminal() error {\n\treturn chEnsureMT5TerminalV36()\n}\n`+s.slice(b+1);

  const old=`\tchMu.Lock()\n\tchStopping = true\n\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd}\n\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil\n\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0\n\tchMu.Unlock()\n\n\t// Never hold the UI mutex while waiting for taskkill.\n`;
  must(s,old,'chStopBrowsers');
  const neu=`\tchMu.Lock()\n\tchStopping = true\n\tmt5Wnd := chMT5Wnd\n\tmt5Owned := chMT5Cmd != nil && chMT5Cmd.Process != nil\n\tcmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd}\n\tchAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil\n\tchAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0\n\tchMu.Unlock()\n\n\t// A terminal that was already running before MH Analysis selected it is not\n\t// owned by MH Analysis. Restore it as a normal desktop window on shutdown.\n\tif mt5Wnd != 0 && !mt5Owned { v566RestoreStandaloneMT5(mt5Wnd) }\n\n\t// Never hold the UI mutex while waiting for taskkill.\n`;
  s=s.replace(old,neu);
  write(p,s);
}

// Exact-path/PID-only MT5 embedding. No global MT5 enumeration may hide or
// re-parent unrelated terminals.
{
  const p='mt5_embed_v36.go'; let s=read(p);
  let a=s.indexOf('func v36FindRunningMT5() uintptr {');
  let b=s.indexOf('\nfunc v36EmbedMT5(',a);
  if(a<0||b<0)throw new Error('v36FindRunningMT5 block not found');
  s=s.slice(0,a)+`func v36FindRunningMT5() uintptr { return v566FindSelectedMT5Window() }\n`+s.slice(b+1);

  a=s.indexOf('func v5410FindMT5Candidate() uintptr {');
  b=s.indexOf('\nfunc v546HideAllMT5TopLevel()',a);
  if(a<0||b<0)throw new Error('v5410FindMT5Candidate block not found');
  s=s.slice(0,a)+`func v5410FindMT5Candidate() uintptr { return v566FindSelectedMT5Window() }\n`+s.slice(b+1);

  a=s.indexOf('func v546HideAllMT5TopLevel()');
  b=s.indexOf('\nfunc v546EmbedOnlyMT5(',a);
  if(a<0||b<0)throw new Error('hide-all MT5 block not found');
  s=s.slice(0,a)+`func v546HideAllMT5TopLevel() {\n    // V56.6 isolation rule: never hide/minimize/re-parent any unrelated MT5.\n}\n`+s.slice(b+1);

  a=s.indexOf('func v55MaintainMT5Embed(');
  b=s.indexOf('\nfunc v55MT5HideGuard(',a);
  if(a<0||b<0)throw new Error('MT5 maintenance block not found');
  s=s.slice(0,a)+`func v55MaintainMT5Embed(wait time.Duration) {\n    deadline:=time.Now().Add(wait)\n    for time.Now().Before(deadline) {\n        chMu.Lock(); hwnd:=chMT5Wnd; chMu.Unlock()\n        if hwnd!=0 {\n            if path,err:=v566SelectedMT5Path();err==nil && v566WindowMatchesPath(hwnd,path) {\n                parent,_,_:=v36GetParent.Call(hwnd)\n                if parent!=hostHWND { _=v36EmbedMT5(hwnd) }\n            }\n        }\n        time.Sleep(350*time.Millisecond)\n    }\n}\n`+s.slice(b+1);

  a=s.indexOf('func v55MT5HideGuard(');
  b=s.indexOf('\n\nfunc chEnsureMT5TerminalV36()',a);
  if(a<0||b<0)throw new Error('MT5 hide guard block not found');
  s=s.slice(0,a)+`func v55MT5HideGuard(stop <-chan struct{}) { <-stop }\n`+s.slice(b+2);

  a=s.indexOf('func chEnsureMT5TerminalV36() error {');
  if(a<0)throw new Error('chEnsureMT5TerminalV36 not found');
  const ensure=`func chEnsureMT5TerminalV36() error {\n    path,err:=v566SelectedMT5Path()\n    if err!=nil{return err}\n\n    chMu.Lock();existingEmbedded:=chMT5Wnd;chMu.Unlock()\n    if existingEmbedded!=0 && v566WindowMatchesPath(existingEmbedded,path) {\n        parent,_,_:=v36GetParent.Call(existingEmbedded)\n        if parent!=hostHWND && !v36EmbedMT5(existingEmbedded) { return errors.New("Selected MT5 could not be embedded. Make sure MH Analysis and that MT5 use the same Windows privilege level.") }\n        chResizeChildren()\n        if !v55WaitMT5RenderReady(3*time.Second){return errors.New("Selected MT5 is still initializing. Please click MH MT5 again in a moment.")}\n        go v55MaintainMT5Embed(5*time.Second);go mt5ApplyLatestQueued();return nil\n    }\n\n    chMu.Lock();if chMT5StartingV34{chMu.Unlock();return nil};chMT5StartingV34=true;chMu.Unlock()\n    defer func(){chMu.Lock();chMT5StartingV34=false;chMu.Unlock()}()\n\n    // Reuse only a running window whose process image matches the exact selected EXE path.\n    if hwnd:=v566FindWindowForPath(path);hwnd!=0 {\n        if !v36EmbedMT5(hwnd){return errors.New("Selected running MT5 was found, but Windows refused child embedding. Make sure MH Analysis and that MT5 use the same Windows privilege level.")}\n        chMu.Lock();chMT5Cmd=nil;chMu.Unlock()\n        if !v55WaitMT5RenderReady(4*time.Second){return errors.New("Selected MT5 embedded but did not become render-ready.")}\n        go v55MaintainMT5Embed(8*time.Second);go mt5ApplyLatestQueued();return nil\n    }\n\n    v5410MT5ExeBase=strings.ToLower(filepath.Base(path))\n    cmd:=exec.Command(path)\n    cmd.SysProcAttr=&syscall.SysProcAttr{HideWindow:true,CreationFlags:0x08000000}\n    if err:=cmd.Start();err!=nil{return fmt.Errorf("Could not start selected MT5: %w",err)}\n    chMu.Lock();chMT5Cmd=cmd;chMu.Unlock()\n\n    deadline:=time.Now().Add(20*time.Second)\n    var hwnd uintptr\n    for time.Now().Before(deadline) {\n        hwnd=v566FindWindowForPID(uint32(cmd.Process.Pid))\n        if hwnd==0 { hwnd=v566FindWindowForPath(path) }\n        if hwnd!=0 { break }\n        time.Sleep(80*time.Millisecond)\n    }\n    if hwnd==0 {\n        _=cmd.Process.Kill()\n        chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock()\n        return errors.New("The selected MT5 started but its exact terminal window could not be found. No other MT5 terminal was touched.")\n    }\n    if !v566WindowMatchesPath(hwnd,path) {\n        _=cmd.Process.Kill()\n        chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock()\n        return errors.New("MT5 window path validation failed. No other MT5 terminal was touched.")\n    }\n    if !v36EmbedMT5(hwnd) {\n        _=cmd.Process.Kill()\n        chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock()\n        return errors.New("Selected MT5 could not be embedded inside MH Analysis.")\n    }\n    if !v55WaitMT5RenderReady(4*time.Second){\n        _=cmd.Process.Kill()\n        chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMT5Wnd=0;chMu.Unlock()\n        return errors.New("Selected MT5 started but its embedded view did not become render-ready.")\n    }\n    go v55MaintainMT5Embed(10*time.Second);go mt5ApplyLatestQueued();return nil\n}\n`;
  s=s.slice(0,a)+ensure;
  write(p,s);
}

// First MH MT5 click in each app run confirms the exact saved/selected EXE.
{
  const p='webview2_host.go'; let s=read(p);
  const old='func wv2ShowMT5(){v546HideAllMT5TopLevel();';
  must(s,old,'wv2ShowMT5');
  s=s.replace(old,'func wv2ShowMT5(){if !v566MT5SelectionConfirmed{v566ShowMT5Selector();return};v546HideAllMT5TopLevel();');
  const hook='case wmMT5ReadyV5412:wv2ActivateMT5V5412();return 0;case wmWhatsAppNativeEnterV5414:';
  must(s,hook,'MT5 ready message hook');
  s=s.replace(hook,'case wmMT5ReadyV5412:wv2ActivateMT5V5412();return 0;case wmMT5SelectedV566:wv2ShowMT5();return 0;case wmWhatsAppNativeEnterV5414:');
  write(p,s);
}

// A pre-existing selected MT5 has no *exec.Cmd owned by MH Analysis. Derive its
// PID from the exact embedded HWND so native prefill stays isolated to that process.
{
  const p='mt5_prefill.go'; let s=read(p);
  if(!s.includes('"unsafe"')){
    const marker='\t"unicode/utf16"\n'; must(s,marker,'mt5 prefill imports');
    s=s.replace(marker,marker+'\t"unsafe"\n');
  }
  const ready=`func mt5ReadyAndVisible() bool {\n\tchMu.Lock()\n\twnd := chMT5Wnd\n\tcmd := chMT5Cmd\n\tchMu.Unlock()\n\treturn wnd != 0 && cmd != nil && cmd.Process != nil\n}`;
  must(s,ready,'mt5ReadyAndVisible');
  s=s.replace(ready,`func mt5ReadyAndVisible() bool {\n\tchMu.Lock()\n\twnd := chMT5Wnd\n\tchMu.Unlock()\n\treturn wnd != 0\n}`);
  const start=`\tchMu.Lock()\n\tcmd := chMT5Cmd\n\twnd := chMT5Wnd\n\tchMu.Unlock()\n\tif cmd == nil || cmd.Process == nil || wnd == 0 {\n\t\treturn "", fmt.Errorf("MT5 terminal is not ready")\n\t}`;
  must(s,start,'mt5RunUIPrefill start');
  s=s.replace(start,`\tchMu.Lock()\n\twnd := chMT5Wnd\n\tchMu.Unlock()\n\tif wnd == 0 {\n\t\treturn "", fmt.Errorf("MT5 terminal is not ready")\n\t}\n\tvar mt5PID uint32\n\tchGetWindowThreadPID.Call(wnd, uintptr(unsafe.Pointer(&mt5PID)))\n\tif mt5PID == 0 {\n\t\treturn "", fmt.Errorf("Selected MT5 process could not be resolved")\n\t}`);
  const env='"MH_MT5_PID="+strconv.Itoa(cmd.Process.Pid),';
  must(s,env,'MT5 PID env');
  s=s.replace(env,'"MH_MT5_PID="+strconv.FormatUint(uint64(mt5PID),10),');
  write(p,s);
}

// Re-evaluation management is now Pair + Timeframe scoped. Let the EA match the
// exact timeframe instead of using the old symbol-wide active-state gate.
{
  const p='web/app.js'; let s=read(p);
  const broad="  const st=await readMT5ActiveStateV552(symbol);if(!st?.active||String(st.direction||'').toUpperCase()!==String(managed.direction||'').toUpperCase())return null;\n";
  must(s,broad,'broad re-evaluation active-state gate');
  s=s.replace(broad,"  // V56.6: EA performs exact Pair + Timeframe matching; do not block on symbol-wide state.\n");
  const payload="partial_tp:partialTpEnabled,reason:status||'RE-EVALUATE'";
  must(s,payload,'manage payload');
  s=s.replace(payload,"partial_tp:partialTpEnabled,timeframe:String(timeframe||'').toLowerCase(),reason:status||'RE-EVALUATE'");
  write(p,s);
}

// Carry timeframe through manage.txt so V1.36 can modify only the intended
// position/pending strategy on the same pair.
{
  const p='ea_signal_bridge.go'; let s=read(p);
  s=s.replace('// manage.txt: MANAGE_ID|SYMBOL|BUY/SELL|SL|FINAL_TP|REASON|TP1|TP2|PARTIAL_TP','// manage.txt: MANAGE_ID|SYMBOL|BUY/SELL|SL|FINAL_TP|REASON|TP1|TP2|PARTIAL_TP|TIMEFRAME');
  if(!s.includes('Timeframe string  `json:"timeframe"`')){
    const marker='\tDirection string  `json:"direction"`\n'; must(s,marker,'eaManageRequest direction');
    s=s.replace(marker,marker+'\tTimeframe string  `json:"timeframe"`\n');
  }
  const norm='q.ManageID=cleanEAToken(q.ManageID);q.Symbol=normalizeEABridgeSymbol(q.Symbol);q.Direction=eaDirection(q.Direction);q.Reason=cleanEAToken(q.Reason)';
  must(s,norm,'manage normalization');
  s=s.replace(norm,norm+';q.Timeframe=strings.ToLower(strings.TrimSpace(q.Timeframe))');
  const dircheck='if q.Direction!="BUY"&&q.Direction!="SELL"{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"direction must be BUY or SELL"});return}';
  must(s,dircheck,'manage direction check');
  s=s.replace(dircheck,dircheck+'\n\tif q.Timeframe!="1m"&&q.Timeframe!="5m"&&q.Timeframe!="15m"&&q.Timeframe!="30m"&&q.Timeframe!="1h"{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"unsupported manage timeframe"});return}');
  const line="line:=strings.Join([]string{q.ManageID,q.Symbol,q.Direction,strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),q.Reason,strconv.FormatFloat(q.TP1,'f',-1,64),strconv.FormatFloat(q.TP2,'f',-1,64),strconv.FormatBool(q.PartialTP)},\"|\")+\"\\r\\n\"";
  must(s,line,'manage mailbox line');
  s=s.replace(line,"line:=strings.Join([]string{q.ManageID,q.Symbol,q.Direction,strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),q.Reason,strconv.FormatFloat(q.TP1,'f',-1,64),strconv.FormatFloat(q.TP2,'f',-1,64),strconv.FormatBool(q.PartialTP),q.Timeframe},\"|\")+\"\\r\\n\"");
  write(p,s);
}

// Verification markers.
const mt5=read('mt5_embed_v36.go');
if(!mt5.includes('v566FindWindowForPath(path)')||!mt5.includes('No other MT5 terminal was touched'))throw new Error('V56.6 exact MT5 isolation missing');
if(!read('webview2_host.go').includes('v566ShowMT5Selector'))throw new Error('V56.6 MT5 selector hook missing');
if(!read('ea_signal_bridge.go').includes('PARTIAL_TP|TIMEFRAME'))throw new Error('V56.6 timeframe manage bridge missing');
if(!read('web/app.js').includes('EA performs exact Pair + Timeframe matching'))throw new Error('V56.6 timeframe app isolation missing');
console.log('V56.6 isolation patch applied');
