from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# V.55.20: NEW ANALYZE may confirm the exact same still-pending signal.
# Keep the original pending signal identity/timestamps intact, clearly mark it as
# UNTOUCHED, and never imply RE-EVALUATE or send a duplicate order.
old_msg="""function sameSignalMessageV30(d){
  const s=d?.signal;return s?`SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL. ${symbol} ${timeframe} ${s.direction} • Entry ${fmt(s.entry)} • SL ${fmt(s.sl)} • TP1 ${fmt(s.tp1)} • TP2 ${fmt(s.tp2)}.`:'NO NEW SIGNAL';
}
"""
new_msg="""function sameSignalMessageV30(d){
  const s=d?.signal;
  if(!s)return'NO NEW SIGNAL';
  if(d?._untouchedPendingSame)return`UNTOUCHED PENDING — SAME SIGNAL STILL VALID. Entry has not triggered yet. Fresh NEW ANALYZE still supports the same setup. No duplicate order sent. ${symbol} ${timeframe} ${s.direction} • Entry ${fmt(s.entry)} • SL ${fmt(s.sl)} • TP1 ${fmt(s.tp1)} • TP2 ${fmt(s.tp2)}.`;
  return`SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL. ${symbol} ${timeframe} ${s.direction} • Entry ${fmt(s.entry)} • SL ${fmt(s.sl)} • TP1 ${fmt(s.tp1)} • TP2 ${fmt(s.tp2)}.`;
}
"""
if old_msg not in s: raise SystemExit('sameSignalMessageV30 anchor missing')
s=s.replace(old_msg,new_msg,1)

old_check="""    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);
    if(activated)reason=`Previous ${activated.direction} signal has triggered and is now an ACTIVE trade (${activated.performance}, move ${activated.move>=0?'+':''}${fmt(activated.move)}). That old signal was retired. This result is a completely fresh ${timeframe} analysis. ${d.explanation}`;
    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}
"""
new_check="""    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);
    if(activated)reason=`Previous ${activated.direction} signal has triggered and is now an ACTIVE trade (${activated.performance}, move ${activated.move>=0?'+':''}${fmt(activated.move)}). That old signal was retired. This result is a completely fresh ${timeframe} analysis. ${d.explanation}`;
    if(d.signal){
      const same=await checkSameSignalV30(d),untouched=!!(same?.duplicate&&prev&&!signalEntryActivation(c,prev));
      if(untouched){
        const fresh=d.signal;
        d._untouchedPendingSame=true;
        d.signal={...prev,score:fresh.score,previousScore:prev.score,reconfirmedAt:Date.now(),reconfirmed:true,status:'UNTOUCHED PENDING'};
        d.explanation=`UNTOUCHED PENDING — SAME SIGNAL STILL VALID. Entry has not triggered yet. Fresh NEW ANALYZE still supports the same setup. No duplicate order is sent. Fresh ranking: BUY ${d.buyScore} vs SELL ${d.sellScore}.`;
        reason=sameSignalMessageV30(d);
      }else if(same?.duplicate)reason=sameSignalMessageV30(d);
    }
"""
if old_check not in s: raise SystemExit('NEW duplicate check anchor missing')
s=s.replace(old_check,new_check,1)

old_heading="""  $('#analysisStatusHeading').textContent=mode==='REEVAL'?'RE-EVALUATE SIGNAL':(d?._sameActiveSignal?'SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL':'NEW ANALYSIS');
"""
new_heading="""  $('#analysisStatusHeading').textContent=mode==='REEVAL'?'RE-EVALUATE SIGNAL':(d?._untouchedPendingSame?'UNTOUCHED PENDING — SAME SIGNAL STILL VALID':(d?._sameActiveSignal?'SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL':'NEW ANALYSIS'));
"""
if old_heading not in s: raise SystemExit('analysis heading anchor missing')
s=s.replace(old_heading,new_heading,1)

old_status="""  const statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge');
"""
new_status="""  const statusValue=isRe?'Re-Evaluate':(d?._untouchedPendingSame?'UNTOUCHED PENDING — SAME SIGNAL STILL VALID':(sig?'Signal generated':'No clear edge'));
"""
if old_status not in s: raise SystemExit('WhatsApp status anchor missing')
s=s.replace(old_status,new_status,1)

old_lines="""  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];
  if(d?._activatedTradeRetired){const a=d._activatedTradeRetired;lines.push(`📌 *Previous trade:* ACTIVE • ${a.performance} • Move ${a.move>=0?'+':''}${fmt(a.move)}`)}
"""
new_lines="""  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];
  if(d?._untouchedPendingSame)lines.push('',`*UNTOUCHED PENDING — SAME SIGNAL STILL VALID*`,`Entry not triggered yet. Fresh NEW ANALYZE still supports the same setup. No duplicate order sent.`,'');
  if(d?._activatedTradeRetired){const a=d._activatedTradeRetired;lines.push(`📌 *Previous trade:* ACTIVE • ${a.performance} • Move ${a.move>=0?'+':''}${fmt(a.move)}`)}
"""
if old_lines not in s: raise SystemExit('WhatsApp lines anchor missing')
s=s.replace(old_lines,new_lines,1)

old_auto="""        if(d._sameActiveSignal)setAutoStatus('NEW ANALYZE queued to WhatsApp • same signal active • no duplicate Record / MT5 pending','good');
"""
new_auto="""        if(d._untouchedPendingSame)setAutoStatus('NEW ANALYZE sent • UNTOUCHED PENDING • same signal still valid • no duplicate order','good');
        else if(d._sameActiveSignal)setAutoStatus('NEW ANALYZE queued to WhatsApp • same signal active • no duplicate Record / MT5 pending','good');
"""
if old_auto not in s: raise SystemExit('manual status anchor missing')
s=s.replace(old_auto,new_auto,1)

p.write_text(s,encoding='utf-8')
Path('VERSION').write_text('V.55.20\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name);t=q.read_text(encoding='utf-8');t=t.replace('V.55.19','V.55.20');q.write_text(t,encoding='utf-8')
