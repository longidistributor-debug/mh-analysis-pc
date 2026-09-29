from pathlib import Path
import re


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'{label}: anchor not found')
    return text.replace(old, new, 1)


def regex_once(text, pattern, repl, label, flags=0):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out


# ---------------- web/app.js ----------------
app_path = Path('web/app.js')
app = app_path.read_text(encoding='utf-8')

# V.56.25 RSI: restore standard Wilder-smoothed RSI instead of a simple last-window ratio.
old_rsi = "function rsi(v,p=14){if(v.length<2)return 50;p=Math.max(1,Math.min(p,v.length-1));let g=0,l=0;for(let i=v.length-p;i<v.length;i++){const d=v[i]-v[i-1];if(d>0)g+=d;else l-=d}if(l<1e-12)return 100;const rs=g/l;return 100-100/(1+rs)}"
new_rsi = """function rsi(v,p=14){
  if(v.length<2)return 50;
  p=Math.max(1,Math.min(p,v.length-1));
  let gain=0,loss=0;
  for(let i=1;i<=p;i++){const d=v[i]-v[i-1];if(d>0)gain+=d;else if(d<0)loss-=d}
  gain/=p;loss/=p;
  for(let i=p+1;i<v.length;i++){const d=v[i]-v[i-1],g=d>0?d:0,l=d<0?-d:0;gain=(gain*(p-1)+g)/p;loss=(loss*(p-1)+l)/p}
  if(loss<1e-12)return gain<1e-12?50:100;
  const rs=gain/loss;return 100-100/(1+rs);
}"""
app = replace_once(app, old_rsi, new_rsi, 'Wilder RSI')

# V.56.25: never use pre-signal candle extremes to claim that SL/TP1/TP2 was already hit.
# The creation candle is ambiguous because its earlier high/low happened before the signal;
# only its later/current close is safe, then full OHLC is allowed from following candles.
old_touch = "function signalTouched(c,s,field){const idx=Math.max(0,c.findIndex(x=>Number(x.t)>=Number(s.createdCandleTime)));const w=c.slice(idx<0?0:idx),p=Number(s[field]);if(!Number.isFinite(p))return false;if(field==='sl')return s.direction==='BUY'?w.some(x=>x.l<=p):w.some(x=>x.h>=p);return s.direction==='BUY'?w.some(x=>x.h>=p):w.some(x=>x.l<=p)}"
new_touch = """function signalTouched(c,s,field){
  const created=Number(s?.createdCandleTime),p=Number(s?.[field]);
  if(!Number.isFinite(created)||!Number.isFinite(p))return false;
  const idx=c.findIndex(x=>Number(x.t)>=created);if(idx<0)return false;
  const buy=String(s.direction||'').toUpperCase()==='BUY',creationClose=Number(c[idx]?.c),after=c.slice(idx+1);
  if(field==='sl'){
    if(Number.isFinite(creationClose)&&(buy?creationClose<=p:creationClose>=p))return true;
    return buy?after.some(x=>x.l<=p):after.some(x=>x.h>=p);
  }
  if(Number.isFinite(creationClose)&&(buy?creationClose>=p:creationClose<=p))return true;
  return buy?after.some(x=>x.h>=p):after.some(x=>x.l<=p);
}"""
app = replace_once(app, old_touch, new_touch, 'post-signal target tracking')

# V.56.25: keep the strict standard path unchanged, but allow an exceptional high-quality
# reference-backed setup without requiring a near-perfect 3/7 reference count / zero conflict.
old_gate = """const standardSetupV5624=corePass>=2&&tacticalPass>=2&&structuralPass>=2&&referencePass>=3&&strongReference&&oppositeConflicts<=1&&score>=requiredScore&&edge>requiredEdge;
const bestSetupV5624=score>=70&&corePass>=2&&structuralPass>=2&&referencePass>=3&&oppositeConflicts===0&&edge>requiredEdge;
const ok=standardSetupV5624||bestSetupV5624;
let reason=bestSetupV5624&&!standardSetupV5624?'Best setup confirmed by direction, structure and references':'Reference-weighted confirmation passed';"""
new_gate = """const standardSetupV5624=corePass>=2&&tacticalPass>=2&&structuralPass>=2&&referencePass>=3&&strongReference&&oppositeConflicts<=1&&score>=requiredScore&&edge>requiredEdge;
const bestSetupV5625=score>=74&&corePass>=2&&tacticalPass>=2&&structuralPass>=2&&referencePass>=2&&strongReference&&oppositeConflicts<=1&&edge>Math.max(3,requiredEdge*.85);
const ok=standardSetupV5624||bestSetupV5625;
let reason=bestSetupV5625&&!standardSetupV5624?'Best setup confirmed by strong direction, structure and references':'Reference-weighted confirmation passed';"""
app = replace_once(app, old_gate, new_gate, 'balanced best-setup gate')
app = replace_once(app,
    "else if(referencePass<3)reason=`Only ${referencePass}/7 runtime reference checks aligned`;",
    "else if(referencePass<3&&!bestSetupV5625)reason=`Only ${referencePass}/7 runtime reference checks aligned`;",
    'best-setup reason guard')

