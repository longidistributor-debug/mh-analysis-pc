from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

old="""    const selectedLot=lotForSignalScore(sig.score);lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Lot:* ${selectedLot.toFixed(2)} (${lotSizeEnabled?'Score Auto':'Fixed'})`,`*Partial TP:* ${partialTpEnabled?'ON':'OFF'}`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);"""
new="""    const selectedLot=lotForSignalScore(sig.score);lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`  ↳ *Why SL:* ${sig.slReason||'Structural invalidation / current timeframe risk envelope'}`,`*TP1:* ${fmt(sig.tp1)}`,`  ↳ *Why TP1:* ${sig.tp1Reason||'Nearest reachable opposing structure / liquidity objective'}`,`*TP2:* ${fmt(sig.tp2)}`,`  ↳ *Why TP2:* ${sig.tp2Reason||'Next reachable structure / liquidity stretch objective'}`,`*Score:* ${sig.score}/100`,`*Lot:* ${selectedLot.toFixed(2)} (${lotSizeEnabled?'Score Auto':'Fixed'})`,`*Partial TP:* ${partialTpEnabled?'ON':'OFF'}`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);"""
if old not in s:
    raise SystemExit('WhatsApp signal line anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.17\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name); t=q.read_text(encoding='utf-8'); t=t.replace('V.55.16','V.55.17'); q.write_text(t,encoding='utf-8')
