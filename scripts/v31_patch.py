from pathlib import Path
import re

# Applied AFTER retained V28/V29/V30 patches. Keep all existing signal/identity logic.
idx=Path('web/index.html')
s=idx.read_text(encoding='utf-8-sig')
s=re.sub(r'<div class="version">.*?</div>', '<div class="version">V.31 (Late - CH Shaukat Ali)</div>', s, count=1, flags=re.S)
# footer must not carry version/memorial
s=re.sub(r'<footer class="mhMainCopyright">.*?</footer>', '<footer class="mhMainCopyright">MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved.</footer>', s, count=1, flags=re.S)
if '/v31.css' not in s: s=s.replace('</head>','<link rel="stylesheet" href="/v31.css" />\n</head>')
if '/v31.js' not in s: s=s.replace('</body>','<script src="/v31.js"></script>\n</body>')
idx.write_text(s,encoding='utf-8')

rec=Path('web/records.html')
r=rec.read_text(encoding='utf-8-sig')
r=re.sub(r'<div class="recordsVersion">.*?</div>', '<div class="recordsVersion">V.31 (Late - CH Shaukat Ali)</div>', r, count=1, flags=re.S)
if '/v31.css' not in r: r=r.replace('</head>','<link rel="stylesheet" href="/v31.css" />\n</head>')
if '/v31.js' not in r: r=r.replace('</body>','<script src="/v31.js"></script>\n</body>')
rec.write_text(r,encoding='utf-8')

# Login: exactly one scroll owner; credits participate in layout, never overlap form.
auth=Path('web/auth.css')
a=auth.read_text(encoding='utf-8-sig')
a += '''\n/* V31 login single-scroll/no-overlap */\nhtml.mhLicenseLocked,html.mhLicenseLocked body,.mhLicenseLocked body{overflow:hidden!important}\n#mhLicenseOverlay.show{overflow-y:auto!important;overflow-x:hidden!important;align-items:flex-start!important;padding:24px 18px 32px!important}\n#mhLicenseOverlay.show .mhLicenseCard{margin:auto auto 18px!important;flex:0 0 auto!important}\n.mhLicenseCredits{position:static!important;display:block!important;margin:18px auto 0!important;padding:0 12px 18px!important;max-width:760px!important}\n@media(max-height:800px){#mhLicenseOverlay{padding-bottom:28px!important}.mhLicenseCredits{position:static!important}.mhLicenseCard{margin-bottom:12px!important}}\n'''
auth.write_text(a,encoding='utf-8')

# Navigation: do not hide current view until async target is ready. This removes first-click blank/double-click requirement.
wv=Path('webview2_host.go')
w=wv.read_text(encoding='utf-8-sig')
old='''\t_ = wv2Browser.Hide()\n\tchShowWindow.Call(wv2Container, chSWHide)\n\n\tif which == 2 {\n\t\tif chWhatsappWnd == 0 {\n\t\t\tgo wv2EnsureAuxBrowser(2)\n\t\t\treturn\n\t\t}'''
new='''\t// V31: keep the current MH view visible until the requested child is actually ready.\n\t// This prevents a blank first click and removes the need to click twice.\n\tif which == 2 && chWhatsappWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(2)\n\t\treturn\n\t}\n\tif which == 3 && chRecordsWnd == 0 {\n\t\tgo wv2EnsureAuxBrowser(3)\n\t\treturn\n\t}\n\t_ = wv2Browser.Hide()\n\tchShowWindow.Call(wv2Container, chSWHide)\n\n\tif which == 2 {'''
if old not in w: raise SystemExit('V31 navigation anchor missing')
w=w.replace(old,new,1)
# Remove now-redundant records blank-first-click block.
w=w.replace('''\tif which == 3 {\n\t\tif chRecordsWnd == 0 {\n\t\t\tgo wv2EnsureAuxBrowser(3)\n\t\t\treturn\n\t\t}\n\t\tchShowWindowAsync.Call(chRecordsWnd, chSWShow)''','''\tif which == 3 {\n\t\tchShowWindowAsync.Call(chRecordsWnd, chSWShow)''',1)
# MT5: keep analysis visible while MT5 starts; chEnsureMT5Terminal reparents then chApplyDesiredBrowserView shows it embedded.
w=re.sub(r'func wv2ShowMT5\(\) \{.*?\n\}', '''func wv2ShowMT5() {\n\twv2SetDesiredView(4)\n\t// V31: never blank the host while MT5 is starting. The terminal is hidden,\n\t// re-parented into MH Analysis, resized, then shown by chApplyDesiredBrowserView.\n\tgo func() {\n\t\tif err := chEnsureMT5Terminal(); err != nil {\n\t\t\tmessageBox(hostHWND, err.Error(), "MT5 System", 0x10)\n\t\t\twv2SetDesiredView(1)\n\t\t}\n\t}()\n}''', w, count=1, flags=re.S)
# Windows capture exclusion on the actual top-level host.
if 'chSetWindowDisplayAffinityV31' not in w:
    w=w.replace('var (\n\twv2Browser', 'var chSetWindowDisplayAffinityV31 = chUser32.NewProc("SetWindowDisplayAffinity")\nconst chWDAExcludeFromCaptureV31 = 0x00000011\n\nvar (\n\twv2Browser',1)
    w=w.replace('''\tif hostHWND == 0 {\n\t\tmessageBox(0, "Could not create MH Analysis window.", "MH Analysis", 0x10)\n\t\treturn\n\t}\n''','''\tif hostHWND == 0 {\n\t\tmessageBox(0, "Could not create MH Analysis window.", "MH Analysis", 0x10)\n\t\treturn\n\t}\n\t// V31 best-effort Windows capture exclusion (Snipping Tool/most screen capture/share APIs).\n\tchSetWindowDisplayAffinityV31.Call(hostHWND, chWDAExcludeFromCaptureV31)\n''',1)