# Remove the old generic 1R->entry breakeven. V.56.25 uses the exact staged TP2 rules below.
app = replace_once(app,
    "    if(move>=originalRisk)sl=Math.max(sl,prev.entry);",
    "    // V.56.25 staged TP2 protection is applied only to an EA-owned live POSITION.",
    'remove BUY generic breakeven')
app = replace_once(app,
    "    if(move>=originalRisk)sl=Math.min(sl,prev.entry);",
    "    // V.56.25 staged TP2 protection is applied only to an EA-owned live POSITION.",
    'remove SELL generic breakeven')
# `originalRisk` is no longer used after the exact staged-BE change.
app = replace_once(app,
    "  const originalRisk=Math.max(Math.abs(prev.entry-prev.sl),1e-9),move=prev.direction==='BUY'?last.c-prev.entry:prev.entry-last.c;",
    "  const move=prev.direction==='BUY'?last.c-prev.entry:prev.entry-last.c;",
    'remove unused originalRisk')

# Exact TP2 protection requested by user. Mid-points of the requested ranges are used:
# 40% TP2 progress -> entry +/- $2.50, then TP1 + $6.50 -> SL at TP1.
protection_anchor = "function adaptiveExpiryBars(c){"
protection_helper = """const TP2_BE_PROGRESS_V5625=.40;
const TP2_BE_LOCK_USD_V5625=2.50;
const TP1_LOCK_OFFSET_USD_V5625=6.50;
function applyTP2ProtectionV5625(original,managed,c){
  if(!partialTpEnabled||!original||!managed||original.direction!==managed.direction)return managed;
  const last=Number(c?.at(-1)?.c),entry=Number(original.entry),tp1=Number(original.tp1),tp2=Number(original.tp2),buy=String(original.direction).toUpperCase()==='BUY';
  if(![last,entry,tp1,tp2].every(Number.isFinite))return managed;
  const total=buy?tp2-entry:entry-tp2,moved=buy?last-entry:entry-last;if(!(total>0))return managed;
  let sl=Number(managed.reversalProtection?managed.sl:original.sl);if(!Number.isFinite(sl))sl=Number(original.sl);
  const improve=level=>{if(!Number.isFinite(level))return;sl=buy?Math.max(sl,level):Math.min(sl,level)};
  let stage='NONE';
  if(moved/total>=TP2_BE_PROGRESS_V5625){improve(entry+(buy?TP2_BE_LOCK_USD_V5625:-TP2_BE_LOCK_USD_V5625));stage='PROTECTED_BE'}
  const beyondTp1=buy?last-tp1:tp1-last;
  if(beyondTp1>=TP1_LOCK_OFFSET_USD_V5625){improve(tp1);stage='TP1_LOCK'}
  const gap=Math.max((Number(stats(c)?.trMedian)||0)*.05,.01);
  sl=buy?Math.min(sl,last-gap):Math.max(sl,last+gap);
  return{...managed,sl,protectionStageV5625:stage,protectionProgressV5625:moved/total};
}
"""
if protection_anchor not in app:
    raise SystemExit('TP2 protection anchor not found')
app = app.replace(protection_anchor, protection_helper + protection_anchor, 1)

