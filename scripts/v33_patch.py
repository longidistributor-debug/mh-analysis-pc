from pathlib import Path
import re

# V33 scope: ONLY MT5 in-host embedding + WhatsApp New Analysis/Re-evaluate delivery.
# Preserve V32 behavior everywhere else.

# --- MT5: broaden detection to real broker terminals and require in-host reparent/show ---
p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8-sig')
# Ensure title/process helpers exist.
if 'chGetWindowTextV33' not in s:
    s=s.replace('chGetWindowTextV32     = chUser32.NewProc("GetWindowTextW")','chGetWindowTextV32     = chUser32.NewProc("GetWindowTextW")\n\tchGetWindowTextV33     = chUser32.NewProc("GetWindowTextW")',1)
helper=r'''
// V33: broker MT5 titles often do NOT contain the literal "MetaTrader 5".
// Identify top-level terminal windows by title/class and process image, then embed the real HWND.
func chFindInstalledMT5WindowV33() uintptr {
	var found uintptr
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		if hwnd == 0 || hwnd == hostHWND { return 1 }
		var pid uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
		clsBuf:=make([]uint16,256); nc,_,_:=chGetClassName.Call(hwnd,uintptr(unsafe.Pointer(&clsBuf[0])),uintptr(len(clsBuf)))
		cls:=""; if nc>0 { cls=strings.ToLower(syscall.UTF16ToString(clsBuf)) }
		tBuf:=make([]uint16,512); nt,_,_:=chGetWindowTextV33.Call(hwnd,uintptr(unsafe.Pointer(&tBuf[0])),uintptr(len(tBuf)))
		title:=""; if nt>0 { title=strings.ToLower(syscall.UTF16ToString(tBuf)) }
		// MT5 broker terminals consistently expose MetaQuotes/MetaTrader markers or terminal64 process windows.
		looks:=strings.Contains(cls,"metaquotes") || strings.Contains(title,"metatrader") || strings.Contains(title,"meta trader")
		if !looks && pid!=0 {
			// PID-based terminal window fallback: compare against the PID of any running terminal64.exe.
			out,_:=exec.Command("powershell","-NoProfile","-NonInteractive","-Command",fmt.Sprintf("$p=Get-Process -Id %d -ErrorAction SilentlyContinue; if($p){$p.ProcessName}",pid)).Output()
			pn:=strings.ToLower(strings.TrimSpace(string(out)))
			looks = pn=="terminal64" || pn=="terminal"
		}
		if looks { found=hwnd; return 0 }
		return 1
	})
	chEnumWindows.Call(cb,0)
	return found
}

func chEmbedMT5V33(hwnd uintptr) bool {
	if hwnd==0 || hostHWND==0 { return false }
	chShowWindow.Call(hwnd,chSWHide)
	chAttachBrowser(hwnd)
	// SetParent can fail silently on some broker builds; enforce child style/parent once more after attach.
	chSetParent.Call(hwnd,hostHWND)
	style,_,_:=chGetWindowLongPtr.Call(hwnd,^uintptr(15))
	style &^= chWSPopup|chWSCaption|chWSBorder|chWSDlgFrame|chWSThickFrame|chWSMinBox|chWSMaxBox|chWSSysMenu
	style |= chWSChild|chWSVisible
	chSetWindowLongPtr.Call(hwnd,^uintptr(15),style)
	chMu.Lock(); chMT5Wnd=hwnd; chMu.Unlock()
	chResizeChildren(); chShowWindow.Call(hwnd,chSWShow); chApplyDesiredBrowserView()
	return true
}
'''
if 'func chFindInstalledMT5WindowV33()' not in s:
    s=s.replace('\nfunc chFindExistingMT5WindowV32() uintptr {',helper+'\nfunc chFindExistingMT5WindowV32() uintptr {',1)
# V33 should get first chance before V32's narrower detector/spawn path.
anchor='func chEnsureMT5Terminal() error {'
if anchor not in s: raise SystemExit('MT5 ensure anchor missing')
if 'V33: first embed the already installed/running broker terminal' not in s:
    s=s.replace(anchor,anchor+'''\n\t// V33: first embed the already installed/running broker terminal. Never deliberately open it externally.\n\tif existing:=chFindInstalledMT5WindowV33(); existing!=0 {\n\t\tif chEmbedMT5V33(existing) { go mt5ApplyLatestQueued(); return nil }\n\t}''',1)
