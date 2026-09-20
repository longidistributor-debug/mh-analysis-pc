from pathlib import Path

MARK = "MH_SECURE_LICENSE_V807"


def replace_once(s, old, new, label):
    if new in s:
        return s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return s.replace(old, new, 1)

# -----------------------------------------------------------------------------
# Desktop version only. V80.6 same-PC identity persistence and async EXIT remain.
# -----------------------------------------------------------------------------
p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
s = replace_once(s, 'const licAppVersion = "80.6"', 'const licAppVersion = "80.7"', "license version")
p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Auth UI repair:
# - NEVER hide the auth layer based on local/session-storage hints.
# - First show a deterministic dark VERIFYING state while /status is checked.
# - Only show username/password when the server says login is required.
# - Successful login unlocks the current DOM directly; NO page reload/navigation.
# - Authorization dispatches mh-license-authorized, which starts the main app once.
# -----------------------------------------------------------------------------
p = Path("web/auth.js")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V806", MARK, 1)

s = s.replace('  const SESSION_HINT = "mhLicenseSessionHintV806";\n', '')
s = s.replace('''    if (code !== "internet_required" && code !== "database_unavailable") {
      try { localStorage.removeItem(SESSION_HINT); } catch {}
    }
''', '')

show_anchor = '''  function show(code, msg) {
    build();
    code = normCode(code);
'''
show_replacement = '''  function showChecking(msg = "Verifying your secure license…") {
    build();
    overlay.classList.add("show", "mhLicenseChecking");
    document.documentElement.classList.add("mhLicenseLocked");
    document.documentElement.dataset.mhLicenseAuthorized = "0";
    const title = overlay.querySelector("#mhLicenseTitle");
    const sub = overlay.querySelector(".mhLicenseSub");
    if (title) title.textContent = "Secure Access";
    if (sub) sub.textContent = "Checking your account, license validity and authorized Windows device.";
    form.hidden = true;
    const supportBtn = overlay.querySelector("#mhLicenseWhatsapp");
    if (supportBtn) supportBtn.hidden = true;
    message.textContent = msg;
    message.dataset.code = "checking";
    meta.textContent = "";
  }

  function show(code, msg) {
    build();
    code = normCode(code);
    overlay.classList.remove("mhLicenseChecking");
    document.documentElement.dataset.mhLicenseAuthorized = "0";
    const title = overlay.querySelector("#mhLicenseTitle");
    const sub = overlay.querySelector(".mhLicenseSub");
    if (title) title.textContent = "Account Login";
    if (sub) sub.textContent = "This installation requires an active administrator-issued license and one authorized Windows device.";
    form.hidden = false;
    const supportBtn = overlay.querySelector("#mhLicenseWhatsapp");
    if (supportBtn) supportBtn.hidden = false;
'''
s = replace_once(s, show_anchor, show_replacement, "checking state")

s = s.replace('    try { localStorage.setItem(SESSION_HINT, "1"); } catch {}\n', '')
hide_anchor = '''    resetDashboardViewport();
    if (data?.username) {
'''
hide_replacement = '''    resetDashboardViewport();
    document.documentElement.dataset.mhLicenseAuthorized = "1";
    setTimeout(() => window.dispatchEvent(new CustomEvent("mh-license-authorized", { detail: data || {} })), 0);
    if (data?.username) {
'''
s = replace_once(s, hide_anchor, hide_replacement, "authorized event")

old_login = '''      passInput.value = "";
      hide(j);
      // Full page initialization is retained, but the persistent session hint
      // prevents the empty login form from flashing during the reload.
      try { sessionStorage.setItem("mhLicensePostLoginV806", "1"); } catch {}
      resetDashboardViewport();
      location.reload();'''
new_login = '''      passInput.value = "";
      message.textContent = "Access granted. Loading MH Analysis…";
      hide(j);'''
s = replace_once(s, old_login, new_login, "direct post-login transition")

