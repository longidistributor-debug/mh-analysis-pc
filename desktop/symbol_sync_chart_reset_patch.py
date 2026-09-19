from pathlib import Path

MARK='MH_SYMBOL_SYNC_CHART_RESET_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# web/app.js: support both selectable MH symbols for Exness prefill and guarantee
# a newly selected pair/timeframe starts from a truly empty chart.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,
        "let chartDecision=null;\n",
        "let chartDecision=null;\nlet contextGeneration=0; // "+MARK+"\n",
        'context generation')

    s=rep(s,
        "if(!sig||String(state).toUpperCase()!=='NEW'||symbol!=='XAUUSD')return;",
        "if(!sig||String(state).toUpperCase()!=='NEW'||!['XAUUSD','BTCUSDT'].includes(symbol))return;",
        'Exness selectable symbols')

    s=rep(s,
        "const market=Number(arr.at(-1)?.c??publicGoldPrice);",
        "const market=Number(arr.at(-1)?.c??(symbol==='XAUUSD'?publicGoldPrice:NaN));",
        'Exness current market price')

    old_load="""function loadChart(){\n  $('#chartLabel').textContent=`${symbol} • ${timeframe}`;\n  $('#currentPair').textContent=`${symbol} • ${timeframe}`;\n  $('#nativeSymbol').textContent=symbol;\n  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));\n  if(!lwChart||!candleSeries)setupLightweightChart();\n  try{candleSeries?.setData([])}catch(_){}\n"""
    new_load="""function loadChart(){\n  $('#chartLabel').textContent=`${symbol} • ${timeframe}`;\n  $('#currentPair').textContent=`${symbol} • ${timeframe}`;\n  $('#nativeSymbol').textContent=symbol;\n  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));\n  // Hard reset the chart instance on every manual context switch so candles from\n  // the previous pair/timeframe can never remain visible. No API request occurs.\n  try{chartResizeObserver?.disconnect?.()}catch(_){}\n  chartResizeObserver=null;\n  if(lwChart){try{lwChart.remove()}catch(_){}}\n  lwChart=null;candleSeries=null;volumeSeries=null;markerPlugin=null;signalPriceLines=[];\n  setupLightweightChart();\n  try{candleSeries?.setData([])}catch(_){}\n"""
    s=rep(s,old_load,new_load,'hard chart reset')

    s=rep(s,
        "async function contextChanged(){\n  // IMPORTANT: manual context selection must be API-silent. Do not call\n",
        "async function contextChanged(){\n  contextGeneration++; // "+MARK+"\n  // IMPORTANT: manual context selection must be API-silent. Do not call\n",
        'context generation increment')

    s=rep(s,
        "async function executeNewAnalysis(fromAuto=false){\n  if(busy)return null;autoActionStartedAt=Date.now();busy=true;setBusy(true,`${fromAuto?'AUTO • ':''}NEW ANALYZE • fetching one fresh candle snapshot…`);\n  try{\n    const k=keyFor(),prev=(active.get(k)||restoreActiveSignal(k))?.signal||null;\n",
        "async function executeNewAnalysis(fromAuto=false){\n  if(busy)return null;const analysisGeneration=contextGeneration,analysisKey=keyFor();autoActionStartedAt=Date.now();busy=true;setBusy(true,`${fromAuto?'AUTO • ':''}NEW ANALYZE • fetching one fresh candle snapshot…`);\n  try{\n    const k=analysisKey,prev=(active.get(k)||restoreActiveSignal(k))?.signal||null;\n",
        'new analysis context snapshot')

    s=rep(s,
        "    const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null),newsRisk=await detectNewsRisk(c);\n    applyNewsRisk(d,newsRisk);\n",
        "    const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null),newsRisk=await detectNewsRisk(c);\n    if(analysisGeneration!==contextGeneration||analysisKey!==keyFor())return null; // "+MARK+" stale result guard\n    applyNewsRisk(d,newsRisk);\n",
        'new analysis stale result guard')

p.write_text(s,encoding='utf-8')

