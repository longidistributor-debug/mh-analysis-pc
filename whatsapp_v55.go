//go:build windows

package main

import (
    "unsafe"
)

func wv2WhatsAppCDPFireV55(method, params string) bool {
    if wv2WhatsappCoreV55 == 0 { return false }
    desktopNativeWaInitTables()
    cb := &desktopNativeWaAsyncCB{Vtbl: &desktopNativeWaAsyncTable, Ref: 1, Ch: make(chan desktopNativeWaAsyncResult, 1)}
    ptr := uintptr(unsafe.Pointer(cb))
    desktopNativeWaPending.Store(ptr, cb)
    hr := comCall(
        wv2WhatsappCoreV55,
        36,
        uintptr(unsafe.Pointer(wstr(method))),
        uintptr(unsafe.Pointer(wstr(params))),
        ptr,
    )
    if int32(hr) < 0 {
        desktopNativeWaPending.Delete(ptr)
        return false
    }
    return true
}

func wv2WhatsAppTrustedEnterV55() bool {
    events := []string{
        `{"type":"rawKeyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
        `{"type":"char","key":"Enter","code":"Enter","text":"\r","unmodifiedText":"\r","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
        `{"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
    }
    for _, params := range events {
        if !wv2WhatsAppCDPFireV55("Input.dispatchKeyEvent", params) { return false }
    }
    return true
}
