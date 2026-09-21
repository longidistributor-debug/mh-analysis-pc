//go:build windows

package main

// V.23 regression-safe runtime corrections.
// This file is intentionally additive: it does not replace the working V.22
// authentication, updater, analysis, records, or WhatsApp sending code.

import (
    "strings"
    "syscall"
    "time"
    "unsafe"
)

var (
    v23GetWindowText       = chUser32.NewProc("GetWindowTextW")
    v23GetWindowTextLength = chUser32.NewProc("GetWindowTextLengthW")
)

func init() {
    go v23RuntimeGuard()
}

// v23RuntimeGuard makes Signal Link visibility deterministic and recovers MT5
// windows even when a broker launcher reuses an already-running terminal PID.
func v23RuntimeGuard() {
    ticker := time.NewTicker(150 * time.Millisecond)
    defer ticker.Stop()
    for range ticker.C {
        if chStopping {
            return
        }

        chViewMu.Lock()
        view := chDesiredView
        chViewMu.Unlock()

        // WhatsApp owns the separate Signal Link navigation option.
        // It must never float over MH Analysis, Records, or MT5.
        if chSignalLinkBtn != 0 {
            if view == 2 {
                chShowWindow.Call(chSignalLinkBtn, chSWShow)
                chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
            } else {
                chShowWindow.Call(chSignalLinkBtn, chSWHide)
            }
        }

        // When MT5 is selected, recover a real top-level MetaTrader terminal
        // regardless of whether it was launched by this process or reused by
        // the broker launcher. This fixes the blank/non-embedded MT5 case.
        if view == 4 {
            chMu.Lock()
            missing := chMT5Wnd == 0
            chMu.Unlock()
            if missing {
                if wnd := v23FindMT5MainWindow(); wnd != 0 {
                    chShowWindow.Call(wnd, chSWHide)
                    chAttachBrowser(wnd)
                    chMu.Lock()
                    if chMT5Wnd == 0 {
                        chMT5Wnd = wnd
                    }
                    chMu.Unlock()
                    chResizeChildren()
                    chApplyDesiredBrowserView()
                    go mt5ApplyLatestQueued()
                }
            }
        }
    }
}

func v23FindMT5MainWindow() uintptr {
    var found uintptr
    cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND {
            return 1
        }
        vis, _, _ := chIsWindowVisible.Call(hwnd)
        if vis == 0 {
            return 1
        }

        title := strings.ToLower(strings.TrimSpace(v23WindowTitle(hwnd)))
        cls := strings.ToLower(strings.TrimSpace(v23WindowClass(hwnd)))

        // MT5 broker builds normally expose MetaTrader in the title; some use
        // MetaQuotes class names. Exclude browser/host windows defensively.
        isMT5 := strings.Contains(title, "metatrader 5") ||
            strings.Contains(title, "meta trader 5") ||
            strings.Contains(cls, "metaquotes")
        if !isMT5 || strings.Contains(cls, "chrome_widgetwin") || strings.Contains(title, "mh analysis") {
            return 1
        }

        found = hwnd
        return 0
    })
    chEnumWindows.Call(cb, 0)
    return found
}

func v23WindowTitle(hwnd uintptr) string {
    n, _, _ := v23GetWindowTextLength.Call(hwnd)
    if n == 0 {
        return ""
    }
    buf := make([]uint16, int(n)+1)
    got, _, _ := v23GetWindowText.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
    if got == 0 {
        return ""
    }
    return syscall.UTF16ToString(buf[:got])
}

func v23WindowClass(hwnd uintptr) string {
    buf := make([]uint16, 256)
    n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
    if n == 0 {
        return ""
    }
    return syscall.UTF16ToString(buf[:n])
}