# exness_bridge.go: accept BTCUSDT and automatically try to switch the Exness
# terminal's instrument selector before preparing the pending-order ticket.
p=Path('exness_bridge.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,
        'if q.Symbol != "XAUUSD" || (q.Direction != "BUY" && q.Direction != "SELL") || q.Entry <= 0 || q.SL <= 0 || q.TP1 <= 0 || q.MarketPrice <= 0 {',
        'if (q.Symbol != "XAUUSD" && q.Symbol != "BTCUSDT") || (q.Direction != "BUY" && q.Direction != "SELL") || q.Entry <= 0 || q.SL <= 0 || q.TP1 <= 0 || q.MarketPrice <= 0 {',
        'BTCUSDT request validation')
    s=s.replace('"error": "invalid XAUUSD signal payload"','"error": "invalid XAUUSD/BTCUSDT signal payload"',1)

    old="""const body=txt(document.body).toLowerCase();\nif(/log in|login|sign in/.test(body)&&document.querySelector('input[type=\"password\"]')) return JSON.stringify({status:'LOGIN REQUIRED'});\nif(!/(xau\\s*\\/\\s*usd|xauusd|gold)/i.test(body)) return JSON.stringify({status:'OPEN GOLD / XAUUSD FIRST'});\nfunction clickText(words){\n"""
    new="""const body=txt(document.body).toLowerCase();\nif(/log in|login|sign in/.test(body)&&document.querySelector('input[type=\"password\"]')) return JSON.stringify({status:'LOGIN REQUIRED'});\nconst wanted=p.symbol==='BTCUSDT'?['btcusdt','btcusd','bitcoin']:['xauusd','xau / usd','gold'];\nconst currentMatches=()=>wanted.some(w=>txt(document.body).toLowerCase().includes(w));\nfunction clickText(words){\n"""
    s=rep(s,old,new,'symbol-aware terminal check')

    anchor="""function findInput(keys){\n  const inputs=[...document.querySelectorAll('input,textarea')].filter(visible);\n  for(const i of inputs){\n    const meta=[i.name,i.id,i.placeholder,i.getAttribute('aria-label'),i.getAttribute('data-testid'),txt(i.parentElement),txt(i.closest('label'))].filter(Boolean).join(' ').toLowerCase();\n    if(keys.some(k=>meta.includes(k)))return i;\n  }\n  return null;\n}\nclickText(['New order','Trade']);\n"""
    replacement="""function findInput(keys){\n  const inputs=[...document.querySelectorAll('input,textarea')].filter(visible);\n  for(const i of inputs){\n    const meta=[i.name,i.id,i.placeholder,i.getAttribute('aria-label'),i.getAttribute('data-testid'),txt(i.parentElement),txt(i.closest('label'))].filter(Boolean).join(' ').toLowerCase();\n    if(keys.some(k=>meta.includes(k)))return i;\n  }\n  return null;\n}\nasync function ensureInstrument(){\n  if(currentMatches())return true;\n  const currentWords=p.symbol==='BTCUSDT'?['XAUUSD','XAU / USD','Gold','BTCUSD','BTCUSDT']:['BTCUSD','BTCUSDT','Bitcoin','XAUUSD','Gold'];\n  clickText(currentWords);\n  await sleep(450);\n  const search=findInput(['search','symbol','instrument','market']);\n  if(search){setNative(search,p.symbol==='BTCUSDT'?'BTCUSD':'XAUUSD');await sleep(450);}\n  const all=[...document.querySelectorAll('button,[role=\"button\"],[role=\"option\"],[role=\"menuitem\"],div,span')].filter(visible);\n  const candidates=p.symbol==='BTCUSDT'?['btcusdt','btcusd','bitcoin']:['xauusd','xau / usd','gold'];\n  const match=all.find(e=>candidates.some(w=>txt(e).toLowerCase()===w))||all.find(e=>candidates.some(w=>txt(e).toLowerCase().includes(w)));\n  if(match){match.click();await sleep(850);}\n  return currentMatches();\n}\nif(!(await ensureInstrument()))return JSON.stringify({status:'SYMBOL SWITCH REQUIRED',symbol:p.symbol,submitted:false});\nclickText(['New order','Trade']);\n"""
    s=rep(s,anchor,replacement,'automatic Exness symbol switch')

    s=s.replace("return JSON.stringify(out);\n})()`, string(payload))","out.symbol=p.symbol;return JSON.stringify(out);\n})()`, string(payload))",1)

    # Permanent marker without changing behavior.
    s=s.replace('type exnessOrderPrep struct {','// '+MARK+'\ntype exnessOrderPrep struct {',1)

p.write_text(s,encoding='utf-8')
print('PASS symbol sync + hard chart reset: XAUUSD/BTCUSDT prefill supported; no final submit action added')
