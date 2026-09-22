from pathlib import Path
import re


def rd(p): return Path(p).read_text(encoding='utf-8-sig')
def wr(p,s): Path(p).write_text(s,encoding='utf-8',newline='\n')
def need(cond,msg):
    if not cond: raise SystemExit(msg)

# ---------------------------------------------------------------------------
# Version stamps
# ---------------------------------------------------------------------------
for p,pat,repl in [
    ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.30"'),
    ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.30"'),
]:
    s=rd(p); s,n=re.subn(pat,repl,s,count=1); need(n==1,f'V30 version anchor missing: {p}'); wr(p,s)
Path('VERSION').write_text('V.30\n',encoding='ascii')

# ---------------------------------------------------------------------------
# Main + Records branding, exact Unicode cleanup, credits
# ---------------------------------------------------------------------------
p='web/index.html'; s=rd(p)
s=re.sub(r'<div class="version">.*?</div>', '<div class="version">V.30 AUTO CYCLE (HAMMAD &amp; SOMI)<span class="mhMemorial">Late - CH Shaukat Ali</span></div>', s, count=1)
s=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">.*?</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.30</div>', s, count=1)
s=re.sub(r'<div class="bismillah">.*?</div>', '<div class="bismillah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>', s, count=1)
# Fix all known inherited mojibake in visible HTML. Keep wording/layout intact.
repls={
 'â—†':'◆','â”€':'─','â€¢':'•','â‚¿':'₿','â—Ž':'◎','â€”':'—','Â©':'©','Â¥':'¥','Â£':'£',
 'â—':'●','â†»':'↻','â—´':'◴','â€¦':'…','â†‘':'↑','â†“':'↓','â†’':'→','â†':'←',
 'ðŸ”¥':'🔥','ðŸŽ¯':'🎯','ðŸ“Š':'📊','ðŸ“ˆ':'📈','ðŸ“‰':'📉','ðŸ’¡':'💡','ðŸ•’':'🕒',
 'ðŸ”„':'🔄','ðŸš¨':'🚨','ðŸ§­':'🧭','ðŸ“Œ':'📌','ðŸ”':'🔝','ðŸ•˜':'🕘'
}
for a,b in repls.items(): s=s.replace(a,b)
s=re.sub(r'<footer class="mhMainCopyright">.*?</footer>', '<footer class="mhMainCopyright">MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved. <span>V.30</span> <span>Late - CH Shaukat Ali</span></footer>', s, count=1)
# V30 layout CSS loaded last.
if '/v30.css' not in s: s=s.replace('</head>','<link rel="stylesheet" href="/v30.css" />\n</head>',1)
wr(p,s)

p='web/records.html'; s=rd(p)
s=re.sub(r'<div class="recordsVersion">.*?</div>', '<div class="recordsVersion">V.30 • LOCAL MT5 TRADE LIFECYCLE <span class="recordsMemorial">Late - CH Shaukat Ali</span></div>', s, count=1)
s=re.sub(r'<footer class="recordsFooter">.*?</footer>', '<footer class="recordsFooter"><span>MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved. • V.30 • Late - CH Shaukat Ali</span><span id="lastRefresh">Local records ready.</span></footer>', s, count=1, flags=re.S)
if '/v30.css' not in s: s=s.replace('</head>','<link rel="stylesheet" href="/v30.css" />\n</head>',1)
for a,b in repls.items(): s=s.replace(a,b)
wr(p,s)

p='web/auth.js'; s=rd(p)
anchor='<div>Admin Layout Credit: Ruhi Mughal</div>'
need(anchor in s,'V30 Ruhi credit anchor missing')
if 'Icons Assistant: Sinha Creates' not in s:
    s=s.replace(anchor,'<div>Icons Assistant: Sinha Creates</div>'+anchor,1)
wr(p,s)

