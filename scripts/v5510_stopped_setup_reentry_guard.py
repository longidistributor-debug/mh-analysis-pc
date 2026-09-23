from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

anchor="const activeStorageKey=k=>`mh-active-signal-v797:${k}`;\n"
insert="""const stoppedStorageKey=k=>`mh-stopped-setup-v5510:${k}`;
function persistStoppedSetupV5510(k,s,c){try{if(!s)return;const st=stats(c),m=empiricalDistanceModel(c,s.direction,st),last=c?.at?.(-1);localStorage.setItem(stoppedStorageKey(k),JSON.stringify({direction:s.direction,entry:Number(s.entry),sl:Number(s.sl),tp1:Number(s.tp1),tp2:Number(s.tp2),stoppedAt:Date.now(),stoppedCandleTime:Number(last?.t||0),entryTolerance:Number(m?.entryTolerance||st.trMedian*.5),trMedian:Number(st.trMedian||0)}))}catch(e){}}
function restoreStoppedSetupV5510(k){try{const x=JSON.parse(localStorage.getItem(stoppedStorageKey(k))||'null');return x&&Number.isFinite(Number(x.entry))?x:null}catch(e){return null}}
function clearStoppedSetupV5510(k){try{localStorage.removeItem(stoppedStorageKey(k))}catch(e){}}
function applyStoppedSetupReentryGuardV5510(d,c,k){
  const failed=restoreStoppedSetupV5510(k),sig=d?.signal;if(!failed||!sig)return false;
  if(String(sig.direction)!==String(failed.direction)){clearStoppedSetupV5510(k);return false}
  const st=stats(c),m=empiricalDistanceModel(c,sig.direction,st),tol=Math.max(Number(failed.entryTolerance)||0,Number(m?.entryTolerance)||0,Number(failed.trMedian||0)*.5,Number(st.trMedian||0)*.5),drift=Math.abs(Number(sig.entry)-Number(failed.entry));
  if(drift>tol){clearStoppedSetupV5510(k);return false}
  d.signal=null;d._stoppedReentryBlocked=true;d.explanation=`No new trade: the previous ${failed.direction} setup was stopped out and the fresh analysis is still proposing the same failed entry zone. A genuinely new structure / meaningful entry-zone shift is required before re-entry.`;return true;
}
"""
if 'function applyStoppedSetupReentryGuardV5510' not in s:
    if anchor not in s: raise SystemExit('activeStorageKey anchor missing')
    s=s.replace(anchor,anchor+insert,1)

# NEW ANALYZE: use a stable expression anchor and keep the patch idempotent.
new_marker="persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k)"
if new_marker not in s:
    analyze_anchor="const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null)"
    if analyze_anchor not in s: raise SystemExit('NEW ANALYZE expression anchor missing')
    replacement=analyze_anchor+";if(prev&&signalTouched(c,prev,'sl'))persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k)"
    s=s.replace(analyze_anchor,replacement,1)

old2="else if(slHit){status='INVALID — original structural invalidation / SL was breached';}"
new2="else if(slHit){persistStoppedSetupV5510(k,s,c);status='INVALID — original structural invalidation / SL was breached';}"
if "else if(slHit){persistStoppedSetupV5510(k,s,c);" not in s:
    if old2 not in s: raise SystemExit('SL invalidation anchor missing')
    s=s.replace(old2,new2,1)

p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.10\n',encoding='utf-8')
for fn in ['updater.go','license_auth.go','web/index.html']:
    q=Path(fn); t=q.read_text(encoding='utf-8'); t=t.replace('V.55.9','V.55.10'); q.write_text(t,encoding='utf-8')
