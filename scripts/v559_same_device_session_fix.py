from pathlib import Path

p=Path('license_auth.go')
s=p.read_text(encoding='utf-8')

# Version only; no trading/MT5/EA logic is touched.
s=s.replace('const licAppVersion = "V.55.8"','const licAppVersion = "V.55.9"')

old='''\tlicRemoteCheckMinSpacing = 90 * time.Second\n)'''
new='''\tlicRemoteCheckMinSpacing = 90 * time.Second\n\t// Credentials are process-memory only and are used solely to renew an expired\n\t// server access session on the already-bound Windows device. Never written to disk.\n\tlicLoginUsername         string\n\tlicLoginPassword         string\n)'''
if old not in s: raise SystemExit('auth var anchor missing')
s=s.replace(old,new,1)

anchor='''func licEnsureAuthorized(force bool) bool {'''
helper=r'''// licReLoginSameDeviceLocked renews a server session after an access token expires.
// It deliberately repeats the exact normal login/device proof on the SAME bound machine.
// Expired/disabled licenses and device mismatches remain server-authoritative failures.
// Caller must already hold licMu.
func licReLoginSameDeviceLocked(username, password string) bool {
	username = strings.ToLower(strings.TrimSpace(username))
	if username == "" || password == "" {
		return false
	}
	d, err := licEnsureDevice()
	if err != nil {
		return false
	}
	status, ch, callErr := licPost("auth/challenge", map[string]any{"username": username, "device_id": d.ID}, "")
	if callErr != nil || status < 200 || status >= 300 || !ch.OK || ch.ChallengeID == "" || ch.Challenge == "" {
		return false
	}
	sig := ed25519.Sign(d.Private, []byte(ch.Challenge))
	status, rr, callErr := licPost("auth/login", map[string]any{
		"username": username,
		"password": password,
		"challenge_id": ch.ChallengeID,
		"signature": base64.StdEncoding.EncodeToString(sig),
		"public_key": base64.StdEncoding.EncodeToString(d.DER),
		"device_id": d.ID,
		"device_info": licMachineInfo(),
	}, "")
	if callErr != nil || status < 200 || status >= 300 || !rr.OK || strings.TrimSpace(rr.AccessToken) == "" {
		return false
	}
	if rr.User.DeviceID != "" && rr.User.DeviceID != d.ID {
		return false
	}
	ns := &licSession{Username: rr.User.Username, AccessToken: rr.AccessToken, User: rr.User}
	if err := licSaveSession(ns); err != nil {
		return false
	}
	licAuthorized = true
	licLastCheck = time.Now()
	licLastCode = ""
	licLastMessage = ""
	return true
}

'''
if anchor not in s: raise SystemExit('ensure auth anchor missing')
s=s.replace(anchor,helper+anchor,1)

old401='''\tlicSetRemoteError(status, vr, callErr)\n\tif status == http.StatusUnauthorized {\n\t\tlicClearSession()\n\t\tlicLastCode = "session_invalid"\n\t\tlicLastMessage = "Your secure session has ended. Please log in again."\n\t}\n\treturn false'''
new401='''\tlicSetRemoteError(status, vr, callErr)\n\tif status == http.StatusUnauthorized {\n\t\t// Access tokens can expire while the app remains open. Renew through the\n\t\t// normal signed SAME-device login instead of treating token age as logout.\n\t\t// The server still rejects expired/disabled licenses or another device.\n\t\tif licReLoginSameDeviceLocked(s.Username, licLoginPassword) {\n\t\t\treturn true\n\t\t}\n\t\tlicClearSession()\n\t\tlicLastCode = "session_invalid"\n\t\tlicLastMessage = "Your secure session has ended. Please log in again."\n\t}\n\treturn false'''
if old401 not in s: raise SystemExit('401 anchor missing')
s=s.replace(old401,new401,1)

oldsuccess='''\tif err == nil {\n\t\tlicAuthorized = true\n\t\tlicLastCheck = time.Now()\n\t\tlicLastCode = ""\n\t\tlicLastMessage = ""\n\t}'''
newsuccess='''\tif err == nil {\n\t\tlicAuthorized = true\n\t\tlicLastCheck = time.Now()\n\t\tlicLastCode = ""\n\t\tlicLastMessage = ""\n\t\t// Keep credentials only for this running process so an expired access token\n\t\t// can be renewed without an unwanted logout on the same bound PC.\n\t\tlicLoginUsername = q.Username\n\t\tlicLoginPassword = q.Password\n\t}'''
if oldsuccess not in s: raise SystemExit('login success anchor missing')
s=s.replace(oldsuccess,newsuccess,1)

# Explicit logout also forgets in-memory renewal credentials.
oldlogout='''\tlicMu.Lock()\n\tlicClearSession()\n\tlicMu.Unlock()'''
newlogout='''\tlicMu.Lock()\n\tlicClearSession()\n\tlicLoginUsername = ""\n\tlicLoginPassword = ""\n\tlicMu.Unlock()'''
if oldlogout not in s: raise SystemExit('logout anchor missing')
s=s.replace(oldlogout,newlogout,1)

p.write_text(s,encoding='utf-8')

# Standard V.55.9 version surfaces.
Path('VERSION').write_text('V.55.9\n',encoding='utf-8')
for fn in ['updater.go','web/index.html']:
    q=Path(fn); t=q.read_text(encoding='utf-8').replace('V.55.8','V.55.9'); q.write_text(t,encoding='utf-8')

print('V.55.9 same-device session fix applied')
