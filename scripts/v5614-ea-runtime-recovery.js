const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

// V56.14 EA runtime recovery:
// 1) A local Record is NOT proof the EA received/placed the pending order.
//    Re-use the existing signal_id and safely re-publish it to the EA mailbox.
//    The EA deduplicates the same signal_id after successful processing.
// 2) Partial-TP ON/OFF is part of same-signal identity so an old non-partial
//    Record cannot suppress a new Partial-TP handoff.
// 3) Restore the requested automatic lot map.
{
  const p='web/app.js';let s=read(p);

  const lotOld=`function lotForSignalScore(score){\n  if(!lotSizeEnabled)return 0.02;\n  const n=Math.max(0,Math.min(100,Number(score)||0));\n  if(n>=95)return 0.06;\n  if(n>=90)return 0.05;\n  if(n>=85)return 0.05;\n  if(n>=80)return 0.04;\n  if(n>=70)return 0.04;\n  if(n>=65)return 0.03;\n  return 0.02;\n}`;
  const lotNew=`function lotForSignalScore(score){\n  if(!lotSizeEnabled)return 0.02;\n  const n=Math.max(0,Math.min(100,Number(score)||0));\n  // V56.14 requested auto-lot map: 0-65=.02, 66-72=.03, 73-82=.04, 83-100=.05.\n  if(n>=83)return 0.05;\n  if(n>=73)return 0.04;\n  if(n>=66)return 0.03;\n  return 0.02;\n}`;
  must(s,lotOld,'old auto-lot map');s=s.replace(lotOld,lotNew);

  const dupReq="body:JSON.stringify({symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2})";
  must(s,dupReq,'same-signal request');
  s=s.replace(dupReq,"body:JSON.stringify({symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,partial_tp:partialTpEnabled})");

  const dupResult="const j=await r.json();d._sameActiveSignal=!!j.duplicate;d._sameSignalStatus=j.existing_status||'';return j;";
  must(s,dupResult,'same-signal result');
  s=s.replace(dupResult,"const j=await r.json();d._sameActiveSignal=!!j.duplicate;d._sameSignalStatus=j.existing_status||'';d._sameSignalId=j.existing_signal_id||'';return j;");

  const captureLegacy="body:JSON.stringify({signal_id:id,symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,score:sig.score,setup:d.bestFamily||sig.setupReason||'',action:'NEW'})";
  if(s.includes(captureLegacy))s=s.replace(captureLegacy,"body:JSON.stringify({signal_id:id,symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,score:sig.score,setup:d.bestFamily||sig.setupReason||'',partial_tp:partialTpEnabled,action:'NEW'})");

  const a=s.indexOf('async function dispatchUniqueSignalV36(d){');
  const b=s.indexOf('\nasync function executeNewAnalysis(fromAuto=false){',a);
  if(a<0||b<0)throw new Error('dispatchUniqueSignalV36 bounds not found');
  const dispatch=`async function dispatchUniqueSignalV36(d){\n  const sig=d?.signal;if(!sig)return null;\n  const baseSignalId=\`MH\${Date.now()}_\${symbol}_\${timeframe}\`,selectedLot=lotForSignalScore(sig.score);\n  let signalId=partialTpEnabled?\`\${baseSignalId}__PT1_\${Number(sig.tp1).toFixed(10)}\`:baseSignalId;\n  const finalTp=partialTpEnabled?Number(sig.tp2):Number(sig.tp1);\n  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);\n  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);\n  let rj={};\n\n  // V56.14: a duplicate Record may exist even when the EA handoff previously\n  // failed. Re-use that exact signal_id and publish it again instead of blocking.\n  if(d?._sameActiveSignal&&String(d?._sameSignalId||'').trim()){\n    signalId=String(d._sameSignalId).trim();\n    rj={duplicate:true,same_signal:true,existing_signal_id:signalId,existing_status:d._sameSignalStatus||''};\n  }else{\n    const recordPayload={signal_id:signalId,symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2),score:Number(sig.score)||0,setup:d.bestFamily||sig.setupReason||'',partial_tp:partialTpEnabled,action:'NEW'};\n    const rr=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordPayload)});\n    try{rj=await rr.json()}catch(_){}\n    if(!rr.ok)throw new Error(rj.error||\`Records HTTP \${rr.status}\`);\n    if(rj.duplicate||rj.same_signal){\n      d._sameActiveSignal=true;d._sameSignalStatus=rj.existing_status||'';d._sameSignalId=rj.existing_signal_id||'';\n      if(String(rj.existing_signal_id||'').trim())signalId=String(rj.existing_signal_id).trim();\n      else throw new Error('Same signal Record exists but has no reusable signal_id');\n    }\n  }\n\n  const er=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:finalTp,lot:selectedLot,expiry:0})});\n  let ej={};try{ej=await er.json()}catch(_){}\n  if(!er.ok)throw new Error(ej.error||\`EA bridge HTTP \${er.status}\`);\n  try{await prepareMT5SignalV796(d,'NEW')}catch(_){}\n  const retry=(rj.duplicate||rj.same_signal)?'EA handoff retried':'MT5 pending sent';\n  setAutoStatus(\`Signal ready • \${retry} • \${pending} • Lot \${selectedLot.toFixed(2)} • Partial TP \${partialTpEnabled?'ON':'OFF'}\`,'good');\n  return {record:rj,ea:ej,signal_id:signalId,retried:!!(rj.duplicate||rj.same_signal)};\n}\n`;
  s=s.slice(0,a)+dispatch+s.slice(b);

  const bg="if(d.signal&&!d._sameActiveSignal){dispatchUniqueSignalV36(d).catch(e=>console.warn('Background Record/EA handoff failed',e));} // V546_BACKGROUND_FANOUT";
  must(s,bg,'background EA fanout');
  s=s.replace(bg,"if(d.signal){try{await dispatchUniqueSignalV36(d)}catch(e){console.warn('Record/EA handoff failed',e);setAutoStatus(`MT5 pending failed • ${e.message||e}`,'bad')}} // V5614_RELIABLE_EA_FANOUT");

  s=s.replace("Same signal still active • no duplicate Record / MT5 pending","Same signal active • no duplicate Record • EA pending handoff will be safely retried");
  s=s.replace("same signal active • no duplicate Record / MT5 pending","same signal active • no duplicate Record • EA pending handoff retried");

  write(p,s);
}

