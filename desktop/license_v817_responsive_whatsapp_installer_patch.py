from pathlib import Path

MARK='MH_V817_RESPONSIVE_WHATSAPP'
VERSION_TEXT='v79.6 (CH Shaukat Ali)'

# --- Main + Records visible version labels -------------------------------------------------
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
old='<div class="version">v79.6 AUTO CYCLE (HAMMAD & SOMI)</div>'
new=f'<div class="version">{VERSION_TEXT}</div>'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('main version anchor missing')
p.write_text(s,encoding='utf-8')

p=Path('web/records.html')
s=p.read_text(encoding='utf-8')
old='<div class="recordsVersion">v79.8 • LOCAL MT5 TRADE LIFECYCLE</div>'
new=f'<div class="recordsVersion">{VERSION_TEXT}</div>'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('records version anchor missing')
p.write_text(s,encoding='utf-8')

# --- Reset Records button order: RESET first, CANCEL second --------------------------------
p=Path('web/records.js')
s=p.read_text(encoding='utf-8')
old='<div class="mhResetActionsV816"><button type="button" class="cancel">CANCEL</button><button type="button" class="confirm">RESET</button></div>'
new='<div class="mhResetActionsV816"><button type="button" class="confirm">RESET</button><button type="button" class="cancel">CANCEL</button></div>'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('reset button order anchor missing')
p.write_text(s,encoding='utf-8')

# --- Prevent duplicate outer scrollbar while inline Records owns the full Analysis surface --
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if 'mhRecordsPrevOverflowV817' not in s:
    old='''      overlay.style.display = 'block';\n      document.documentElement.dataset.mhNativeRecordsVisible = '1';\n    } else {\n      overlay.style.display = 'none';\n      document.documentElement.dataset.mhNativeRecordsVisible = '0';\n    }'''
    new='''      window.mhRecordsPrevOverflowV817 = {\n        html: document.documentElement.style.overflow || '',\n        body: document.body.style.overflow || ''\n      };\n      document.documentElement.style.overflow = 'hidden';\n      document.body.style.overflow = 'hidden';\n      overlay.style.display = 'block';\n      document.documentElement.dataset.mhNativeRecordsVisible = '1';\n    } else {\n      overlay.style.display = 'none';\n      const prev = window.mhRecordsPrevOverflowV817 || {html:'',body:''};\n      document.documentElement.style.overflow = prev.html;\n      document.body.style.overflow = prev.body;\n      document.documentElement.dataset.mhNativeRecordsVisible = '0';\n    }'''
    if old not in s:
        raise SystemExit('records inline visibility anchor missing')
    s=s.replace(old,new,1)
    s += '\n// '+MARK+'\n'
p.write_text(s,encoding='utf-8')

