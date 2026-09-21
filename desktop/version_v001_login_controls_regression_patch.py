from pathlib import Path

MARK='MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'

# Keep Account Login mandatory on every fresh EXE launch. Do not silently consume
# an old authorized session and bypass the visible username/password form.
p=Path('web/auth.js')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    # Successful login must unlock the already-loaded UI without reloading into an
    # automatic session check that skips the login screen.
    s=s.replace('''      hide(j);
      location.reload();''','''      hide(j);
      // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: remain in this loaded UI; no login bypass reload.''')
    # Final pre-login bootstrap: verified-current => SHOW login and wait for user.
    s=s.replace('''    build();
    show("login_required");
    status(false);''','''    build();
    show("login_required");
    // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX: never auto-authorize a previous session at startup.''')
    # Do not let the periodic license status hide a login form the user has not submitted.
    s=s.replace('''    if(v.verified && !v.required && overlay && overlay.classList.contains("show")) status(false);''','''    // Login overlay is intentionally user-driven on every fresh launch.''')
    s='// '+MARK+'\n'+s
p.write_text(s,encoding='utf-8')

# Hidden update overlay must be physically non-interactive so it cannot swallow
# KEYS / EXIT / Get Signal or any normal application click.
p=Path('web/update-v001.css')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s += '''\n/* MH_V001_LOGIN_CONTROLS_REGRESSION_FIX */
#mhMandatoryUpdateV001.mhUpdateHiddenV001{display:none!important;visibility:hidden!important;pointer-events:none!important;}
#mhMandatoryUpdateV001:not(.mhUpdateHiddenV001){pointer-events:auto!important;}
'''
p.write_text(s,encoding='utf-8')

# Update lock is exact and reversible: current version explicitly unlocks the native
# four-tab bar; only a positively verified newer mandatory release hides it.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
old='''    required := m.Mandatory && mhNewerVersionV001(m.Version, mhPublicVersionV001)
    if required { go chSetMandatoryUpdateLockV001(true) }'''
new='''    required := m.Mandatory && mhNewerVersionV001(m.Version, mhPublicVersionV001)
    go chSetMandatoryUpdateLockV001(required) // MH_V001_LOGIN_CONTROLS_REGRESSION_FIX'''
if old not in s:
    raise SystemExit('update lock anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

print(MARK+': mandatory visible login restored; hidden update overlay non-interactive; native tab lock reversible')