# ---------------------------------------------------------------------------
# Semantic duplicate guard: server + frontend; exact same ACTIVE signal is not new
# ---------------------------------------------------------------------------
p='records_mt5_local.go'; s=rd(p)
if 'MH_SAME_SIGNAL_GUARD_V30' not in s:
    anchor='func recordNumberOK(v float64) bool {\n\treturn !math.IsNaN(v) && !math.IsInf(v, 0) && v > 0\n}\n'
    need(anchor in s,'V30 records helper anchor missing')
    helper=r'''

// MH_SAME_SIGNAL_GUARD_V30
func sameSignalDisplayPriceV30(a, b float64) bool {
	if !recordNumberOK(a) || !recordNumberOK(b) { return false }
	scale := 100000.0
	if math.Max(math.Abs(a), math.Abs(b)) >= 100 { scale = 100.0 }
	return math.Round(a*scale) == math.Round(b*scale)
}
func sameSignalPointV30(x mt5LocalRecord, q mt5LocalCapture) bool {
	return strings.EqualFold(strings.TrimSpace(x.Symbol),strings.TrimSpace(q.Symbol)) &&
		strings.EqualFold(strings.TrimSpace(x.Timeframe),strings.TrimSpace(q.Timeframe)) &&
		strings.EqualFold(strings.TrimSpace(x.Direction),strings.TrimSpace(q.Direction)) &&
		sameSignalDisplayPriceV30(x.Entry,q.Entry) && sameSignalDisplayPriceV30(x.SL,q.SL) &&
		sameSignalDisplayPriceV30(x.TP1,q.TP1) && sameSignalDisplayPriceV30(x.TP2,q.TP2)
}
func activeRecordV30(x mt5LocalRecord) bool {
	if recordTerminalMT5(x) { return false }
	st:=strings.ToUpper(strings.TrimSpace(x.Status))
	if strings.Contains(st,"CANCEL") || strings.Contains(st,"EXPIRED") || strings.Contains(st,"REJECT") || strings.Contains(st,"CLOSED") || strings.Contains(st,"TP HIT") || strings.Contains(st,"SL HIT") || strings.Contains(st,"BREAK EVEN") { return false }
	return true
}
func findSameActiveV30(s mt5LocalStore,q mt5LocalCapture) int {
	for i:=len(s.Records)-1;i>=0;i-- { if activeRecordV30(s.Records[i]) && sameSignalPointV30(s.Records[i],q) { return i } }
	return -1
}
func mt5DuplicateSignalHandlerV30(w http.ResponseWriter,r *http.Request){
	w.Header().Set("Content-Type","application/json")
	if r.Method!=http.MethodPost { http.Error(w,"method",http.StatusMethodNotAllowed); return }
	var q mt5LocalCapture
	if json.NewDecoder(r.Body).Decode(&q)!=nil { http.Error(w,"bad json",http.StatusBadRequest); return }
	q.Symbol=strings.ToUpper(strings.TrimSpace(q.Symbol)); q.Timeframe=strings.TrimSpace(q.Timeframe); q.Direction=strings.ToUpper(strings.TrimSpace(q.Direction))
	mt5RecordsMu.Lock(); s:=loadMT5LocalStore(); _,_,_=syncMT5Lifecycle(&s); i:=findSameActiveV30(s,q); _=saveMT5LocalStore(s); mt5RecordsMu.Unlock()
	if i>=0 { x:=s.Records[i]; _=json.NewEncoder(w).Encode(map[string]any{"ok":true,"duplicate":true,"same_signal":true,"existing_signal_id":x.SignalID,"existing_status":x.Status}); return }
	_=json.NewEncoder(w).Encode(map[string]any{"ok":true,"duplicate":false})
}
'''
    s=s.replace(anchor,anchor+helper,1)
    # semantic guard inside capture, after SignalID duplicate check
    old='''\tfor _, x := range s.Records {\n\t\tif x.SignalID == q.SignalID || x.ID == q.SignalID {\n\t\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": q.SignalID})\n\t\t\treturn\n\t\t}\n\t}\n\tnow := time.Now()\n'''
    new='''\tfor _, x := range s.Records {\n\t\tif x.SignalID == q.SignalID || x.ID == q.SignalID {\n\t\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "id": q.SignalID})\n\t\t\treturn\n\t\t}\n\t}\n\t_, _, _ = syncMT5Lifecycle(&s)\n\tif i := findSameActiveV30(s, q); i >= 0 {\n\t\tx := s.Records[i]\n\t\t_ = saveMT5LocalStore(s)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "saved": false, "duplicate": true, "same_signal": true, "existing_signal_id": x.SignalID, "existing_status": x.Status})\n\t\treturn\n\t}\n\tnow := time.Now()\n'''
    need(old in s,'V30 capture duplicate insertion anchor missing'); s=s.replace(old,new,1)
    route='\tmux.HandleFunc("/api/records-v2", mt5LocalRecordsHandler)\n'
    need(route in s,'V30 duplicate route anchor missing'); s=s.replace(route,route+'\tmux.HandleFunc("/api/records-v2/duplicate", mt5DuplicateSignalHandlerV30)\n',1)
