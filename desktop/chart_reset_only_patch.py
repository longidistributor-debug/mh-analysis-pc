from pathlib import Path

MARK='MH_CHART_RESET_ONLY_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if MARK in s:
    print('PASS chart reset patch already applied')
    raise SystemExit(0)

s=rep(s,
    "let chartDecision=null;\n",
    "let chartDecision=null;\nlet contextGeneration=0; // "+MARK+"\n",
    'context generation')

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
print('PASS chart reset only: stale context guard retained with no broker web integration')