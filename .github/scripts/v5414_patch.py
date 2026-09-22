from pathlib import Path
import re, runpy

# Build on the verified V54.13 runtime, then fix only the two real-PC regressions.
runpy.run_path('.github/scripts/v5413_patch.py', run_name='__main__')

# -----------------------------------------------------------------------------
# 1) WHATSAPP: the message is already reaching the composer, but synthetic DOM
#    click/KeyboardEvent is not trusted enough while WebView2 is in background.
#    Keep the same logged-in WebView, but after paste send a native WM_KEYDOWN /
#    WM_CHAR / WM_KEYUP Enter directly to the WebView2 Chromium child window.
#    This does not move the user's mouse and does not require opening WhatsApp.
# -----------------------------------------------------------------------------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')

proc_anchor = 'var chSetWindowDisplayAffinityV31 = chUser32.NewProc("SetWindowDisplayAffinity")'
if proc_anchor not in s:
    raise SystemExit('V54.14 Win32 proc anchor missing')
proc_extra = proc_anchor + '''
var chEnumChildWindowsV5414 = chUser32.NewProc("EnumChildWindows")
var chSendMessageV5414 = chUser32.NewProc("SendMessageW")
var chRedrawWindowV5414 = chUser32.NewProc("RedrawWindow")'''
s = s.replace(proc_anchor, proc_extra, 1)

