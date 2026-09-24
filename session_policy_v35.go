//go:build windows

package main

import "time"

// V35_SESSION_POLICY
// Login is still mandatory on every fresh MH Analysis process. Once the user has
// successfully logged in, inactivity must never log them out while that process
// remains open. Remote credentials/device/expiry are validated at login; the next
// fresh process requires credentials again through the existing manual-login gate.
func init() {
	licRemoteCheckMinSpacing = 365 * 24 * time.Hour
}
