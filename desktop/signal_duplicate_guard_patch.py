from pathlib import Path

MARK='MH_SAME_SIGNAL_GUARD_V799'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# -----------------------------------------------------------------------------
# Backend: one semantic same-point gate shared by Records and the UI.
# A duplicate means SAME symbol + timeframe + direction + displayed Entry/SL/TP1/TP2
# while an earlier matching signal is still pending/open. Terminal trades do not block
# a genuinely new future setup at the same prices.
# -----------------------------------------------------------------------------
p=Path('records_mt5_local.go')
s=p.read_text(encoding='utf-8')

helpers=r'''
// MH_SAME_SIGNAL_GUARD_V799
func sameSignalDisplayPrice(a, b float64) bool {
	if !recordNumberOK(a) || !recordNumberOK(b) {
		return false
	}
	scale := 100000.0
	if math.Max(math.Abs(a), math.Abs(b)) >= 100 {
		scale = 100.0
	}
	return math.Round(a*scale) == math.Round(b*scale)
}

func sameSignalPointRecordCapture(x mt5LocalRecord, q mt5LocalCapture) bool {
	return strings.EqualFold(strings.TrimSpace(x.Symbol), strings.TrimSpace(q.Symbol)) &&
		strings.EqualFold(strings.TrimSpace(x.Timeframe), strings.TrimSpace(q.Timeframe)) &&
		strings.EqualFold(strings.TrimSpace(x.Direction), strings.TrimSpace(q.Direction)) &&
		sameSignalDisplayPrice(x.Entry, q.Entry) &&
		sameSignalDisplayPrice(x.SL, q.SL) &&
		sameSignalDisplayPrice(x.TP1, q.TP1) &&
		sameSignalDisplayPrice(x.TP2, q.TP2)
}

func mt5RecordHasLifecycle(x mt5LocalRecord) bool {
	return x.OrderTicket > 0 || x.PositionID > 0 || x.DealTicket > 0 ||
		x.PendingPlacedAt > 0 || x.ActivatedAt > 0 || x.EntryAt > 0 ||
		strings.TrimSpace(x.LastMT5Event) != ""
}

func mt5RecordBlocksSameSignal(x mt5LocalRecord, now int64) bool {
	if recordTerminalMT5(x) {
		return false
	}
	if mt5RecordHasLifecycle(x) {
		return true
	}
	// Protect the short gap between saving a fresh record and receiving the EA's
	// PENDING_PLACED event. Old orphan SIGNAL GENERATED rows do not block forever.
	return strings.EqualFold(strings.TrimSpace(x.Status), "SIGNAL GENERATED") && now-x.CreatedAt >= 0 && now-x.CreatedAt <= 120
}

func findActiveSameSignal(s mt5LocalStore, q mt5LocalCapture) int {
	now := time.Now().Unix()
	for i := len(s.Records)-1; i >= 0; i-- {
		x := s.Records[i]
		if mt5RecordBlocksSameSignal(x, now) && sameSignalPointRecordCapture(x, q) {
			return i
		}
	}
	return -1
}

func sameSignalRecordKey(x mt5LocalRecord) string {
	priceKey := func(v float64) string {
		scale := 100000.0
		if math.Abs(v) >= 100 { scale = 100.0 }
		return fmt.Sprintf("%.0f", math.Round(v*scale))
	}
	return strings.ToUpper(strings.TrimSpace(x.Symbol))+"|"+
		strings.ToLower(strings.TrimSpace(x.Timeframe))+"|"+
		strings.ToUpper(strings.TrimSpace(x.Direction))+"|"+
		priceKey(x.Entry)+"|"+priceKey(x.SL)+"|"+priceKey(x.TP1)+"|"+priceKey(x.TP2)
}

// Clean the old V79.7 rows visible in Records: if one matching signal has a real
// active MT5 lifecycle, later same-point rows that never reached MT5 are redundant.
func compactActiveSameSignalDuplicates(s *mt5LocalStore) int {
	groups := map[string][]int{}
	for i, x := range s.Records {
		groups[sameSignalRecordKey(x)] = append(groups[sameSignalRecordKey(x)], i)
	}
	drop := map[int]bool{}
	now := time.Now().Unix()
	for _, idxs := range groups {
		active := -1
		activeCount := 0
		for _, i := range idxs {
			x := s.Records[i]
			if mt5RecordHasLifecycle(x) && mt5RecordBlocksSameSignal(x, now) {
				active = i
				activeCount++
			}
		}
		if activeCount != 1 { continue }
		base := s.Records[active]
		for _, i := range idxs {
			if i == active { continue }
			x := s.Records[i]
			if !mt5RecordHasLifecycle(x) && !recordTerminalMT5(x) && x.CreatedAt >= base.CreatedAt {
				drop[i] = true
			}
		}
	}
	if len(drop)==0 { return 0 }
	kept := make([]mt5LocalRecord,0,len(s.Records)-len(drop))
	for i,x := range s.Records { if !drop[i] { kept=append(kept,x) } }
	s.Records=kept
	return len(drop)
}
'''

