const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

// V56.15: correct RSI-14 using Wilder smoothing (same method used by standard RSI),
// keep the visual guide at 70/30, not the accidental 75/30 line.
{
  const p='web/app.js';let s=read(p);
  const old="function rsi(v,p=14){if(v.length<2)return 50;p=Math.max(1,Math.min(p,v.length-1));let g=0,l=0;for(let i=v.length-p;i<v.length;i++){const d=v[i]-v[i-1];if(d>0)g+=d;else l-=d}if(l<1e-12)return 100;const rs=g/l;return 100-100/(1+rs)}";
  must(s,old,'legacy RSI');
  const neu=`function rsiSeriesWilder(v,p=14){\n  const n=v.length,out=Array(n).fill(50);if(n<2)return out;p=Math.max(1,Math.min(p,n-1));if(n<=p)return out;\n  let gain=0,loss=0;for(let i=1;i<=p;i++){const d=v[i]-v[i-1];if(d>0)gain+=d;else loss-=d}\n  let ag=gain/p,al=loss/p;const value=()=>al<1e-12?(ag<1e-12?50:100):(100-100/(1+ag/al));out[p]=value();\n  for(let i=p+1;i<n;i++){const d=v[i]-v[i-1],g=d>0?d:0,l=d<0?-d:0;ag=(ag*(p-1)+g)/p;al=(al*(p-1)+l)/p;out[i]=value()}\n  return out;\n}\nfunction rsi(v,p=14){const a=rsiSeriesWilder(v,p);return a.length?a[a.length-1]:50}`;
  s=s.replace(old,neu);
  const drawOld="const closes=arr.map(x=>x.c),vals=[];\n  for(let i=0;i<closes.length;i++)vals.push(i<14?50:rsi(closes.slice(0,i+1),14));";
  must(s,drawOld,'RSI chart series');s=s.replace(drawOld,"const closes=arr.map(x=>x.c),vals=rsiSeriesWilder(closes,14);");
  s=s.replace('[75,30].forEach(v=>{','[70,30].forEach(v=>{');
  write(p,s);
}

// V56.15: do not claim TP/SL was hit from OHLC that happened before the signal.
// The creation candle contains pre-signal price history, so only later candles can
// prove a lifecycle touch. This deliberately prefers "unknown" over a false hit.
{
  const p='web/app.js';let s=read(p);
  const old="function signalTouched(c,s,field){const idx=Math.max(0,c.findIndex(x=>Number(x.t)>=Number(s.createdCandleTime)));const w=c.slice(idx<0?0:idx),p=Number(s[field]);if(!Number.isFinite(p))return false;if(field==='sl')return s.direction==='BUY'?w.some(x=>x.l<=p):w.some(x=>x.h>=p);return s.direction==='BUY'?w.some(x=>x.h>=p):w.some(x=>x.l<=p)}";
  must(s,old,'signalTouched');
  const neu="function signalTouched(c,s,field){const born=Number(s?.createdCandleTime);const w=(c||[]).filter(x=>Number(x?.t)>born),p=Number(s?.[field]);if(!Number.isFinite(born)||!Number.isFinite(p)||!w.length)return false;if(field==='sl')return s.direction==='BUY'?w.some(x=>x.l<=p):w.some(x=>x.h>=p);return s.direction==='BUY'?w.some(x=>x.h>=p):w.some(x=>x.l<=p)}";
  s=s.replace(old,neu);write(p,s);
}

// V56.15: keep the signal selective without a blunt hard threshold. V56.9 already
// calibrates family/direction weights; retain that calibration while adding broader
// indication/reference consensus so one isolated top-family spike cannot dominate.
{
  const p='web/app.js';let s=read(p);
  const re=/function aggregate\(fs\)\{[^\n]*\}/;
  if(!re.test(s))throw new Error('aggregate function not found');
  const neu="function aggregate(fs){if(!fs.length)return[50,[]];const r=fs.slice().sort((a,b)=>b.score-a.score),top=r.slice(0,5),weights=top.map((x,i)=>(top.length-i)*v569FamilyMultiplier(x)),topScore=top.reduce((z,x,i)=>z+x.score*weights[i],0)/Math.max(1,weights.reduce((a,b)=>a+b,0)),broad=r.slice(0,Math.min(12,r.length)),broadAvg=avg(broad.map(x=>x.score)),support=broad.filter(x=>x.score>=58).length/Math.max(1,broad.length),consensus=40+support*60,blended=topScore*.78+broadAvg*.17+consensus*.05,dir=top[0]?.direction||'',score=50+(blended-50)*v569DirectionalMultiplier(dir);return[smooth(score),r]}";
  s=s.replace(re,neu);write(p,s);
}