# --- Responsive/adaptive main UI -------------------------------------------------------------
p=Path('web/styles.css')
s=p.read_text(encoding='utf-8')
css=r'''

/* MH_V817_RESPONSIVE_WHATSAPP: compact windows reflow instead of overlap/crop */
html,body{max-width:100%;overflow-x:hidden}
.appShell{min-width:0;max-width:100%;overflow:visible}
.appHeader>*{min-width:0}.brandArea{min-width:0}.brandName,.version{max-width:100%}
.mainGrid>*{min-width:0}.centerCol,.chartPanel,.nativeChartShell{min-width:0}
@media(max-width:1050px){
  .appHeader{height:auto;min-height:96px;grid-template-columns:minmax(0,1fr) auto;padding:8px;gap:8px}
  .bismillahArea{grid-column:1/-1;grid-row:2;order:3}.bismillah{font-size:20px}.ornament{display:none}
  .brandArea{flex-wrap:wrap}.headerStatus{align-self:start}
  .marketToolbar{height:auto;min-height:0;grid-template-columns:1fr;align-items:stretch}
  .pairGroup{flex-wrap:wrap}.pair{flex:1 1 130px;min-width:120px}
  .capGrid{grid-template-columns:repeat(2,minmax(0,1fr));min-height:118px}.capTitle{grid-column:1/-1;height:auto;border-bottom:1px solid #16463b}.capItem{min-height:52px}
  .tfGroup{grid-column:auto;grid-template-columns:1fr auto;justify-content:stretch}.tfGroup select{width:100%}
  .mapStrip{height:auto;min-height:0;grid-template-columns:repeat(2,minmax(0,1fr));gap:0}.mapTitle{grid-column:1/-1;padding:8px}.mapMetric,.scoreBox{border-top:1px solid #174238}
  .cleanTickerTrack{grid-template-columns:repeat(3,minmax(0,1fr))}
  .mainGrid{grid-template-columns:1fr;min-height:0}.leftCol,.centerCol,.rightCol{grid-column:1!important;min-width:0}.rightCol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.calendarPanel,.recentPanel{min-width:0}
  .chartPanel{min-height:680px}.nativeChartShell{min-height:620px}.priceCanvasWrap{min-height:450px}
}
@media(max-width:700px){
  .appHeader{grid-template-columns:1fr}.headerStatus{justify-content:flex-start}.bismillahArea{grid-column:1;grid-row:auto}
  .brandArea{gap:6px}.logo{width:34px;height:34px}.brandName{font-size:13px}.version{font-size:8px}.supportLink{display:none!important}
  .capGrid{grid-template-columns:1fr}.capTitle{grid-column:1}.mapStrip{grid-template-columns:1fr}.mapTitle{grid-column:1}
  .cleanTickerTrack{grid-template-columns:repeat(2,minmax(0,1fr))}.rightCol{grid-template-columns:1fr}.actionRow{grid-template-columns:1fr}.chartPanel{min-height:620px}.nativeChartToolbar{flex-wrap:wrap;height:auto;min-height:48px;padding:6px}.nativeTfButtons{flex-wrap:wrap}.nativeChartToolbar>span:last-child{margin-left:0;width:100%}
}
'''
if MARK not in s:
    s += css
p.write_text(s,encoding='utf-8')

# --- Responsive Records UI ------------------------------------------------------------------
p=Path('web/records.css')
s=p.read_text(encoding='utf-8')
rcss=r'''

/* MH_V817_RESPONSIVE_WHATSAPP: Records has one scrollbar and adaptive compact layout */
html,body{max-width:100%;overflow-x:hidden}.recordsShell{min-width:0;max-width:100%;overflow:visible}
.recordsHeader>*{min-width:0}.recordsGrid>*{min-width:0}
@media(max-width:1050px){
  .recordsHeader{grid-template-columns:1fr auto;min-height:92px;height:auto;padding:8px}.recordsBismillah{grid-column:1/-1;grid-row:2}.recordsBismillah .arabic{font-size:20px}
  .statsGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.recordsGrid{grid-template-columns:1fr}.calendarGrid{grid-template-columns:repeat(7,minmax(0,1fr))}.filterPanel{align-items:flex-start;flex-direction:column}.rangeInfo{text-align:left}.recordsActions{align-items:flex-end}
  .tradeTableWrap{max-width:100%;overflow:auto}
}
@media(max-width:700px){
  .recordsHeader{grid-template-columns:1fr}.recordsBismillah{display:none}.recordsActions{align-items:flex-start}.checkState{text-align:left}
  .filterGroup{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}.filterGroup label,.filterGroup button{width:100%}.statsGrid{grid-template-columns:1fr 1fr}.dayStats{grid-template-columns:repeat(2,minmax(0,1fr))}.timeframeBreakdown{grid-template-columns:repeat(2,minmax(0,1fr))}.calendarCell{height:58px;padding:4px}.calendarCell .outcomes{display:none}
}
'''
if MARK not in s:
    s += rcss
p.write_text(s,encoding='utf-8')

