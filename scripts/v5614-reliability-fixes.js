const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

// V56.14 #1: pair/timeframe selection remains API-silent, but the visible
// context must immediately match the selected pair. Never leave the old XAUUSD
// label/candles visible after BTCUSDT is selected.
{
  const p='web/app.js';let s=read(p);
  const marker='async function contextChanged(){';
  must(s,marker,'contextChanged');
  if(!s.includes('function v5614SyncVisibleContext(){')){
    const helper=`function v5614SyncVisibleContext(){\n  // UI-only context switch: zero market/provider requests.\n  const label=\`${'${symbol}'} • ${'${timeframe}'}\`;\n  const chartLabel=$('#chartLabel');if(chartLabel)chartLabel.textContent=label;\n  const currentPair=$('#currentPair');if(currentPair)currentPair.textContent=label;\n  const nativeSymbol=$('#nativeSymbol');if(nativeSymbol)nativeSymbol.textContent=symbol;\n  $$('.pair').forEach(b=>b.classList.toggle('active',String(b.dataset.symbol||'').toUpperCase()===String(symbol||'').toUpperCase()));\n  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));\n  try{candleSeries?.setData([])}catch(_){}\n  try{volumeSeries?.setData([])}catch(_){}\n  try{drawRsiChart($('#rsiCanvas'),[])}catch(_){}\n  clearSignalLevels();\n  const empty=$('#chartEmpty');if(empty){empty.classList.remove('hidden');empty.textContent=\`Press NEW ANALYZE or RE-EVALUATE to load ${'${symbol}'} ${'${timeframe}'}.\`;}\n  const feed=$('#nativeFeedStatus');if(feed)feed.textContent='Manual selection • 0 FCS calls • press NEW ANALYZE or RE-EVALUATE';\n}\n`;
    s=s.replace(marker,helper+'\n'+marker);
  }
  const a=s.indexOf('async function contextChanged(){');
  const b=s.indexOf('\n}',a);
  if(a<0||b<0)throw new Error('contextChanged block bounds not found');
  let block=s.slice(a,b+2);
  if(!block.includes('v5614SyncVisibleContext();')){
    const brace=block.indexOf('{')+1;
    block=block.slice(0,brace)+'\n  v5614SyncVisibleContext();'+block.slice(brace);
    s=s.slice(0,a)+block+s.slice(b+2);
  }
  write(p,s);
}

// V56.14 #2: EA owns SL Adjustment. App sends RAW analysis SL unchanged.
{
  const p='ea_signal_bridge.go';let s=read(p);
  const a=s.indexOf('\t// V.55.8: SL Adjustment is isolated here');
  const b=s.indexOf('\n\t// Reversal safety remains app-side',a);
  if(a<0||b<0)throw new Error('legacy app-side SL adjustment block not found');
  s=s.slice(0,a)+'\t// V56.14: send RAW analysis SL unchanged. EA V1.37 is the single SL Adjustment authority.\n'+s.slice(b);
  write(p,s);
}

// V56.14 #3: publish native mode state at startup so EA config and buttons agree.
{
  const p='ea_modes_v558.go';let s=read(p);
  const a=s.indexOf('func registerV558ModeRoutes(mux *http.ServeMux) {');
  const b=s.indexOf('\n}\n\nfunc v558Snapshot()',a);
  if(a<0||b<0)throw new Error('mode route function not found');
  let block=s.slice(a,b+2);
  if(!block.includes('V56.14 startup synchronization')){
    const close=block.lastIndexOf('\n}');
    block=block.slice(0,close)+'\n    _ = v558PublishConfig() // V56.14 startup synchronization'+block.slice(close);
    s=s.slice(0,a)+block+s.slice(b+2);
  }
  s=s.replace('"V.56.0",','"V.56.14",');
  write(p,s);
}