// V56.15: EA handoff is the primary action. A Records write must never prevent a
// valid pending order. Use a stable signal id (ending in timeframe for EA isolation),
// safely retry the same id, then capture the Record as best-effort bookkeeping.
{
  const p='web/app.js';let s=read(p);
  const a=s.indexOf('async function dispatchUniqueSignalV36(d){');
  const b=s.indexOf('\nasync function executeNewAnalysis(fromAuto=false){',a);
  if(a<0||b<0)throw new Error('dispatchUniqueSignalV36 bounds not found');
  const dispatch=`async function dispatchUniqueSignalV36(d){\n  const sig=d?.signal;if(!sig)return null;\n  const stable=String(sig.id||sig.createdCandleTime||Date.now()).replace(/[^A-Za-z0-9.-]/g,'').slice(0,32)||String(Date.now());\n  const generatedBase=\`MH\${stable}_\${symbol}_\${timeframe}\`;\n  let signalId=(d?._sameActiveSignal&&String(d?._sameSignalId||'').trim())?String(d._sameSignalId).trim():(partialTpEnabled?\`\${generatedBase}__PT1_\${Number(sig.tp1).toFixed(10)}\`:generatedBase);\n  const selectedLot=lotForSignalScore(sig.score),finalTp=partialTpEnabled?Number(sig.tp2):Number(sig.tp1);\n  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);\n  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);\n\n  // Pending handoff first: local Records bookkeeping is not allowed to block MT5.\n  const er=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:finalTp,lot:selectedLot,expiry:0})});\n  let ej={};try{ej=await er.json()}catch(_){}\n  if(!er.ok)throw new Error(ej.error||\`EA bridge HTTP \${er.status}\`);\n\n  let rj={ok:false,skipped:false};\n  if(d?._sameActiveSignal){\n    rj={duplicate:true,same_signal:true,existing_signal_id:signalId,existing_status:d._sameSignalStatus||''};\n  }else{\n    const recordPayload={signal_id:signalId,symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2),score:Number(sig.score)||0,setup:d.bestFamily||sig.setupReason||'',partial_tp:partialTpEnabled,action:'NEW'};\n    try{\n      const rr=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordPayload)});\n      try{rj=await rr.json()}catch(_){}\n      if(!rr.ok)rj={ok:false,error:rj.error||\`Records HTTP \${rr.status}\`};\n    }catch(e){rj={ok:false,error:String(e?.message||e)}}\n  }\n\n  try{await prepareMT5SignalV796(d,'NEW')}catch(_){}\n  const recordNote=rj?.error?' • Record warning (pending still sent)':'';\n  setAutoStatus(\`MT5 pending sent • \${pending} • Lot \${selectedLot.toFixed(2)} • Partial TP \${partialTpEnabled?'ON':'OFF'}\${recordNote}\`,'good');\n  return {record:rj,ea:ej,signal_id:signalId,pending_sent:true};\n}\n`;
  s=s.slice(0,a)+dispatch+s.slice(b);write(p,s);
}

// Assertions.
{
  const s=read('web/app.js');
  must(s,'function rsiSeriesWilder','Wilder RSI');
  must(s,'[70,30].forEach','RSI 70/30 guides');
  must(s,'Number(x?.t)>born','post-signal lifecycle touch');
  must(s,'topScore*.78+broadAvg*.17+consensus*.05','holistic aggregate');
  must(s,'v569DirectionalMultiplier(dir)','V56.9 calibration preserved');
  must(s,'Pending handoff first: local Records bookkeeping is not allowed to block MT5.','EA-first handoff');
  must(s,'generatedBase=`MH${stable}_${symbol}_${timeframe}`','stable timeframe-ending signal id');
}
console.log('V56.15 RSI + lifecycle + holistic signal + reliable EA handoff patch applied');
