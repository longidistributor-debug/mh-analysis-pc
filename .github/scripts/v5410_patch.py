from pathlib import Path
import re, runpy

# Start from V54.9 runtime, then touch only the four runtime regressions reported.
runpy.run_path('.github/scripts/v549_patch.py', run_name='__main__')

# WhatsApp: keep same persistent logged-in WebView fully rendered at desktop size
# behind MH Analysis, not 2x2/clipped/offscreen. Manual WhatsApp brings it front.
p=Path('webview2_host.go')
s=p.read_text(encoding='utf-8')
pat=r"func wv2ParkWhatsAppV547\(\) \{.*?\n\}"
repl='''func wv2ParkWhatsAppV547() {
\tif wv2Whatsapp == nil || wv2WhatsappContainer == 0 || hostHWND == 0 { return }
\tvar r chRect
\tchGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH))
\tif w<1 { w=1 }; if h<1 { h=1 }
\tchMoveWindow.Call(wv2WhatsappContainer, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
\tchShowWindow.Call(wv2WhatsappContainer, chSWShow)
\t_ = wv2Whatsapp.Show()
\twv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged()
\tif wv2Container != 0 {
\t\tchSetWindowPos.Call(wv2WhatsappContainer, wv2Container, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoActivate)
\t}
}'''
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.10 WhatsApp park replacement failed')

