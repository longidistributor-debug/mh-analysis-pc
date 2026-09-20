from pathlib import Path

MARK = "MH_SECURE_LICENSE_V808"

p = Path("license_auth.go")
s = p.read_text(encoding="utf-8")

if 'const licAppVersion = "80.8"' not in s:
    old = 'const licAppVersion = "80.7"'
    if old not in s:
        raise SystemExit("V80.7 license version anchor missing")
    s = s.replace(old, 'const licAppVersion = "80.8"', 1)

# Keep one in-process copy so repeated logins during the same EXE run can never
# race into a second key generation or depend on a temporarily locked file.
var_anchor = '\tlicRemoteCheckMinSpacing = 90 * time.Second\n)'
var_new = '\tlicRemoteCheckMinSpacing = 90 * time.Second\n\tlicDeviceMu              sync.Mutex // '+MARK+'\n\tlicDeviceMem             *licDevice\n)'
if var_new not in s:
    if var_anchor not in s:
        raise SystemExit("license var anchor missing")
    s = s.replace(var_anchor, var_new, 1)

# Add a third machine-DPAPI recovery copy under ProgramData. LocalAppData remains
# the primary location, so existing installs are fully backward compatible.
path_anchor = 'func licDevicePath() string        { return filepath.Join(licRootDir(), "license-device-v1.bin") }\nfunc licDeviceMachinePath() string { return filepath.Join(licRootDir(), "license-device-v1-machine.bin") } // MH_SECURE_LICENSE_V806\nfunc licSessionPath() string       { return filepath.Join(licRootDir(), "license-session-v1.bin") }'
path_new = '''func licDevicePath() string        { return filepath.Join(licRootDir(), "license-device-v1.bin") }
func licDeviceMachinePath() string { return filepath.Join(licRootDir(), "license-device-v1-machine.bin") } // MH_SECURE_LICENSE_V806
func licDeviceRecoveryPath() string {
\tb := strings.TrimSpace(os.Getenv("PROGRAMDATA"))
\tif b == "" { b = licRootDir() } else { b = filepath.Join(b, "MHAnalysis") }
\treturn filepath.Join(b, "license-device-v1-recovery.bin")
} // '''+MARK+'''
func licSessionPath() string       { return filepath.Join(licRootDir(), "license-session-v1.bin") }'''
if path_new not in s:
    if path_anchor not in s:
        raise SystemExit("device path anchor missing")
    s = s.replace(path_anchor, path_new, 1)

# Windows os.Rename does not replace an existing destination reliably. The old
# writer could leave a perfectly valid .tmp file behind and then report failure.
# Remove destination immediately before rename; .tmp is intentionally retained on
# a rename failure and V80.8 knows how to recover from it next launch.
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
        raise SystemExit("user DPAPI writer anchor missing")
    s = s.replace(old_write, new_write, 1)

start = s.find('func licEnsureDevice() (*licDevice, error) {')
end = s.find('\nfunc licLoadSession()', start)
if start < 0 or end < 0:
    raise SystemExit("licEnsureDevice anchors missing")

new_block = r'''func licPersistDeviceCopies(disk licDeviceDisk) error {
	var ok int
	var errs []string
	if err := licWriteProtected(licDevicePath(), disk); err == nil {
		ok++
	} else {
		errs = append(errs, "user="+err.Error())
	}
	if err := licWriteProtectedMachine(licDeviceMachinePath(), disk); err == nil {
		ok++
	} else {
		errs = append(errs, "machine="+err.Error())
	}
	if err := licWriteProtectedMachine(licDeviceRecoveryPath(), disk); err == nil {
		ok++
	} else {
		errs = append(errs, "recovery="+err.Error())
	}
	if ok == 0 {
		return fmt.Errorf("could not persist secure device identity: %s", strings.Join(errs, " / "))
	}
	return nil
}

func licReadDeviceCandidate(path string, machine bool) (*licDevice, licDeviceDisk, error) {
	var disk licDeviceDisk
	var err error
	if machine {
		err = licReadProtectedMachine(path, &disk)
	} else {
		err = licReadProtected(path, &disk)
	}
	if err != nil {
		return nil, disk, err
	}
	if disk.PrivateKey == "" {
		return nil, disk, errors.New("stored device key is empty")
	}
	d, err := licDeviceFromDisk(disk)
	return d, disk, err
}

func licEnsureDevice() (*licDevice, error) {
	licDeviceMu.Lock()
	defer licDeviceMu.Unlock()

	if licDeviceMem != nil {
		return licDeviceMem, nil
	}

	type candidate struct {
		path    string
		machine bool
	}
	candidates := []candidate{
		{licDevicePath(), false},
		{licDevicePath() + ".tmp", false},
		{licDeviceMachinePath(), true},
		{licDeviceMachinePath() + ".tmp", true},
		{licDeviceRecoveryPath(), true},
		{licDeviceRecoveryPath() + ".tmp", true},
	}

	identityArtifactExists := false
	for _, c := range candidates {
		if st, err := os.Stat(c.path); err == nil && !st.IsDir() {
			identityArtifactExists = true
			d, disk, err := licReadDeviceCandidate(c.path, c.machine)
			if err == nil && d != nil {
				// Self-heal every canonical copy from the exact same recovered key.
				// No new identity is generated, so the server sees the same device.
				_ = licPersistDeviceCopies(disk)
				for _, tmp := range []string{licDevicePath()+".tmp", licDeviceMachinePath()+".tmp", licDeviceRecoveryPath()+".tmp"} {
					_ = os.Remove(tmp)
				}
				licDeviceMem = d
				return licDeviceMem, nil
			}
		}
	}

	// Never rotate silently when an old identity artifact exists. Generating a new
	// key here would make the same PC appear as a second device and cause the exact
	// DEVICE_NOT_AUTHORIZED problem V80.8 is designed to prevent.
	if identityArtifactExists {
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
	disk := licDeviceDisk{PrivateKey: base64.StdEncoding.EncodeToString(priv)}
	if err := licPersistDeviceCopies(disk); err != nil {
		return nil, err
	}
	sum := sha256.Sum256(der)
	licDeviceMem = &licDevice{Private: priv, Public: pub, DER: der, ID: hex.EncodeToString(sum[:])}
	return licDeviceMem, nil
}
'''

s = s[:start] + new_block + s[end:]

# Make the UI explain the only remaining safe failure case. If all encrypted
# copies are physically corrupted/unrecoverable, an admin device reset is required;
# silently inventing a new key would weaken one-device enforcement.
old_err = '''\td, err := licEnsureDevice()
\tif err != nil {
\t\tw.WriteHeader(http.StatusInternalServerError)
\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": "device_key_failed", "message": "Could not create secure device identity."})
\t\treturn
\t}'''
new_err = '''\td, err := licEnsureDevice()
\tif err != nil {
\t\tw.WriteHeader(http.StatusInternalServerError)
\t\tcode := "device_key_failed"
\t\tmessage := "Could not create secure device identity."
\t\tif strings.Contains(err.Error(), "existing secure device identity could not be recovered") {
\t\t\tcode = "device_identity_recovery_required"
\t\t\tmessage = "This Windows device has an old secure identity that could not be recovered. Use Admin Reset Device once, then log in again."
\t\t}
\t\t_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "code": code, "message": message})
\t\treturn
\t}'''
if new_err not in s:
    if old_err not in s:
        raise SystemExit("login device error anchor missing")
    s = s.replace(old_err, new_err, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": durable same-device key reuse, tmp self-heal, LocalMachine recovery copy, and no silent key rotation applied")
