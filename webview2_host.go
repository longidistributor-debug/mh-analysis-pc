//go:build windows

package main

import (
    "os"
    "path/filepath"
    "runtime"
    "syscall"
    "time"
    "unsafe"

    "github.com/jchv/go-webview2/pkg/edge"
)

var (
    wv2Browser *edge.Chromium
    wv2Container uintptr
)

func wv2CreateContainer(parent, inst uintptr) uintptr {
    h, _, _ := chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("STATIC"))), uintptr(unsafe.Pointer(chWstr(""))), chWSChild|chWSVisible, 0, uintptr(barH), 1, 1, parent, 0, inst, 0)
    return h
}

func wv2Resize() {
    if hostHWND == 0 || wv2Container == 0 { return }
    var r chRect
    chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
    w := int32(r.R-r.L); h := int32(r.B-r.T-int32(barH))
    if w < 1 { w = 1 }; if h < 1 { h = 1 }
    chMoveWindow.Call(wv2Container, 0, uintptr(barH), uintptr(w), uintptr(h), 1)
    if wv2Browser != nil { wv2Browser.Resize() }
    if chMT5Wnd != 0 { chMoveWindow.Call(chMT5Wnd, 0, uintptr(barH), uintptr(w), uintptr(h), 1) }
}

func wv2ShowLocal(which int) {
    if wv2Browser == nil { return }
    if chMT5Wnd != 0 { chShowWindow.Call(chMT5Wnd, chSWHide) }
    chShowWindow.Call(wv2Container, chSWShow)
    if which == 2 { wv2Browser.Navigate("https://web.whatsapp.com/")
    } else if which == 3 { wv2Browser.Navigate(serverURL+"records.html")
    } else { wv2Browser.Navigate(serverURL) }
    wv2Browser.Focus()
}

func wv2ButtonAllowed(id int) bool {
    if licAuthorized { return true }
    section := "MH Analysis"
    if id == idWhatsapp { section="WhatsApp" }; if id == idRecords { section="Records" }; if id == idMT5 { section="MT5 System" }
    licSetNavNotice(section)
    wv2ShowLocal(1)
    return false
}

func wv2WndProc(hwnd uintptr, msg uint32, wp, lp uintptr) uintptr {
    switch msg {
    case chWMSize:
        wv2Resize(); return 0
    case chWMCommand:
        id := int(wp & 0xffff)
        if !wv2ButtonAllowed(id) { return 0 }
        switch id {
        case idAnalysis: wv2ShowLocal(1)
        case idWhatsapp: wv2ShowLocal(2)
        case idRecords: wv2ShowLocal(3)
        case idMT5:
            chShowWindow.Call(wv2Container, chSWHide)
            go func(){ if err:=chEnsureMT5Terminal(); err!=nil { messageBox(hostHWND,err.Error(),"MT5 System",0x10) } }()
        }
        return 0
    case wmSwitchAnalysis:
        wv2ShowLocal(1); return 0
    case wmSwitchWhatsApp:
        if licAuthorized { wv2ShowLocal(2) } else { licSetNavNotice("WhatsApp"); wv2ShowLocal(1) }; return 0
    case chWMOpenAPISettings:
        chShowNativeSettingsDialog(1); return 0
    case chWMOpenWhatsAppSettings:
        if licAuthorized { wv2ShowLocal(2); chShowNativeSettingsDialog(2) }; return 0
    case chWMClose:
        chShowWindow.Call(hwnd,chSWHide)
        if chMT5Wnd != 0 { chShowWindow.Call(chMT5Wnd,chSWHide) }
        chDestroyWindow.Call(hwnd); return 0
    case chWMDestroy:
        chStopBrowsers()
        wv2Browser=nil
        chPostQuitMessage.Call(0); return 0
    }
    r,_,_:=chDefWindowProc.Call(hwnd,uintptr(msg),wp,lp); return r
}

func runWebView2Host() {
    runtime.LockOSThread(); defer runtime.UnlockOSThread()
    inst,_,_:=chGetModuleHandle.Call(0)
    className:=chWstr("MHAnalysisWebView2HostV09")
    icon,_,_:=chLoadIcon.Call(inst,1); if icon==0 { icon,_,_=chLoadIcon.Call(0,32512) }
    cursor,_,_:=chLoadCursor.Call(0,chIDCArrow)
    brush,_,_:=chCreateSolidBrush.Call(uintptr(8|(22<<8)|(26<<16)))
    wc:=chWndClassEx{CbSize:uint32(unsafe.Sizeof(chWndClassEx{})),LpfnWndProc:syscall.NewCallback(wv2WndProc),HInstance:inst,HIcon:icon,HCursor:cursor,HbrBackground:brush,LpszClassName:className,HIconSm:icon}
    if r,_,_:=chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc))); r==0 { messageBox(0,"Could not initialize MH Analysis window.","MH Analysis",0x10); return }
    hostHWND,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(className)),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSOverlapped,100,100,1280,820,0,0,inst,0)
    if hostHWND==0 { messageBox(0,"Could not create MH Analysis window.","MH Analysis",0x10); return }
    btnAnalysis,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSChild|chWSVisible,8,7,140,30,hostHWND,idAnalysis,inst,0)
    btnWhatsapp,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("WhatsApp"))),chWSChild|chWSVisible,156,7,140,30,hostHWND,idWhatsapp,inst,0)
    btnRecords,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("Records"))),chWSChild|chWSVisible,304,7,140,30,hostHWND,idRecords,inst,0)
    btnMT5,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MT5 System"))),chWSChild|chWSVisible,452,7,140,30,hostHWND,idMT5,inst,0)

    wv2Container=wv2CreateContainer(hostHWND,inst)
    data:=filepath.Join(os.Getenv("LOCALAPPDATA"),"MHAnalysis","WebView2"); _=os.MkdirAll(data,0755)
    b:=edge.NewChromium(); b.DataPath=data; wv2Browser=b
    if !b.Embed(wv2Container) { messageBox(hostHWND,"Microsoft Edge WebView2 Runtime is required.","MH Analysis",0x10); chDestroyWindow.Call(hostHWND); return }
    b.Resize(); b.Navigate(serverURL); b.Focus()
    time.Sleep(100*time.Millisecond)
    chShowWindow.Call(hostHWND,chSWMaximize); chUpdateWindow.Call(hostHWND); wv2Resize(); b.Focus()
    var m chMsg
    for { r,_,_:=chGetMessage.Call(uintptr(unsafe.Pointer(&m)),0,0,0); if int32(r)<=0 { break }; chTranslateMessage.Call(uintptr(unsafe.Pointer(&m))); chDispatchMessage.Call(uintptr(unsafe.Pointer(&m))) }
}
