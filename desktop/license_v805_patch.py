from pathlib import Path

MARK = "MH_SECURE_LICENSE_V805"

# 1) Device identity: the Vercel Node crypto backend expects a PEM public key.
p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
if '"encoding/pem"' not in s:
    s = s.replace('"encoding/hex"\n', '"encoding/hex"\n\t"encoding/pem"\n', 1)
if 'const licAppVersion = "80.5"' not in s:
    old = 'const licAppVersion = "80.4"'
    if old not in s:
        raise SystemExit("license_auth.go V80.4 version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.5"', 1)
old_key = '"public_key":   base64.StdEncoding.EncodeToString(d.DER),'
new_key = '"public_key":   string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: d.DER})),'
if old_key in s:
    s = s.replace(old_key, new_key, 1)
elif new_key not in s:
    raise SystemExit("license_auth.go public_key anchor missing")
s = s.replace('return map[string]string{"machine_name": host, "os": runtime.GOOS, "arch": runtime.GOARCH, "app_version": licAppVersion}',
              'return map[string]string{"device_name": host, "os_version": runtime.GOOS, "arch": runtime.GOARCH, "app_version": licAppVersion}', 1)
p.write_text(s, encoding="utf-8")

# 2) Native host sizing: synchronously size every embedded child to the real host client width.
# This removes the uncovered white strip on the right on some Windows/DPI setups.
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
repls = {
    'chSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)':
        'chMoveWindow.Call(chAnalysisWnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) // '+MARK,
    'chSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)':
        'chMoveWindow.Call(chWhatsappWnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) // '+MARK,
    'chSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)':
        'chMoveWindow.Call(chRecordsWnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) // '+MARK,
    'chSetWindowPos.Call(chMT5Wnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)':
        'chMoveWindow.Call(chMT5Wnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) // '+MARK,
}
for old, new in repls.items():
    if old in s:
        s = s.replace(old, new, 1)
    elif new not in s:
        raise SystemExit("chrome_host.go resize anchor missing: "+old[:50])
old_reveal = '''\t\tif hostHWND!=0 {\n\t\t\tchShowWindowAsync.Call(hostHWND, chSWMaximize)\n\t\t\tchUpdateWindow.Call(hostHWND)\n\t\t}\n'''
new_reveal = '''\t\tif hostHWND!=0 {\n\t\t\tchShowWindowAsync.Call(hostHWND, chSWMaximize)\n\t\t\tchUpdateWindow.Call(hostHWND)\n\t\t\tchResizeChildren() // '''+MARK+''' immediate full-client sizing\n\t\t\tgo func(){ time.Sleep(180*time.Millisecond); chResizeChildren() }()\n\t\t}\n'''
if old_reveal in s:
    s = s.replace(old_reveal, new_reveal, 1)
elif new_reveal not in s:
    raise SystemExit("chrome_host.go reveal anchor missing")
p.write_text(s, encoding="utf-8")

# 3) Keep the same login content but mark V80.5.
p = Path("web/auth.js")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    if "MH_SECURE_LICENSE_V804" not in s:
        raise SystemExit("auth.js V80.4 marker missing")
    s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)
p.write_text(s, encoding="utf-8")

# 4) Balance card + credits as one centered no-scroll group.
p = Path("web/auth.css")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    if "MH_SECURE_LICENSE_V804" not in s:
        raise SystemExit("auth.css V80.4 marker missing")
    s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)

override = r'''

/* MH_SECURE_LICENSE_V805 — balanced one-screen login group */
#mhLicenseOverlay.show{
  display:flex!important;
  flex-direction:column!important;
  align-items:center!important;
  justify-content:center!important;
  gap:16px!important;
  padding:12px 24px!important;
  overflow:hidden!important;
  width:100vw!important;
  min-width:100vw!important;
  max-width:100vw!important;
  height:100vh!important;
  min-height:100vh!important;
  max-height:100vh!important;
}
#mhLicenseOverlay.show .mhLicenseCard{
  position:relative!important;
  transform:none!important;
  transform-origin:center center!important;
  margin:0!important;
  flex:0 0 auto!important;
}
#mhLicenseOverlay.show .mhLicenseCredits{
  position:static!important;
  left:auto!important;
  right:auto!important;
  bottom:auto!important;
  width:min(460px,94vw)!important;
  flex:0 0 auto!important;
  margin:0!important;
  text-align:center!important;
  font-size:9.4px!important;
  line-height:1.32!important;
}
@media(max-height:650px){
  #mhLicenseOverlay.show{gap:8px!important;padding:5px 20px!important}
  #mhLicenseOverlay.show .mhLicenseCard{transform:scale(.88)!important;margin:-32px 0!important}
  #mhLicenseOverlay.show .mhLicenseCredits{font-size:8.1px!important;line-height:1.20!important}
}
'''
if 'balanced one-screen login group' not in s:
    s += override
p.write_text(s, encoding="utf-8")

print(MARK + " applied: PEM device identity, full-width embedded view, balanced login credits")
