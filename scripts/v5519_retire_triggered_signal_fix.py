from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# V.55.19: once the same-timeframe pending signal has actually activated and MT5
# reports live exposure in the same direction, retire that signal from the local
# pending/re-evaluation queue. It must never be re-sent as a NEW/RE-EVALUATE signal.
anchor="""function signalTouched(c,s,field){\n  const p=Number(s?.[field]);if(!Number.isFinite(p))return false;\n  const activation=signalEntryActivation(c,s);\n  if(!activation)return false; // pending order never filled after this signal, so SL/TP cannot be hit\n  const dir=String(s?.direction||'').toUpperCase(),i=Math.max(0,activation.index),a=c[i];\n  // On the activation candle, OHLC high/low ordering is unknown. Only the candle's\n  // closing/current price is safe evidence after entry activation; older intrabar extremes\n  // may have happened before the order filled.\n  if(a&&Number.isFinite(Number(a.c))){\n    const q=Number(a.c);\n    if(field==='sl'){\n      if(dir==='BUY'?q<=p:q>=p)return true;\n    }else if(dir==='BUY'?q>=p:q<=p)return true;\n  }\n  // From the NEXT candle onward, the whole OHLC range is definitely post-entry.\n  const w=c.slice(i+1);\n  if(field==='sl')return dir==='BUY'?w.some(x=>Number(x.l)<=p):w.some(x=>Number(x.h)>=p);\n  return dir==='BUY'?w.some(x=>Number(x.h)>=p):w.some(x=>Number(x.l)<=p);\n}\n"""
insert=anchor+"""function activatedTradeSnapshotV5519(c,s,mt5){\n  if(!s||!mt5?.active)return null;\n  const activation=signalEntryActivation(c,s);if(!activation)return null;\n  const sigDir=String(s.direction||'').toUpperCase(),mt5Dir=String(mt5.direction||'').toUpperCase();\n  if(mt5Dir&&mt5Dir!=='MIXED'&&mt5Dir!==sigDir)return null;\n  const last=Number(c?.at?.(-1)?.c),entry=Number(s.entry);if(!Number.isFinite(last)||!Number.isFinite(entry))return null;\n  const move=sigDir==='BUY'?last-entry:entry-last;\n  return{active:true,direction:sigDir,entry,last,move,performance:move>1e-9?'POSITIVE':move<-1e-9?'NEGATIVE':'FLAT',activationIndex:activation.index};\n}\nfunction retireTriggeredSignalV5519(k,s,c,mt5){\n  const snap=activatedTradeSnapshotV5519(c,s,mt5);if(!snap)return null;\n  active.delete(k);persistActiveSignal(k,null);return snap;\n}\n"""
if anchor not in s: raise SystemExit('signalTouched anchor missing')
s=s.replace(anchor,insert,1)

# WhatsApp must not fall back to the retired original signal.
s=s.replace("const sig=d?.signal||d?.originalSignal||null;\n  const isRe=action==='RE-EVALUATE';",
            "const sig=d?._activatedTradeRetired?(d?.signal||null):(d?.signal||d?.originalSignal||null);\n  const isRe=action==='RE-EVALUATE';",1)
s=s.replace("const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];\n  if(isRe){lines.push('',`*Reason:* ${reason}`,'')}\n  else{lines.push('')}",
            "const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];\n  if(d?._activatedTradeRetired){const a=d._activatedTradeRetired;lines.push(`📌 *Previous trade:* ACTIVE • ${a.performance} • Move ${a.move>=0?'+':''}${fmt(a.move)}`)}\n  if(isRe){lines.push('',`*Reason:* ${reason}`,'')}\n  else{lines.push('')}",1)
s=s.replace("const sig=d?.signal||d?.originalSignal||null;\n  return JSON.stringify({",
            "const sig=d?._activatedTradeRetired?(d?.signal||null):(d?.signal||d?.originalSignal||null);\n  return JSON.stringify({",1)

