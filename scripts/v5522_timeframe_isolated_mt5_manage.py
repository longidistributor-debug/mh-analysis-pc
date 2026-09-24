from pathlib import Path

# V.55.22: every RE-EVALUATE / active-trade manage command must carry the
# originating analysis timeframe. The EA can then modify only the exact
# timeframe-bound position/order instead of every same-symbol/same-direction trade.

p=Path('ea_signal_bridge.go')
s=p.read_text(encoding='utf-8')
s=s.replace('''\tPartialTP bool    `json:"partial_tp"`\n\tReason    string  `json:"reason"`\n}''','''\tPartialTP bool    `json:"partial_tp"`\n\tReason    string  `json:"reason"`\n\tTimeframe string  `json:"timeframe"`\n}''',1)
s=s.replace('// manage.txt: MANAGE_ID|SYMBOL|BUY/SELL|SL|FINAL_TP|REASON|TP1|TP2|PARTIAL_TP','// manage.txt: MANAGE_ID|SYMBOL|BUY/SELL|SL|FINAL_TP|REASON|TP1|TP2|PARTIAL_TP|TIMEFRAME',1)
s=s.replace('''q.ManageID=cleanEAToken(q.ManageID);q.Symbol=normalizeEABridgeSymbol(q.Symbol);q.Direction=eaDirection(q.Direction);q.Reason=cleanEAToken(q.Reason)''','''q.ManageID=cleanEAToken(q.ManageID);q.Symbol=normalizeEABridgeSymbol(q.Symbol);q.Direction=eaDirection(q.Direction);q.Reason=cleanEAToken(q.Reason);q.Timeframe=cleanEAToken(q.Timeframe)''',1)
s=s.replace('''\tif q.SL<=0||q.TP<=0{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"sl/tp must be positive"});return}\n''','''\tif q.SL<=0||q.TP<=0{w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"sl/tp must be positive"});return}\n\tif q.Timeframe==""||!eaSafeToken.MatchString(q.Timeframe){w.WriteHeader(http.StatusBadRequest);_=json.NewEncoder(w).Encode(map[string]any{"error":"timeframe is required for safe EA management"});return}\n''',1)
s=s.replace('''line:=strings.Join([]string{q.ManageID,q.Symbol,q.Direction,strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),q.Reason,strconv.FormatFloat(q.TP1,'f',-1,64),strconv.FormatFloat(q.TP2,'f',-1,64),strconv.FormatBool(q.PartialTP)},"|")+"\\r\\n"''','''line:=strings.Join([]string{q.ManageID,q.Symbol,q.Direction,strconv.FormatFloat(q.SL,'f',-1,64),strconv.FormatFloat(q.TP,'f',-1,64),q.Reason,strconv.FormatFloat(q.TP1,'f',-1,64),strconv.FormatFloat(q.TP2,'f',-1,64),strconv.FormatBool(q.PartialTP),q.Timeframe},"|")+"\\r\\n"''',1)
p.write_text(s,encoding='utf-8')

p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
old="""body:JSON.stringify({manage_id:`MHM${Date.now()}_${symbol}_${timeframe}`,symbol,direction:managed.direction,sl:Number(managed.sl),tp:partialTpEnabled?Number(managed.tp2):Number(managed.tp1),tp1:Number(managed.tp1),tp2:Number(managed.tp2),partial_tp:partialTpEnabled,reason:status||'RE-EVALUATE'})"""
new="""body:JSON.stringify({manage_id:`MHM${Date.now()}_${symbol}_${timeframe}`,symbol,timeframe,direction:managed.direction,sl:Number(managed.sl),tp:partialTpEnabled?Number(managed.tp2):Number(managed.tp1),tp1:Number(managed.tp1),tp2:Number(managed.tp2),partial_tp:partialTpEnabled,reason:status||'RE-EVALUATE'})"""
if old not in s: raise SystemExit('manage payload anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

Path('VERSION').write_text('V.55.22\n',encoding='utf-8')
for name in ['updater.go','license_auth.go','web/index.html']:
    q=Path(name);t=q.read_text(encoding='utf-8');t=t.replace('V.55.21','V.55.22');q.write_text(t,encoding='utf-8')
