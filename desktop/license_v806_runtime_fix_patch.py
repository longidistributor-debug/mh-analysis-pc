from pathlib import Path

MARK = "MH_SECURE_LICENSE_V806"


def replace_once(s, old, new, label):
    if new in s:
        return s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return s.replace(old, new, 1)

# -----------------------------------------------------------------------------
# Desktop license client: never silently rotate an existing device identity.
# Keep a second machine-DPAPI backup so the same physical Windows PC can recover
# the exact Ed25519 key if the user-scope DPAPI copy becomes unavailable.
# -----------------------------------------------------------------------------
p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")
s = replace_once(s, 'const licAppVersion = "80.4"', 'const licAppVersion = "80.6"', "license version")

s = replace_once(
    s,
    'func licDevicePath() string  { return filepath.Join(licRootDir(), "license-device-v1.bin") }\nfunc licSessionPath() string { return filepath.Join(licRootDir(), "license-session-v1.bin") }',
    'func licDevicePath() string        { return filepath.Join(licRootDir(), "license-device-v1.bin") }\nfunc licDeviceMachinePath() string { return filepath.Join(licRootDir(), "license-device-v1-machine.bin") } // '+MARK+'\nfunc licSessionPath() string       { return filepath.Join(licRootDir(), "license-session-v1.bin") }',
    "device paths",
)

machine_helpers = r'''

// MH_SECURE_LICENSE_V806: LocalMachine DPAPI backup of the same private key.
// This backup is not a second device identity; it only prevents accidental key
// rotation on the already-authorized Windows PC.
func licDPAPIProtectMachine(data []byte) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("empty dpapi input")
	}
	in := licBlobFromBytes(data)
	var out licDataBlob
	r, _, e := licCryptProtectData.Call(
		uintptr(unsafe.Pointer(&in)),
		0, 0, 0, 0,
		uintptr(0x1|0x4), // CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE
		uintptr(unsafe.Pointer(&out)),
	)
	if r == 0 {
		return nil, fmt.Errorf("CryptProtectData(LocalMachine) failed: %v", e)
	}
	defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	return licBytesFromBlob(out), nil
}

func licDPAPIUnprotectMachine(data []byte) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("empty dpapi input")
	}
	in := licBlobFromBytes(data)
	var out licDataBlob
	r, _, e := licCryptUnprotectData.Call(
		uintptr(unsafe.Pointer(&in)),
		0, 0, 0, 0, 0,
		uintptr(0x1),
		uintptr(unsafe.Pointer(&out)),
	)
	if r == 0 {
		return nil, fmt.Errorf("CryptUnprotectData(LocalMachine) failed: %v", e)
	}
	defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)))
	return licBytesFromBlob(out), nil
}

func licWriteProtectedMachine(path string, v any) error {
	raw, err := json.Marshal(v)
	if err != nil {
		return err
	}
	enc, err := licDPAPIProtectMachine(raw)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err = os.WriteFile(tmp, enc, 0600); err != nil {
		return err
	}
	_ = os.Remove(path)
	return os.Rename(tmp, path)
}

func licReadProtectedMachine(path string, v any) error {
	enc, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	raw, err := licDPAPIUnprotectMachine(enc)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, v)
}

func licDeviceFromDisk(disk licDeviceDisk) (*licDevice, error) {
	raw, err := base64.StdEncoding.DecodeString(disk.PrivateKey)
	if err != nil || len(raw) != ed25519.PrivateKeySize {
		return nil, errors.New("stored device key is invalid")
	}
	priv := ed25519.PrivateKey(raw)
	pub := priv.Public().(ed25519.PublicKey)
	der, err := x509.MarshalPKIXPublicKey(pub)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(der)
	return &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}, nil
}
'''
anchor = '\nfunc licWriteProtected(path string, v any) error {'
if machine_helpers not in s:
    if anchor not in s:
        raise SystemExit("machine DPAPI helper anchor missing")
    s = s.replace(anchor, machine_helpers + anchor, 1)

start = s.find('func licEnsureDevice() (*licDevice, error) {')
end = s.find('\nfunc licLoadSession()', start)
if start < 0 or end < 0:
    raise SystemExit("licEnsureDevice function anchors missing")