# After launching, use broad detector as fallback and embed through the hardened helper.
s=s.replace('if wnd == 0 { wnd = chFindExistingMT5WindowV32() }','if wnd == 0 { wnd = chFindInstalledMT5WindowV33() }\n\tif wnd == 0 { wnd = chFindExistingMT5WindowV32() }',1)
# Replace final generic attachment in MT5 launch section where possible.
needle='''\tchShowWindow.Call(wnd, chSWHide)\n\tchAttachBrowser(wnd)\n\tchMu.Lock()\n\tchMT5Wnd = wnd\n\tchMT5Cmd = cmd\n\tchMu.Unlock()'''
if needle in s:
    s=s.replace(needle,'''\tif !chEmbedMT5V33(wnd) { return errors.New("MT5 window could not be embedded inside MH Analysis") }\n\tchMu.Lock(); chMT5Cmd = cmd; chMu.Unlock()''',1)
p.write_text(s,encoding='utf-8')

# --- WhatsApp: queue must inject the exact organized message, then send ---
p=Path('main.go'); s=p.read_text(encoding='utf-8-sig')
# Replace URL-only queue processing with navigation + deterministic composer injection.
old='''\twvNavigate(whatsappCore, t.target)\n\ttime.AfterFunc(4*time.Second, func() { postMessage(hostHWND, wmWhatsAppClick, 0, 0) })'''
new='''\twvNavigate(whatsappCore, t.target)\n\t// V33: the group URL opens the chat, but it does not carry the organized signal text.\n\t// Wait for WhatsApp Web, inject the queued message into the composer, then click Send.\n\tmsgJSON,_:=json.Marshal(t.message)\n\ttime.AfterFunc(5*time.Second, func(){\n\t\tscript:=fmt.Sprintf(`(()=>{const msg=%s;const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(!box)return false;box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,msg);box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));return true;})()`,string(msgJSON))\n\t\twvExecute(whatsappCore,script)\n\t\ttime.AfterFunc(700*time.Millisecond,func(){ postMessage(hostHWND,wmWhatsAppClick,0,0) })\n\t})'''
if old not in s: raise SystemExit('WhatsApp queue anchor missing')
s=s.replace(old,new,1)
# Stop recursive send loop from consuming another queue item before the current send settles.
s=s.replace('''func clickWhatsAppSend() {\n\tscript := `(()=>{const b=document.querySelector('[data-icon=\\"send\\"]')?.closest('button')||document.querySelector('button[aria-label=\\"Send\\"]');if(b){b.click();return true;}const box=document.querySelector('[contenteditable=\\"true\\"][data-tab]');if(box){box.focus();box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));return true;}return false;})()`\n\twvExecute(whatsappCore, script)\n\ttime.AfterFunc(1200*time.Millisecond, func() { postMessage(hostHWND, wmWhatsAppSend, 0, 0) })\n}''','''func clickWhatsAppSend() {\n\t// V33: click the real send control after composer injection; Enter is only a fallback.\n\tscript := `(()=>{const b=document.querySelector('[data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]');if(b){b.click();return true;}const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(box){box.focus();box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));return true;}return false;})()`\n\twvExecute(whatsappCore, script)\n\ttime.AfterFunc(1200*time.Millisecond, func() { postMessage(hostHWND, wmWhatsAppSend, 0, 0) })\n}''',1)
p.write_text(s,encoding='utf-8')

# Version parity V33.
for fn,pat,repl in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.33"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.33"')]:
 p=Path(fn); x=p.read_text(encoding='utf-8-sig'); x=re.sub(pat,repl,x,count=1); p.write_text(x,encoding='utf-8')
for fn in ['web/index.html','web/records.html']:
 p=Path(fn); x=p.read_text(encoding='utf-8-sig'); x=re.sub(r'V\.\d+(?:\.\d+)? \(Late - CH Shaukat Ali\)','V.33 (Late - CH Shaukat Ali)',x); p.write_text(x,encoding='utf-8')
print('V33 MT5 embed + WhatsApp delivery patch applied')
