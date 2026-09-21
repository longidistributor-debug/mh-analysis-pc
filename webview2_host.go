//go:build windows

package main

import (
    "os"
    "path/filepath"
    "syscall"
    "time"
    "unsafe"

    "github.com/jchv/go-webview2/pkg/edge"
)

// V.09 replaces the external Chrome/Edge app-window/reparenting path with a
// real WebView2 controller embedded directly in the MH Analysis host. This is
// one native MH window, so HTML inputs receive keyboard input normally and no
// browser app window can create a second taskbar icon.
var (
    wv2Browser *edge.Chromium
    wv2Container uintptr
    wv2CurrentView = 1
)

func wv2CreateContainer(parent uintptr) uintptr {
    cls, _ := syscall.UTF16PtrFromString("STATIC")
    empty, _ := syscall.UTF16PtrFromString("")
    h, _, _ := chCreateWindowEx.Call(
        0,
        uintptr(unsafe.Pointer(cls)),
        uintptr(unsafe.Pointer(empty)),
        chWSChild|chWSVisible,
        0, uintptr(barH), 1, 1,
        parent, 0, chGetModuleHandle(), 0,
    )
    return h
}

func wv2Resize() {
    if hostHWND == 0 || wv2Container == 0 { return }
    var r chRect
    chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
    w := int32(r.R-r.L)
    h := int32(r.B-r.T-int32(barH))
    if w < 1 { w = 1 }; if h < 1 { h = 1 }
    chMoveWindow.Call(wv2Container, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
    if wv2Browser != nil { wv2Browser.Resize() }
    if btnAnalysis != 0 { chMoveWindow.Call(btnAnalysis, 8, 7, 140, 30, 1) }
    if btnWhatsapp != 0 { chMoveWindow.Call(btnWhatsapp, 156, 7, 140, 30, 1) }
    if btnRecords != 0 { chMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1) }
    if btnMT5 != 0 { chMoveWindow.Call(btnMT5, 452, 7, 140, 30, 1) }
}

func wv2Navigate(which int) {
    if wv2Browser == nil { return }
    wv2CurrentView = which
    switch which {
    case 2:
        wv2Browser.Navigate("https://web.whatsapp.com/")
    case 3:
        wv2Browser.Navigate(serverURL + "records.html")
    default:
        wv2Browser.Navigate(serverURL)
    }
    wv2Browser.Focus()
}

func wv2WndProc(hwnd, msg, wp, lp uintptr) uintptr {
    switch msg {
    case chWMSize:
        wv2Resize(); return 0
    case chWMCommand:
        id := int(wp & 0xffff)
        switch id {
        case chIDAnalysis: wv2Navigate(1)
        case chIDWhatsapp: wv2Navigate(2)
        case chIDRecords: wv2Navigate(3)
        case chIDMT5:
            // MT5 remains the user's installed terminal. Launch it only on demand;
            // never create another hidden browser window.
            chLaunchOrFocusMT5()
        }
        return 0
    case chWMClose:
        // Hide the one MH host first for a clean shutdown; no child app windows exist.
        chShowWindow.Call(hwnd, chSWHide)
        chDestroyWindow.Call(hwnd); return 0
    case chWMDestroy:
        if wv2Browser != nil { wv2Browser.Close(); wv2Browser = nil }
        chPostQuitMessage.Call(0); return 0
    }
    r, _, _ := chDefWindowProc.Call(hwnd, msg, wp, lp); return r
}

func runWebView2Host() {
    runtimeData := filepath.Join(os.Getenv("LOCALAPPDATA"), "MHAnalysis", "WebView2")
    _ = os.MkdirAll(runtimeData, 0755)

    hinst := chGetModuleHandle()
    className, _ := syscall.UTF16PtrFromString("MHAnalysisWebView2HostV09")
    title, _ := syscall.UTF16PtrFromString("MH Analysis")
    wc := chWndClassEx{CbSize:uint32(unsafe.Sizeof(chWndClassEx{})), Style:3, LpfnWndProc:syscall.NewCallback(wv2WndProc), HInstance:hinst, HCursor:chLoadCursor(), HbrBackground:6, LpszClassName:className}
    chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc)))
    hwnd, _, _ := chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(className)), uintptr(unsafe.Pointer(title)), chWSOverlappedWindow, 0x80000000,0x80000000,1280,820,0,0,hinst,0)
    if hwnd == 0 { messageBox(0,"Could not create MH Analysis window.","MH Analysis",0x10); return }
    hostHWND = hwnd
    btnAnalysis = chCreateButton(hwnd,"MH Analysis",chIDAnalysis,8)
    btnWhatsapp = chCreateButton(hwnd,"WhatsApp",chIDWhatsapp,156)
    btnRecords = chCreateButton(hwnd,"Records",chIDRecords,304)
    btnMT5 = chCreateButton(hwnd,"MT5 System",chIDMT5,452)

    wv2Container = wv2CreateContainer(hwnd)
    if wv2Container == 0 { messageBox(hwnd,"Could not create MH Analysis view.","MH Analysis",0x10); chDestroyWindow.Call(hwnd); return }

    browser := edge.NewChromium()
    browser.DataPath = runtimeData
    wv2Browser = browser
    if !browser.Embed(wv2Container) {
        messageBox(hwnd,"Microsoft Edge WebView2 Runtime is required for MH Analysis.","MH Analysis",0x10)
        chDestroyWindow.Call(hwnd); return
    }
    browser.Resize()
    browser.Navigate(serverURL)
    browser.Focus()

    // Present only after WebView2 is embedded. This removes the startup white/black
    // flash and means Windows sees exactly one top-level MH Analysis window.
    time.Sleep(120*time.Millisecond)
    chShowWindow.Call(hwnd, chSWMaximize)
    chUpdateWindow.Call(hwnd)
    browser.Focus()

    var msg chMsg
    for {
        r, _, _ := chGetMessage.Call(uintptr(unsafe.Pointer(&msg)),0,0,0)
        if int32(r) <= 0 { break }
        chTranslateMessage.Call(uintptr(unsafe.Pointer(&msg)))
        chDispatchMessage.Call(uintptr(unsafe.Pointer(&msg)))
    }
}
