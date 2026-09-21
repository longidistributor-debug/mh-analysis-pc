package main

import (
    "strings"
    "syscall"
    "unsafe"
)

// chFindExistingMT5WindowV23 finds an already-running MT5 terminal when a broker
// launcher reuses an existing process instead of creating a window for the PID
// started by MH Analysis.
func chFindExistingMT5WindowV23() uintptr {
    var found uintptr
    cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND { return 1 }
        vis, _, _ := chIsWindowVisible.Call(hwnd)
        if vis == 0 { return 1 }

        clsBuf := make([]uint16, 256)
        n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&clsBuf[0])), uintptr(len(clsBuf)))
        cls := ""
        if n != 0 { cls = strings.ToLower(syscall.UTF16ToString(clsBuf)) }
        title := strings.ToLower(chWindowText(hwnd))

        // Native MetaTrader terminals use a MetaQuotes window class. Keep a
        // conservative title fallback for broker-customized MT5 builds.
        if strings.Contains(cls, "metaquotes") || strings.Contains(title, "metatrader 5") {
            found = hwnd
            return 0
        }
        return 1
    })
    chEnumWindows.Call(cb, 0)
    return found
}

func chAttachExistingMT5V23(wnd uintptr) bool {
    if wnd == 0 || hostHWND == 0 { return false }
    chShowWindow.Call(wnd, chSWHide)
    chAttachBrowser(wnd)
    chMu.Lock()
    chMT5Wnd = wnd
    chMu.Unlock()
    chResizeChildren()
    chApplyDesiredBrowserView()
    go mt5ApplyLatestQueued()
    return true
}

func chRefreshSignalLinkV23(show bool) {
    if chSignalLinkBtn == 0 { return }
    if show {
        chShowWindow.Call(chSignalLinkBtn, chSWShow)
        chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
        chSetWindowPos.Call(chSignalLinkBtn, 0, 600, 7, 145, 30, chSWPFrame)
        chUpdateWindow.Call(chSignalLinkBtn)
    } else {
        chShowWindow.Call(chSignalLinkBtn, chSWHide)
    }
    if hostHWND != 0 { chUpdateWindow.Call(hostHWND) }
}