# --- Native toolbar responsive sizing + WhatsApp persistent-profile wake/reload -------------
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Add native toolbar layout helper before chResizeChildren and call it after legacy positions.
    helper=r'''

// MH_V817_RESPONSIVE_WHATSAPP: resize the native toolbar itself so narrow EXE
// windows do not crop/overlap MH Analysis / WhatsApp / Records / MT5 / Signal Link.
func chResizeToolbarV817(w int32) {
	chViewMu.Lock(); which := chDesiredView; chViewMu.Unlock()
	count := int32(4)
	if which == 2 { count = 5 }
	gap := int32(8); margin := int32(8)
	bw := (w - margin*2 - gap*(count-1)) / count
	if bw > 145 { bw = 145 }
	if bw < 72 { bw = 72 }
	x := margin
	for _, h := range []uintptr{btnAnalysis, btnWhatsapp, btnRecords, btnMT5} {
		if h != 0 { chMoveWindow.Call(h, uintptr(x), 7, uintptr(bw), 30, 1) }
		x += bw + gap
	}
	if chSignalLinkBtn != 0 {
		chMoveWindow.Call(chSignalLinkBtn, uintptr(x), 7, uintptr(bw), 30, 1)
	}
}

// Persistent WhatsAppProfile is never cleared. On tab selection, this only wakes
// a stale/blank renderer using its existing profile/session; it does not log out.
func chEnsureWhatsAppSurfaceV817() {
	for _, wait := range []time.Duration{150*time.Millisecond, 700*time.Millisecond, 1500*time.Millisecond} {
		time.Sleep(wait)
		chMu.Lock(); stopping := chStopping; wnd := chWhatsappWnd; chMu.Unlock()
		if stopping || wnd == 0 { return }
		chResizeChildren()
		chShowWindowAsync.Call(wnd, chSWShow)
		chCDPMu.Lock()
		wsURL, err := chCDPPageSocket()
		if err != nil { chCDPMu.Unlock(); continue }
		conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
		if err != nil { chCDPMu.Unlock(); continue }
		_, _ = chCDPCommand(conn, 1, "Page.enable", map[string]any{})
		msg, err := chCDPCommand(conn, 2, "Runtime.evaluate", map[string]any{"expression": `(() => JSON.stringify({u:location.href,s:document.readyState,n:((document.body&&document.body.innerText)||'').length}))()`, "returnByValue": true})
		state := chEvalValue(msg)
		if err == nil && (state == "" || !strings.Contains(state, "web.whatsapp.com")) {
			_, _ = chCDPCommand(conn, 3, "Page.navigate", map[string]any{"url":"https://web.whatsapp.com/"})
		} else if err == nil && strings.Contains(state, `"s":"complete"`) && (strings.Contains(state, `"n":0`) || strings.Contains(state, `"n":1`) || strings.Contains(state, `"n":2`)) {
			_, _ = chCDPCommand(conn, 3, "Page.reload", map[string]any{"ignoreCache":false})
		}
		_ = conn.Close(); chCDPMu.Unlock()
		if err == nil { return }
	}
}
'''
    anchor='\nfunc chResizeChildren() {'
    if anchor not in s: raise SystemExit('resize helper anchor missing')
    s=s.replace(anchor,helper+anchor,1)

    # Insert toolbar adaptive override before function exits. Use the last fixed Signal Link move block.
    anchor='''\tif chSignalLinkBtn != 0 {\n\t\tchMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)\n\t}\n}'''
    repl='''\tif chSignalLinkBtn != 0 {\n\t\tchMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)\n\t}\n\tchResizeToolbarV817(w) // '''+MARK+'''\n}'''
    if anchor in s:
        s=s.replace(anchor,repl,1)
    elif 'chResizeToolbarV817(w)' not in s:
        raise SystemExit('toolbar resize call anchor missing')

    # V81.5 final chSwitchView is synchronous. Wake WhatsApp only after normal view switch.
    start=s.find('func chSwitchView(which int) {')
    end=s.find('\nfunc chPopWhatsAppTask',start)
    if start<0 or end<0: raise SystemExit('chSwitchView anchor missing')
    chunk=s[start:end]
    old='\tchApplyDesiredBrowserView()\n'
    new='\tchApplyDesiredBrowserView()\n\tchResizeChildren() // '+MARK+' responsive settle\n\tif which == 2 { go chEnsureWhatsAppSurfaceV817() }\n'
    if old in chunk and 'chEnsureWhatsAppSurfaceV817' not in chunk:
        chunk=chunk.replace(old,new,1)
        s=s[:start]+chunk+s[end:]
    elif 'chEnsureWhatsAppSurfaceV817' not in chunk:
        raise SystemExit('WhatsApp switch anchor missing')

    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
    p.write_text(s,encoding='utf-8')

print(MARK+': responsive native/web views, persistent WhatsApp wake, reset order, version labels, single Records scrollbar')
