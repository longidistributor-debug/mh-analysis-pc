from pathlib import Path

MARK='MH_NATIVE_MT5_PREFILL_V796'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# Register the local-only MT5 prefill route.
p=Path('main.go')
s=p.read_text(encoding='utf-8')
if 'registerMT5PrefillRoutes(mux)' not in s:
    s=rep(s,
        '\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n',
        '\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n\tregisterMT5PrefillRoutes(mux) // '+MARK+'\n',
        'main MT5 prefill route')
p.write_text(s,encoding='utf-8')

# Every fresh NEW ANALYZE (manual or timer driven) queues the exact signal for
# native MT5. RE-EVALUATE never creates a new order ticket.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if 'prepareMT5SignalV796' not in s:
    fn=r'''async function prepareMT5SignalV796(d,state='NEW'){
  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW')return;
  const arr=candleCache.get(keyFor())||[];
  const market=Number(arr.at(-1)?.c);
  if(!Number.isFinite(market)||market<=0)return;
  try{
    const r=await fetch('/api/mt5/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,
      market_price:market,score:sig.score,setup:d.bestFamily||sig.setupReason||''
    })});
    if(!r.ok){const t=await r.text();throw new Error(t||`HTTP ${r.status}`)}
  }catch(e){console.warn('MT5 prefill queue failed',e)}
}
'''
    s=rep(s,'async function executeNewAnalysis(fromAuto=false){\n',fn+'async function executeNewAnalysis(fromAuto=false){\n','app MT5 prefill function')
    s=rep(s,
        "    renderDecision(d,reason,'NEW');\n",
        "    renderDecision(d,reason,'NEW');\n    if(d.signal)void prepareMT5SignalV796(d,'NEW'); // "+MARK+"\n",
        'app MT5 prefill call')
p.write_text(s,encoding='utf-8')

# When the user opens the MT5 System tab, apply the latest queued NEW ANALYZE
# signal after the native terminal is visible. If MT5 is already open, clicking
# the tab again safely retries a waiting prefill.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=rep(s,
'''\tif chMT5Wnd != 0 {
\t\tchMu.Unlock(); chApplyDesiredBrowserView(); return nil
\t}
''',
'''\tif chMT5Wnd != 0 {
\t\tchMu.Unlock(); chApplyDesiredBrowserView(); go mt5ApplyLatestQueued(); return nil // '''+MARK+'''\n\t}
''','existing MT5 queued prefill')
    s=rep(s,
'''\tchResizeChildren()
\tchApplyDesiredBrowserView()
\treturn nil
}
''',
'''\tchResizeChildren()
\tchApplyDesiredBrowserView()
\tgo mt5ApplyLatestQueued() // '''+MARK+'''\n\treturn nil
}
''','new MT5 queued prefill')
p.write_text(s,encoding='utf-8')

print('PASS native MT5 prefill: NEW ANALYZE queues Entry/SL/TP1 pending-order ticket; final Place remains manual')