# Reconcile Record duplicates with live EA-owned exposure. A stale Record must never suppress
# a missing pending order.
duplicate_anchor = "function sameSignalMessageV30(d){"
duplicate_helper = """function managedDirectionV5625(st){return String(st?.managed_direction||'').toUpperCase()}
function hasManagedSignalExposureV5625(st,sig){const dir=managedDirectionV5625(st),want=String(sig?.direction||'').toUpperCase();return st?.managed_active===true&&(dir==='MIXED'||dir===want)}
function hasManagedPositionV5625(st,sig){const dir=String(st?.managed_position_direction||'').toUpperCase(),want=String(sig?.direction||'').toUpperCase();return st?.managed_position_active===true&&dir===want}
async function readMT5ModesV5625(){try{const r=await fetch('/api/mt5/modes',{cache:'no-store'}),j=await r.json();return r.ok?j:null}catch(_){return null}}
async function reconcileRecordDuplicateV5625(d){
  const same=await checkSameSignalV30(d);if(!same?.duplicate)return same;
  const st=await readMT5ActiveStateV552(symbol);
  if(!hasManagedSignalExposureV5625(st,d?.signal)){d._sameActiveSignal=false;d._sameSignalStatus='';d._staleRecordDuplicate=true}
  return same;
}
"""
if duplicate_anchor not in app:
    raise SystemExit('duplicate reconciliation anchor not found')
app = app.replace(duplicate_anchor, duplicate_helper + duplicate_anchor, 1)

old_same_line = "    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}"
new_same_line = "    if(d.signal){const same=await reconcileRecordDuplicateV5625(d);if(same?.duplicate&&d._sameActiveSignal)reason=sameSignalMessageV30(d);}"
app = replace_once(app, old_same_line, new_same_line, 'live duplicate reconciliation')

# Active management may only target an EA-owned open POSITION, never manual/PENDING/FLOATING.
old_manage_guard = "  const st=await readMT5ActiveStateV552(symbol);if(!st?.active||String(st.direction||'').toUpperCase()!==String(managed.direction||'').toUpperCase())return null;"
new_manage_guard = "  const st=await readMT5ActiveStateV552(symbol);if(!hasManagedPositionV5625(st,managed))return null;const modes=await readMT5ModesV5625();if(modes?.sl_adjustment!==true)return null;"
app = replace_once(app, old_manage_guard, new_manage_guard, 'EA-position-only manage guard')

# Canonical fanout: MT5 pending first; Record capture is bookkeeping and may not block execution.
fanout_pattern = r"async function dispatchUniqueSignalV36\(d\)\{.*?\n\}\nfunction waitForUiCommitV5623\(\)\{"
fanout_new = """async function dispatchUniqueSignalV36(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const live=await readMT5ActiveStateV552(symbol);
  if(hasManagedSignalExposureV5625(live,sig)){d._sameActiveSignal=true;d._sameSignalStatus='ACTIVE IN MT5';setAutoStatus('Same EA trade/pending is active in MT5 • no duplicate pending','warn');return{duplicate:true,source:'mt5'};}
  const baseSignalId=`MH${Date.now()}_${symbol}_${timeframe}`,selectedLot=lotForSignalScore(sig.score),signalId=partialTpEnabled?`${baseSignalId}__PT1_${Number(sig.tp1).toFixed(10)}`:baseSignalId,finalTp=partialTpEnabled?Number(sig.tp2):Number(sig.tp1);
  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry),pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);
  const er=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:finalTp,lot:selectedLot,expiry:0})});
  let ej={};try{ej=await er.json()}catch(_){}if(!er.ok)throw new Error(ej.error||`EA bridge HTTP ${er.status}`);
  const recordPayload={signal_id:signalId,symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2),score:Number(sig.score)||0,setup:d.bestFamily||sig.setupReason||'',action:'NEW'};
  let rj=null,recordError='';
  try{const rr=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordPayload)});try{rj=await rr.json()}catch(_){rj={}}if(!rr.ok)throw new Error(rj.error||`Records HTTP ${rr.status}`)}catch(e){recordError=String(e?.message||e);console.warn('Record sync failed after MT5 pending was sent',e)}
  try{await prepareMT5SignalV796(d,'NEW')}catch(_){}
  setAutoStatus(recordError?`MT5 pending sent • ${pending} • Record sync pending`:`Signal recorded • MT5 pending sent • ${pending} • Lot ${selectedLot.toFixed(2)} • Partial TP ${partialTpEnabled?'ON':'OFF'}`,recordError?'warn':'good');
  return{record:rj,ea:ej,signal_id:signalId,record_error:recordError};
}
function waitForUiCommitV5623(){"""
app = regex_once(app, fanout_pattern, fanout_new, 'MT5-first canonical fanout', flags=re.S)

