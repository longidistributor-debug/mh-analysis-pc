from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'

# Keep Account Login mandatory on every fresh EXE launch. Do not silently consume
# an old authorized session and bypass the visible username/password form.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('''      hide(j);
      location.reload();''','''      hide(j);
      // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: remain in this loaded UI; no login bypass reload.''')
    s=s.replace('''    build();
    show("login_required");
    status(false);''','''    build();
    show("login_required");
    // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: never auto-authorize a previous session at startup.''')
    s=s.replace('''    if(v.verified && !v.required && overlay && overlay.classList.contains("show")) status(false);''','''    // Login overlay is intentionally user-driven on every fresh launch.''')
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Hidden update overlay must never swallow KEYS / EXIT / Get Signal clicks.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

# Update lock must be reversible. Older patches may format this block differently,
# so normalize the first required-calculation block instead of depending on one stale anchor.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
required_pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(required_pat,s)
if not m:
    raise SystemExit('required-version calculation missing')
replacement=m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'
s=s[:m.start()]+replacement+s[m.end():]
p.write_text(s,encoding='utf-8')

print(MARK+': mandatory visible login restored; hidden update overlay non-interactive; native tab lock reversible')