// V56.14 #4: harden exact selected MT5 startup/embedding; unrelated MT5 stays untouched.
{
  const p='mt5_embed_v36.go';let s=read(p);
  if(s.indexOf('func chEnsureMT5TerminalV36() error {')<0)throw new Error('generated V56.6 MT5 ensure function not found');
  const stale='    chMu.Lock();existingEmbedded:=chMT5Wnd;chMu.Unlock()\n';
  must(s,stale,'existing embedded MT5 marker');
  if(!s.includes('V56.14 stale selected-window recovery')){
    s=s.replace(stale,stale+`    // V56.14 stale selected-window recovery: clear only an invalid old HWND.\n    if existingEmbedded!=0 && !v566WindowMatchesPath(existingEmbedded,path) {\n        chMu.Lock(); if chMT5Wnd==existingEmbedded { chMT5Wnd=0 }; chMu.Unlock()\n        existingEmbedded=0\n    }\n`);
  }
  s=s.replace('v55WaitMT5RenderReady(3*time.Second)','v55WaitMT5RenderReady(8*time.Second)');
  s=s.replace(/v55WaitMT5RenderReady\(4\*time\.Second\)/g,'v55WaitMT5RenderReady(8*time.Second)');
  s=s.replace('deadline:=time.Now().Add(20*time.Second)','deadline:=time.Now().Add(35*time.Second)');
  s=s.replace('go v55MaintainMT5Embed(5*time.Second)','go v55MaintainMT5Embed(10*time.Second)');
  s=s.replace('go v55MaintainMT5Embed(8*time.Second)','go v55MaintainMT5Embed(12*time.Second)');
  const runOld=`    if hwnd:=v566FindWindowForPath(path);hwnd!=0 {\n        if !v36EmbedMT5(hwnd){return errors.New("Selected running MT5 was found, but Windows refused child embedding. Make sure MH Analysis and that MT5 use the same Windows privilege level.")}\n`;
  const runNew=`    if hwnd:=v566FindWindowForPath(path);hwnd!=0 {\n        if !v36EmbedMT5(hwnd){\n            time.Sleep(650*time.Millisecond)\n            retry:=v566FindWindowForPath(path)\n            if retry==0 || !v36EmbedMT5(retry){return errors.New("Selected running MT5 was found, but Windows refused child embedding. Make sure MH Analysis and that MT5 use the same Windows privilege level.")}\n            hwnd=retry\n        }\n`;
  must(s,runOld,'running MT5 embed block');s=s.replace(runOld,runNew);
  const launchOld=`    if !v36EmbedMT5(hwnd) {\n        _=cmd.Process.Kill()\n        chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock()\n        return errors.New("Selected MT5 could not be embedded inside MH Analysis.")\n    }\n`;
  const launchNew=`    if !v36EmbedMT5(hwnd) {\n        time.Sleep(650*time.Millisecond)\n        retry:=v566FindWindowForPID(uint32(cmd.Process.Pid))\n        if retry==0 { retry=v566FindWindowForPath(path) }\n        if retry==0 || !v566WindowMatchesPath(retry,path) || !v36EmbedMT5(retry) {\n            _=cmd.Process.Kill()\n            chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock()\n            return errors.New("Selected MT5 could not be embedded inside MH Analysis after a safe retry.")\n        }\n        hwnd=retry\n    }\n`;
  must(s,launchOld,'launched MT5 embed block');s=s.replace(launchOld,launchNew);
  write(p,s);
}

// Assertions.
{
  const app=read('web/app.js');
  must(app,'function v5614SyncVisibleContext()','V56.14 visible context sync');
  const a=app.indexOf('async function contextChanged(){'),b=app.indexOf('\n}',a),blk=app.slice(a,b);
  if(/fetchCandles|analysis-snapshot-v569|\/api\/history/.test(blk))throw new Error('V56.14 context selection made a market request');
  const bridge=read('ea_signal_bridge.go');
  must(bridge,'V56.14: send RAW analysis SL unchanged','raw SL bridge');
  if(bridge.includes('if v558Snapshot().SLAdjustment && q.Lot >= 0.02'))throw new Error('legacy app-side SL mutation still present');
  const modes=read('ea_modes_v558.go');must(modes,'V56.14 startup synchronization','mode startup sync');
  const mt5=read('mt5_embed_v36.go');
  must(mt5,'V56.14 stale selected-window recovery','MT5 stale handle recovery');
  must(mt5,'deadline:=time.Now().Add(35*time.Second)','MT5 launch wait');
  must(mt5,'No other MT5 terminal was touched','exact MT5 isolation baseline');
}
console.log('V56.14 BTC context + MT5 reliability + SL authority fixes applied');