# During re-evaluation, apply staged protection only when SL Adjustment is ON and the live
# trade is an EA-owned POSITION. Otherwise retain the original SL and do not touch it.
old_display = """    if(displayOriginal){const sideScore=s.direction==='BUY'?current.buyScore:current.sellScore;if(same&&current.signal)current.signal={...current.signal,score:sideScore,status};else current.signal={...(current.signal||s),score:sideScore,status};current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Age ${age} bars; adaptive lifecycle ${life} bars.`}
    else{current.signal=null;current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Run NEW ANALYZE if you want a new setup.`}"""
new_display = """    if(displayOriginal){const sideScore=s.direction==='BUY'?current.buyScore:current.sellScore;if(same&&current.signal)current.signal={...current.signal,score:sideScore,status};else current.signal={...(current.signal||s),score:sideScore,status};current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Age ${age} bars; adaptive lifecycle ${life} bars.`}
    else{current.signal=null;current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Run NEW ANALYZE if you want a new setup.`}
    if(displayOriginal&&current.signal){const [protectState,modeState]=await Promise.all([readMT5ActiveStateV552(symbol),readMT5ModesV5625()]);if(modeState?.sl_adjustment===true&&hasManagedPositionV5625(protectState,s))current.signal=applyTP2ProtectionV5625(s,current.signal,c);else current.signal={...current.signal,sl:Number(s.sl)}}"""
app = replace_once(app, old_display, new_display, 'staged protection integration')

app_path.write_text(app, encoding='utf-8', newline='\n')


# ---------------- ea_signal_bridge.go ----------------
ea_path = Path('ea_signal_bridge.go')
ea = ea_path.read_text(encoding='utf-8')

# Track decoder-provided MAGIC so manual Magic=0 / unknown trades can never be modified.
old_struct = """type eaActiveTrade struct {
\tSymbol  string  `json:\"symbol\"`
\tType    string  `json:\"type\"`
\tTicket  string  `json:\"ticket\"`
\tState   string  `json:\"state\"`
\tEntry   float64 `json:\"entry\"`
\tSL      float64 `json:\"sl\"`
\tTP      float64 `json:\"tp\"`
\tLot     float64 `json:\"lot\"`
\tUpdated int64   `json:\"updated\"`
}"""
new_struct = """type eaActiveTrade struct {
\tSymbol  string  `json:\"symbol\"`
\tType    string  `json:\"type\"`
\tTicket  string  `json:\"ticket\"`
\tState   string  `json:\"state\"`
\tMagic   string  `json:\"magic,omitempty\"`
\tManaged bool    `json:\"managed\"`
\tEntry   float64 `json:\"entry\"`
\tSL      float64 `json:\"sl\"`
\tTP      float64 `json:\"tp\"`
\tLot     float64 `json:\"lot\"`
\tUpdated int64   `json:\"updated\"`
}"""
ea = replace_once(ea, old_struct, new_struct, 'EA active Magic fields')

old_parser = """\t\tif len(p) >= 5 && strings.EqualFold(strings.TrimSpace(p[0]), \"ACTIVE\") {
\t\t\tt := eaActiveTrade{Type: strings.ToUpper(strings.TrimSpace(p[1])), Symbol: normalizeEABridgeSymbol(p[2]), State: strings.ToUpper(strings.TrimSpace(p[3])), Ticket: strings.TrimSpace(p[4])}
\t\t\tif t.Symbol != \"\" && eaDirection(t.Type) != \"\" {
\t\t\t\tout = append(out, t)
\t\t\t}
\t\t\tcontinue
\t\t}"""
new_parser = """\t\tif len(p) >= 5 && strings.EqualFold(strings.TrimSpace(p[0]), \"ACTIVE\") {
\t\t\tmagic := \"\"
\t\t\tif len(p) >= 6 { magic = strings.TrimSpace(p[5]) }
\t\t\tmanaged := magic != \"\" && magic != \"0\"
\t\t\tt := eaActiveTrade{Type: strings.ToUpper(strings.TrimSpace(p[1])), Symbol: normalizeEABridgeSymbol(p[2]), State: strings.ToUpper(strings.TrimSpace(p[3])), Ticket: strings.TrimSpace(p[4]), Magic: magic, Managed: managed}
\t\t\tif t.Symbol != \"\" && eaDirection(t.Type) != \"\" {
\t\t\t\tout = append(out, t)
\t\t\t}
\t\t\tcontinue
\t\t}"""
ea = replace_once(ea, old_parser, new_parser, 'EA Magic parser')

