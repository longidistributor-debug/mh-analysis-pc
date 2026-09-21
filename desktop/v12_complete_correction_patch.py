from pathlib import Path

VERSION='V.12'
LABEL='V.12 (CH Shaukat Ali)'

def read(p): return Path(p).read_text(encoding='utf-8-sig')
def write(p,s): Path(p).write_text(s,encoding='utf-8',newline='\n')
def once(s,old,new,label):
    if new in s: return s
    if old not in s: raise SystemExit(f'{label}: anchor missing')
    return s.replace(old,new,1)

# 1) Restore intended UTF-8 UI text and apply V.12 branding without redesigning layout.
p='web/index.html'; s=read(p)
repls={
'V.10':'V.12',
'v79.6 AUTO CYCLE (HAMMAD & SOMI)':LABEL,
'Ø¨ÙØ³Ù’Ù…Ù Ø§Ù„Ù„ÙŽÙ‘Ù‡Ù Ø§Ù„Ø±ÙŽÙ‘Ø­Ù’Ù…ÙŽÙ°Ù†Ù Ø§Ù„Ø±ÙŽÙ‘Ø­ÙÙŠÙ…Ù':'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
'â—†':'◆','â”€':'─','â€¢':'•','â€”':'—','â‚¿':'₿','â‚¬':'€','Â¥':'¥','Â£':'£','â—Ž':'◎','â—':'●','â†»':'↻','â€¦':'…','â—´':'◴','â†’':'→','â‰¥':'≥','â‰¤':'≤','Â©':'©','â€“':'–','â€™':'’','â€œ':'“','â€':'”'
}
for a,b in repls.items(): s=s.replace(a,b)
write(p,s)

p='web/records.html'; s=read(p)
s=s.replace('v79.8 • LOCAL MT5 TRADE LIFECYCLE',LABEL)
write(p,s)

# 2) V.12 updater/version values.
p='VERSION'; write(p,'V.12\n')
p='updater.go'; s=read(p)
import re
s=re.sub(r'mhPublicVersionV001\s*=\s*"V\.[^"]+"','mhPublicVersionV001 = "V.12"',s)
write(p,s)
p='license_auth.go'; s=read(p)
s=re.sub(r'const licAppVersion = "[^"]+"','const licAppVersion = "V.12"',s)
write(p,s)

# 3) Windows capture protection on the single top-level MH Analysis window.
p='chrome_host.go'; s=read(p)
if 'MH_V12_CAPTURE_PROTECTION' not in s:
    s=once(s,
        'chSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")',
        'chSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")\n\tchSetWindowDisplayAffinity = chUser32.NewProc("SetWindowDisplayAffinity") // MH_V12_CAPTURE_PROTECTION',
        'display affinity proc')
write(p,s)

p='webview2_host.go'; s=read(p)
if 'MH_V12_CAPTURE_PROTECTION' not in s:
    anchor='''\tif hostHWND == 0 {\n\t\tmessageBox(0, "Could not create MH Analysis window.", "MH Analysis", 0x10)\n\t\treturn\n\t}\n'''
    insert=anchor+'''\t// MH_V12_CAPTURE_PROTECTION: ask Windows to exclude this top-level app window\n\t// from supported OS capture APIs. This covers the embedded WebView2/MT5 child surface.\n\t// WDA_EXCLUDEFROMCAPTURE = 0x11 (Windows 10 2004+). Fall back to WDA_MONITOR.\n\tif r, _, _ := chSetWindowDisplayAffinity.Call(hostHWND, uintptr(0x11)); r == 0 {\n\t\tchSetWindowDisplayAffinity.Call(hostHWND, uintptr(0x1))\n\t}\n'''
    s=once(s,anchor,insert,'capture host')

# 4) Fix MT5 tab architecture: WebView2 host must select view 4 before terminal startup.
old='''\t\tcase idMT5:\n\t\t\t_ = wv2Browser.Hide()\n\t\t\tchShowWindow.Call(wv2Container, chSWHide)\n\t\t\tgo func() {\n\t\t\t\tif err := chEnsureMT5Terminal(); err != nil {\n\t\t\t\t\tmessageBox(hostHWND, err.Error(), "MT5 System", 0x10)\n\t\t\t\t}\n\t\t\t}()\n'''
new='''\t\tcase idMT5:\n\t\t\t// MH_V12_MT5_VIEW_FIX: chEnsureMT5Terminal uses chApplyDesiredBrowserView;\n\t\t\t// select MT5 before startup so it cannot immediately hide the terminal again.\n\t\t\tchViewMu.Lock()\n\t\t\tchDesiredView = 4\n\t\t\tchViewMu.Unlock()\n\t\t\t_ = wv2Browser.Hide()\n\t\t\tchShowWindow.Call(wv2Container, chSWHide)\n\t\t\tgo func() {\n\t\t\t\tif err := chEnsureMT5Terminal(); err != nil {\n\t\t\t\t\t// Never leave a blank screen when MT5 cannot start/embed.\n\t\t\t\t\tchViewMu.Lock(); chDesiredView = 1; chViewMu.Unlock()\n\t\t\t\t\twv2ShowLocal(1)\n\t\t\t\t\tmessageBox(hostHWND, err.Error(), "MT5 System", 0x10)\n\t\t\t\t\treturn\n\t\t\t\t}\n\t\t\t\tchApplyDesiredBrowserView()\n\t\t\t\tgo mt5ApplyLatestQueued()\n\t\t\t}()\n'''
s=once(s,old,new,'MT5 WebView2 command')
write(p,s)

print('V.12 complete correction patch applied')