wv.write_text(w,encoding='utf-8')

# External support endpoint. Internal WhatsApp tab remains separate.
main=Path('main.go')
m=main.read_text(encoding='utf-8-sig')
if '"os/exec"' not in m: m=m.replace('"os"','"os"\n\t"os/exec"',1)
if '/api/open-support-external' not in m:
    anchor='''\tmux.HandleFunc("/api/open-whatsapp", func(w http.ResponseWriter, r *http.Request) {'''
    route='''\tmux.HandleFunc("/api/open-support-external", func(w http.ResponseWriter, r *http.Request) {\n\t\tif r.Method != http.MethodPost { http.Error(w, "method", 405); return }\n\t\t// Open support outside MH Analysis; never replace the internal WhatsApp automation view.\n\t\t_ = exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", "https://wa.me/923434824609").Start()\n\t\tw.WriteHeader(204)\n\t})\n'''
    if anchor not in m: raise SystemExit('support route anchor missing')
    m=m.replace(anchor,route+anchor,1)
main.write_text(m,encoding='utf-8')

Path('web/v31.css').write_text('''/* V31 UI/security/layout */\nhtml,body{max-width:100%;overflow-x:hidden}\nbody:not(.mhLicenseLocked),body:not(.mhLicenseLocked) *{user-select:none!important;-webkit-user-select:none!important}\ninput,textarea,[contenteditable="true"]{user-select:text!important;-webkit-user-select:text!important}\n.rsiCanvasWrap{box-sizing:border-box!important;border:1px solid rgba(0,210,170,.42)!important;border-radius:0 0 12px 12px!important;overflow:hidden!important;margin:0 8px 8px!important}\n.mhMainCopyright{white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;padding:6px 12px!important;box-sizing:border-box!important}\n''',encoding='utf-8')

Path('web/v31.js').write_text('''(()=>{\n'use strict';\n// Block ordinary copy/cut/context-menu/zoom shortcuts while preserving login/settings typing.\nconst editable=e=>!!e.target.closest('input,textarea,[contenteditable="true"]');\nfor(const ev of ['copy','cut','contextmenu','dragstart']) document.addEventListener(ev,e=>{if(!editable(e))e.preventDefault()},true);\ndocument.addEventListener('selectstart',e=>{if(!editable(e))e.preventDefault()},true);\ndocument.addEventListener('keydown',e=>{\n  if(e.key==='PrintScreen'){e.preventDefault();return;}\n  if(!editable(e) && e.ctrlKey && ['c','x','a','+','-','=','0'].includes(e.key.toLowerCase())){e.preventDefault();e.stopPropagation();}\n},true);\ndocument.addEventListener('wheel',e=>{if(e.ctrlKey)e.preventDefault()},{passive:false,capture:true});\n// Support button is explicitly external. Internal top navigation WhatsApp is untouched.\nconst support=document.getElementById('openWhatsappTab');\nif(support){\n  const clone=support.cloneNode(true); support.replaceWith(clone);\n  clone.addEventListener('click',async e=>{e.preventDefault();try{await fetch('/api/open-support-external',{method:'POST'})}catch(_){}});\n}\n})();\n''',encoding='utf-8')
print('V31 patch applied')
