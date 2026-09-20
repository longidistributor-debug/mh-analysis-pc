from pathlib import Path

MARK = "MH_SECURE_LICENSE_V805"

# Bump desktop-reported license client version.
p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
if 'const licAppVersion = "80.5"' not in s:
    old = 'const licAppVersion = "80.4"'
    if old not in s:
        raise SystemExit("license_auth.go V80.4 version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.5"', 1)
p.write_text(s, encoding="utf-8")

# Keep the same login content, but mark the balanced V80.5 UI.
p = Path("web/auth.js")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    if "MH_SECURE_LICENSE_V804" not in s:
        raise SystemExit("auth.js V80.4 marker missing")
    s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)
p.write_text(s, encoding="utf-8")

# Balance the complete login group vertically: card + credits act as one centered stack.
# This makes the visual space above the form and below the credits equal while locked.
p = Path("web/auth.css")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    if "MH_SECURE_LICENSE_V804" not in s:
        raise SystemExit("auth.css V80.4 marker missing")
    s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)

old_overlay_bits = "display:none;align-items:center;justify-content:center;overflow:hidden!important;padding:24px 24px 116px;"
new_overlay_bits = "display:none;flex-direction:column;align-items:center;justify-content:center;gap:20px;overflow:hidden!important;padding:12px 24px;"
if old_overlay_bits in s:
    s = s.replace(old_overlay_bits, new_overlay_bits, 1)
elif new_overlay_bits not in s:
    raise SystemExit("auth.css overlay layout anchor missing")

# Remove the previous manual upward offset. The whole card+credits stack is now centered naturally.
if "transform:translateY(-4.5%);" in s:
    s = s.replace("transform:translateY(-4.5%);", "transform:none;", 1)
elif ".mhLicenseCard{position:relative" in s and "transform:none;" not in s:
    raise SystemExit("auth.css card offset anchor missing")

# Credits must participate in normal flex layout instead of being pinned to the bottom.
old_credit_pos = ".mhLicenseCredits{position:absolute;left:24px;right:24px;bottom:30px;"
new_credit_pos = ".mhLicenseCredits{position:static;left:auto;right:auto;bottom:auto;width:min(460px,94vw);flex:0 0 auto;"
if old_credit_pos in s:
    s = s.replace(old_credit_pos, new_credit_pos, 1)
elif new_credit_pos not in s:
    raise SystemExit("auth.css credits position anchor missing")

# Replace V80.4 short-height absolute positioning with compact centered stacking.
old_media_800 = "@media(max-height:800px){#mhLicenseOverlay{align-items:center;overflow:hidden!important;padding-top:12px;padding-bottom:96px}.mhLicenseCredits{position:absolute;bottom:24px;font-size:9.2px;line-height:1.36}.mhLicenseCard{transform:translateY(-4.5%) scale(.94);transform-origin:center center}}"
old_media_650 = "@media(max-height:650px){#mhLicenseOverlay{padding-bottom:88px}.mhLicenseCard{transform:translateY(-3%) scale(.85)}.mhLicenseCredits{bottom:18px;font-size:8.5px;line-height:1.28}}"
new_media = "@media(max-height:680px){#mhLicenseOverlay{gap:12px;padding:6px 20px}.mhLicenseCredits{position:static;font-size:9px;line-height:1.3}.mhLicenseCard{zoom:.94;transform:none}}\n@media(max-height:610px){#mhLicenseOverlay{gap:8px;padding:4px 16px}.mhLicenseCard{zoom:.86;transform:none}.mhLicenseCredits{font-size:8.2px;line-height:1.2}}"
if old_media_800 in s:
    s = s.replace(old_media_800, new_media, 1)
    if old_media_650 in s:
        s = s.replace(old_media_650, "", 1)
elif new_media not in s:
    raise SystemExit("auth.css short-height media anchors missing")

p.write_text(s, encoding="utf-8")

print(MARK + " applied: card and credits centered as one balanced no-scroll login stack")