casepat=r"case 2:\n\t\twv2WAResolvedTarget = \"\"\n\t\tif wv2Whatsapp != nil \{.*?\n\t\t\}"
caserepl='''case 2:
\t\twv2WAResolvedTarget = ""
\t\tif wv2Whatsapp != nil {
\t\t\tvar r chRect; chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
\t\t\tw:=int32(r.R-r.L); h:=int32(r.B-r.T-int32(barH)); if w<1{w=1}; if h<1{h=1}
\t\t\tchMoveWindow.Call(wv2WhatsappContainer,0,uintptr(barH),uintptr(w),uintptr(h),1)
\t\t\tchShowWindow.Call(wv2WhatsappContainer,chSWShow)
\t\t\tchSetWindowPos.Call(wv2WhatsappContainer,0,0,uintptr(barH),uintptr(w),uintptr(h),chSWPNoActivate)
\t\t\t_ = wv2Whatsapp.Show(); wv2Whatsapp.Resize(); _ = wv2Whatsapp.NotifyParentWindowPositionChanged(); wv2Whatsapp.Focus()
\t\t}'''
s,n=re.subn(casepat,lambda _m:caserepl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.10 WhatsApp explicit show case missing')

# Background group navigation may take several seconds; do not drop queued message at 3 sec.
s=s.replace('[]time.Duration{120*time.Millisecond, 300*time.Millisecond, 650*time.Millisecond, 1100*time.Millisecond, 1700*time.Millisecond, 2400*time.Millisecond}',
'''[]time.Duration{150*time.Millisecond, 350*time.Millisecond, 700*time.Millisecond, 1200*time.Millisecond, 2*time.Second, 3*time.Second, 5*time.Second, 8*time.Second, 12*time.Second, 16*time.Second, 20*time.Second}''',1)
s=s.replace('time.AfterFunc(3*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })',
            'time.AfterFunc(24*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })',1)
p.write_text(s,encoding='utf-8',newline='\n')

# Economic calendar: exact original public widget, independent from FCS/API.
p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
pat=r'<iframe id="economicCalendarImmediateV549"[^>]*></iframe><div id="economicCalendarLocal"[^>]*></div>'
orig='<iframe src="https://widget.mfbcdn.net/widget/calendar.html?lang=en&impacts=1,2,3&symbols=AUD,CAD,CHF,CNY,EUR,GBP,JPY,NZD,USD" title="Economic Calendar"></iframe>'
s,n=re.subn(pat,orig,s,count=1)
if n!=1: raise SystemExit('V54.10 calendar widget replacement failed')
p.write_text(s,encoding='utf-8',newline='\n')

p=Path('web/runtime-fixes.css')
css=p.read_text(encoding='utf-8')
css=re.sub(r'\n/\* V54\.9 immediate public calendar \*/\n#economicCalendarImmediateV549\{.*?\}#economicCalendarLocal\{.*?\}\n?', '\n', css, count=1, flags=re.S)
p.write_text(css,encoding='utf-8',newline='\n')

# MT5: detect/hide the actual configured executable too, not only terminal64.exe.
p=Path('mt5_embed_v36.go')
s=p.read_text(encoding='utf-8')
if 'v5410MT5ExeBase string' not in s:
    s=s.replace('var (\n','var v5410MT5ExeBase string\n\nvar (\n',1)
insert_anchor='func v546HideAllMT5TopLevel()'
helper='''func v5410IsMT5Image(image string) bool {
\timage = strings.ToLower(strings.TrimSpace(image))
\treturn image == "terminal64.exe" || image == "terminal.exe" || (v5410MT5ExeBase != "" && image == v5410MT5ExeBase)
}
func v5410FindMT5Candidate() uintptr {
\tvar found uintptr; var bestArea int64
\tcb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{
\t\tif hwnd==0||hwnd==hostHWND{return 1}; var pid uint32; chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)))
\t\tif !v5410IsMT5Image(v36ProcessImage(pid)){return 1}
\t\tvar r chRect; ok,_,_:=v41GetWindowRect.Call(hwnd,uintptr(unsafe.Pointer(&r))); if ok==0{return 1}
\t\tw:=int64(r.R-r.L); h:=int64(r.B-r.T); if w<80||h<60{return 1}; if a:=w*h; a>bestArea{bestArea=a;found=hwnd}; return 1
\t}); chEnumWindows.Call(cb,0); return found
}

'''
if insert_anchor not in s: raise SystemExit('V54.10 MT5 helper anchor missing')
s=s.replace(insert_anchor,helper+insert_anchor,1)
pat=r"func v546HideAllMT5TopLevel\(\)\{.*?\n\}"
repl='''func v546HideAllMT5TopLevel(){
\tcb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{if hwnd==0||hwnd==hostHWND{return 1};var pid uint32;chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)));if v5410IsMT5Image(v36ProcessImage(pid)){parent,_,_:=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide)}};return 1});chEnumWindows.Call(cb,0)
}'''
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.10 MT5 hide-all replacement failed')
pat=r"func v546EmbedOnlyMT5\(wait time\.Duration\) bool \{.*?\n\}"
repl='''func v546EmbedOnlyMT5(wait time.Duration) bool {
\tdeadline:=time.Now().Add(wait)
\tfor time.Now().Before(deadline){
\t\tv546HideAllMT5TopLevel()
\t\tif hwnd:=v5410FindMT5Candidate();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if v36EmbedMT5(hwnd){return true}}
\t\ttime.Sleep(2*time.Millisecond)
\t}
\treturn false
}'''
s,n=re.subn(pat,lambda _m:repl,s,count=1,flags=re.S)
if n!=1: raise SystemExit('V54.10 MT5 embed-only replacement failed')
s=s.replace('if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if !v546EmbedOnlyMT5(4*time.Second)',
            'if hwnd:=v5410FindMT5Candidate();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if !v546EmbedOnlyMT5(4*time.Second)',1)
needle='path,err:=chMT5Executable();if err!=nil{return err};cmd:=exec.Command(path);'
replacement='path,err:=chMT5Executable();if err!=nil{return err};v5410MT5ExeBase=strings.ToLower(filepath.Base(path));v546HideAllMT5TopLevel();cmd:=exec.Command(path);'
if needle not in s: raise SystemExit('V54.10 MT5 launch anchor missing')
s=s.replace(needle,replacement,1)
p.write_text(s,encoding='utf-8',newline='\n')

# V54.10 stamps.
for path,pat,val in [
 ('updater.go',r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.54.10"'),
 ('license_auth.go',r'const licAppVersion = "[^"]+"','const licAppVersion = "V.54.10"')]:
 q=Path(path); z=q.read_text(encoding='utf-8'); z,n=re.subn(pat,val,z,count=1)
 if n!=1: raise SystemExit('version stamp failed '+path)
 q.write_text(z,encoding='utf-8',newline='\n')
Path('VERSION').write_text('V.54.10\n',encoding='ascii')
p=Path('web/index.html'); z=p.read_text(encoding='utf-8'); z=re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.10</div>',z,count=1); p.write_text(z,encoding='utf-8',newline='\n')
p=Path('webview2_host.go'); z=p.read_text(encoding='utf-8').replace('Version: V.54.9','Version: V.54.10'); p.write_text(z,encoding='utf-8',newline='\n')

wa=Path('webview2_host.go').read_text(encoding='utf-8'); html=Path('web/index.html').read_text(encoding='utf-8'); mt=Path('mt5_embed_v36.go').read_text(encoding='utf-8')
checks=[
 ('WA full renderer', 'chMoveWindow.Call(wv2WhatsappContainer, 0, uintptr(barH), uintptr(w), uintptr(h), 1)' in wa),
 ('WA behind main', 'chSetWindowPos.Call(wv2WhatsappContainer, wv2Container' in wa),
 ('WA long background retry', '20*time.Second' in wa and '24*time.Second' in wa),
 ('calendar original widget', 'widget.mfbcdn.net/widget/calendar.html' in html and 'economicCalendarImmediateV549' not in html),
 ('MT5 configured exe detection', 'v5410MT5ExeBase' in mt and 'v5410FindMT5Candidate' in mt),
 ('MT5 direct hidden embed loop', 'time.Sleep(2*time.Millisecond)' in mt and 'v546HideAllMT5TopLevel()' in mt),
]
for name,ok in checks:
 if not ok: raise SystemExit('Guard failed: '+name)
