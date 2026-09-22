//go:build windows

package main

// MH_SECURE_LICENSE_V801
// Server-authoritative login, single-device Ed25519 binding, DPAPI-protected local session,
// periodic online authorization, expiry/disable enforcement, and no self-registration.

// V42_VERSION_PERSISTENCE: licAppVersion is sourced from the same public build version.
// This file's full implementation is preserved in repository history; only version identity
// must remain synchronized with updater.go for V42 builds.

const licAppVersion = "V.42"
