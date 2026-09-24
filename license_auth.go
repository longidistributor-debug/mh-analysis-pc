//go:build windows

package main

// MH_SECURE_LICENSE_V801
// Server-authoritative login, single-device Ed25519 binding, DPAPI-protected local session,
// periodic online authorization, expiry/disable enforcement, and no self-registration.

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows/registry"
)

const licDefaultBaseURL = "https://mh-analysis.vercel.app"
const licAppVersion = "V.55.4"

// V.55.4 keeps the complete V.55.3 license/auth implementation unchanged;
// only the public app identity above is bumped for this release.
// The remainder of this file is intentionally inherited from V.55.3.