wr(p,s)

p='web/app.js'; s=rd(p)
if 'MH_SAME_SIGNAL_GUARD_V30' not in s:
    anchor="async function captureSignalRecordV796(d,state='NEW'){"
    need(anchor in s,'V30 app duplicate anchor missing')
    js=r'''// MH_SAME_SIGNAL_GUARD_V30
async function checkSameSignalV30(d){
  const sig=d?.signal;if(!sig){d._sameActiveSignal=false;return null}
  try{
    const r=await fetch('/api/records-v2/duplicate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2})});
    const j=await r.json();d._sameActiveSignal=!!j.duplicate;d._sameSignalStatus=j.existing_status||'';return j;
  }catch(_){d._sameActiveSignal=false;return null}
}
function sameSignalMessageV30(d){
  const s=d?.signal;return s?`SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL. ${symbol} ${timeframe} ${s.direction} • Entry ${fmt(s.entry)} • SL ${fmt(s.sl)} • TP1 ${fmt(s.tp1)} • TP2 ${fmt(s.tp2)}.`:'NO NEW SIGNAL';
}
async function captureSignalRecordV30(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const id=`MH${Date.now()}${Math.floor(Math.random()*900+100)}`;
  const r=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:id,symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,score:sig.score,setup:d.bestFamily||sig.setupReason||'',action:'NEW'})});
  return r.json().catch(()=>null);
}

'''
    s=s.replace(anchor,js+anchor,1)
    # recent local list should not claim duplicate is a new signal
    s=s.replace("function addRecent(d,state='NEW'){\n  const sig=d.signal,","function addRecent(d,state='NEW'){\n  if(d?._sameActiveSignal){renderRecentSignals();return}\n  const sig=d.signal,",1)
    # Put duplicate check before active/side effects and alter reason.
    old="d._ranked=buildRankedForUi(c,d);const reason=refreshReason(prev,d);\n    if(d.signal){const obj={signal:d.signal,state:d.signal.reconfirmed?'RECONFIRMED':'PENDING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}"
    new="d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);\n    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}\n    if(d.signal){const obj={signal:d.signal,state:d.signal.reconfirmed?'RECONFIRMED':'PENDING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}"
    need(old in s,'V30 new-analysis duplicate anchor missing'); s=s.replace(old,new,1)
    # Side effects: only truly new unique signal gets record + MT5 + WhatsApp signal.
    old="renderDecision(d,reason,'NEW');\n    if(d.signal)void prepareMT5SignalV796(d,'NEW'); // MH_NATIVE_MT5_PREFILL_V796"
    new="renderDecision(d,reason,'NEW');\n    if(d.signal&&!d._sameActiveSignal){void captureSignalRecordV30(d);void prepareMT5SignalV796(d,'NEW');} // V30 unique signal fan-out"
    need(old in s,'V30 MT5 fanout anchor missing'); s=s.replace(old,new,1)
    # Auto duplicate: retain clock but no repeated outbound signal.
    old="async function autoSendAndSchedule(d,action,status=''){\n  if(!autoSignalEnabled)return;\n  const triggerAt=autoActionStartedAt||Date.now();"
    new="async function autoSendAndSchedule(d,action,status=''){\n  if(!autoSignalEnabled)return;\n  const triggerAt=autoActionStartedAt||Date.now();\n  if(d?._sameActiveSignal){setAutoStatus('Same signal still active • no new signal sent','warn');scheduleFixedAfterDecision(d,action,triggerAt);return;}"
    need(old in s,'V30 auto duplicate anchor missing'); s=s.replace(old,new,1)
    # manual WhatsApp duplicate suppression
    old="if(backendSettings.has_whatsapp){\n          setAutoStatus('Sending NEW ANALYZE to WhatsApp…','warn');"
    new="if(backendSettings.has_whatsapp&&!d._sameActiveSignal){\n          setAutoStatus('Sending NEW ANALYZE to WhatsApp…','warn');"
    need(old in s,'V30 manual WhatsApp anchor missing'); s=s.replace(old,new,1)
