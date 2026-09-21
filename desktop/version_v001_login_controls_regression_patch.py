from pathlib import Path
import re

MARK='MH_V001_RUNTIME_ACCEPTANCE_FIX'

# FINAL auth behavior: update precheck may run first, but when no newer mandatory
# update exists the visible Account Login MUST remain until credentials are entered.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Successful manual login unlocks current process without reload; reload was causing
# saved backend session to immediately bypass the visible login lifecycle.
s=re.sub(r'(passInput\.value\s*=\s*"";\s*\n\s*hide\(j\);)\s*\n\s*location\.reload\(\);',r'\1\n      // '+MARK+': manual login unlocks this running process.',s,count=1)

# Remove startup auto-authorization. Persistent backend/app data is NOT deleted.
s=re.sub(r'(build\(\);\s*\n\s*show\("login_required"\);)\s*\n\s*status\(false\);',r'\1\n  // '+MARK+': never consume an old server session on fresh EXE startup.',s,count=1)

# Periodic validation only after manual login has hidden the overlay.
s=s.replace('setInterval(() => status(false), 4 * 60 * 1000);','setInterval(() => { if (!overlay?.classList.contains("show")) status(false); }, 4 * 60 * 1000);')

# If update-aware bootstrap exists after earlier patches, force login only when the
# mandatory-update gate is not active. Never hide login merely because /status has
# an old authorized session.
if 'async function mhV001Bootstrap' in s:
    start=s.index('async function mhV001Bootstrap')
    end=s.find('\n}',start)
    if end>start:
        block=s[start:end+2]
        block=re.sub(r'(?m)^\s*status\(false\);\s*\n?','',block)
        block=re.sub(r'(?m)^\s*showChecking\([^\n]*\);\s*\n?','',block)
        if 'show("login_required")' not in block:
            pos=block.rfind('}')
            block=block[:pos]+'  if(!document.getElementById("mhMandatoryUpdateV001") || document.getElementById("mhMandatoryUpdateV001").classList.contains("mhUpdateHiddenV001")) show("login_required");\n'+block[pos:]
        s=s[:start]+block+s[end+2:]

if MARK not in s: s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Restore original host geometry from V80.9 after later chrome-crop patches. This
# removes the white bottom strip and guarantees the native toolbar remains visible.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')

# Neutralize the later crop-layout helper by making it use the original content
# rectangle below the toolbar, with no negative-Y child placement or artificial H.
pat=r'func chLayoutUpdateChromeV001Final\(hwnd uintptr, w, h int32\) \{.*?\n\}'
replacement=r'''func chLayoutUpdateChromeV001Final(hwnd uintptr, w, h int32) {
	if hwnd == 0 { return }
	// MH_V001_RUNTIME_ACCEPTANCE_FIX: original V80.9 geometry, no negative crop.
	chNormalizeEmbeddedTreeV001Final(hwnd)
	chMoveWindow.Call(hwnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
}'''
s,n=re.subn(pat,replacement,s,count=1,flags=re.S)
if n!=1: raise SystemExit('final chrome layout helper missing')

# Replace final resize routine with one authoritative rectangle for all views and
# explicitly restore the four top buttons + WhatsApp Signal Link behavior.
start=s.find('func chResizeChildren() {')
end=s.find('\nfunc chApplyDesiredBrowserView(',start)
if start<0 or end<0: raise SystemExit('resize/apply anchors missing')
resize=r'''func chResizeChildren() {
	if hostHWND == 0 { return }
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int32(r.R-r.L); clientH := int32(r.B-r.T); h := clientH-int32(barH)
	if w<1 { w=1 }; if h<1 { h=1 }
	layout := func(child uintptr) { if child!=0 { chMoveWindow.Call(child,0,uintptr(barH),uintptr(w),uintptr(h),1) } }
	layout(chAnalysisWnd); layout(chWhatsappWnd); layout(chRecordsWnd); layout(chMT5Wnd)
	if btnAnalysis!=0 { chMoveWindow.Call(btnAnalysis,8,7,140,30,1); chShowWindow.Call(btnAnalysis,chSWShow) }
	if btnWhatsapp!=0 { chMoveWindow.Call(btnWhatsapp,156,7,140,30,1); chShowWindow.Call(btnWhatsapp,chSWShow) }
	if btnRecords!=0 { chMoveWindow.Call(btnRecords,304,7,140,30,1); chShowWindow.Call(btnRecords,chSWShow) }
	if btnMT5!=0 { chMoveWindow.Call(btnMT5,452,7,140,30,1); chShowWindow.Call(btnMT5,chSWShow) }
	chViewMu.Lock(); which:=chDesiredView; chViewMu.Unlock()
	if chSignalLinkBtn!=0 { chMoveWindow.Call(chSignalLinkBtn,600,7,145,30,1); if which==2 { chShowWindow.Call(chSignalLinkBtn,chSWShow) } else { chShowWindow.Call(chSignalLinkBtn,chSWHide) } }
}'''
s=s[:start]+resize+s[end:]
p.write_text(s,encoding='utf-8')

# Hidden update gate must occupy nothing and intercept nothing.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s+='''\n/* MH_V001_RUNTIME_ACCEPTANCE_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;width:0!important;height:0!important;overflow:hidden!important;}
'''
p.write_text(s,encoding='utf-8')

# Keep release exactly V.01 and toolbar lock reversible only for verified newer update.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=re.sub(r'const mhPublicVersionV001 = "[^"]+"','const mhPublicVersionV001 = "V.01"',s)
pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(pat,s)
if m: s=s[:m.start()]+m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // '+MARK+s[m.end():]
p.write_text(s,encoding='utf-8')

print(MARK+': V.01 login every launch + original toolbar/buttons + no white bottom strip + saved data preserved')
