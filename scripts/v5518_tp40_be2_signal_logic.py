from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# V.55.18: preserve the existing TP2 selection exactly, then derive TP1 at 40%
# of the Entry->TP2 distance. No other analysis/trading logic is changed.
old="""  const tp1Obj=chooseObjectiveBounded(entry,allOpp,desiredTp1,dir,Math.max(model.noise*.35,profile.tp1Floor*.25),profile.tp1Cap),tp1=tp1Obj??(dir==='BUY'?entry+desiredTp1:entry-desiredTp1);\n  const further=allOpp.filter(x=>dir==='BUY'?x>tp1:x<tp1),tp2Obj=chooseObjectiveBounded(entry,further,desiredTp2,dir,Math.abs(tp1-entry)*1.05,profile.tp2Cap),tp2=tp2Obj??(dir==='BUY'?entry+desiredTp2:entry-desiredTp2);\n  const score=dir==='BUY'?buyScore:sellScore,risk=Math.max(Math.abs(entry-sl),1e-9),rr1=Math.abs(tp1-entry)/risk,rr2=Math.abs(tp2-entry)/risk,reasons=ranked.slice(0,7).flatMap(f=>[`${f.name} ${Math.round(f.score)}/100`,f.reasons[0]]).filter(Boolean).slice(0,14);\n"""
new="""  const structuralTp1Obj=chooseObjectiveBounded(entry,allOpp,desiredTp1,dir,Math.max(model.noise*.35,profile.tp1Floor*.25),profile.tp1Cap),structuralTp1=structuralTp1Obj??(dir==='BUY'?entry+desiredTp1:entry-desiredTp1);\n  const further=allOpp.filter(x=>dir==='BUY'?x>structuralTp1:x<structuralTp1),tp2Obj=chooseObjectiveBounded(entry,further,desiredTp2,dir,Math.abs(structuralTp1-entry)*1.05,profile.tp2Cap),tp2=tp2Obj??(dir==='BUY'?entry+desiredTp2:entry-desiredTp2);\n  const tp1=entry+(tp2-entry)*0.40;\n  const score=dir==='BUY'?buyScore:sellScore,risk=Math.max(Math.abs(entry-sl),1e-9),rr1=Math.abs(tp1-entry)/risk,rr2=Math.abs(tp2-entry)/risk,reasons=ranked.slice(0,7).flatMap(f=>[`${f.name} ${Math.round(f.score)}/100`,f.reasons[0]]).filter(Boolean).slice(0,14);\n"""
if old not in s: raise SystemExit('TP calculation anchor missing')
s=s.replace(old,new,1)

old_reason="tp1Reason:`TP1 uses reachable opposing structure/liquidity inside the measured ${tf} target envelope. Current computed R:R ${two(rr1)}R.`"
new_reason="tp1Reason:`TP1 is fixed at 40% of the Entry→TP2 distance so 50% partial profit can be secured before the original final TP2 objective. Current computed R:R ${two(rr1)}R.`"
if old_reason not in s: raise SystemExit('TP1 reason anchor missing')
s=s.replace(old_reason,new_reason,1)

p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.18\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name); t=q.read_text(encoding='utf-8'); t=t.replace('V.55.17','V.55.18'); q.write_text(t,encoding='utf-8')
