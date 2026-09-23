//go:build windows

package main

import (
    "syscall"
    "time"
    "unsafe"
)

// MH_MT5_FULL_TERMINAL_REPAINT_V553
// MT5 is embedded as its real main terminal HWND. Some broker builds do not
// repaint the menu/toolbars after SetParent until the mouse passes over them.
// While MH MT5 is the selected view, keep the complete terminal sized/visible
// and explicitly repaint the terminal plus all child controls. No chart-only
// extraction is used here.
func v553RepaintMT5FullTerminal(hwnd uintptr) {
    if hwnd == 0 || hostHWND == 0 {
        return
    }
    parent, _, _ := v36GetParent.Call(hwnd)
    if parent != hostHWND {
        return
    }

    var r chRect
    chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
    w := int32(r.R - r.L)
    h := int32(r.B - r.T - int32(barH))
    if w < 1 { w = 1 }
    if h < 1 { h = 1 }

    chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPFrame)
    chShowWindow.Call(hwnd, chSWShow)

    const redrawFlags = 0x0001 | 0x0004 | 0x0080 | 0x0100 // invalidate|erase|allchildren|updatenow
    chRedrawWindowV5414.Call(hwnd, 0, 0, redrawFlags)
    chUpdateWindow.Call(hwnd)

    cb := syscall.NewCallback(func(child, _ uintptr) uintptr {
        if child != 0 {
            chRedrawWindowV5414.Call(child, 0, 0, redrawFlags)
            chUpdateWindow.Call(child)
        }
        return 1
    })
    chEnumChildWindowsV5414.Call(hwnd, cb, 0)
}

func init() {
    // This watcher only acts while the user is actually on MH MT5. It fixes
    // first-open blank rendering and the menu/toolbar paint-on-hover symptom.
    go func() {
        ticker := time.NewTicker(350 * time.Millisecond)
        defer ticker.Stop()
        for range ticker.C {
            if hostHWND == 0 {
                continue
            }
            chViewMu.Lock()
            desired := chDesiredView
            chViewMu.Unlock()
            if desired != 4 {
                continue
            }
            chMu.Lock()
            hwnd := chMT5Wnd
            chMu.Unlock()
            if hwnd != 0 {
                v553RepaintMT5FullTerminal(hwnd)
            }
        }
    }()
}
