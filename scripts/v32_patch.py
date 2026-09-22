from pathlib import Path
import re

# V32 is applied AFTER V28-V31 retained patches.
# 1) Login overlay must be one centered column: card then credits, never side-by-side.
auth=Path('web/auth.css')
a=auth.read_text(encoding='utf-8-sig')
a += '''
/* V32 login geometry: one column, one scroll owner, no split/overlap */
#mhLicenseOverlay.show{display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:flex-start!important;overflow-y:auto!important;overflow-x:hidden!important;box-sizing:border-box!important;width:100%!important;height:100%!important}
#mhLicenseOverlay.show .mhLicenseCard{width:min(460px,calc(100vw - 36px))!important;max-width:460px!important;margin:24px auto 0!important;flex:0 0 auto!important}
#mhLicenseOverlay.show .mhLicenseCredits{position:static!important;width:min(760px,calc(100vw - 36px))!important;left:auto!important;right:auto!important;bottom:auto!important;margin:18px auto 28px!important;flex:0 0 auto!important;text-align:center!important}
'''
auth.write_text(a,encoding='utf-8')

# 2/3) First click must finish creating the requested embedded child before switching.
wv=Path('webview2_host.go')
w=wv.read_text(encoding='utf-8-sig')
w=w.replace('''\tif which == 2 && chWhatsappWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(2)\n\t\treturn\n\t}\n\tif which == 3 && chRecordsWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(3)\n\t\treturn\n\t}''','''\tif which == 2 && chWhatsappWnd == 0 {\n\t\t// V32: create/attach before returning so one click is enough.\n\t\twv2EnsureAuxBrowser(2)\n\t}\n\tif which == 3 && chRecordsWnd == 0 {\n\t\t// V32: Records must be attached and visible on the first click.\n\t\twv2EnsureAuxBrowser(3)\n\t}\n\tif which == 2 && chWhatsappWnd == 0 { return }\n\tif which == 3 && chRecordsWnd == 0 { return }''',1)
# Do not race hidden prewarm against user navigation.
w=re.sub(r'''\n\t// Keep WhatsApp CDP and Records ready in their own hidden embedded windows\..*?\n\tgo func\(\) \{\n\t\ttime\.Sleep\(1100 \* time\.Millisecond\)\n\t\twv2EnsureAuxBrowser\(3\)\n\t\}\(\)\n''','\n\t// V32: auxiliary views are created deterministically on first click; no startup prewarm race.\n',w,count=1,flags=re.S)
# Signal Link must be visible on the same WhatsApp click.
needle='''func wv2ShowLocal(which int) {\n\tif wv2Browser == nil {\n\t\treturn\n\t}\n\twv2SetDesiredView(which)'''
repl='''func wv2ShowLocal(which int) {\n\tif wv2Browser == nil {\n\t\treturn\n\t}\n\twv2SetDesiredView(which)\n\tif chSignalLinkBtn != 0 {\n\t\tif which == 2 { chShowWindow.Call(chSignalLinkBtn, chSWShow) } else { chShowWindow.Call(chSignalLinkBtn, chSWHide) }\n\t}'''
if needle not in w: raise SystemExit('V32 wv2ShowLocal anchor missing')
w=w.replace(needle,repl,1)
wv.write_text(w,encoding='utf-8')

# 4) MT5: detect an already-running/broker terminal window and re-parent it instead of leaving external.
ch=Path('chrome_host.go')
c=ch.read_text(encoding='utf-8-sig')
if 'chGetWindowTextV32' not in c:
    c=c.replace('chGetClassName          = chUser32.NewProc("GetClassNameW")','chGetClassName          = chUser32.NewProc("GetClassNameW")\n\tchGetWindowTextV32     = chUser32.NewProc("GetWindowTextW")',1)