s=rep(s,
'''func recordNumberOK(v float64) bool {
	return !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0
}
''',
'''func recordNumberOK(v float64) bool {
	return !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0
}
'''+helpers,
'backend duplicate helpers')

# Semantic duplicate protection in the capture endpoint as a server-side safety net.
s=rep(s,
'''	s := loadMT5LocalStore()
	for _, x := range s.Records {
		if x.SignalID == q.SignalID || x.ID == q.SignalID {
''',
'''	s := loadMT5LocalStore()
	_, _, _ = syncMT5Lifecycle(&s)
	_ = compactActiveSameSignalDuplicates(&s)
	for _, x := range s.Records {
		if x.SignalID == q.SignalID || x.ID == q.SignalID {
''',
'capture lifecycle sync')
s=rep(s,
'''	for _, x := range s.Records {
		if x.SignalID == q.SignalID || x.ID == q.SignalID {
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": q.SignalID})
			return
		}
	}
	now := time.Now()
''',
'''	for _, x := range s.Records {
		if x.SignalID == q.SignalID || x.ID == q.SignalID {
			_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": q.SignalID})
			return
		}
	}
	if i := findActiveSameSignal(s, q); i >= 0 {
		x := s.Records[i]
		_ = saveMT5LocalStore(s)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "same_point": true, "existing_signal_id": x.SignalID, "existing_status": x.Status})
		return
	}
	now := time.Now()
''',
'capture same-point guard')

handler=r'''
func mt5DuplicateSignalHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q mt5LocalCapture
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Timeframe = strings.TrimSpace(q.Timeframe)
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	if q.Symbol == "" || q.Timeframe == "" || (q.Direction != "BUY" && q.Direction != "SELL") ||
		!recordNumberOK(q.Entry) || !recordNumberOK(q.SL) || !recordNumberOK(q.TP1) || !recordNumberOK(q.TP2) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "duplicate": false})
		return
	}
	mt5RecordsMu.Lock()
	s := loadMT5LocalStore()
	_, _, _ = syncMT5Lifecycle(&s)
	removed := compactActiveSameSignalDuplicates(&s)
	i := findActiveSameSignal(s, q)
	_ = saveMT5LocalStore(s)
	mt5RecordsMu.Unlock()
	if i >= 0 {
		x := s.Records[i]
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok": true, "duplicate": true, "same_point": true,
			"existing_signal_id": x.SignalID, "existing_status": x.Status,
			"duplicates_compacted": removed,
		})
		return
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "duplicate": false, "duplicates_compacted": removed})
}

'''
s=rep(s,
'func mt5LocalRecordsHandler(w http.ResponseWriter, r *http.Request) {',
handler+'func mt5LocalRecordsHandler(w http.ResponseWriter, r *http.Request) {',
'duplicate endpoint handler')