wr(p,s)

# Disable legacy DOM fan-out to avoid a second random record / MT5 queue.
p='web/v03.js'; s=rd(p)
start=s.find('// V.27 SIGNAL FAN-OUT FIX')
if start>=0:
    end=s.rfind('})();')
    need(end>start,'V30 v03 end anchor missing')
    s=s[:start]+"// V.30: signal side-effects are owned by app.js after semantic duplicate validation.\n"+s[end:]
wr(p,s)

# ---------------------------------------------------------------------------
# WhatsApp Signal Link: support full saved group/chat URL + message composer
# ---------------------------------------------------------------------------
p='main.go'; s=rd(p)
s=s.replace('type waTask struct{ target string }','type waTask struct{ target string; message string }')
old=r'''\tv := getSettings()
\tnum := digits(v.WhatsAppLink)
\tif num == "" {
\t\tw.WriteHeader(400)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": "WhatsApp Signal Link is not saved."})
\t\treturn
\t}
\ttarget := "https://web.whatsapp.com/send?phone=" + num + "&text=" + url.QueryEscape(q.Message)
\twaMu.Lock()
\twaQueue = append(waQueue, waTask{target: target})
'''
# source contains tabs/newlines; use literal normal string version
old='''\tv := getSettings()\n\tnum := digits(v.WhatsAppLink)\n\tif num == "" {\n\t\tw.WriteHeader(400)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": "WhatsApp Signal Link is not saved."})\n\t\treturn\n\t}\n\ttarget := "https://web.whatsapp.com/send?phone=" + num + "&text=" + url.QueryEscape(q.Message)\n\twaMu.Lock()\n\twaQueue = append(waQueue, waTask{target: target})\n'''
new='''\tv := getSettings()\n\tsaved := strings.TrimSpace(v.WhatsAppLink)\n\tif saved == "" {\n\t\tw.WriteHeader(400)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": "WhatsApp Signal Link is not saved."})\n\t\treturn\n\t}\n\ttarget := ""\n\tif u, err := url.Parse(saved); err == nil && (u.Scheme == "https" || u.Scheme == "http") && (strings.EqualFold(u.Host,"chat.whatsapp.com") || strings.EqualFold(u.Host,"web.whatsapp.com") || strings.EqualFold(u.Host,"wa.me") || strings.HasSuffix(strings.ToLower(u.Host),".whatsapp.com")) {\n\t\ttarget = saved\n\t} else if num := digits(saved); num != "" {\n\t\ttarget = "https://web.whatsapp.com/send?phone=" + num\n\t}\n\tif target == "" {\n\t\tw.WriteHeader(400); _ = json.NewEncoder(w).Encode(map[string]any{"error":"Signal Link must be a WhatsApp group/chat link or phone number."}); return\n\t}\n\twaMu.Lock()\n\twaQueue = append(waQueue, waTask{target: target, message: q.Message})\n'''
need(old in s,'V30 WhatsApp handler anchor missing'); s=s.replace(old,new,1)
wr(p,s)

