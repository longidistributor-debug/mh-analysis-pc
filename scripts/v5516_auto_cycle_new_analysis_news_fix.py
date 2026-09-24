from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# V.55.16 root cause: NEW ANALYZE assigned newsRisk without declaring it.
# app.js runs in strict mode, so every NEW ANALYZE could fail with
# "newsRisk is not defined" while RE-EVALUATE continued to work.
old="const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null);if(prev&&signalTouched(c,prev,'sl'))persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k),newsRisk=await detectNewsRisk(c);"
new="const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null);if(prev&&signalTouched(c,prev,'sl'))persistStoppedSetupV5510(k,prev,c);applyStoppedSetupReentryGuardV5510(d,c,k);const newsRisk=await detectNewsRisk(c);"
if old not in s:
    raise SystemExit('NEW ANALYZE newsRisk anchor missing')
s=s.replace(old,new,1)

# Use the existing fixed absolute 15-minute scheduler for failure/skip paths too.
# The old calls referenced a non-existent scheduleFixedAfterDecision helper,
# which could disturb recovery timing after an analysis failure.
s=s.replace("scheduleFixedAfterDecision(null,'NEW ANALYSIS',autoActionStartedAt||Date.now())","scheduleAfterCompletedFixedAction('NEW ANALYSIS',autoActionStartedAt||Date.now())")
s=s.replace("scheduleFixedAfterDecision(null,'RE-EVALUATE',autoActionStartedAt)","scheduleAfterCompletedFixedAction('RE-EVALUATE',autoActionStartedAt)")
s=s.replace("scheduleFixedAfterDecision(null,'RE-EVALUATE',autoActionStartedAt||Date.now())","scheduleAfterCompletedFixedAction('RE-EVALUATE',autoActionStartedAt||Date.now())")
if 'scheduleFixedAfterDecision(' in s:
    raise SystemExit('undefined fixed scheduler call remains')

# Keep the exact wall-clock cycle documented in source so future changes cannot
# silently turn it into a rolling timer.
marker="const FIXED_REEVAL_OFFSET=5*60*1000;"
replacement="const FIXED_REEVAL_OFFSET=5*60*1000;\n// V.55.16 FIXED WALL CLOCK: NEW at :00/:15/:30/:45; RE-EVALUATE at :05/:20/:35/:50."
if marker not in s:
    raise SystemExit('fixed cycle marker missing')
s=s.replace(marker,replacement,1)

p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.16\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name)
    t=q.read_text(encoding='utf-8')
    if 'V.55.15' not in t:
        raise SystemExit(f'{name}: V.55.15 anchor missing')
    q.write_text(t.replace('V.55.15','V.55.16'),encoding='utf-8')