# Compact old redundant rows whenever Records syncs/loads.
s=rep(s,
'''	eventsRead, matched, syncErr := syncMT5Lifecycle(&s)
	_ = saveMT5LocalStore(s)
''',
'''	eventsRead, matched, syncErr := syncMT5Lifecycle(&s)
	_ = compactActiveSameSignalDuplicates(&s)
	_ = saveMT5LocalStore(s)
''',
'list duplicate compaction')
s=rep(s,
'''	eventsRead, matched, err := syncMT5Lifecycle(&s)
	if err == nil {
		err = saveMT5LocalStore(s)
''',
'''	eventsRead, matched, err := syncMT5Lifecycle(&s)
	_ = compactActiveSameSignalDuplicates(&s)
	if err == nil {
		err = saveMT5LocalStore(s)
''',
'sync duplicate compaction')
s=rep(s,
'''	mux.HandleFunc("/api/records-v2", mt5LocalRecordsHandler)
	mux.HandleFunc("/api/records-v2/capture", captureMT5LocalRecord)
''',
'''	mux.HandleFunc("/api/records-v2", mt5LocalRecordsHandler)
	mux.HandleFunc("/api/records-v2/duplicate", mt5DuplicateSignalHandler) // MH_SAME_SIGNAL_GUARD_V799
	mux.HandleFunc("/api/records-v2/capture", captureMT5LocalRecord)
''',
'register duplicate route')
p.write_text(s,encoding='utf-8')

# -----------------------------------------------------------------------------
# Frontend gate. It runs BEFORE WhatsApp / Records / MT5 side effects.
# -----------------------------------------------------------------------------
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')

js=r'''// MH_SAME_SIGNAL_GUARD_V799
async function checkSameSignalV799(d){
  const sig=d?.signal;
  if(!sig){if(d)d._duplicateSignal=false;return null}
  try{
    const r=await fetch('/api/records-v2/duplicate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2)
    })});
    const j=await r.json();
    d._duplicateSignal=!!j.duplicate;
    d._duplicateOf=j.existing_signal_id||'';
    d._duplicateStatus=j.existing_status||'';
    return j;
  }catch(_){d._duplicateSignal=false;return null}
}
function sameSignalTextV799(d){
  const sig=d?.signal;
  if(!sig)return 'SAME SIGNAL';
  return `SAME SIGNAL • ${symbol} ${timeframe} ${sig.direction} • Entry ${fmt(sig.entry)} • SL ${fmt(sig.sl)} • TP1 ${fmt(sig.tp1)} • TP2 ${fmt(sig.tp2)} • duplicate WhatsApp / Record / MT5 pending skipped`;
}

'''
s=rep(s,
"async function captureSignalRecordV796(d,state='NEW'){",
js+"async function captureSignalRecordV796(d,state='NEW'){",
'frontend duplicate helpers')
s=rep(s,
'''  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW')return;
''',
'''  const sig=d?.signal;
  if(!sig||d?._duplicateSignal||String(state).toUpperCase()!=='NEW')return;
''',
'record capture duplicate guard')
s=rep(s,
"function addRecent(d,state='NEW'){\n  const sig=d.signal,",
"function addRecent(d,state='NEW'){\n  if(d?._duplicateSignal){renderRecentSignals();return;}\n  const sig=d.signal,",
'recent list duplicate guard')
s=rep(s,
'''async function sendManualNewAnalyzeSignalToEAV796(d){
  const sig=d?.signal;
  if(!sig)return null;
''',
'''async function sendManualNewAnalyzeSignalToEAV796(d){
  const sig=d?.signal;
  if(!sig||d?._duplicateSignal)return null;
''',
'EA duplicate guard')