p='chrome_host.go'; s=rd(p)
s=s.replace('_ = chSendWhatsAppViaCDP(task.target)','_ = chSendWhatsAppViaCDP(task.target, task.message)')
s=s.replace('func chSendWhatsAppViaCDP(target string) error {','func chSendWhatsAppViaCDP(target, message string) error {')
# Replace send-button-only JS with composer + message injection preserving WhatsApp markdown.
old=r'''\tjs := `(() => {
\t\tconst body=(document.body && document.body.innerText)||'';
\t\tif(/scan.*qr|use whatsapp on your computer/i.test(body)) return 'login';
\t\tconst candidates=[...document.querySelectorAll('button')];
\t\tlet b=candidates.find(x => ((x.getAttribute('aria-label')||'').toLowerCase()==='send'));
\t\tif(!b){
\t\t\tconst icon=document.querySelector('span[data-icon="send"], span[data-testid="send"]');
\t\t\tif(icon) b=icon.closest('button') || icon.parentElement;
\t\t}
\t\tif(b && !b.disabled){ b.click(); return 'sent'; }
\t\treturn 'wait';
\t})()`
'''
old='''\tjs := `(() => {\n\t\tconst body=(document.body && document.body.innerText)||'';\n\t\tif(/scan.*qr|use whatsapp on your computer/i.test(body)) return 'login';\n\t\tconst candidates=[...document.querySelectorAll('button')];\n\t\tlet b=candidates.find(x => ((x.getAttribute('aria-label')||'').toLowerCase()==='send'));\n\t\tif(!b){\n\t\t\tconst icon=document.querySelector('span[data-icon="send"], span[data-testid="send"]');\n\t\t\tif(icon) b=icon.closest('button') || icon.parentElement;\n\t\t}\n\t\tif(b && !b.disabled){ b.click(); return 'sent'; }\n\t\treturn 'wait';\n\t})()`\n'''
new='''\tmsgJSON, _ := json.Marshal(message)\n\tjs := fmt.Sprintf(`(() => {\n\t\tconst body=(document.body && document.body.innerText)||'';\n\t\tif(/scan.*qr|use whatsapp on your computer/i.test(body)) return 'login';\n\t\tconst message=%s;\n\t\tlet box=[...document.querySelectorAll('[contenteditable="true"]')].find(x => ((x.getAttribute('data-tab')||'')==='10') || ((x.getAttribute('aria-placeholder')||x.getAttribute('aria-label')||'').toLowerCase().includes('message')) || x.getAttribute('role')==='textbox');\n\t\tif(box && message && box.dataset.mhV30Message!==message){\n\t\t\tbox.focus(); const sel=window.getSelection(); const range=document.createRange(); range.selectNodeContents(box); sel.removeAllRanges(); sel.addRange(range); document.execCommand('delete',false,null);\n\t\t\tdocument.execCommand('insertText',false,message); box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message})); box.dataset.mhV30Message=message;\n\t\t}\n\t\tconst candidates=[...document.querySelectorAll('button')];\n\t\tlet b=candidates.find(x => ((x.getAttribute('aria-label')||'').toLowerCase()==='send'));\n\t\tif(!b){const icon=document.querySelector('span[data-icon="send"], span[data-testid="send"]');if(icon)b=icon.closest('button')||icon.parentElement;}\n\t\tif(box && b && !b.disabled){b.click();return 'sent';}\n\t\treturn 'wait';\n\t})()`, string(msgJSON))\n'''
need(old in s,'V30 WhatsApp CDP JS anchor missing'); s=s.replace(old,new,1)
wr(p,s)

# ---------------------------------------------------------------------------
# MT5: keep MH view visible until terminal is embedded; auto-apply and auto-submit
# ---------------------------------------------------------------------------
p='webview2_host.go'; s=rd(p)
old='''func wv2ShowMT5() {\n\twv2SetDesiredView(4)\n\t_ = wv2Browser.Hide()\n\tchShowWindow.Call(wv2Container, chSWHide)\n\tif chWhatsappWnd != 0 {\n\t\tchShowWindowAsync.Call(chWhatsappWnd, chSWHide)\n\t}\n\tif chRecordsWnd != 0 {\n\t\tchShowWindowAsync.Call(chRecordsWnd, chSWHide)\n\t}\n\tgo func() {\n\t\tif err := chEnsureMT5Terminal(); err != nil {\n\t\t\tmessageBox(hostHWND, err.Error(), "MT5 System", 0x10)\n\t\t}\n\t}()\n}\n'''
new='''func wv2ShowMT5() {\n\twv2SetDesiredView(4)\n\twv2HideAuxViews()\n\t// V30: do not blank MH Analysis while MT5 is still starting.\n\tgo func() {\n\t\tif err := chEnsureMT5Terminal(); err != nil {\n\t\t\twv2SetDesiredView(1); messageBox(hostHWND, err.Error(), "MT5 System", 0x10); return\n\t\t}\n\t\t_ = wv2Browser.Hide(); chShowWindow.Call(wv2Container, chSWHide)\n\t\tchShowWindowAsync.Call(chMT5Wnd, chSWShow); chResizeChildren(); chFocusEmbeddedBrowser(chMT5Wnd)\n\t}()\n}\n'''
need(old in s,'V30 MT5 show anchor missing'); s=s.replace(old,new,1)
wr(p,s)

