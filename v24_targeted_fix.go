//go:build windows

package main

import (
    "strings"
    "syscall"
    "time"
    "unsafe"
)

// V.24 is based directly on the known V.22 source. This guard changes only
// Signal Link visibility and MT5 recovery; auth/login/updater/UI are untouched.
func init() { go v24TargetedRuntimeGuard() }

func v24TargetedRuntimeGuard() {
    ticker := time.NewTicker(250 * time.Millisecond)
    defer ticker.Stop()
    for range ticker.C {
        if chStopping { return }
        chViewMu.Lock(); view := chDesiredView; chViewMu.Unlock()

        if chSignalLinkBtn != 0 {
            if view == 2 {
                chShowWindow.Call(chSignalLinkBtn, chSWShow)
                chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
                chUpdateWindow.Call(chSignalLinkBtn)
            } else {
                chShowWindow.Call(chSignalLinkBtn, chSWHide)
            }
        }

        if view == 4 {
            chMu.Lock(); missing := chMT5Wnd == 0; chMu.Unlock()
            if missing {
                if wnd := v24FindExistingMT5Window(); wnd != 0 {
                    chShowWindow.Call(wnd, chSWHide)
                    chAttachBrowser(wnd)
                    chMu.Lock()
                    if chMT5Wnd == 0 { chMT5Wnd = wnd }
                    chMu.Unlock()
                    chResizeChildren()
                    chApplyDesiredBrowserView()
                    go mt5ApplyLatestQueued()
                }
            }
        }
    }
}

func v24FindExistingMT5Window() uintptr {
    var found uintptr
    getText := chUser32.NewProc("GetWindowTextW")
    getLen := chUser32.NewProc("GetWindowTextLengthW")
    cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND { return 1 }
        vis, _, _ := chIsWindowVisible.Call(hwnd); if vis == 0 { return 1 }
        clsBuf := make([]uint16, 256)
        n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&clsBuf[0])), uintptr(len(clsBuf)))
        cls := ""; if n > 0 { cls = strings.ToLower(syscall.UTF16ToString(clsBuf[:n])) }
        ln, _, _ := getLen.Call(hwnd)
        title := ""
        if ln > 0 {
            b := make([]uint16, int(ln)+1)
            got, _, _ := getText.Call(hwnd, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)))
            if got > 0 { title = strings.ToLower(syscall.UTF16ToString(b[:got])) }
        }
        if strings.Contains(cls, "chrome_widgetwin") || strings.Contains(title, "mh analysis") { return 1 }
        if strings.Contains(cls, "metaquotes") || strings.Contains(title, "metatrader 5") || strings.Contains(title, "meta trader 5") {
            found = hwnd; return 0
        }
        return 1
    })
    chEnumWindows.Call(cb, 0)
    return found
}