new_ensure = r'''func licEnsureDevice() (*licDevice, error) {
	primaryExists := false
	backupExists := false
	if st, err := os.Stat(licDevicePath()); err == nil && !st.IsDir() {
		primaryExists = true
	}
	if st, err := os.Stat(licDeviceMachinePath()); err == nil && !st.IsDir() {
		backupExists = true
	}

	var disk licDeviceDisk
	if err := licReadProtected(licDevicePath(), &disk); err == nil && disk.PrivateKey != "" {
		if d, err := licDeviceFromDisk(disk); err == nil {
			// Migrate/refresh the machine-level backup without changing identity.
			_ = licWriteProtectedMachine(licDeviceMachinePath(), disk)
			return d, nil
		}
	}

	var backup licDeviceDisk
	if err := licReadProtectedMachine(licDeviceMachinePath(), &backup); err == nil && backup.PrivateKey != "" {
		if d, err := licDeviceFromDisk(backup); err == nil {
			// Restore the user-scope copy from the exact same machine key.
			_ = licWriteProtected(licDevicePath(), backup)
			return d, nil
		}
	}

	// Critical anti-rotation rule: if an identity file already exists, do not
	// generate a different key. A different key would make this same PC look like
	// a second device to the license server.
	if primaryExists || backupExists {
		return nil, errors.New("existing secure device identity could not be recovered")
	}

	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	der, err := x509.MarshalPKIXPublicKey(pub)
	if err != nil {
		return nil, err
	}
	disk = licDeviceDisk{PrivateKey: base64.StdEncoding.EncodeToString(priv)}
	primaryErr := licWriteProtected(licDevicePath(), disk)
	backupErr := licWriteProtectedMachine(licDeviceMachinePath(), disk)
	if primaryErr != nil && backupErr != nil {
		return nil, fmt.Errorf("could not persist secure device identity: %v / %v", primaryErr, backupErr)
	}
	sum := sha256.Sum256(der)
	return &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}, nil
}
'''
s = s[:start] + new_ensure + s[end:]
p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Login UX: keep full app initialization via reload, but suppress the blank login
# flash after a successful login and force the dashboard back to its organized top.
# -----------------------------------------------------------------------------
p = Path("web/auth.js")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)

s = replace_once(
    s,
    '  const normCode = (v) => String(v || "").trim().toLowerCase();\n',
    '''  const normCode = (v) => String(v || "").trim().toLowerCase();
  const SESSION_HINT = "mhLicenseSessionHintV806";
  try { history.scrollRestoration = "manual"; } catch {}

  function resetDashboardViewport() {
    const reset = () => {
      try { window.scrollTo(0, 0); } catch {}
      try { if (document.scrollingElement) document.scrollingElement.scrollTop = 0; } catch {}
      try { document.documentElement.scrollTop = 0; } catch {}
      try { document.body.scrollTop = 0; } catch {}
      try { document.querySelector(".appShell")?.scrollTo?.(0, 0); } catch {}
      try { window.dispatchEvent(new Event("resize")); } catch {}
    };
    reset();
    requestAnimationFrame(reset);
    setTimeout(reset, 60);
    setTimeout(reset, 220);
  }
''',
    "auth viewport helper",
)

s = replace_once(
    s,
    '''  function show(code, msg) {
    build();
    code = normCode(code);
    overlay.classList.add("show");''',
    '''  function show(code, msg) {
    build();
    code = normCode(code);
    if (code !== "internet_required" && code !== "database_unavailable") {
      try { localStorage.removeItem(SESSION_HINT); } catch {}
    }
    overlay.classList.add("show");''',
    "show session hint clear",
)

s = replace_once(
    s,
    '''  function hide(data) {
    build();
    overlay.classList.remove("show");
    document.documentElement.classList.remove("mhLicenseLocked");''',
    '''  function hide(data) {
    build();
    overlay.classList.remove("show");
    document.documentElement.classList.remove("mhLicenseLocked");
    try { localStorage.setItem(SESSION_HINT, "1"); } catch {}
    resetDashboardViewport();''',
    "hide direct dashboard",
)

s = replace_once(
    s,
    '        if (reloadAfter) location.reload();',
    '        if (reloadAfter) resetDashboardViewport();',
    "status reload suppression",
)

