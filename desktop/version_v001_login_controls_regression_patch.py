from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'

# Saved application/trading state survives, but authorization never bypasses the
# visible login on a fresh EXE process.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Successful manual login unlocks the already loaded UI. Do not reload into a
# server session that can bypass the visible-login contract.
s=re.sub(
    r'(passInput\.value\s*=\s*"";\s*\n\s*hide\(j\);)\s*\n\s*location\.reload\(\);',
    r'\1\n      // '+MARK+': manual login succeeded; keep this loaded UI.',
    s,
    count=1,
)

# Fresh startup must always stop at Account Login. Match formatting flexibly.
startup_pat=r'(\bbuild\(\);\s*\n\s*show\("login_required"\);)\s*\n\s*status\(false\);\s*\n\s*setInterval\(\(\)\s*=>\s*status\(false\),\s*4\s*\*\s*60\s*\*\s*1000\);'
m=re.search(startup_pat,s)
if not m:
    raise SystemExit('fresh-login startup block missing')
startup=m.group(1)+'''\n  // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: every fresh EXE launch requires credentials.\n  // Saved Analysis/WhatsApp/Records/MT5 state remains untouched.\n  setInterval(() => {\n    // Validate only after manual login has already unlocked this running process.\n    if (!overlay?.classList.contains("show")) status(false);\n  }, 4 * 60 * 1000);'''
s=s[:m.start()]+startup+s[m.end():]

if MARK not in s:
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Hidden update overlay must never swallow normal app controls after login.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */\n#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}\n#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}\n'''
p.write_text(s,encoding='utf-8')

# Only a verified newer mandatory release locks the native toolbar; current V.01
# explicitly restores normal MH Analysis / WhatsApp / Records / MT5 controls.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
required_pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(required_pat,s)
if not m:
    raise SystemExit('required-version calculation missing')
replacement=m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // '+MARK
s=s[:m.start()]+replacement+s[m.end():]
p.write_text(s,encoding='utf-8')

print(MARK+': fresh startup login forced; saved app data preserved; toolbar lock reversible')
