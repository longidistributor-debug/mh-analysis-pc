from pathlib import Path

MARK='MH_V817_RESPONSIVE_WHATSAPP'
VER='v79.6 (CH Shaukat Ali)'

def repl_once(s, old, new, label):
    if new in s: return s
    if old not in s: raise SystemExit(label+' anchor missing')
    return s.replace(old,new,1)

# Visible version label on both MH Analysis and Records.
p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=repl_once(s,'<div class="version">v79.6 AUTO CYCLE (HAMMAD & SOMI)</div>',f'<div class="version">{VER}</div>','main version')
p.write_text(s,encoding='utf-8')
p=Path('web/records.html'); s=p.read_text(encoding='utf-8')
s=repl_once(s,'<div class="recordsVersion">v79.8 • LOCAL MT5 TRADE LIFECYCLE</div>',f'<div class="recordsVersion">{VER}</div>','records version')
p.write_text(s,encoding='utf-8')

# RESET first, CANCEL second.
p=Path('web/records.js'); s=p.read_text(encoding='utf-8')
s=repl_once(s,'<div class="mhResetActionsV816"><button type="button" class="cancel">CANCEL</button><button type="button" class="confirm">RESET</button></div>','<div class="mhResetActionsV816"><button type="button" class="confirm">RESET</button><button type="button" class="cancel">CANCEL</button></div>','reset order')
p.write_text(s,encoding='utf-8')

# Inline Records owns the viewport while open: disable parent scrolling so only the Records iframe scrolls.
p=Path('web/app.js'); s=p.read_text(encoding='utf-8')
if 'mhRecordsPrevOverflowV817' not in s:
    old="""      overlay.style.display = 'block';
      document.documentElement.dataset.mhNativeRecordsVisible = '1';
    } else {
      overlay.style.display = 'none';
      document.documentElement.dataset.mhNativeRecordsVisible = '0';
    }"""
    new="""      window.mhRecordsPrevOverflowV817 = {html:document.documentElement.style.overflow||'',body:document.body.style.overflow||''};
      document.documentElement.style.overflow = 'hidden';
      document.body.style.overflow = 'hidden';
      overlay.style.display = 'block';
      document.documentElement.dataset.mhNativeRecordsVisible = '1';
    } else {
      overlay.style.display = 'none';
      const prev=window.mhRecordsPrevOverflowV817||{html:'',body:''};
      document.documentElement.style.overflow=prev.html;
      document.body.style.overflow=prev.body;
      document.documentElement.dataset.mhNativeRecordsVisible = '0';
    }"""
    if old not in s: raise SystemExit('records overflow anchor missing')
    s=s.replace(old,new,1)+'\n// '+MARK+'\n'
p.write_text(s,encoding='utf-8')

