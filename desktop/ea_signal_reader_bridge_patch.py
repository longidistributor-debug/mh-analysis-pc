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

# No extra EA button is added. A manual NEW ANALYZE click is the explicit
# per-signal action: when that click produces a signal, hand it to the attached
# EA immediately. Timer-driven NEW ANALYZE does not hand off a trade signal.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if 'sendManualNewAnalyzeSignalToEAV796' not in s:
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
async function sendManualNewAnalyzeSignalToEAV796(d){
  const sig=d?.signal;
  if(!sig)return null;
  const signalId=`MH${Date.now()}_${symbol}_${timeframe}`;
  try{
    const payload={signal_id:signalId,symbol,type:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp:Number(sig.tp1),lot:0,expiry:0};
    const r=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    let j={};try{j=await r.json()}catch(_){ }
    if(!r.ok)throw new Error(j.error||`EA bridge HTTP ${r.status}`);
    let st=null;
    for(let i=0;i<8&&!st;i++){
      await new Promise(res=>setTimeout(res,300));
      st=await readEAStatusV796(signalId);
    }
    if(st){
      const detail=[st.symbol,st.type,st.message].filter(Boolean).join(' • ');
      console.log(`MH EA ${st.state}: ${detail}`);
    }else console.log('MH EA signal published; status pending',signalId);
    return st||{state:'SENT',id:signalId};
  }catch(e){
    console.warn('MH EA bridge failed',e);
    const exp=$('#explanation');
    if(exp){exp.className='detailText bad';exp.textContent=`EA bridge: ${e.message||e}`}
    return null;
  }
}
'''
    s=rep(s,
        'async function saveBackendSetting(payload){',
        fn+'\nasync function saveBackendSetting(payload){',
        'EA bridge JS functions')
    s=rep(s,
        "    renderDecision(d,reason,'NEW');\n",
        "    renderDecision(d,reason,'NEW');\n    if(d.signal&&!fromAuto)void sendManualNewAnalyzeSignalToEAV796(d); // "+MARK+" manual NEW ANALYZE handoff\n",
        'manual NEW ANALYZE EA handoff')
p.write_text(s,encoding='utf-8')

print('PASS EA signal reader bridge: no extra button; manual NEW ANALYZE signal is handed to attached EA automatically')
