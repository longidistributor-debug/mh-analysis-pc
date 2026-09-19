from pathlib import Path

p = Path('web/app.js')
s = p.read_text(encoding='utf-8')

old = '''function resetViewForContext(){
  restoreActiveSignal(keyFor());const d=lastDecision.get(keyFor());
  if(d){renderDecision(d,d.explanation,'VIEW')}
  else{
    $('#signalCard').className='panel signalPanel neutralState';$('#signalBadge').className='signalBadge neutral';$('#signalBadge').textContent='NO ANALYSIS';$('#signalQuality').textContent='—';
    $('#plan').className='plan muted';$('#plan').textContent=`Chart is interactive. NEW ANALYZE makes one fresh ${symbol} ${timeframe} history request and analyzes those same candles.`;
    ['#mapRegime','#mapAdx','#mapVwap','#mapBullOb','#mapBearOb','#mapFvg','#mapEq','#mapDiv','#buyScoreTop','#sellScoreTop'].forEach(id=>$(id).textContent='—');
    $('#analysisStatusHeading').textContent='ANALYSIS STATUS';$('#explanation').textContent='Pair/timeframe changed. Loading the latest chart snapshot.';$('#reasons').textContent='—';$('#topSetups').textContent='No ranking yet.';
    updateSignalHeadline(null);clearSignalLevels();
  }
}
async function contextChanged(){
  loadChart();
  resetViewForContext();
  refreshMarketCap();
  const feed=$('#nativeFeedStatus');if(feed)feed.textContent='Ready • press NEW ANALYZE or RE-EVALUATE';
}
'''

new = '''function resetViewForContext(){
  // Manual pair/timeframe browsing is VIEW-ONLY. Never restore an old decision
  // into the newly selected context and never imply that fresh market data was
  // requested. The screen remains blank until an explicit analysis action.
  $('#signalCard').className='panel signalPanel neutralState';$('#signalBadge').className='signalBadge neutral';$('#signalBadge').textContent='NO ANALYSIS';$('#signalQuality').textContent='—';
  $('#plan').className='plan muted';$('#plan').textContent=`${symbol} ${timeframe} selected. Press NEW ANALYZE to request fresh data, or RE-EVALUATE an existing signal.`;
  ['#mapRegime','#mapAdx','#mapVwap','#mapBullOb','#mapBearOb','#mapFvg','#mapEq','#mapDiv','#buyScoreTop','#sellScoreTop'].forEach(id=>$(id).textContent='—');
  if($('#mapRisk')){$('#mapRisk').textContent='—';$('#mapRisk').className=''}
  $('#analysisStatusHeading').textContent='ANALYSIS STATUS';
  $('#explanation').className='detailText muted';$('#explanation').textContent='Manual selection only • no market/API request has been made.';
  $('#reasons').className='detailText';$('#reasons').textContent='—';$('#topSetups').textContent='No ranking yet.';
  chartDecision=null;updateSignalHeadline(null);clearSignalLevels();
}
async function contextChanged(){
  // IMPORTANT: manual context selection must be API-silent. Do not call
  // fetchCandles/loadContextChart/refreshMarketCap or any history endpoint here.
  loadChart();
  resetViewForContext();
  const feed=$('#nativeFeedStatus');if(feed)feed.textContent='Manual selection • no market request • press NEW ANALYZE or RE-EVALUATE';
}
'''

if old not in s:
    raise SystemExit('manual context block not found; source changed')
s = s.replace(old, new, 1)

# Guardrails: manual context changes must never acquire market history.
start = s.index('async function contextChanged(){')
end = s.index('\n}\n\nasync function saveBackendSetting', start) + 2
block = s[start:end]
for forbidden in ('fetchCandles(', 'candlesForAnalysis(', 'loadContextChart(', 'refreshMarketCap(', "fetch('/api/history"):
    if forbidden in block:
        raise SystemExit(f'forbidden manual-context request path remains: {forbidden}')

# Explicit analysis actions must still request fresh history.
if s.count('const f=await candlesForAnalysis()') < 2:
    raise SystemExit('NEW/RE-EVALUATE fresh-history paths missing')
if "scheduleAutoAt('NEW',info.nextCycleAt)" not in s:
    raise SystemExit('Get Signal fixed-cycle scheduling missing')

p.write_text(s, encoding='utf-8')
print('PASS manual pair/timeframe selection is blank and API-silent; explicit analysis paths preserved')
