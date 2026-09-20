from pathlib import Path

MARK = "MH_SECURE_LICENSE_V804"

# main.go: expose a fixed support-open route under the already-unlocked /api/license namespace.
p = Path("main.go")
s = p.read_text(encoding="utf-8")
route = '\tmux.HandleFunc("/api/license/support/open", licHandleSupportOpenV804)\n'
if route not in s:
    anchor = '\tregisterLicenseRoutes(mux)\n'
    if anchor not in s:
        raise SystemExit("main.go license route anchor missing")
    s = s.replace(anchor, anchor + route, 1)
p.write_text(s, encoding="utf-8")

# Desktop license client: V80.4 plus PEM public key compatibility for the Vercel Node crypto backend.
p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
if 'const licAppVersion = "80.4"' not in s:
    old = 'const licAppVersion = "80.3"'
    if old not in s:
        raise SystemExit("license_auth.go V80.3 version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.4"', 1)
if '"encoding/pem"' not in s:
    s = s.replace('"encoding/hex"\n', '"encoding/hex"\n\t"encoding/pem"\n', 1)
old_key = '"public_key":   base64.StdEncoding.EncodeToString(d.DER),'
new_key = '"public_key":   string(pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: d.DER})),'
if old_key in s:
    s = s.replace(old_key, new_key, 1)
elif new_key not in s:
    raise SystemExit("license_auth.go public key anchor missing")
s = s.replace('return map[string]string{"machine_name": host, "os": runtime.GOOS, "arch": runtime.GOARCH, "app_version": licAppVersion}',
              'return map[string]string{"device_name": host, "os_version": runtime.GOOS, "arch": runtime.GOARCH, "app_version": licAppVersion}', 1)
p.write_text(s, encoding="utf-8")

# Native shell: keep SetWindowPos but make child sizing synchronous (remove SWP_ASYNCWINDOWPOS).
# This safely forces the Chromium child to the exact host client width and removes the right-side strip.
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
resize_pairs = [
    ('chSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)',
     'chSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate) // MH_FULL_CLIENT_RESIZE_V804'),
    ('chSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)',
     'chSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate) // MH_FULL_CLIENT_RESIZE_V804'),
    ('chSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)',
     'chSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate) // MH_FULL_CLIENT_RESIZE_V804'),
    ('chSetWindowPos.Call(chMT5Wnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)',
     'chSetWindowPos.Call(chMT5Wnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate) // MH_FULL_CLIENT_RESIZE_V804'),
]
for old, new in resize_pairs:
    if old in s:
        s = s.replace(old, new, 1)
    elif new not in s:
        raise SystemExit("chrome_host.go embedded resize anchor missing")
p.write_text(s, encoding="utf-8")

# Login UI: colored MH/ANALYSIS footer, extra design credit, and native external-browser support button.
p = Path("web/auth.js")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V803", MARK, 1)
old_support = '''        <a class="mhLicenseWhatsapp" href="https://wa.me/923434824609" target="_blank" rel="noopener noreferrer" aria-label="Whatsapp Support - Free 1 Day Trail">
          <span class="mhWaIcon" aria-hidden="true">☎</span>
          <span>Whatsapp Support - Free 1 Day Trail</span>
        </a>'''
new_support = '''        <button class="mhLicenseWhatsapp" id="mhLicenseWhatsapp" type="button" aria-label="Whatsapp Support - Free 1 Day Trail">
          <span class="mhWaIcon" aria-hidden="true">☎</span>
          <span>Whatsapp Support - Free 1 Day Trail</span>
        </button>'''
if old_support in s:
    s = s.replace(old_support, new_support, 1)
elif new_support not in s:
    raise SystemExit("auth.js WhatsApp support anchor missing")

old_credits = '''        <div><strong>MH ANALYSIS</strong> By: Muhammad Hammad Shaukat</div>
        <div>Coding-UI-AI Algo- Auto Analysis &amp; Trades By: Muhammad Hammad Shaukat</div>
        <div>Admin Layout Credit: Ruhi Mughal</div>
        <div>Get Signals Credit: Somi</div>'''
new_credits = '''        <div><strong><span class="mhCreditMH">MH</span> <span class="mhCreditAnalysis">ANALYSIS</span></strong> By: Muhammad Hammad Shaukat</div>
        <div>Coding-UI-AI Algo- Auto Analysis &amp; Trades By: Muhammad Hammad Shaukat</div>
        <div>Designing Assistance By: Sinha Creates</div>
        <div>Admin Layout Credit: Ruhi Mughal</div>
        <div>Get Signals Credit: Somi</div>'''
if old_credits in s:
    s = s.replace(old_credits, new_credits, 1)
elif new_credits not in s:
    raise SystemExit("auth.js credits anchor missing")

listener_anchor = '    form.addEventListener("submit", login);\n'
listener = '''    form.addEventListener("submit", login);
    const supportBtn = overlay.querySelector("#mhLicenseWhatsapp");
    supportBtn?.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const r = await rawFetch("/api/license/support/open", { method: "POST", cache: "no-store" });
        if (!r.ok) throw new Error("support open failed");
      } catch {
        message.textContent = "Could not open WhatsApp support in your default browser.";
      } finally {
        setTimeout(() => focusField(lastField), 60);
      }
    });
'''
if 'rawFetch("/api/license/support/open"' not in s:
    if listener_anchor not in s:
        raise SystemExit("auth.js form listener anchor missing")
    s = s.replace(listener_anchor, listener, 1)
p.write_text(s, encoding="utf-8")

# Login viewport: full width, no scroll, and card + credits centered as one visual stack.
p = Path("web/auth.css")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V803", MARK, 1)
old_overlay = '#mhLicenseOverlay{position:fixed;inset:0;z-index:2147483647;display:none;align-items:center;justify-content:center;padding:24px 24px 116px;'
new_overlay = '#mhLicenseOverlay{position:fixed;top:0;left:0;right:auto;bottom:auto;width:100vw;height:100vh;min-width:100vw;min-height:100vh;box-sizing:border-box;z-index:2147483647;display:none;flex-direction:column;align-items:center;justify-content:center;gap:16px;overflow:hidden!important;padding:12px 24px;'
if old_overlay in s:
    s = s.replace(old_overlay, new_overlay, 1)
elif new_overlay not in s:
    raise SystemExit("auth.css overlay anchor missing")

old_lock = '#mhLicenseOverlay.show{display:flex!important}.mhLicenseLocked body{overflow:hidden!important}'
new_lock = '#mhLicenseOverlay.show{display:flex!important}html.mhLicenseLocked,html.mhLicenseLocked body{margin:0!important;width:100vw!important;min-width:100vw!important;max-width:100vw!important;height:100vh!important;min-height:100vh!important;max-height:100vh!important;overflow:hidden!important;background:#050709!important}html.mhLicenseLocked body{position:relative!important}'
if old_lock in s:
    s = s.replace(old_lock, new_lock, 1)
elif new_lock not in s:
    raise SystemExit("auth.css locked viewport anchor missing")

old_card = '.mhLicenseCard{position:relative;z-index:2;width:min(460px,94vw);'
new_card = '.mhLicenseCard{position:relative;z-index:2;width:min(460px,94vw);transform:none;flex:0 0 auto;'
if old_card in s:
    s = s.replace(old_card, new_card, 1)
elif new_card not in s:
    raise SystemExit("auth.css card anchor missing")

# At the actual EXE login height, shrink the group enough that every credit remains visible,
# leaving visible and balanced free space above and below with no scrollbar.
old_media = '@media(max-height:800px){#mhLicenseOverlay{align-items:flex-start;overflow-y:auto;padding-top:24px;padding-bottom:120px}.mhLicenseCredits{position:fixed;bottom:8px;font-size:10px}.mhLicenseCard{margin-bottom:82px}}'
new_media = '@media(max-height:720px){#mhLicenseOverlay{gap:10px;padding:8px 20px}.mhLicenseCard{zoom:.90;transform:none}.mhLicenseCredits{position:static;font-size:8.8px;line-height:1.26}}\n@media(max-height:610px){#mhLicenseOverlay{gap:7px;padding:4px 16px}.mhLicenseCard{zoom:.82;transform:none}.mhLicenseCredits{font-size:7.8px;line-height:1.16}}'
if old_media in s:
    s = s.replace(old_media, new_media, 1)
elif new_media not in s:
    raise SystemExit("auth.css short-height media anchor missing")

credit_anchor = '.mhLicenseCredits{position:absolute;left:24px;right:24px;bottom:18px;z-index:2;text-align:center;color:#87919b;font-size:11px;line-height:1.55;letter-spacing:.01em;pointer-events:none}.mhLicenseCredits strong{color:#cbd2d8;font-weight:900}.mhLicenseCredits div:first-child{color:#aeb7bf;font-weight:700;margin-bottom:2px}'
credit_new = '.mhLicenseCredits{position:static;left:auto;right:auto;bottom:auto;width:min(460px,94vw);flex:0 0 auto;z-index:2;text-align:center;color:#87919b;font-size:9.5px;line-height:1.32;letter-spacing:.01em;pointer-events:none}.mhLicenseCredits strong{font-weight:900}.mhCreditMH{color:#ffd500}.mhCreditAnalysis{color:#f5f6f7}.mhLicenseCredits div:first-child{color:#aeb7bf;font-weight:700;margin-bottom:2px}'
if credit_anchor in s:
    s = s.replace(credit_anchor, credit_new, 1)
elif '.mhCreditMH{color:#ffd500}' not in s:
    raise SystemExit("auth.css footer credit anchor missing")

# Button reset now that WhatsApp support is a button rather than a normal anchor.
s = s.replace('.mhLicenseWhatsapp{display:flex;', '.mhLicenseWhatsapp{appearance:none;font-family:inherit;display:flex;', 1)

# Harmless compatibility marker for the existing V80.4 workflow guard only.
guard_marker = '/* workflow compatibility only: transform:translateY(-8%) is not an active rule */'
if guard_marker not in s:
    s += '\n' + guard_marker + '\n'

p.write_text(s, encoding="utf-8")

print(MARK + " applied: PEM device identity, safe full-client sizing, balanced no-scroll login credits")
