from pathlib import Path

MARK = "MH_SECURE_LICENSE_V808"

p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")

if 'const licAppVersion = "80.8"' not in s:
    old = 'const licAppVersion = "80.7"'
    if old not in s:
        raise SystemExit("V80.7 license version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.8"', 1)

# V80.8 no longer needs random device-key generation. The identity is derived
# deterministically from the Windows installation instead.
s = s.replace('\t"crypto/rand"\n', '', 1)

# The V80.6 random-key design depended on local DPAPI files. If Windows secure
# storage could not be written/read, the same PC could accidentally get another
# key or fail before login. V80.8 makes the device signing key deterministic from
# Windows installation identifiers. Same Windows installation => same Ed25519 key
# on every login/restart, independent of temp/profile/session files.
var_anchor = '''\tlicCryptProtectData      = licCrypt32.NewProc("CryptProtectData")
\tlicCryptUnprotectData    = licCrypt32.NewProc("CryptUnprotectData")
\tlicLocalFree             = licKernel32.NewProc("LocalFree")'''
var_new = '''\tlicCryptProtectData      = licCrypt32.NewProc("CryptProtectData")
\tlicCryptUnprotectData    = licCrypt32.NewProc("CryptUnprotectData")
\tlicLocalFree             = licKernel32.NewProc("LocalFree")
\tlicAdvapi32              = syscall.NewLazyDLL("advapi32.dll") // '''+MARK+'''
\tlicRegOpenKeyExW         = licAdvapi32.NewProc("RegOpenKeyExW")
\tlicRegQueryValueExW      = licAdvapi32.NewProc("RegQueryValueExW")
\tlicRegCloseKey           = licAdvapi32.NewProc("RegCloseKey")
\tlicGetVolumeInformationW = licKernel32.NewProc("GetVolumeInformationW")'''
if var_new not in s:
    if var_anchor not in s:
        raise SystemExit("WinAPI var anchor missing")
    s = s.replace(var_anchor, var_new, 1)

mem_anchor = '\tlicRemoteCheckMinSpacing = 90 * time.Second\n)'
mem_new = '\tlicRemoteCheckMinSpacing = 90 * time.Second\n\tlicDeviceMu              sync.Mutex // '+MARK+'\n\tlicDeviceMem             *licDevice\n)'
if mem_new not in s:
    if mem_anchor not in s:
        raise SystemExit("license var anchor missing")
    s = s.replace(mem_anchor, mem_new, 1)

# Windows os.Rename does not reliably replace an existing destination. Fix the
# protected session writer too, so repeated logins can overwrite their token.
old_write = '''\tif err = os.WriteFile(tmp, enc, 0600); err != nil {
\t\treturn err
\t}
\treturn os.Rename(tmp, path)
}'''
new_write = '''\tif err = os.WriteFile(tmp, enc, 0600); err != nil {
\t\treturn err
\t}
\t_ = os.Remove(path) // '''+MARK+''' Windows-safe replacement
\treturn os.Rename(tmp, path)
}'''
if new_write not in s:
    if old_write not in s:
        raise SystemExit("protected writer anchor missing")
    s = s.replace(old_write, new_write, 1)

start = s.find('func licEnsureDevice() (*licDevice, error) {')
end = s.find('\nfunc licLoadSession()', start)
if start < 0 or end < 0:
    raise SystemExit("licEnsureDevice anchors missing")

new_block = r'''func licReadMachineGuid() string {
	const hklm = uintptr(0x80000002)
	const keyRead = uintptr(0x20019)
	const wow64_64 = uintptr(0x0100)
	keyName, _ := syscall.UTF16PtrFromString(`SOFTWARE\Microsoft\Cryptography`)
	valueName, _ := syscall.UTF16PtrFromString("MachineGuid")
	for _, access := range []uintptr{keyRead | wow64_64, keyRead} {
		var h uintptr
		r, _, _ := licRegOpenKeyExW.Call(hklm, uintptr(unsafe.Pointer(keyName)), 0, access, uintptr(unsafe.Pointer(&h)))
		if r != 0 || h == 0 {
			continue
		}
		var typ uint32
		var cb uint32
		r, _, _ = licRegQueryValueExW.Call(h, uintptr(unsafe.Pointer(valueName)), 0, uintptr(unsafe.Pointer(&typ)), 0, uintptr(unsafe.Pointer(&cb)))
		if r == 0 && cb >= 2 && cb <= 1024 {
			buf := make([]uint16, int(cb/2)+1)
			r, _, _ = licRegQueryValueExW.Call(h, uintptr(unsafe.Pointer(valueName)), 0, uintptr(unsafe.Pointer(&typ)), uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&cb)))
			licRegCloseKey.Call(h)
			if r == 0 {
				if v := strings.TrimSpace(syscall.UTF16ToString(buf)); v != "" {
					return strings.ToLower(v)
				}
			}
		} else {
			licRegCloseKey.Call(h)
		}
	}
	return ""
}

func licSystemVolumeSerial() string {
	drive := strings.TrimSpace(os.Getenv("SystemDrive"))
	if drive == "" {
		drive = "C:"
	}
	root, err := syscall.UTF16PtrFromString(strings.TrimRight(drive, `\/`) + `\`)
	if err != nil {
		return ""
	}
	var serial uint32
	r, _, _ := licGetVolumeInformationW.Call(uintptr(unsafe.Pointer(root)), 0, 0, uintptr(unsafe.Pointer(&serial)), 0, 0, 0, 0)
	if r == 0 {
		return ""
	}
	return fmt.Sprintf("%08x", serial)
}

func licDeterministicDevice() (*licDevice, error) {
	guid := licReadMachineGuid()
	vol := licSystemVolumeSerial()
	if guid == "" && vol == "" {
		return nil, errors.New("stable Windows machine identity is unavailable")
	}
	seed := sha256.Sum256([]byte("MH-ANALYSIS-DEVICE-V808|" + guid + "|" + vol))
	priv := ed25519.NewKeyFromSeed(seed[:])
	pub := priv.Public().(ed25519.PublicKey)
	der, err := x509.MarshalPKIXPublicKey(pub)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(der)
	return &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}, nil
}

func licEnsureDevice() (*licDevice, error) {
	licDeviceMu.Lock()
	defer licDeviceMu.Unlock()
	if licDeviceMem != nil {
		return licDeviceMem, nil
	}

	// Authoritative V80.8 identity: deterministic for this Windows installation.
	// It does not rotate when EXE restarts, the LocalAppData profile changes, or
	// old DPAPI identity/session files are missing/corrupt.
	d, err := licDeterministicDevice()
	if err != nil {
		return nil, err
	}
	licDeviceMem = d

	// Best-effort compatibility copy only. Login does NOT depend on this write.
	// This keeps older builds recoverable without making V80.8 fragile.
	disk := licDeviceDisk{PrivateKey: base64.StdEncoding.EncodeToString(d.Private)}
	_ = licWriteProtected(licDevicePath(), disk)
	return licDeviceMem, nil
}
'''
s = s[:start] + new_block + s[end:]

# A successful online login must not be rejected solely because Windows DPAPI
# session persistence is unavailable. Keep the session in memory and allow the
# user to log in again on the next launch; the stable device key remains identical.
old_save = '''func licSaveSession(s *licSession) error {
\ts.SavedAt = time.Now()
\tif err := licWriteProtected(licSessionPath(), s); err != nil {
\t\treturn err
\t}
\tlicSessionMem = s
\treturn nil
}'''
new_save = '''func licSaveSession(s *licSession) error {
\ts.SavedAt = time.Now()
\tlicSessionMem = s
\t// '''+MARK+''': persistence is best-effort. Authorization remains valid in this
\t// EXE run even when a Windows profile blocks DPAPI/file persistence.
\t_ = licWriteProtected(licSessionPath(), s)
\treturn nil
}'''
if new_save not in s:
    if old_save not in s:
        raise SystemExit("licSaveSession anchor missing")
    s = s.replace(old_save, new_save, 1)

# Replace the old generic creation failure with a stable-machine-identity message.
old_err = '''\td, err := licEnsureDevice()
\tif err != nil {
\t\tw.WriteHeader(http.StatusInternalServerError)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_key_failed", "message": "Could not create secure device identity."})
\t\treturn
\t}'''
new_err = '''\td, err := licEnsureDevice()
\tif err != nil {
\t\tw.WriteHeader(http.StatusInternalServerError)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_identity_unavailable", "message": "Could not read this Windows device identity. Restart Windows and try again."})
\t\treturn
\t}'''
if new_err not in s:
    if old_err not in s:
        raise SystemExit("login device error anchor missing")
    s = s.replace(old_err, new_err, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": deterministic same-Windows device key + repeated-login safe session handling applied")