# Managed exposure helper: optional POSITION-only filter excludes PENDING/FLOATING/unknown states.
active_func_end = """\treturn matches, dir, nil
}

func eaActiveStateHandler"""
managed_helper = """\treturn matches, dir, nil
}

func managedExposureFor(symbol string, positionsOnly bool) ([]eaActiveTrade, string, error) {
\tall, err := readEAActiveTrades()
\tif err != nil { return nil, \"\", err }
\tsymbol = normalizeEABridgeSymbol(symbol)
\tmatches := []eaActiveTrade{}
\tdir := \"\"
\tfor _, t := range all {
\t\tif t.Symbol != symbol || !t.Managed { continue }
\t\tif positionsOnly && !strings.EqualFold(strings.TrimSpace(t.State), \"POSITION\") { continue }
\t\td := eaDirection(t.Type); if d == \"\" { continue }
\t\tmatches = append(matches, t)
\t\tif dir == \"\" { dir = d } else if dir != d { dir = \"MIXED\" }
\t}
\treturn matches, dir, nil
}

func eaActiveStateHandler"""
ea = replace_once(ea, active_func_end, managed_helper, 'managed exposure helper')

# Rich active endpoint: generic exposure remains for reversal safety; managed fields are the
# only fields allowed to drive automatic SL management / duplicate execution suppression.
active_handler_pattern = r"func eaActiveStateHandler\(w http\.ResponseWriter, r \*http\.Request\) \{.*?\n\}\n\nfunc eaManageHandler"
active_handler_new = """func eaActiveStateHandler(w http.ResponseWriter, r *http.Request) {
\tw.Header().Set(\"Content-Type\", \"application/json\")
\tif r.Method != http.MethodGet { http.Error(w, \"method\", http.StatusMethodNotAllowed); return }
\tsym := normalizeEABridgeSymbol(r.URL.Query().Get(\"symbol\"))
\tif sym != \"\" {
\t\ttrades, dir, err := activeExposureFor(sym); if err != nil { w.WriteHeader(http.StatusInternalServerError); _ = json.NewEncoder(w).Encode(map[string]any{\"error\": err.Error()}); return }
\t\tmanaged, managedDir, err := managedExposureFor(sym, false); if err != nil { w.WriteHeader(http.StatusInternalServerError); _ = json.NewEncoder(w).Encode(map[string]any{\"error\": err.Error()}); return }
\t\tpositions, positionDir, err := managedExposureFor(sym, true); if err != nil { w.WriteHeader(http.StatusInternalServerError); _ = json.NewEncoder(w).Encode(map[string]any{\"error\": err.Error()}); return }
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"ok\": true, \"symbol\": sym, \"active\": len(trades) > 0, \"direction\": dir, \"trades\": trades, \"managed_active\": len(managed) > 0, \"managed_direction\": managedDir, \"managed_trades\": managed, \"managed_position_active\": len(positions) > 0, \"managed_position_direction\": positionDir, \"managed_positions\": positions})
\t\treturn
\t}
\ttrades, err := readEAActiveTrades(); if err != nil { w.WriteHeader(http.StatusInternalServerError); _ = json.NewEncoder(w).Encode(map[string]any{\"error\": err.Error()}); return }
\t_ = json.NewEncoder(w).Encode(map[string]any{\"ok\": true, \"active\": len(trades) > 0, \"trades\": trades})
}

func eaManageHandler"""
ea = regex_once(ea, active_handler_pattern, active_handler_new, 'EA active ownership endpoint', flags=re.S)

