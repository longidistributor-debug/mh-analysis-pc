from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')

# Manual login unlocks the current process; never reload into a saved server session.
s=re.sub(r'(passInput\.value\s*=\s*"";\s*(?:\n\s*message\.textContent\s*=\s*"[^"]*";)?\s*\n\s*hide\(j\);)\s*\n\s*location\.reload\(\);',r'\1\n      // '+MARK+': manual login unlocks this process without reload.',s,count=1)

# The final exact-behavior patch owns startup/update precheck. Enforce fresh login
# at the end of that precheck instead of depending on a legacy recurring timer.
# Existing backend session may remain for saved data, but it must never bypass the
# visible username/password prompt on a new EXE process.
if 'async function mhV001Bootstrap' in s:
    # Remove immediate auth status calls inside bootstrap only.
    start=s.index('async function mhV001Bootstrap')
    end=s.find('\n}',start)
    if end < 0: raise SystemExit('bootstrap end missing')
    end += 2
    block=s[start:end]
    block=re.sub(r'(?m)^\s*showChecking\([^\n]*\);\s*\n?','',block)
    block=re.sub(r'(?m)^\s*status\(false\);\s*\n?','',block)
    # Insert login after update verification path completes. If a verified required
    # update exists, update JS/native lock remains in control and login stays behind it.
    if MARK not in block:
        pos=block.rfind('}')
        block=block[:pos]+'  show("login_required");\n  // '+MARK+': fresh EXE always requires username + password; persistent app data untouched.\n'+block[pos:]
    s=s[:start]+block+s[end:]
else:
    # Fallback for older generated auth: normalize final startup sequence.
    s=re.sub(r'(?m)^\s*showChecking\([^\n]*\);\s*\n?','',s)
    # Remove only startup immediate status call, not status() function body/calls used after login.
    matches=list(re.finditer(r'(?m)^\s*status\(false\);\s*$',s))
    if matches:
        m=matches[-1]; s=s[:m.start()]+'  show("login_required");\n  // '+MARK+': fresh EXE login enforced; saved app data untouched.\n'+s[m.end():]
    elif 'show("login_required")' not in s:
        raise SystemExit('no safe final auth bootstrap anchor found')

if MARK not in s: s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Hidden update overlay cannot swallow toolbar/login controls.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s+='''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

# Lock toolbar only when backend verifies a genuinely newer mandatory version.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(pat,s)
if not m: raise SystemExit('required-version calculation missing')
s=s[:m.start()]+m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // '+MARK+s[m.end():]
p.write_text(s,encoding='utf-8')
print(MARK+': V.01 fresh login enforced at final update-aware bootstrap; data preserved; toolbar lock reversible')
