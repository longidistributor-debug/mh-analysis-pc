from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Successful manual login stays in the current loaded UI; never reload into a
# server session that can bypass the next visible-login contract.
s=re.sub(
    r'(passInput\.value\s*=\s*"";\s*\n\s*(?:message\.textContent\s*=\s*"[^"]*";\s*\n\s*)?hide\(j\);)\s*\n\s*location\.reload\(\);',
    r'\1\n      // '+MARK+': manual login succeeded; keep this loaded UI.',
    s,
    count=1,
)

# V807 creates a verify-first bootstrap. Desktop V.01 must not call /status on
# fresh process startup because an existing backend session could auto-authorize.
patterns=[
    r'build\(\);\s*\n\s*resetDashboardViewport\(\);\s*\n\s*showChecking\(\);\s*\n\s*status\(false\);\s*\n\s*setInterval\(\(\)\s*=>\s*status\(false\),\s*4\s*\*\s*60\s*\*\s*1000\);',
    r'build\(\);\s*\n\s*show\("login_required"\);\s*\n\s*status\(false\);\s*\n\s*setInterval\(\(\)\s*=>\s*status\(false\),\s*4\s*\*\s*60\s*\*\s*1000\);'
]
replacement='''build();
  resetDashboardViewport();
  show("login_required");
  // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: credentials are mandatory every fresh EXE process.
  // Analysis/WhatsApp/Records/MT5 persistent application data is not cleared here.
  setInterval(() => {
    // Validate only after this running process was manually unlocked.
    if (!overlay?.classList.contains("show")) status(false);
  }, 4 * 60 * 1000);'''
changed=False
for pat in patterns:
    ns,n=re.subn(pat,replacement,s,count=1)
    if n:
        s=ns;changed=True;break
if not changed:
    raise SystemExit('fresh-login bootstrap missing: expected verify-first or login/status block')
if MARK not in s:
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

p=Path('updater.go')
s=p.read_text(encoding='utf-8')
required_pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(required_pat,s)
if not m:
    raise SystemExit('required-version calculation missing')
replacement2=m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // '+MARK
s=s[:m.start()]+replacement2+s[m.end():]
p.write_text(s,encoding='utf-8')

print(MARK+': verify-first startup replaced by mandatory fresh login; app data preserved; toolbar lock reversible')