p='mt5_prefill.go'; s=rd(p)
s=s.replace('// This bridge only prepares the native MT5 pending-order ticket. It deliberately\n// stops before the final Place/Submit action so the user reviews the order in MT5.','// V30 queues and submits a validated native MT5 pending order automatically after exact symbol, pending type, Entry, SL and TP checks.')
s=s.replace('q.Status = "QUEUED FOR MT5 REVIEW"','q.Status = "QUEUED FOR MT5 AUTO PENDING"')
# Always make sure terminal exists, not only if tab is visible.
old='''\tif mt5ReadyAndVisible() {\n\t\tgo mt5ApplyLatestQueued()\n\t}\n'''
new='''\tgo func(){\n\t\tif !mt5ReadyAndVisible() { _ = chEnsureMT5Terminal() }\n\t\tmt5ApplyLatestQueued()\n\t}()\n'''
need(old in s,'V30 MT5 prepare launch anchor missing'); s=s.replace(old,new,1)
# ready should mean terminal ready, regardless of selected tab
s=re.sub(r'func mt5ReadyAndVisible\(\) bool \{.*?\n\}', '''func mt5ReadyAndVisible() bool {\n\tchMu.Lock(); wnd:=chMT5Wnd; cmd:=chMT5Cmd; chMu.Unlock()\n\treturn wnd != 0 && cmd != nil && cmd.Process != nil\n}''', s, count=1, flags=re.S)
# PowerShell output supports submitted state and auto clicks exact Place button.
s=s.replace("[pscustomobject]@{ok=$ok;status=$status;detail=$detail;submitted=$false} | ConvertTo-Json -Compress","[pscustomobject]@{ok=$ok;status=$status;detail=$detail;submitted=($status -eq 'PENDING ORDER SUBMITTED')} | ConvertTo-Json -Compress")
old='''Out-Result $true 'READY FOR USER CONFIRMATION' (\"$($p.pending_type) • Entry $($p.entry) • SL $($p.sl) • TP1 $($p.tp1)\")'''
new='''$place=$null\n$buttons=All $dialog ([System.Windows.Automation.ControlType]::Button)\nfor($i=0;$i -lt $buttons.Count;$i++){if((N $buttons.Item($i)) -match '(?i)^\\s*Place\\s*$'){ $place=$buttons.Item($i); break }}\nif($null -eq $place){Out-Result $false 'PLACE BUTTON NOT FOUND' 'Validated ticket is filled but MT5 Place button was not found';exit 0}\ntry{if(-not $place.Current.IsEnabled){Out-Result $false 'PLACE BUTTON DISABLED' 'MT5 rejected the current pending-order parameters';exit 0}}catch{}\ntry{$inv=$place.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern);$inv.Invoke()}catch{Out-Result $false 'PLACE FAILED' $_.Exception.Message;exit 0}\nStart-Sleep -Milliseconds 350\nOut-Result $true 'PENDING ORDER SUBMITTED' (\"$($p.pending_type) • Entry $($p.entry) • SL $($p.sl) • TP1 $($p.tp1)\")'''
need(old in s,'V30 MT5 Place anchor missing'); s=s.replace(old,new,1)
s=s.replace('res.Status = "READY FOR USER CONFIRMATION"','res.Status = "PENDING ORDER SUBMITTED"')
wr(p,s)

print('V30 complete fixes applied')