s = replace_once(
    s,
    '''      passInput.value = "";
      hide(j);
      location.reload();''',
    '''      passInput.value = "";
      hide(j);
      // Full page initialization is retained, but the persistent session hint
      // prevents the empty login form from flashing during the reload.
      try { sessionStorage.setItem("mhLicensePostLoginV806", "1"); } catch {}
      resetDashboardViewport();
      location.reload();''',
    "post login reload transition",
)

s = replace_once(
    s,
    '''  build();
  show("login_required");
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);''',
    '''  build();
  let skipLoginFlash = false;
  try {
    skipLoginFlash = sessionStorage.getItem("mhLicensePostLoginV806") === "1" || localStorage.getItem(SESSION_HINT) === "1";
    sessionStorage.removeItem("mhLicensePostLoginV806");
  } catch {}
  resetDashboardViewport();
  if (!skipLoginFlash) show("login_required");
  status(false);
  setInterval(() => status(false), 4 * 60 * 1000);''',
    "auth bootstrap flash suppression",
)

s = replace_once(
    s,
    '''    logout: async () => {
      await rawFetch("/api/license/logout", { method: "POST" }).catch(() => {});
      location.reload();
    },''',
    '''    logout: async () => {
      try { localStorage.removeItem(SESSION_HINT); sessionStorage.removeItem("mhLicensePostLoginV806"); } catch {}
      await rawFetch("/api/license/logout", { method: "POST" }).catch(() => {});
      location.reload();
    },''',
    "logout hint cleanup",
)
p.write_text(s, encoding="utf-8")

# Keep CSS marker synchronized with the V80.6 guard; layout itself is retained.
p = Path("web/auth.css")
s = p.read_text(encoding="utf-8")
s = s.replace("MH_SECURE_LICENSE_V804", MARK, 1)
p.write_text(s, encoding="utf-8")

# -----------------------------------------------------------------------------
# Native EXIT: hide immediately, do browser/process cleanup off the UI thread,
# then destroy the host only when cleanup has completed. This removes the Windows
# "Not Responding" hang while keeping child-process cleanup reliable.
# -----------------------------------------------------------------------------
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

s = replace_once(
    s,
    '\tchWMClose       = 0x0010\n\tchWMDestroy     = 0x0002\n',
    '\tchWMClose       = 0x0010\n\tchWMDestroy     = 0x0002\n\tchWMShutdownDone = 0x805A // '+MARK+'\n',
    "shutdown message constant",
)

s = replace_once(
    s,
    '\tchStopping    bool\n',
    '\tchStopping    bool\n\tchCloseOnce   sync.Once // '+MARK+'\n',
    "shutdown once state",
)

old_close = '''\tcase chWMClose:
\t\tchShowWindow.Call(hwnd,chSWHide)
\t\tchPrepareBrowserWindowsForShutdown()
\t\tchStopBrowsers()
\t\tchDestroyWindow.Call(hwnd)
\t\treturn 0
\tcase chWMDestroy:
\t\tchStopBrowsers()
\t\tchPostQuitMessage.Call(0)
\t\treturn 0'''
new_close = '''\tcase chWMClose:
\t\t// '''+MARK+''': disappear immediately; never block the Win32 UI thread on
\t\t// Chrome/Edge/MT5 process cleanup.
\t\tchShowWindow.Call(hwnd, chSWHide)
\t\tchCloseOnce.Do(func() {
\t\t\tgo func() {
\t\t\t\tchPrepareBrowserWindowsForShutdown()
\t\t\t\tchStopBrowsers()
\t\t\t\tpostMessage(hwnd, chWMShutdownDone, 0, 0)
\t\t\t}()
\t\t})
\t\treturn 0
\tcase chWMShutdownDone:
\t\tchDestroyWindow.Call(hwnd)
\t\treturn 0
\tcase chWMDestroy:
\t\tchPostQuitMessage.Call(0)
\t\treturn 0'''
if old_close in s:
    s = s.replace(old_close, new_close, 1)
elif MARK not in s or 'case chWMShutdownDone:' not in s:
    raise SystemExit("native shutdown block anchor missing")

p.write_text(s, encoding="utf-8")

print(MARK + ": direct organized login transition, persistent same-PC key, and non-blocking EXIT applied")