# Fail-safe server enforcement: adjustment toggle must be ON and the target must be a real
# EA-owned POSITION with matching direction. Manual Magic=0 and pending/floating states are rejected.
manage_guard_anchor = """\tif q.Direction != \"BUY\" && q.Direction != \"SELL\" {
\t\tw.WriteHeader(http.StatusBadRequest)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"error\": \"direction must be BUY or SELL\"})
\t\treturn
\t}
\tif q.SL <= 0 || q.TP <= 0 {"""
manage_guard_new = """\tif q.Direction != \"BUY\" && q.Direction != \"SELL\" {
\t\tw.WriteHeader(http.StatusBadRequest)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"error\": \"direction must be BUY or SELL\"})
\t\treturn
\t}
\tif !v558Snapshot().SLAdjustment {
\t\tw.WriteHeader(http.StatusConflict)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"error\": \"SL Adjustment is OFF\", \"code\": \"SL_ADJUSTMENT_OFF\"})
\t\treturn
\t}
\tpositions, positionDir, exposureErr := managedExposureFor(q.Symbol, true)
\tif exposureErr != nil {
\t\tw.WriteHeader(http.StatusInternalServerError)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"error\": exposureErr.Error()})
\t\treturn
\t}
\tif len(positions) == 0 || positionDir == \"MIXED\" || positionDir != q.Direction {
\t\tw.WriteHeader(http.StatusConflict)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{\"error\": \"no matching EA-owned live position to manage\", \"code\": \"NO_MANAGED_EA_POSITION\"})
\t\treturn
\t}
\tif q.SL <= 0 || q.TP <= 0 {"""
ea = replace_once(ea, manage_guard_anchor, manage_guard_new, 'server manual/floating isolation guard')

ea_path.write_text(ea, encoding='utf-8', newline='\n')


# ---------------- Version identities only ----------------
Path('VERSION').write_text('V.56.25\n', encoding='utf-8', newline='\n')
version_replacements = {
    'license_auth.go': (r'const licAppVersion = \"V\.[0-9.]+\"', 'const licAppVersion = \"V.56.25\"'),
    'updater.go': (r'const mhPublicVersionV001 = \"V\.[0-9.]+\"', 'const mhPublicVersionV001 = \"V.56.25\"'),
    'webview2_host.go': (r'Version: V\.[0-9.]+', 'Version: V.56.25'),
    'web/index.html': (r'id=\"mhUpdateVersionV001\">V\.[0-9.]+<', 'id=\"mhUpdateVersionV001\">V.56.25<'),
}
for fn, (pat, repl) in version_replacements.items():
    p = Path(fn); s = p.read_text(encoding='utf-8'); s, n = re.subn(pat, repl, s, count=1)
    if n != 1: raise SystemExit(f'version identity not found in {fn}')
    p.write_text(s, encoding='utf-8', newline='\n')


# ---------------- Surgical regression assertions ----------------
app = app_path.read_text(encoding='utf-8')
ea = ea_path.read_text(encoding='utf-8')
for marker in [
    'gain=(gain*(p-1)+g)/p',
    'TP2_BE_PROGRESS_V5625=.40',
    'TP2_BE_LOCK_USD_V5625=2.50',
    'TP1_LOCK_OFFSET_USD_V5625=6.50',
    'bestSetupV5625=score>=74',
    'reconcileRecordDuplicateV5625',
    'MT5 pending sent',
    'managed_position_active',
    'modeState?.sl_adjustment===true',
]:
    if marker not in app: raise SystemExit('app V.56.25 marker missing: ' + marker)
if 'if(move>=originalRisk)' in app: raise SystemExit('legacy generic breakeven still present')
if 'Math.max(0,c.findIndex(x=>Number(x.t)>=Number(s.createdCandleTime)))' in app: raise SystemExit('historical TP scan bug remains')
for marker in ['Magic   string', 'Managed bool', 'managedExposureFor', 'NO_MANAGED_EA_POSITION', 'SL_ADJUSTMENT_OFF', 'managed_position_active']:
    if marker not in ea: raise SystemExit('EA V.56.25 marker missing: ' + marker)
if Path('VERSION').read_text(encoding='utf-8').strip() != 'V.56.25': raise SystemExit('VERSION mismatch')
print('V.56.25 surgical patch applied')