# Keep WhatsApp full desktop-size and completely outside the visible client area.
# The previous 1px clipping could leave WebView2 in a partially occluded/blank paint state.
pat = r"func wv2ParkWhatsAppV547\(\) \{.*?\n\}"
repl = '''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
\tif w<1 { w=1 }; if h<1 { h=1 }
\tx:=w+32
\t// Full-size desktop renderer stays alive, but parent clipping keeps it invisible.
\tchMoveWindow.Call(wv2WhatsappContainer, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged()
\tchSetWindowPos.Call(wv2WhatsappContainer, 1, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), chSWPNoActivate)
}'''
s, n = re.subn(pat, lambda _m: repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('V54.14 WhatsApp park replacement failed')

# Native Enter helper: send directly to the Chromium child HWND instead of a JS KeyboardEvent.
helper_anchor = 'func wv2WhatsAppAckV542(token uintptr) {'
helper = r'''func wv2WhatsAppInputHWNDV5414() uintptr {
\tif wv2WhatsappContainer == 0 { return 0 }
\tvar found uintptr
\tcb:=syscall.NewCallback(func(hwnd,_ uintptr) uintptr {
\t\tbuf:=make([]uint16,128)
\t\tn,_,_:=chGetClassName.Call(hwnd,uintptr(unsafe.Pointer(&buf[0])),uintptr(len(buf)))
\t\tif n>0 {
\t\t\tcls:=strings.ToLower(syscall.UTF16ToString(buf))
\t\t\tif strings.Contains(cls,"chrome_widgetwin") { found=hwnd }
\t\t}
\t\treturn 1
\t})
\tchEnumChildWindowsV5414.Call(wv2WhatsappContainer,cb,0)
\tif found==0 { found=wv2WhatsappContainer }
\treturn found
}

func wv2WhatsAppNativeEnterV5414(token uintptr) {
\tif token==0 || token!=wv2WAActiveToken || !wv2WAProcessing { return }
\th:=wv2WhatsAppInputHWNDV5414(); if h==0 { return }
\t// Enter scan code is 0x1C. Direct SendMessage keeps the action inside the
\t// background WebView2 and does not touch the user's desktop mouse cursor.
\tdown:=uintptr(1 | (0x1C << 16))
\tup:=uintptr(1 | (0x1C << 16) | (1 << 30) | (1 << 31))
\tchSendMessageV5414.Call(h,0x0100,13,down) // WM_KEYDOWN
\tchSendMessageV5414.Call(h,0x0102,13,down) // WM_CHAR
\tchSendMessageV5414.Call(h,0x0101,13,up)   // WM_KEYUP
}

'''
if helper_anchor not in s:
    raise SystemExit('V54.14 WhatsApp helper anchor missing')
s = s.replace(helper_anchor, helper + helper_anchor, 1)

# After every composer evaluation give WhatsApp a short moment to insert the exact
# message, then deliver a native Enter. If DOM click already sent it, Enter is a no-op.
fn = s.index('func wv2EvalWhatsAppV54(token uintptr)')
ev = s.index('\twv2Whatsapp.Eval(script)', fn)
ev_end = ev + len('\twv2Whatsapp.Eval(script)')
s = s[:ev] + '''\twv2Whatsapp.Eval(script)
\ttime.AfterFunc(520*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppNativeEnterV5414, token, 0) })
\ttime.AfterFunc(980*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })''' + s[ev_end:]

# Retry-send must use the native Enter first, not another synthetic click loop.
old_retry = '''\tcase "retry-send":
\t\ttime.AfterFunc(120*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })'''
new_retry = '''\tcase "retry-send":
\t\twv2WhatsAppNativeEnterV5414(token)
\t\ttime.AfterFunc(320*time.Millisecond, func(){ postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })'''
if old_retry not in s:
    raise SystemExit('V54.14 retry-send anchor missing')
s = s.replace(old_retry, new_retry, 1)

# Add one private host message for native Enter.
const_anchor = '\twmMT5ReadyV5412           = 0x8F58'
if const_anchor not in s:
    raise SystemExit('V54.14 message constant anchor missing')
s = s.replace(const_anchor, const_anchor + '\n\twmWhatsAppNativeEnterV5414 = 0x8F59', 1)

handler_anchor = '''\tcase wmMT5ReadyV5412:
\t\twv2ActivateMT5V5412(); return 0'''
handler_new = handler_anchor + '''
\tcase wmWhatsAppNativeEnterV5414:
\t\twv2WhatsAppNativeEnterV5414(wp); return 0'''
if handler_anchor not in s:
    raise SystemExit('V54.14 native-enter handler anchor missing')
s = s.replace(handler_anchor, handler_new, 1)

# When user opens WhatsApp manually, force a full repaint of the same session so
# the view never stays as a blank theme-colour surface after a background send.
case2_marker = '\t\t\twv2Browser.Resize(); wv2Browser.Focus()\n\t\t}\n\tcase 2:'
# Patch the actual case-2 body by inserting repaint immediately after its Focus call.
needle = '_=wv2Whatsapp.Show(); wv2Whatsapp.Resize(); _=wv2Whatsapp.NotifyParentWindowPositionChanged(); wv2Whatsapp.Focus()'
if needle not in s:
    raise SystemExit('V54.14 manual WhatsApp show anchor missing')
s = s.replace(needle, needle + '; chRedrawWindowV5414.Call(wv2WhatsappContainer,0,0,0x0001|0x0080|0x0100); chUpdateWindow.Call(wv2WhatsappContainer)', 1)

p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# 2) ECONOMIC CALENDAR: stop showing the third-party iframe error page. Restore
#    the local cached calendar renderer as the visible source. It paints the last
#    good values immediately and refreshes the public calendar feed in background.
# -----------------------------------------------------------------------------
p = Path('web/index.html')
s = p.read_text(encoding='utf-8')
iframe = '<iframe id="economicCalendarWidgetV5413" src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=0,1,2,3&countries=Australia,Belgium,Canada,China,France,Germany,Italy,Japan,Mexico,New%20Zealand,South%20Africa,Spain,Switzerland,United%20Kingdom,United%20States" title="Economic Calendar" loading="eager" tabindex="-1" aria-label="Economic Calendar"></iframe>'
local = '<div id="economicCalendarLocal" class="economicCalendarLocal"><div class="calendarLoading">Loading calendar…</div></div>'
if iframe not in s:
    raise SystemExit('V54.14 calendar iframe anchor missing')
s = s.replace(iframe, local, 1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/app.js')
s = p.read_text(encoding='utf-8')
startup = 'await loadPersistentUICacheV5411();await loadRecentSignalsV5413();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
startup2 = 'await loadPersistentUICacheV5411();await loadRecentSignalsV5413();renderRecentSignals();primeTickerV549();primeMovingTickerV547();refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart();setupChartControls();loadChart();refreshMarketCap();'
if startup not in s:
    raise SystemExit('V54.14 calendar startup anchor missing')
s = s.replace(startup, startup2, 1)
p.write_text(s, encoding='utf-8', newline='\n')

p = Path('web/runtime-fixes.css')
css = p.read_text(encoding='utf-8')
css += '''
/* V54.14: reliable cached local calendar; no visible third-party unavailable page. */
.calendarCrop{position:relative!important;overflow:auto!important;background:transparent!important}.calendarCrop #economicCalendarWidgetV5413{display:none!important}.calendarCrop .economicCalendarLocal{display:block!important;width:100%!important;height:100%!important;max-height:340px!important;visibility:visible!important;opacity:1!important;pointer-events:none!important;user-select:none!important}
'''
p.write_text(css, encoding='utf-8', newline='\n')

# Give the public feed enough background time to succeed; cache still renders first.
p = Path('calendar3d.go')
s = p.read_text(encoding='utf-8')
s = s.replace('Timeout: 2500 * time.Millisecond', 'Timeout: 5 * time.Second', 1)
s = s.replace('2800*time.Millisecond', '5500*time.Millisecond', 1)
p.write_text(s, encoding='utf-8', newline='\n')

# -----------------------------------------------------------------------------
# V54.14 stamps.
# -----------------------------------------------------------------------------
for path, pat, val in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.14"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.14"'),
]:
    q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
    if n!=1: raise SystemExit('V54.14 version stamp failed '+path)
    q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.14\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.14</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.13','Version: V.54.14'); p.write_text(z,encoding='utf-8',newline='\n')

# Regression guards.
wa = Path('webview2_host.go').read_text(encoding='utf-8')
a = Path('web/app.js').read_text(encoding='utf-8')
html = Path('web/index.html').read_text(encoding='utf-8')
cal = Path('calendar3d.go').read_text(encoding='utf-8')
checks = [
    ('native background Enter', 'wv2WhatsAppNativeEnterV5414' in wa and 'WM_KEYDOWN' in wa and 'WM_CHAR' in wa),
    ('native Enter scheduled after paste', '520*time.Millisecond' in wa and 'wmWhatsAppNativeEnterV5414' in wa),
    ('retry uses native Enter', 'case "retry-send"' in wa and 'wv2WhatsAppNativeEnterV5414(token)' in wa),
    ('WhatsApp full-size offscreen', 'x:=w+32' in wa and 'wv2Whatsapp.Resize()' in wa),
    ('manual WhatsApp repaint', 'chRedrawWindowV5414.Call' in wa),
    ('local calendar visible', 'id="economicCalendarLocal"' in html and 'economicCalendarWidgetV5413' not in html),
    ('calendar startup refresh', 'refreshPublicTicker();loadEconomicCalendarV545();setupLightweightChart()' in a),
    ('calendar reliable timeout', 'Timeout: 5 * time.Second' in cal and '5500*time.Millisecond' in cal),
]
for name, ok in checks:
    if not ok:
        raise SystemExit('Guard failed: '+name)
