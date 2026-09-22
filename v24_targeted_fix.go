//go:build windows

package main

import (
    "path/filepath"
    "strings"
    "syscall"
    "time"
    "unsafe"
)

func init() { go v24TargetedRuntimeGuard() }

func v24TargetedRuntimeGuard() {
    ticker := time.NewTicker(150 * time.Millisecond)
    defer ticker.Stop()
    for range ticker.C {
        if chStopping { return }
        chViewMu.Lock(); view := chDesiredView; chViewMu.Unlock()
        if chSignalLinkBtn != 0 {
            if view == 2 {
                // Force the separate Signal Link navigation control visible and above embedded content.
                chShowWindowAsync.Call(chSignalLinkBtn, chSWShow)
                chSetWindowPos.Call(chSignalLinkBtn, 0, 600, 7, 145, 30, chSWPFrame|chSWPAsync)
                chBringWindowToTop.Call(chSignalLinkBtn)
                chUpdateWindow.Call(chSignalLinkBtn)
            } else {
                chShowWindowAsync.Call(chSignalLinkBtn, chSWHide)
            }
        }
        if view == 4 {
            chMu.Lock(); missing := chMT5Wnd == 0; chMu.Unlock()
            if missing {
                if wnd := v24FindExistingMT5Window(); wnd != 0 {
                    chShowWindow.Call(wnd, chSWHide)
                    chAttachBrowser(wnd)
                    chMu.Lock(); if chMT5Wnd == 0 { chMT5Wnd = wnd }; chMu.Unlock()
                    chResizeChildren(); chApplyDesiredBrowserView(); go mt5ApplyLatestQueued()
                }
            }
        }
    }
}

func v24FindExistingMT5Window() uintptr {
    var found uintptr
    getText := chUser32.NewProc("GetWindowTextW")
    getLen := chUser32.NewProc("GetWindowTextLengthW")
    openProcess := chKernel32.NewProc("OpenProcess")
    closeHandle := chKernel32.NewProc("CloseHandle")
    queryImage := chKernel32.NewProc("QueryFullProcessImageNameW")
    cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND { return 1 }
        vis, _, _ := chIsWindowVisible.Call(hwnd); if vis == 0 { return 1 }
        var pid uint32
        chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
        if pid == 0 { return 1 }
        clsBuf := make([]uint16, 256)
        n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&clsBuf[0])), uintptr(len(clsBuf)))
        cls := ""; if n > 0 { cls = strings.ToLower(syscall.UTF16ToString(clsBuf[:n])) }
        ln, _, _ := getLen.Call(hwnd)
        title := ""
        if ln > 0 { b:=make([]uint16,int(ln)+1); got,_,_:=getText.Call(hwnd,uintptr(unsafe.Pointer(&b[0])),uintptr(len(b))); if got>0 { title=strings.ToLower(syscall.UTF16ToString(b[:got])) } }
        image := ""
        h,_,_ := openProcess.Call(0x1000,0,uintptr(pid))
        if h != 0 {
            b:=make([]uint16,1024); sz:=uint32(len(b)); ok,_,_:=queryImage.Call(h,0,uintptr(unsafe.Pointer(&b[0])),uintptr(unsafe.Pointer(&sz))); closeHandle.Call(h)
            if ok != 0 && sz > 0 { image = strings.ToLower(filepath.Base(syscall.UTF16ToString(b[:sz]))) }
        }
        if strings.Contains(cls,"chrome_widgetwin") || strings.Contains(title,"mh analysis") { return 1 }
        // Broker terminals often do not put "MetaTrader 5" in the window title. Process image is authoritative.
        if image == "terminal64.exe" || image == "terminal.exe" || strings.Contains(cls,"metaquotes") || strings.Contains(title,"metatrader 5") || strings.Contains(title,"meta trader 5") {
            found=hwnd; return 0
        }
        return 1
    })
    chEnumWindows.Call(cb,0)
    return found
}
