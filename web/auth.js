// MH_SECURE_LICENSE_V803
(() => {
  const rawFetch = window.fetch.bind(window);
  let overlay, message, form, userInput, passInput, button, meta;
  let checking = false;
  let manualLoginThisProcess = false;
  let lastField = "username";

  const normCode = (v) => String(v || "").trim().toLowerCase();

  function textFor(code, fallback) {
    code = normCode(code);
    const map = {
      login_required: "Enter your username and password to activate MH Analysis.",
      authorization_required: "Please log in to continue.",
      invalid_credentials: "Invalid username or password.",
      license_expired: "Your access has expired. Contact administrator for renewal.",
      account_disabled: "This account is disabled. Contact administrator.",
      license_not_started: "Your license is not active yet. Contact administrator.",
      device_not_authorized: "This account is already activated on another device. Contact administrator.",
      internet_required: "Internet connection is required to verify your MH Analysis license.",
      database_unavailable: "License database is temporarily unavailable.",
      server_not_configured: "License server is not configured.",
      too_many_attempts: "Too many login attempts. Please try again later.",
      session_invalid: "Your secure session has ended. Please log in again.",
      session_revoked: "Your session was revoked. Please log in again.",
      invalid_challenge: "Secure device verification expired. Please try logging in again.",
      invalid_device_key: "This device identity could not be verified.",
      invalid_device_signature: "This device identity could not be verified.",
      device_key_unavailable: "Authorized device key is unavailable. Contact administrator for device reset.",
      local_secure_storage_failed: "Windows secure storage failed. Please contact administrator."
    };
    return map[code] || fallback || "Authorization failed. Contact administrator.";
  }

  function focusField(which = lastField) {
    const target = which === "password" ? passInput : userInput;
    if (!target || !overlay?.classList.contains("show")) return;
    try { window.focus(); } catch {}
    try {
      target.disabled = false;
      target.readOnly = false;
      target.focus({ preventScroll: true });
      const n = target.value.length;
      target.setSelectionRange(n, n);
    } catch {}
  }

  function wireInput(input, which) {
    input.disabled = false;
    input.readOnly = false;
    input.tabIndex = 0;
    input.setAttribute("aria-label", which === "password" ? "Password" : "Username");
    const takeFocus = () => {
      lastField = which;
      setTimeout(() => focusField(which), 0);
      setTimeout(() => focusField(which), 60);
    };
    input.addEventListener("pointerdown", takeFocus, true);
    input.addEventListener("mousedown", takeFocus, true);
    input.addEventListener("click", takeFocus, true);
    input.addEventListener("focus", () => { lastField = which; });
  }

  function build() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.id = "mhLicenseOverlay";
    overlay.innerHTML = `
      <div class="mhLicenseCard" role="dialog" aria-modal="true" aria-labelledby="mhLicenseTitle">
        <div class="mhLicenseLogo">
          <img class="mhLicenseBrandMark" src="/mh-logo.png" alt="MH logo" />
          <span class="mhLicenseBrandText"><b>MH</b><span>ANALYSIS</span></span>
        </div>
        <div class="mhLicenseTag">SECURE ACCESS</div>
        <h1 id="mhLicenseTitle">Account Login</h1>
        <p class="mhLicenseSub">This installation requires an active administrator-issued license and one authorized Windows device.</p>
        <form id="mhLicenseForm" autocomplete="on">
          <label>USERNAME<input id="mhLicenseUser" type="text" name="username" autocomplete="username" inputmode="text" spellcheck="false"></label>
          <label>PASSWORD<input id="mhLicensePass" type="password" name="password" autocomplete="current-password"></label>
          <button id="mhLicenseBtn" type="submit">LOGIN</button>
        </form>
        <div id="mhLicenseMessage" class="mhLicenseMessage"></div>
        <div id="mhLicenseMeta" class="mhLicenseMeta"></div>
        <a class="mhLicenseWhatsapp" href="https://wa.me/923434824609" target="_blank" rel="noopener noreferrer" aria-label="Whatsapp Support - Free 1 Day Trail">
          <span class="mhWaIcon" aria-hidden="true">☎</span>
          <span>Whatsapp Support - Free 1 Day Trail</span>
        </a>
      </div>
      <footer class="mhLicenseCredits" aria-label="MH Analysis credits">
        <div><strong>MH ANALYSIS</strong> By: Muhammad Hammad Shaukat</div>
        <div>Coding-UI-AI Algo- Auto Analysis &amp; Trades By: Muhammad Hammad Shaukat</div>
        <div>Admin Layout Credit: Ruhi Mughal</div>
        <div>Get Signals Credit: Somi</div>
      </footer>`;
    document.body.appendChild(overlay);
    form = overlay.querySelector("#mhLicenseForm");
    userInput = overlay.querySelector("#mhLicenseUser");
    passInput = overlay.querySelector("#mhLicensePass");
    button = overlay.querySelector("#mhLicenseBtn");
    message = overlay.querySelector("#mhLicenseMessage");
    meta = overlay.querySelector("#mhLicenseMeta");
    wireInput(userInput, "username");
    wireInput(passInput, "password");
    form.addEventListener("submit", login);

    overlay.addEventListener("pointerdown", (e) => {
      if (e.target === userInput) lastField = "username";
      else if (e.target === passInput) lastField = "password";
    }, true);

    window.addEventListener("focus", () => {
      if (overlay?.classList.contains("show") && document.activeElement !== userInput && document.activeElement !== passInput) {
        setTimeout(() => focusField(lastField), 25);
      }
    });
  }

  function show(code, msg) {
    build();
    code = normCode(code);
    overlay.classList.add("show");
    document.documentElement.classList.add("mhLicenseLocked");
    message.textContent = textFor(code, msg);
    message.dataset.code = code;
    meta.textContent = code === "license_expired" ? "LICENSE EXPIRED • Contact administrator for renewal" : "";
    setTimeout(() => focusField(lastField), 30);
    setTimeout(() => focusField(lastField), 180);
    setTimeout(() => focusField(lastField), 650);
  }

  function hide(data) {
    build();
    overlay.classList.remove("show");
    document.documentElement.classList.remove("mhLicenseLocked");
    if (data?.username) {
      document.documentElement.dataset.mhLicenseUser = data.username;
      document.documentElement.dataset.mhLicenseUntil = data.valid_until || "";
    }
  }

  async function status(reloadAfter = false) {
    // CLEAN_RUNTIME_V02: never let a previous session authorize a fresh EXE.
    if (!manualLoginThisProcess) { show("login_required"); return; }
    if (checking) return;
    checking = true;
    try {
      const r = await rawFetch("/api/license/status", { cache: "no-store" });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.authorized) {
        hide(j);
        if (reloadAfter) location.reload();
      } else {
        show(j.code || j.error, j.message);
      }
    } catch {
      show("internet_required");
    } finally {
      checking = false;
    }
  }

  async function login(e) {
    e?.preventDefault();
    const username = userInput.value.trim();
    const password = passInput.value;
    if (!username || !password) {
      message.textContent = "Enter username and password.";
      focusField(!username ? "username" : "password");
      return;
    }
    button.disabled = true;
    button.textContent = "VERIFYING…";
    message.textContent = "Checking account, expiry and authorized device…";
    try {
      const r = await rawFetch("/api/license/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        cache: "no-store"
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.authorized) {
        show(j.code || j.error, j.message);
        return;
      }
      passInput.value = "";
      manualLoginThisProcess = true;
      hide(j);
      document.documentElement.dataset.mhLicenseAuthorized = "1";
      window.dispatchEvent(new CustomEvent("mh-license-authorized", { detail: j }));
    } catch {
      show("internet_required");
    } finally {
      button.disabled = false;
      button.textContent = "LOGIN";
    }
  }

  window.fetch = async function(input, init) {
    const r = await rawFetch(input, init);
    try {
      const u = typeof input === "string" ? input : input?.url || "";
      if ((r.status === 401 || r.status === 403) && String(u).includes("/api/") && !String(u).includes("/api/license/")) {
        const j = await r.clone().json().catch(() => ({}));
        show(j.code || j.error || "authorization_required", j.message);
      }
    } catch {}
    return r;
  };

  window.MHLicense = {
    logout: async () => {
      await rawFetch("/api/license/logout", { method: "POST" }).catch(() => {});
      location.reload();
    },
    status
  };

  build();
  // Update gate (when present) stays above this overlay. If the app is current,
  // Account Login is the first usable screen on every EXE start.
  show("login_required");
  setInterval(() => { if (manualLoginThisProcess) status(false); }, 4 * 60 * 1000);
})();
