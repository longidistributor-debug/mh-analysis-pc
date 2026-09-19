//go:build windows

package main

import "syscall"

var (
	mhDPIUser32 = syscall.NewLazyDLL("user32.dll")
	mhDPIShcore = syscall.NewLazyDLL("shcore.dll")

	mhSetProcessDpiAwarenessContext = mhDPIUser32.NewProc("SetProcessDpiAwarenessContext")
	mhSetProcessDPIAware            = mhDPIUser32.NewProc("SetProcessDPIAware")
	mhSetProcessDpiAwareness        = mhDPIShcore.NewProc("SetProcessDpiAwareness")
)

// Windows otherwise DPI-virtualizes GetClientRect/SetWindowPos on 125%-200%
// display scaling. Chrome/Edge is already per-monitor DPI aware, so an unaware
// native parent makes the embedded browser occupy only part of the real screen.
// Enable Per-Monitor V2 before any application window is created so both the
// native shell and embedded browser use the same physical-pixel coordinate space.
func init() {
	// DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 is the pseudo-handle -4.
	if mhSetProcessDpiAwarenessContext.Find() == nil {
		if ok, _, _ := mhSetProcessDpiAwarenessContext.Call(^uintptr(3)); ok != 0 {
			return
		}
	}

	// Windows 8.1 fallback: PROCESS_PER_MONITOR_DPI_AWARE = 2.
	if mhSetProcessDpiAwareness.Find() == nil {
		if hr, _, _ := mhSetProcessDpiAwareness.Call(2); int32(hr) >= 0 {
			return
		}
	}

	// Windows 7 fallback.
	if mhSetProcessDPIAware.Find() == nil {
		mhSetProcessDPIAware.Call()
	}
}
