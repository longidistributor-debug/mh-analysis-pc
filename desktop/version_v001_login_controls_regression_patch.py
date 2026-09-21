from pathlib import Path
import re

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'

# Rule: saved application/trading state survives, but AUTHORIZATION NEVER survives
# an EXE restart. Every fresh process must visibly require username + password.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
# Successful manual login must unlock the current loaded app without a reload that
# can immediately consume the server session and bypass the intended UI state.
s=s.replace('''      hide(j);
      location.reload();''','''      hide(j);
      // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: manual login succeeded; unlock this loaded UI.''')
# Fresh startup: build + show login. Do NOT call status(false), because an existing
# server cookie/session is not permission to skip username/password on a new EXE run.
s=s.replace('''  build();
  show("login_required");
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);''','''  build();
  show("login_required");
  // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: every fresh EXE launch requires credentials.
  // Saved Analysis/WhatsApp/Records/MT5 state remains untouched.
  setInterval(() => {
    // Only validate an already-unlocked running session; never auto-unlock a fresh launch.
    if (!overlay?.classList.contains("show")) status(false);
  }, 4 * 60 * 1000);''')
if MARK not in s:
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Hidden update overlay must never swallow normal app controls after login.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

# Update lock exact/reversible: only a verified newer mandatory version hides the
# native four-button toolbar. Current V.01 must explicitly unlock it again.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
required_pat=r'(required\s*:=\s*m\.Mandatory\s*&&\s*mhNewerVersionV001\(m\.Version,\s*mhPublicVersionV001\)\s*\n)(?:\s*if\s+required\s*\{\s*go\s+chSetMandatoryUpdateLockV001\(true\)\s*\}|\s*go\s+chSetMandatoryUpdateLockV001\([^\n]+\))?'
m=re.search(required_pat,s)
if not m:
    raise SystemExit('required-version calculation missing')
replacement=m.group(1)+'    go chSetMandatoryUpdateLockV001(required) // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'
s=s[:m.start()]+replacement+s[m.end():]
p.write_text(s,encoding='utf-8')

print(MARK+': credentials required every fresh launch; app data preserved; toolbar unlock reversible')
