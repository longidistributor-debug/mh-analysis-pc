//go:build windows

package main

import (
	"time"
	"unsafe"
)

// Send one DevTools command to the SAME persistent WhatsApp WebView2 instance.
// The callback stays alive asynchronously; WebView2 preserves protocol call order.
func wv2WhatsAppCDPFireV55(method, params string) bool {
	if wv2WhatsappCoreV55 == 0 {
		return false
	}
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

// The composer is filled by the existing same-session DOM state machine. Before
// Enter, force Chromium to treat the background embedded page as focused, focus
// the actual WhatsApp composer, then dispatch browser-trusted key events. This
// avoids the old behaviour where text was pasted but only sent after the user
// manually opened the WhatsApp tab.
func wv2WhatsAppTrustedEnterV55() bool {
	if wv2WhatsappCoreV55 == 0 {
		return false
	}
	_ = wv2WhatsAppCDPFireV55("Emulation.setFocusEmulationEnabled", `{"enabled":true}`)
	_ = wv2WhatsAppCDPFireV55("Runtime.evaluate", `{"expression":"(()=>{const b=document.querySelector('footer [contenteditable=\\\"true\\\"][role=\\\"textbox\\\"]')||document.querySelector('footer [contenteditable=\\\"true\\\"]');if(b){b.focus();return true}return false})()","returnByValue":true}`)
	time.Sleep(25 * time.Millisecond)
	events := []string{
		`{"type":"rawKeyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
		`{"type":"char","key":"Enter","code":"Enter","text":"\r","unmodifiedText":"\r","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
		`{"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
	}
	for _, params := range events {
		if !wv2WhatsAppCDPFireV55("Input.dispatchKeyEvent", params) {
			return false
		}
		time.Sleep(12 * time.Millisecond)
	}
	return true
}