# Responsive main UI.
p=Path('web/styles.css'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += r'''

/* MH_V817_RESPONSIVE_WHATSAPP */
html,body{max-width:100%;overflow-x:hidden}.appShell{min-width:0;max-width:100%;overflow:visible}.appHeader>*{min-width:0}.brandArea{min-width:0}.mainGrid>*{min-width:0}.centerCol,.chartPanel,.nativeChartShell{min-width:0}
@media(max-width:1050px){
.appHeader{height:auto;min-height:96px;grid-template-columns:minmax(0,1fr) auto;padding:8px;gap:8px}.bismillahArea{grid-column:1/-1;grid-row:2}.bismillah{font-size:20px}.ornament{display:none}.brandArea{flex-wrap:wrap}.headerStatus{align-self:start}
.marketToolbar{height:auto;min-height:0;grid-template-columns:1fr;align-items:stretch}.pairGroup{flex-wrap:wrap}.pair{flex:1 1 130px;min-width:120px}.capGrid{grid-template-columns:repeat(2,minmax(0,1fr));min-height:118px}.capTitle{grid-column:1/-1;height:auto;border-bottom:1px solid #16463b}.capItem{min-height:52px}.tfGroup{grid-column:auto;grid-template-columns:1fr auto}.tfGroup select{width:100%}
.mapStrip{height:auto;min-height:0;grid-template-columns:repeat(2,minmax(0,1fr))}.mapTitle{grid-column:1/-1;padding:8px}.mapMetric,.scoreBox{border-top:1px solid #174238}.cleanTickerTrack{grid-template-columns:repeat(3,minmax(0,1fr))}
.mainGrid{grid-template-columns:1fr;min-height:0}.leftCol,.centerCol,.rightCol{grid-column:1!important;min-width:0}.rightCol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.chartPanel{min-height:680px}.nativeChartShell{min-height:620px}.priceCanvasWrap{min-height:450px}}
@media(max-width:700px){
.appHeader{grid-template-columns:1fr}.headerStatus{justify-content:flex-start}.bismillahArea{grid-column:1;grid-row:auto}.brandArea{gap:6px}.logo{width:34px;height:34px}.brandName{font-size:13px}.version{font-size:8px}.supportLink{display:none!important}
.capGrid{grid-template-columns:1fr}.capTitle{grid-column:1}.mapStrip{grid-template-columns:1fr}.mapTitle{grid-column:1}.cleanTickerTrack{grid-template-columns:repeat(2,minmax(0,1fr))}.rightCol{grid-template-columns:1fr}.actionRow{grid-template-columns:1fr}.chartPanel{min-height:620px}.nativeChartToolbar{flex-wrap:wrap;height:auto;min-height:48px;padding:6px}.nativeTfButtons{flex-wrap:wrap}.nativeChartToolbar>span:last-child{margin-left:0;width:100%}}
'''
p.write_text(s,encoding='utf-8')

# Responsive Records UI.
p=Path('web/records.css'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += r'''

/* MH_V817_RESPONSIVE_WHATSAPP */
html,body{max-width:100%;overflow-x:hidden}.recordsShell{min-width:0;max-width:100%;overflow:visible}.recordsHeader>*{min-width:0}.recordsGrid>*{min-width:0}
@media(max-width:1050px){.recordsHeader{grid-template-columns:1fr auto;min-height:92px;height:auto;padding:8px}.recordsBismillah{grid-column:1/-1;grid-row:2}.recordsBismillah .arabic{font-size:20px}.statsGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.recordsGrid{grid-template-columns:1fr}.calendarGrid{grid-template-columns:repeat(7,minmax(0,1fr))}.filterPanel{align-items:flex-start;flex-direction:column}.rangeInfo{text-align:left}.recordsActions{align-items:flex-end}.tradeTableWrap{max-width:100%;overflow:auto}}
@media(max-width:700px){.recordsHeader{grid-template-columns:1fr}.recordsBismillah{display:none}.recordsActions{align-items:flex-start}.checkState{text-align:left}.filterGroup{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}.filterGroup label,.filterGroup button{width:100%}.statsGrid{grid-template-columns:1fr 1fr}.dayStats{grid-template-columns:repeat(2,minmax(0,1fr))}.timeframeBreakdown{grid-template-columns:repeat(2,minmax(0,1fr))}.calendarCell{height:58px;padding:4px}.calendarCell .outcomes{display:none}}
'''
p.write_text(s,encoding='utf-8')

# Native toolbar adapts to narrow host width; WhatsApp persistent profile is woken/reloaded if blank.
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
if MARK not in s:
    helper=r'''

// MH_V817_RESPONSIVE_WHATSAPP
func chResizeToolbarV817(w int32) {
	chViewMu.Lock(); which:=chDesiredView; chViewMu.Unlock()
	count:=int32(4); if which==2 { count=5 }
	gap:=int32(8); margin:=int32(8); bw:=(w-margin*2-gap*(count-1))/count
	if bw>145 { bw=145 }; if bw<72 { bw=72 }
	x:=margin
	for _,h:=range []uintptr{btnAnalysis,btnWhatsapp,btnRecords,btnMT5}{ if h!=0 { chMoveWindow.Call(h,uintptr(x),7,uintptr(bw),30,1) }; x+=bw+gap }
	if chSignalLinkBtn!=0 { chMoveWindow.Call(chSignalLinkBtn,uintptr(x),7,uintptr(bw),30,1) }
}

func chEnsureWhatsAppSurfaceV817(){
	for _,wait:=range []time.Duration{150*time.Millisecond,700*time.Millisecond,1500*time.Millisecond}{
		time.Sleep(wait); chMu.Lock(); stopping:=chStopping; wnd:=chWhatsappWnd; chMu.Unlock(); if stopping||wnd==0{return}
		chResizeChildren(); chShowWindowAsync.Call(wnd,chSWShow)
		chCDPMu.Lock(); wsURL,err:=chCDPPageSocket(); if err!=nil{chCDPMu.Unlock();continue}
		conn,_,err:=websocket.DefaultDialer.Dial(wsURL,nil); if err!=nil{chCDPMu.Unlock();continue}
		_,_=chCDPCommand(conn,1,"Page.enable",map[string]any{})
		msg,e:=chCDPCommand(conn,2,"Runtime.evaluate",map[string]any{"expression":`(() => JSON.stringify({u:location.href,s:document.readyState,n:((document.body&&document.body.innerText)||'').length}))()`,"returnByValue":true})
		state:=chEvalValue(msg)
		if e==nil && (state==""||!strings.Contains(state,"web.whatsapp.com")){_,_=chCDPCommand(conn,3,"Page.navigate",map[string]any{"url":"https://web.whatsapp.com/"})} else if e==nil && strings.Contains(state,`"s":"complete"`) && (strings.Contains(state,`"n":0`)||strings.Contains(state,`"n":1`)||strings.Contains(state,`"n":2`)){_,_=chCDPCommand(conn,3,"Page.reload",map[string]any{"ignoreCache":false})}
		_=conn.Close(); chCDPMu.Unlock(); if e==nil{return}
	}
}
'''
    anchor='\nfunc chResizeChildren() {'
    if anchor not in s: raise SystemExit('resize function anchor missing')
    s=s.replace(anchor,helper+anchor,1)
    start=s.find('func chResizeChildren() {'); end=s.find('\nfunc ',start+1)
    if start<0 or end<0: raise SystemExit('resize function bounds missing')
    chunk=s[start:end]
    if 'chResizeToolbarV817(w)' not in chunk:
        close=chunk.rfind('\n}')
        if close<0: raise SystemExit('resize close missing')
        chunk=chunk[:close]+'\n\tchResizeToolbarV817(w) // '+MARK+chunk[close:]
        s=s[:start]+chunk+s[end:]
    start=s.find('func chSwitchView(which int) {'); end=s.find('\nfunc chPopWhatsAppTask',start)
    if start<0 or end<0: raise SystemExit('switch function bounds missing')
    chunk=s[start:end]
    if 'go chEnsureWhatsAppSurfaceV817()' not in chunk:
        needle='\tchApplyDesiredBrowserView()\n'
        if needle not in chunk: raise SystemExit('switch apply anchor missing')
        chunk=chunk.replace(needle,needle+'\tchResizeChildren() // '+MARK+'\n\tif which == 2 { go chEnsureWhatsAppSurfaceV817() }\n',1)
        s=s[:start]+chunk+s[end:]
    s=s.replace('package main\n','package main\n\n// '+MARK+'\n',1)
p.write_text(s,encoding='utf-8')

print(MARK+': corrected responsive views + WhatsApp persistent session wake + Records polish')