// Make Partial TP mode part of Record identity. This avoids an old Record made
// with Partial TP OFF suppressing a later Partial TP ON signal with same prices.
{
  const p='records_mt5_local.go';let s=read(p);
  const rec="\tSetup           string  `json:\"setup\"`\n\tStatus          string  `json:\"status\"`\n";
  must(s,rec,'record Setup/Status fields');
  s=s.replace(rec,"\tSetup           string  `json:\"setup\"`\n\tPartialTP       bool    `json:\"partial_tp,omitempty\"`\n\tStatus          string  `json:\"status\"`\n");
  const cap="\tSetup     string  `json:\"setup\"`\n\tAction    string  `json:\"action\"`\n";
  must(s,cap,'capture Setup/Action fields');
  s=s.replace(cap,"\tSetup     string  `json:\"setup\"`\n\tPartialTP bool    `json:\"partial_tp\"`\n\tAction    string  `json:\"action\"`\n");
  const same="\t\tstrings.EqualFold(strings.TrimSpace(x.Direction), strings.TrimSpace(q.Direction)) &&\n\t\tsameSignalDisplayPriceV30(x.Entry, q.Entry)";
  must(s,same,'same-signal direction marker');
  s=s.replace(same,"\t\tstrings.EqualFold(strings.TrimSpace(x.Direction), strings.TrimSpace(q.Direction)) &&\n\t\tx.PartialTP == q.PartialTP &&\n\t\tsameSignalDisplayPriceV30(x.Entry, q.Entry)");
  const assign="\t\tEntry: q.Entry, SL: q.SL, TP1: q.TP1, TP2: q.TP2, Score: q.Score, Setup: q.Setup,\n\t\tStatus: \"SIGNAL GENERATED\",";
  must(s,assign,'record capture assignment');
  s=s.replace(assign,"\t\tEntry: q.Entry, SL: q.SL, TP1: q.TP1, TP2: q.TP2, Score: q.Score, Setup: q.Setup, PartialTP: q.PartialTP,\n\t\tStatus: \"SIGNAL GENERATED\",");
  write(p,s);
}

// Assertions.
{
  const app=read('web/app.js');
  must(app,'V5614_RELIABLE_EA_FANOUT','reliable EA fanout marker');
  must(app,'d._sameSignalId=j.existing_signal_id','existing signal ID reuse');
  must(app,"partial_tp:partialTpEnabled",'partial mode payload');
  must(app,'if(n>=83)return 0.05','83-100 lot mapping');
  must(app,'if(n>=73)return 0.04','73-82 lot mapping');
  must(app,'if(n>=66)return 0.03','66-72 lot mapping');
  if(app.includes('if(n>=95)return 0.06'))throw new Error('old 0.06 auto-lot tier remains');
  const records=read('records_mt5_local.go');
  must(records,'PartialTP       bool','record PartialTP field');
  must(records,'x.PartialTP == q.PartialTP','partial-mode duplicate identity');
}

console.log('V56.14 reliable EA pending retry + Partial TP identity + requested lot map applied');
