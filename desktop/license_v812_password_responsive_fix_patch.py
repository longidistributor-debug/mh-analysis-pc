from pathlib import Path

MARK = "MH_PASSWORD_RESPONSIVE_FIX_V812"
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")

if MARK in s:
    print(MARK + ": already applied")
    raise SystemExit(0)

# V81.1 used Chromium kiosk to suppress a nested title bar. The exact child-window
# style hardening introduced in V81.1 is now authoritative, so kiosk is no longer
# needed. Kiosk can re-assert fullscreen geometry after a credential bubble closes,
# covering the native tabs and leaving the web viewport with stale dimensions.
s = s.replace('\t\t"--kiosk", // MH_SINGLE_NATIVE_FRAME_HARD_V811: no nested Chromium title bar\n', '')

# Disable Chromium's password manager at the profile level before browser launch.
# This preserves all existing MH Analysis/WhatsApp profile data while preventing
# "Save password?" / Google Password Manager UI from ever appearing in the EXE.
helper = r'''

// MH_PASSWORD_RESPONSIVE_FIX_V812: Browser credential UI is not part of MH Analysis.
// Keep it disabled in every embedded Chromium profile so it can never steal focus,
// resize/reframe the child window, or cover the app after account login.
func chDisableEmbeddedPasswordManager(profileDir string) {
	if profileDir == "" { return }
	def := filepath.Join(profileDir, "Default")
	_ = os.MkdirAll(def, 0755)
	prefPath := filepath.Join(def, "Preferences")
	prefs := map[string]any{}
	if b, err := os.ReadFile(prefPath); err == nil && len(b) > 0 {
		_ = json.Unmarshal(b, &prefs)
	}
	prefs["credentials_enable_service"] = false
	prefs["password_manager_leak_detection"] = false
	profilePrefs, _ := prefs["profile"].(map[string]any)
	if profilePrefs == nil { profilePrefs = map[string]any{} }
	profilePrefs["password_manager_enabled"] = false
	prefs["profile"] = profilePrefs
	if b, err := json.Marshal(prefs); err == nil {
		tmp := prefPath + ".mh.tmp"
		if os.WriteFile(tmp, b, 0600) == nil {
			_ = os.Rename(tmp, prefPath)
		}
	}
}
'''
anchor = '\nfunc chLaunchBrowser(profile, target string, debugPort int) (*exec.Cmd, uintptr, error) {'
if helper not in s:
    if anchor not in s:
        raise SystemExit("browser launch anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

profile_anchor = '\tprofileDir := chProfileDir(profile) // MH_PRESERVE_ORIGINAL_UI_V809: persistent original app state\n'
profile_new = profile_anchor + '\tchDisableEmbeddedPasswordManager(profileDir) // ' + MARK + '\n'
if profile_new not in s:
    if profile_anchor not in s:
        raise SystemExit("profileDir anchor missing")
    s = s.replace(profile_anchor, profile_new, 1)

# Chromium command-line belt-and-suspenders. These flags apply to Analysis,
# WhatsApp and any other embedded Chromium view, so no browser-owned password UI
# is allowed anywhere inside MH Analysis.
old_feature = '\t\t"--disable-features=TranslateUI",\n'
new_feature = '\t\t"--disable-features=TranslateUI,PasswordManagerOnboarding,PasswordManagerAccountStorage,PasswordLeakDetection,PasswordGeneration,PasswordSharing",\n\t\t"--disable-save-password-bubble", // ' + MARK + '\n'
if new_feature not in s:
    if old_feature not in s:
        raise SystemExit("disable-features anchor missing")
    s = s.replace(old_feature, new_feature, 1)

# Make host resize/restore/maximize authoritative after Chromium compositor events.
# The synchronous resize is still the primary path; the two short settles catch a
# late browser fullscreen/frame callback without touching HTML/CSS/JS.
old_case = '''\tcase chWMSize:\n\t\tchResizeChildren()\n\t\treturn 0'''
new_case = '''\tcase chWMSize:\n\t\tchResizeChildren()\n\t\tgo func() {\n\t\t\tfor _, d := range []time.Duration{35*time.Millisecond, 140*time.Millisecond} {\n\t\t\t\ttime.Sleep(d)\n\t\t\t\tchMu.Lock(); stopping := chStopping; chMu.Unlock()\n\t\t\t\tif stopping { return }\n\t\t\t\tchResizeChildren()\n\t\t\t}\n\t\t}() // ''' + MARK + ''': responsive restore/maximize settle\n\t\treturn 0'''
if new_case not in s:
    if old_case not in s:
        raise SystemExit("WM_SIZE anchor missing")
    s = s.replace(old_case, new_case, 1)

p.write_text(s, encoding="utf-8")
print(MARK + ": password prompts disabled; kiosk removed; resize/maximize responsiveness hardened")
