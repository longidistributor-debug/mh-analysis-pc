from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# V.55.14: Get Signal controls ONLY the automatic fixed-cycle scheduler.
# Manual NEW ANALYZE / RE-EVALUATE must always remain callable while Get Signal is OFF.
old="async function runAnalyze(){return executeNewAnalysis(false)}\nasync function runReevaluate(){return executeReevaluate(false)}"
new="async function runAnalyze(){\n  /* V.55.14 MANUAL PATH: deliberately independent of autoSignalEnabled/Get Signal. */\n  return await executeNewAnalysis(false);\n}\nasync function runReevaluate(){\n  /* V.55.14 MANUAL PATH: deliberately independent of autoSignalEnabled/Get Signal. */\n  return await executeReevaluate(false);\n}"
if old not in s: raise SystemExit('manual action anchor missing')
s=s.replace(old,new,1)

# OFF must stop only automatic scheduler timers. It must never gate/manual-disable analysis/history/chart.
old="}else{stopAutoTimers();autoSignalNextAt=0;updateAutoButton();/* V.55.13: manual mode only; data/history stays independent */}\n}"
new="}else{\n    stopAutoTimers();autoSignalNextAt=0;updateAutoButton();\n    /* V.55.14: OFF means AUTO SCHEDULER OFF only. Manual NEW ANALYZE / RE-EVALUATE remain fully enabled. */\n  }\n}"
if old not in s: raise SystemExit('Get Signal OFF anchor missing')
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.14\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name); t=q.read_text(encoding='utf-8'); t=t.replace('V.55.13','V.55.14'); q.write_text(t,encoding='utf-8')