old_boot = '''  build();
  let skipLoginFlash = false;
  try {
    skipLoginFlash = sessionStorage.getItem("mhLicensePostLoginV806") === "1" || localStorage.getItem(SESSION_HINT) === "1";
    sessionStorage.removeItem("mhLicensePostLoginV806");
  } catch {}
  resetDashboardViewport();
  if (!skipLoginFlash) show("login_required");
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);'''
new_boot = '''  build();
  resetDashboardViewport();
  showChecking();
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);'''
s = replace_once(s, old_boot, new_boot, "authoritative auth bootstrap")

old_logout = '''    logout: async () => {
      try { localStorage.removeItem(SESSION_HINT); sessionStorage.removeItem("mhLicensePostLoginV806"); } catch {}
      await rawFetch("/api/license/logout", { method: "POST" }).catch(() => {});
      location.reload();
    },'''
new_logout = '''    logout: async () => {
      showChecking("Signing out securely…");
      await rawFetch("/api/license/logout", { method: "POST" }).catch(() => {});
      userInput.value = "";
      passInput.value = "";
      show("login_required");
    },'''
s = replace_once(s, old_logout, new_logout, "navigation-free logout")

if "mhLicenseSessionHintV806" in s or "mhLicensePostLoginV806" in s:
    raise SystemExit("stale V80.6 auth hints remain")

p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Main page app bootstrap: app.js never runs before authoritative authorization.
# -----------------------------------------------------------------------------
p = Path("web/index.html")
s = p.read_text(encoding="utf-8")
old_scripts = '''<script src="/auth.js"></script>
<script src="/lightweight-charts.standalone.production.js"></script>
<script src="/app.js"></script>
<script src="/runtime-fixes.js"></script>'''
new_scripts = '''<script src="/auth.js"></script>
<script src="/lightweight-charts.standalone.production.js"></script>
<script>
// MH_AUTH_GATED_APP_LOADER_V807: app code starts only after server authorization.
(() => {
  let started = false;
  const loadScript = (src) => new Promise((resolve, reject) => {
    const el = document.createElement("script");
    el.src = src;
    el.async = false;
    el.onload = resolve;
    el.onerror = () => reject(new Error("Failed to load " + src));
    document.body.appendChild(el);
  });
  const start = async () => {
    if (started || document.documentElement.dataset.mhLicenseAuthorized !== "1") return;
    started = true;
    try {
      await loadScript("/app.js");
      await loadScript("/runtime-fixes.js");
      window.scrollTo(0, 0);
      window.dispatchEvent(new Event("resize"));
    } catch (err) {
      started = false;
      console.error("MH authorized app bootstrap failed", err);
    }
  };
  window.addEventListener("mh-license-authorized", start);
  if (document.documentElement.dataset.mhLicenseAuthorized === "1") start();
})();
</script>'''
s = replace_once(s, old_scripts, new_scripts, "main auth-gated loader")
p.write_text(s, encoding="utf-8")

p = Path("web/auth.css")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V806", MARK, 1)
extra = '''
/* MH_SECURE_LICENSE_V807: deterministic startup verification, never blank white. */
#mhLicenseOverlay.mhLicenseChecking .mhLicenseCard{min-height:260px;display:flex;flex-direction:column;justify-content:center}
#mhLicenseOverlay.mhLicenseChecking .mhLicenseTag{align-self:flex-start}
#mhLicenseOverlay.mhLicenseChecking .mhLicenseMessage{color:#d9e0e5;text-align:left;margin-top:12px}
#mhLicenseOverlay.mhLicenseChecking .mhLicenseCredits{opacity:.92}
#mhLicenseOverlay [hidden]{display:none!important}
html.mhLicenseLocked body{background:#050709!important}
'''
if "deterministic startup verification" not in s:
    s += extra
p.write_text(s, encoding="utf-8")

# Also remove stale Analysis-profile crash/session state before every browser launch.
# This specifically fixes the second-open blank-white Chromium app-mode regression
# while preserving Local Storage/cookies used by MH Analysis.
browser_patch = Path("vercel-auth/license_v807_browser_restart_fix.py").read_text(encoding="utf-8")
exec(compile(browser_patch, "vercel-auth/license_v807_browser_restart_fix.py", "exec"), {"__name__": "__main__"})

print(MARK + ": authoritative verify-first UI + direct no-reload app unlock applied")