helper=r'''
// V32: locate an existing MetaTrader 5 top-level window. Broker builds can hand a
// second terminal64.exe launch to an already-running process, so PID-only lookup is insufficient.
func chFindExistingMT5WindowV32() uintptr {
	var found uintptr
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		if hwnd == hostHWND { return 1 }
		clsBuf := make([]uint16, 256)
		nc, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&clsBuf[0])), uintptr(len(clsBuf)))
		cls := ""; if nc > 0 { cls = strings.ToLower(syscall.UTF16ToString(clsBuf)) }
		tBuf := make([]uint16, 512)
		nt, _, _ := chGetWindowTextV32.Call(hwnd, uintptr(unsafe.Pointer(&tBuf[0])), uintptr(len(tBuf)))
		title := ""; if nt > 0 { title = strings.ToLower(syscall.UTF16ToString(tBuf)) }
		if strings.Contains(cls,"metaquotes") || strings.Contains(title,"metatrader 5") {
			found = hwnd; return 0
		}
		return 1
	})
	chEnumWindows.Call(cb,0)
	return found
}
'''
if 'func chFindExistingMT5WindowV32()' not in c:
    c=c.replace('\nfunc chEnsureMT5Terminal() error {',helper+'\nfunc chEnsureMT5Terminal() error {',1)
old='''\tpath, err := chMT5Executable()\n\tif err != nil { return err }\n\tcmd := exec.Command(path)'''
new='''\t// V32: if MT5 is already open, embed that exact terminal instead of spawning an external duplicate.\n\tif existing := chFindExistingMT5WindowV32(); existing != 0 {\n\t\tchShowWindow.Call(existing, chSWHide)\n\t\tchAttachBrowser(existing)\n\t\tchMu.Lock(); chMT5Wnd = existing; chMu.Unlock()\n\t\tchResizeChildren(); chApplyDesiredBrowserView(); go mt5ApplyLatestQueued(); return nil\n\t}\n\tpath, err := chMT5Executable()\n\tif err != nil { return err }\n\tcmd := exec.Command(path)'''
if old not in c: raise SystemExit('V32 MT5 launch anchor missing')
c=c.replace(old,new,1)
# After launch, fall back to global MT5 window detection if broker hands off to another process.
c=c.replace('''\twnd := chWaitForProcessWindow(uint32(cmd.Process.Pid), 35*time.Second)\n\tif wnd == 0 {''','''\twnd := chWaitForProcessWindow(uint32(cmd.Process.Pid), 12*time.Second)\n\tif wnd == 0 { wnd = chFindExistingMT5WindowV32() }\n\tif wnd == 0 {''',1)
ch.write_text(c,encoding='utf-8')

# 5) Login WhatsApp Support must call the native external-browser endpoint.
authjs=Path('web/auth.js')
aj=authjs.read_text(encoding='utf-8-sig')
# Add delegated capture handler so dynamically-created support link cannot navigate inside WebView2.
if 'MH_V32_EXTERNAL_SUPPORT' not in aj:
    aj=aj.replace('  build();show("login_required");setInterval', '''  // MH_V32_EXTERNAL_SUPPORT: always leave the app for support; never navigate the internal WebView.\n  document.addEventListener("click",async e=>{const a=e.target.closest?.(".mhLicenseWhatsapp");if(!a)return;e.preventDefault();e.stopImmediatePropagation();try{await rawFetch("/api/open-support-external",{method:"POST"})}catch{}},true);\n  build();show("login_required");setInterval''',1)
authjs.write_text(aj,encoding='utf-8')

# Version successor parity. Workflow also hard-checks this before publish.
for p in ['updater.go','license_auth.go']:
    q=Path(p); z=q.read_text(encoding='utf-8-sig'); z=z.replace('V.31','V.32'); q.write_text(z,encoding='utf-8')
for p in ['web/index.html','web/records.html']:
    q=Path(p); z=q.read_text(encoding='utf-8-sig'); z=z.replace('V.31 (Late - CH Shaukat Ali)','V.32 (Late - CH Shaukat Ali)'); q.write_text(z,encoding='utf-8')
print('V32 patch applied')