# NEW ANALYZE: retire an already-triggered same-timeframe signal before comparing/
# duplicate messaging. Fresh analysis then stands on its own.
old_new="""    const k=keyFor(),prev=(active.get(k)||restoreActiveSignal(k))?.signal||null;\n    const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null);if(prev&&signalTouched(c,prev,'sl'))persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k);const newsRisk=await detectNewsRisk(c);\n"""
new_new="""    const k=keyFor(),storedPrev=(active.get(k)||restoreActiveSignal(k))?.signal||null;\n    const f=await candlesForAnalysis(),c=f.candles,mt5State=storedPrev?await readMT5ActiveStateV552(symbol):null,activated=storedPrev?retireTriggeredSignalV5519(k,storedPrev,c,mt5State):null,prev=activated?null:storedPrev,d=analyze(c,null);if(prev&&signalTouched(c,prev,'sl'))persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k);const newsRisk=await detectNewsRisk(c);\n    if(activated){d._activatedTradeRetired=activated;d.warnings=[`PREVIOUS SIGNAL RETIRED: entry is now an ACTIVE ${activated.direction} trade (${activated.performance}, move ${activated.move>=0?'+':''}${fmt(activated.move)}). It cannot be re-issued as a signal.`,...(d.warnings||[])]}\n"""
if old_new not in s: raise SystemExit('NEW ANALYZE anchor missing')
s=s.replace(old_new,new_new,1)

old_reason="""    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);\n    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}\n"""
new_reason="""    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);\n    if(activated)reason=`Previous ${activated.direction} signal has triggered and is now an ACTIVE trade (${activated.performance}, move ${activated.move>=0?'+':''}${fmt(activated.move)}). That old signal was retired. This result is a completely fresh ${timeframe} analysis. ${d.explanation}`;\n    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}\n"""
if old_reason not in s: raise SystemExit('NEW reason anchor missing')
s=s.replace(old_reason,new_reason,1)

# RE-EVALUATE: if the original pending signal has activated into a live MT5 trade,
# stop re-evaluating/re-sending it. Retire it and return a fresh market analysis.
old_re="""    const f=await candlesForAnalysis(),c=f.candles,s=a.signal,current=analyze(c,s),newsRisk=await detectNewsRisk(c),age=signalBarsAge(c,s),life=adaptiveExpiryBars(c),last=c.at(-1),model=empiricalDistanceModel(c,s.direction,stats(c));\n    current.newsRisk=newsRisk;\n"""
new_re="""    const f=await candlesForAnalysis(),c=f.candles,s=a.signal,mt5State=await readMT5ActiveStateV552(symbol),activated=retireTriggeredSignalV5519(k,s,c,mt5State);\n    if(activated){\n      const current=analyze(c,null),newsRisk=await detectNewsRisk(c);current.newsRisk=newsRisk;applyNewsRisk(current,newsRisk);current._ranked=buildRankedForUi(c,current);current._activatedTradeRetired=activated;current.originalSignal=null;\n      const status=`PREVIOUS SIGNAL RETIRED — entry is now an ACTIVE ${activated.direction} trade • ${activated.performance} • move ${activated.move>=0?'+':''}${fmt(activated.move)}. Fresh ${timeframe} analysis generated; old triggered signal will not be re-sent.`;\n      current.warnings=[status,...(current.warnings||[])];current.explanation=`${status} ${current.explanation}`;\n      renderDecision(current,current.explanation,'REEVAL');busy=false;setBusy(false);\n      if(autoSignalEnabled)await autoSendAndSchedule(current,'RE-EVALUATE',status);else{try{await sendDecisionWhatsApp(current,'RE-EVALUATE',status);setAutoStatus('RE-EVALUATE sent • triggered signal retired • fresh analysis','good')}catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}}\n      return current;\n    }\n    const current=analyze(c,s),newsRisk=await detectNewsRisk(c),age=signalBarsAge(c,s),life=adaptiveExpiryBars(c),last=c.at(-1),model=empiricalDistanceModel(c,s.direction,stats(c));\n    current.newsRisk=newsRisk;\n"""
if old_re not in s: raise SystemExit('RE-EVALUATE anchor missing')
s=s.replace(old_re,new_re,1)

p.write_text(s,encoding='utf-8')
Path('VERSION').write_text('V.55.19\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name);t=q.read_text(encoding='utf-8');t=t.replace('V.55.18','V.55.19');q.write_text(t,encoding='utf-8')
