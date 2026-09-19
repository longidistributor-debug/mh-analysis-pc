from pathlib import Path

MARK='MH_EA_SIGNAL_READER_BRIDGE_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# Register the local MT5 EA bridge after the existing native MT5 prefill route.
p=Path('main.go')
s=p.read_text(encoding='utf-8')
if 'registerEASignalBridgeRoutes(mux)' not in s:
    s=rep(s,
        '\tregisterMT5PrefillRoutes(mux) // MH_NATIVE_MT5_PREFILL_V796\n',
        '\tregisterMT5PrefillRoutes(mux) // MH_NATIVE_MT5_PREFILL_V796\n\tregisterEASignalBridgeRoutes(mux) // '+MARK+'\n',
        'register EA bridge')
p.write_text(s,encoding='utf-8')

# Add one explicit handoff button. The attached EA remains responsible for
# reading Common\\Files\\MH_Analysis\\signal.txt and reporting status.txt.
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
if 'id="sendToEA"' not in s:
    s=rep(s,
'''      <div class="actionRow">
        <button id="analyze" class="analyzeBtn">↻ NEW ANALYZE</button>
        <button id="reevaluate" class="reevaluateBtn">↻ RE-EVALUATE</button>
      </div>
''',
'''      <div class="actionRow">
        <button id="analyze" class="analyzeBtn">↻ NEW ANALYZE</button>
        <button id="reevaluate" class="reevaluateBtn">↻ RE-EVALUATE</button>
        <button id="sendToEA" class="reevaluateBtn" disabled>EA • SEND SIGNAL</button>
      </div>
''','EA handoff button')
p.write_text(s,encoding='utf-8')

# Wire current NEW ANALYZE result to the exact file format expected by the
# user's attached MH ANALYSIS DECODER EA. This is an explicit per-signal handoff.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if 'sendCurrentSignalToEAV796' not in s:
    fn=r'''
async function readEAStatusV796(expectedId=''){
  try{
    const r=await fetch('/api/mt5/ea/status',{cache:'no-store'}),j=await r.json();
    if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);
    const line=String(j.status||'');
    if(!line)return null;
    const p=line.split('|');
    if(expectedId&&p[0]!==expectedId)return null;
    return {id:p[0]||'',state:p[1]||'',ticket:p[2]||'',symbol:p[3]||'',type:p[4]||'',message:p.slice(5).join('|')||''};
  }catch(_){return null}
}
async function sendCurrentSignalToEAV796(){
  const b=$('#sendToEA'),d=lastDecision.get(keyFor()),sig=d?.signal;
  if(!sig){showError('No active NEW ANALYZE signal to send to the attached MT5 EA.');return}
  const signalId=`MH${Date.now()}_${symbol}_${timeframe}`;
  if(b){b.disabled=true;b.textContent='EA • SENDING…'}
  try{
    const payload={signal_id:signalId,symbol,type:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp:Number(sig.tp1),lot:0.01,expiry:0};
    const r=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    let j={};try{j=await r.json()}catch(_){ }
    if(!r.ok)throw new Error(j.error||`EA bridge HTTP ${r.status}`);
    if(b)b.textContent='EA • SIGNAL SENT';
    // The supplied EA polls every 250ms. Read its status response without
    // blocking the analysis UI; retries allow symbol/permission errors to surface.
    let st=null;
    for(let i=0;i<8&&!st;i++){
      await new Promise(res=>setTimeout(res,300));
      st=await readEAStatusV796(signalId);
    }
    if(st){
      if(b)b.textContent=st.state==='OK'?'EA • RECEIVED ✓':`EA • ${st.state||'STATUS'}`;
      const detail=[st.symbol,st.type,st.message].filter(Boolean).join(' • ');
      const exp=$('#explanation');
      if(exp&&detail){exp.className=`detailText ${st.state==='OK'?'good':'warn'}`;exp.textContent=`EA ${st.state}: ${detail}`}
    }else if(b)b.textContent='EA • SENT / WAITING';
  }catch(e){
    if(b)b.textContent='EA • BRIDGE ERROR';
    const exp=$('#explanation');if(exp){exp.className='detailText bad';exp.textContent=`EA bridge: ${e.message||e}`}
  }finally{
    setTimeout(()=>{const x=$('#sendToEA');if(x){x.textContent='EA • SEND SIGNAL';x.disabled=!lastDecision.get(keyFor())?.signal}},1800)
  }
}
'''
    s=rep(s,
        'async function saveBackendSetting(payload){',
        fn+'\nasync function saveBackendSetting(payload){',
        'EA bridge JS functions')
    s=rep(s,
        "  lastDecision.set(keyFor(),d);chartDecision=d;renderSignalLevels();const sig=d.signal,b=$('#signalBadge'),q=$('#signalQuality'),plan=$('#plan'),card=$('#signalCard');\n",
        "  lastDecision.set(keyFor(),d);chartDecision=d;renderSignalLevels();const sig=d.signal,b=$('#signalBadge'),q=$('#signalQuality'),plan=$('#plan'),card=$('#signalCard');\n  if($('#sendToEA')){$('#sendToEA').disabled=!sig;$('#sendToEA').textContent='EA • SEND SIGNAL'} // "+MARK+"\n",
        'enable EA button on signal')
    s=rep(s,
        "  chartDecision=null;updateSignalHeadline(null);clearSignalLevels();\n",
        "  chartDecision=null;updateSignalHeadline(null);clearSignalLevels();if($('#sendToEA')){$('#sendToEA').disabled=true;$('#sendToEA').textContent='EA • SEND SIGNAL'} // "+MARK+"\n",
        'reset EA button')
    s=rep(s,
        "$('#analyze').onclick=runAnalyze;$('#reevaluate').onclick=runReevaluate;$('#autoSignalToggle').onclick=()=>setAutoSignalEnabled(!autoSignalEnabled);$('#exitApp').onclick=async()=>{try{await fetch('/api/shutdown',{method:'POST'})}catch(e){}window.close()};\n",
        "$('#analyze').onclick=runAnalyze;$('#reevaluate').onclick=runReevaluate;const sendEA=$('#sendToEA');if(sendEA)sendEA.onclick=sendCurrentSignalToEAV796;$('#autoSignalToggle').onclick=()=>setAutoSignalEnabled(!autoSignalEnabled);$('#exitApp').onclick=async()=>{try{await fetch('/api/shutdown',{method:'POST'})}catch(e){}window.close()};\n",
        'EA button handler')
p.write_text(s,encoding='utf-8')

print('PASS EA signal reader bridge: exact Common Files protocol + status feedback + explicit handoff')
