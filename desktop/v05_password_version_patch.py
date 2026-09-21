from pathlib import Path

# V.05: preserve V.04 behavior. Fix the login password field so it accepts
# keyboard text in the embedded browser while remaining visually masked.
p=Path('web/auth.js'); s=p.read_text(encoding='utf-8')
old='id="mhLicensePass" type="password" name="password" autocomplete="off"'
new='id="mhLicensePass" type="text" class="mhSecurePasswordInput" name="password" autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="text"'
if old not in s: raise SystemExit('password input anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

p=Path('web/auth.css'); s=p.read_text(encoding='utf-8')
css='''\n/* V.05: Chromium child-window compatible password entry; text is still masked. */\n#mhLicensePass.mhSecurePasswordInput{\n  -webkit-text-security:disc !important;\n  text-security:disc;\n  ime-mode:auto;\n  user-select:text;\n  -webkit-user-select:text;\n}\n'''
if 'mhSecurePasswordInput' not in s: s += css
p.write_text(s,encoding='utf-8')

p=Path('updater.go'); s=p.read_text(encoding='utf-8')
s=s.replace('const mhPublicVersionV001 = "V.04"','const mhPublicVersionV001 = "V.05"')
if 'const mhPublicVersionV001 = "V.05"' not in s: raise SystemExit('V.05 updater identity missing')
p.write_text(s,encoding='utf-8')

p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('id="mhUpdateVersionV001">V.04<','id="mhUpdateVersionV001">V.05<')
p.write_text(s,encoding='utf-8')
Path('VERSION').write_text('V.05\n',encoding='utf-8')
print('PASS V.05 password typing + version identity')
