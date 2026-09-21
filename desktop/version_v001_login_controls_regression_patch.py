from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Do not reload after successful manual login.
s=re.sub(r'(passInput\.value\s*=\s*"";\s*(?:\n\s*message\.textContent\s*=\s*"[^"]*";)?\s*\n\s*hide\(j\);)\s*\n\s*location\.reload\(\);',r'\1\n      // '+MARK+': manual login unlocks this process without reload.',s,count=1)

# The previous patches may wrap startup with update-precheck code, so do not rely
# on one historical bootstrap shape. Find the final recurring auth status timer;
# remove any immediate status/showChecking call in the local startup prefix and
# force Account Login immediately before that timer.
timer=re.search(r'(?m)^([ \t]*)setInterval\(\(\)\s*=>\s*status\(false\),\s*4\s*\*\s*60\s*\*\s*1000\);',s)
if not timer:
    # Already-patched multiline timer is acceptable/idempotent.
    timer2=re.search(r'setInterval\(\(\)\s*=>\s*\{\s*[^}]*overlay[^}]*status\(false\);\s*\}\s*,\s*4\s*\*\s*60\s*\*\s*1000\);',s,re.S)
    if not timer2:
        raise SystemExit('auth recurring status timer missing')
else:
    start=max(s.rfind('\n',0,timer.start()-700),0)
    prefix=s[start:timer.start()]
    prefix=re.sub(r'(?m)^\s*showChecking\([^\n]*\);\s*\n?','',prefix)
    prefix=re.sub(r'(?m)^\s*status\(false\);\s*\n?','',prefix)
    # If an old login show exists here, normalize to exactly one.
    prefix=re.sub(r'(?m)^\s*show\("login_required"\);\s*\n?','',prefix)
    forced='  show("login_required");\n  // '+MARK+': every fresh EXE process requires username + password.\n  // Persistent Analysis/WhatsApp/Records/MT5 data is intentionally untouched.\n'
    guarded='''  setInterval(() => {
    if (!overlay?.classList.contains("show")) status(false);
  }, 4 * 60 * 1000);'''
    s=s[:start]+prefix+forced+guarded+s[timer.end():]

if MARK not in s:
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s+='''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

p=Path('updater.go')
s=p.read_text(encoding='utf-8')
pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(pat,s)
if not m: raise SystemExit('required-version calculation missing')
s=s[:m.start()]+m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // '+MARK+s[m.end():]
p.write_text(s,encoding='utf-8')
print(MARK+': V.01 fresh login enforced independently of prior bootstrap shape; saved app data untouched; toolbar lock reversible')
