from pathlib import Path

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

# Trade-mode switches are execution preferences only. They must never gate market/history access.
old="function setLotSizeEnabled(on){lotSizeEnabled=!!on;localStorage.setItem(STORAGE_LOT_SIZE,lotSizeEnabled?'1':'0');updateTradeModeButtons();}\nfunction setPartialTpEnabled(on){partialTpEnabled=!!on;localStorage.setItem(STORAGE_PARTIAL_TP,partialTpEnabled?'1':'0');updateTradeModeButtons();}"
new="function setLotSizeEnabled(on){lotSizeEnabled=!!on;localStorage.setItem(STORAGE_LOT_SIZE,lotSizeEnabled?'1':'0');updateTradeModeButtons();/* V.55.13: execution preference only; never touch market/history connection */}\nfunction setPartialTpEnabled(on){partialTpEnabled=!!on;localStorage.setItem(STORAGE_PARTIAL_TP,partialTpEnabled?'1':'0');updateTradeModeButtons();/* V.55.13: execution preference only; never touch market/history connection */}"
if old not in s: raise SystemExit('trade-mode anchor missing')
s=s.replace(old,new,1)

# Manual Get Signal OFF remains manual analysis mode; it must not alter data/history connectivity.
old="}else{stopAutoTimers();autoSignalNextAt=0;updateAutoButton()}\n}"
new="}else{stopAutoTimers();autoSignalNextAt=0;updateAutoButton();/* V.55.13: manual mode only; data/history stays independent */}\n}"
if old not in s: raise SystemExit('get-signal anchor missing')
s=s.replace(old,new,1)

# Preserve strict manual chart loading rule. Pair/timeframe selection only clears/selects UI; no history request.
old="async function contextChanged(){\n  normalizeSupportedTimeframeV554();\n  loadChart();\n  resetViewForContext();\n  const feed=$('#nativeFeedStatus');\n  if(feed)feed.textContent=`${symbol} ${timeframe} selected • press NEW ANALYZE or RE-EVALUATE`;\n}"
new="async function contextChanged(){\n  normalizeSupportedTimeframeV554();\n  loadChart();\n  resetViewForContext();\n  const feed=$('#nativeFeedStatus');\n  if(feed)feed.textContent=`${symbol} ${timeframe} selected • press NEW ANALYZE or RE-EVALUATE`;\n  /* V.55.13: intentionally no fetchCandles/loadContextChart here. Chart loads only on explicit analysis action. */\n}"
if old not in s: raise SystemExit('contextChanged anchor missing')
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.13\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name); t=q.read_text(encoding='utf-8'); t=t.replace('V.55.12','V.55.13'); q.write_text(t,encoding='utf-8')