# All UNIQUE NEW ANALYZE results (manual or timer) may now reach the auto-pending EA.
# Same-point duplicates are blocked before this hook.
s=s.replace(
"if(d.signal&&!fromAuto)void sendManualNewAnalyzeSignalToEAV796(d); // MH_EA_SIGNAL_READER_BRIDGE_V796 manual NEW ANALYZE handoff",
"if(d.signal&&!d._duplicateSignal)void sendManualNewAnalyzeSignalToEAV796(d); // MH_SAME_SIGNAL_GUARD_V799 unique NEW ANALYZE handoff",
1)
if 'MH_SAME_SIGNAL_GUARD_V799 unique NEW ANALYZE handoff' not in s:
    raise SystemExit('EA handoff anchor not found')

s=rep(s,
'''    d._ranked=buildRankedForUi(c,d);const reason=refreshReason(prev,d);
    if(d.signal){const obj={signal:d.signal,state:d.signal.reconfirmed?'RECONFIRMED':'PENDING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
''',
'''    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);
    if(d.signal){const dup=await checkSameSignalV799(d);if(dup?.duplicate)reason=`${sameSignalTextV799(d)}. ${reason}`;}
    if(d.signal){const obj={signal:d.signal,state:d.signal.reconfirmed?'RECONFIRMED':'PENDING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
''',
'NEW duplicate check before side effects')

# Auto cycle: skip duplicate WhatsApp but preserve the fixed timing schedule.
s=rep(s,
'''async function autoSendAndSchedule(d,action,status=''){
  if(!autoSignalEnabled)return;
  const triggerAt=autoActionStartedAt||Date.now();
  try{
''',
'''async function autoSendAndSchedule(d,action,status=''){
  if(!autoSignalEnabled)return;
  const triggerAt=autoActionStartedAt||Date.now();
  if(d?._duplicateSignal){setAutoStatus(sameSignalTextV799(d),'warn');scheduleFixedAfterDecision(d,action,triggerAt);return;}
  try{
''',
'auto WhatsApp duplicate suppression')

# Manual NEW: same signal is displayed locally but no outbound side effect is repeated.
s=rep(s,
'''    if(autoSignalEnabled)await autoSendAndSchedule(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));
    else{
      try{
''',
'''    if(autoSignalEnabled)await autoSendAndSchedule(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));
    else{
      if(d?._duplicateSignal){setAutoStatus(sameSignalTextV799(d),'warn');return d;}
      try{
''',
'manual NEW WhatsApp duplicate suppression')

# RE-EVALUATE: when it resolves to the same active Entry/SL/TP set, do not repeat the
# WhatsApp message. A genuinely different re-evaluation/status continues normally.
s=rep(s,
'''    if(keep){const obj={signal:displayOriginal?current.signal:s,state:status,candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
    renderDecision(current,`RE-EVALUATE SIGNAL: ${status}. ${current.explanation}`,'REEVAL');
''',
'''    if(keep){const obj={signal:displayOriginal?current.signal:s,state:status,candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
    if(current.signal){const dup=await checkSameSignalV799(current);if(dup?.duplicate)current.explanation+=` ${sameSignalTextV799(current)}.`;}
    renderDecision(current,`RE-EVALUATE SIGNAL: ${status}. ${current.explanation}`,'REEVAL');
''',
'REEVAL duplicate check')
s=rep(s,
'''    if(autoSignalEnabled)await autoSendAndSchedule(current,'RE-EVALUATE',status);
    else{
      try{
''',
'''    if(autoSignalEnabled)await autoSendAndSchedule(current,'RE-EVALUATE',status);
    else{
      if(current?._duplicateSignal){setAutoStatus(sameSignalTextV799(current),'warn');return current;}
      try{
''',
'manual REEVAL WhatsApp duplicate suppression')

p.write_text(s,encoding='utf-8')
print('PASS '+MARK+': same Entry/SL/TP + same pair/timeframe duplicates are suppressed across WhatsApp, Records and MT5 pending')
