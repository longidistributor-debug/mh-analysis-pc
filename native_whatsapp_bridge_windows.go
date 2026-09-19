//go:build windows

package main

import (
	"fmt"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

// desktopNativeWhatsAppBridge deliberately uses the same low-level CoreWebView2
// route that existed in the early MH Analysis host, but only for WhatsApp.  The
// visible MH Analysis WebView and all trading code stay untouched.
//
// The WhatsApp controller uses the existing WebView2-WhatsApp user-data folder,
// so the user's logged-in session persists.  When MH Analysis is selected the
// controller remains rendered *outside* the client area instead of being hidden;
// this keeps WhatsApp Web alive without covering the dashboard or moving the
// user's real mouse cursor.

type desktopNativeWaCreateVtbl struct {
	QueryInterface uintptr
	AddRef         uintptr
	Release        uintptr
	Invoke         uintptr
}

type desktopNativeWaCreateCB struct {
	Vtbl *desktopNativeWaCreateVtbl
	Kind int32 // 1 environment, 2 controller
	Ref  uint32
}

type desktopNativeWaAsyncVtbl struct {
	QueryInterface uintptr
	AddRef         uintptr
	Release        uintptr
	Invoke         uintptr
}

type desktopNativeWaAsyncResult struct {
	Text string
	Err  error
}

type desktopNativeWaAsyncCB struct {
	Vtbl *desktopNativeWaAsyncVtbl
	Ref  uint32
	Ch   chan desktopNativeWaAsyncResult
}

var (
	desktopNativeWaMu sync.RWMutex

	desktopNativeWaParent   uintptr
	desktopNativeWaEnv      uintptr
	desktopNativeWaCtl      uintptr
	desktopNativeWaCore     uintptr
	desktopNativeWaDLL      *syscall.DLL
	desktopNativeWaCreateFn *syscall.Proc
	desktopNativeWaDispatch func(func())

	desktopNativeWaCreateTable desktopNativeWaCreateVtbl
	desktopNativeWaAsyncTable  desktopNativeWaAsyncVtbl
	desktopNativeWaEnvCB       *desktopNativeWaCreateCB
	desktopNativeWaCtlCB       *desktopNativeWaCreateCB

	desktopNativeWaReadyCh   = make(chan struct{})
	desktopNativeWaReadyOnce sync.Once
	desktopNativeWaReadyErr  error
	desktopNativeWaStarted   bool

	desktopNativeWaWantedX       int
	desktopNativeWaWantedY       int
	desktopNativeWaWantedW       = 1200
	desktopNativeWaWantedH       = 800
	desktopNativeWaWantedVisible = true

	// COM owns callback pointers asynchronously; this map keeps the Go objects
	// reachable until Invoke runs.
	desktopNativeWaPending sync.Map
)

func desktopNativeWaInitTables() {
	if desktopNativeWaCreateTable.QueryInterface != 0 {
		return
	}
	desktopNativeWaCreateTable = desktopNativeWaCreateVtbl{
		QueryInterface: syscall.NewCallback(desktopNativeWaCreateQI),
		AddRef:         syscall.NewCallback(desktopNativeWaCreateAddRef),
		Release:        syscall.NewCallback(desktopNativeWaCreateRelease),
		Invoke:         syscall.NewCallback(desktopNativeWaCreateInvoke),
	}
	desktopNativeWaAsyncTable = desktopNativeWaAsyncVtbl{
		QueryInterface: syscall.NewCallback(desktopNativeWaAsyncQI),
		AddRef:         syscall.NewCallback(desktopNativeWaAsyncAddRef),
		Release:        syscall.NewCallback(desktopNativeWaAsyncRelease),
		Invoke:         syscall.NewCallback(desktopNativeWaAsyncInvoke),
	}
}

func desktopNativeWaFinishReady(err error) {
	desktopNativeWaMu.Lock()
	if desktopNativeWaReadyErr == nil && err != nil {
		desktopNativeWaReadyErr = err
	}
	desktopNativeWaMu.Unlock()
	desktopNativeWaReadyOnce.Do(func() { close(desktopNativeWaReadyCh) })
}

func desktopNativeWaCreateQI(this, _riid, out uintptr) uintptr {
	if out == 0 {
		return uintptr(uint32(0x80004003)) // E_POINTER
	}
	*(*uintptr)(unsafe.Pointer(out)) = this
	desktopNativeWaCreateAddRef(this)
	return 0
}

func desktopNativeWaCreateAddRef(this uintptr) uintptr {
	o := (*desktopNativeWaCreateCB)(unsafe.Pointer(this))
	o.Ref++
	return uintptr(o.Ref)
}

func desktopNativeWaCreateRelease(this uintptr) uintptr {
	o := (*desktopNativeWaCreateCB)(unsafe.Pointer(this))
	if o.Ref > 1 {
		o.Ref--
	}
	return uintptr(o.Ref)
}

func desktopNativeWaApplyLayoutNow() {
	desktopNativeWaMu.RLock()
	ctl := desktopNativeWaCtl
	x, y, w, h := desktopNativeWaWantedX, desktopNativeWaWantedY, desktopNativeWaWantedW, desktopNativeWaWantedH
	visible := desktopNativeWaWantedVisible
	desktopNativeWaMu.RUnlock()
	if ctl == 0 {
		return
	}
	if w < 1 {
		w = 1
	}
	if h < 1 {
		h = 1
	}
	wvBounds(ctl, rect{L: int32(x), T: int32(y), R: int32(x + w), B: int32(y + h)})
	wvVisible(ctl, visible)
}

func desktopNativeWaCreateInvoke(this, result, arg uintptr) uintptr {
	o := (*desktopNativeWaCreateCB)(unsafe.Pointer(this))
	if int32(result) < 0 || arg == 0 {
		desktopNativeWaFinishReady(fmt.Errorf("WhatsApp WebView2 initialization failed (0x%08X)", uint32(result)))
		return 0
	}

	switch o.Kind {
	case 1:
		desktopNativeWaMu.Lock()
		desktopNativeWaEnv = arg
		parent := desktopNativeWaParent
		desktopNativeWaCtlCB = &desktopNativeWaCreateCB{Vtbl: &desktopNativeWaCreateTable, Kind: 2, Ref: 1}
		cb := desktopNativeWaCtlCB
		desktopNativeWaMu.Unlock()
		hr := comCall(arg, 3, parent, uintptr(unsafe.Pointer(cb))) // CreateCoreWebView2Controller
		if int32(hr) < 0 {
			desktopNativeWaFinishReady(fmt.Errorf("WhatsApp controller creation failed (0x%08X)", uint32(hr)))
		}
	case 2:
		core := getCore(arg)
		if core == 0 {
			desktopNativeWaFinishReady(fmt.Errorf("WhatsApp WebView2 core was unavailable"))
			return 0
		}
		desktopNativeWaMu.Lock()
		desktopNativeWaCtl = arg
		desktopNativeWaCore = core
		desktopNativeWaMu.Unlock()
		desktopNativeWaApplyLayoutNow()
		wvNavigate(core, "https://web.whatsapp.com/")
		desktopNativeWaFinishReady(nil)
	}
	return 0
}

func desktopNativeWaAsyncQI(this, _riid, out uintptr) uintptr {
	if out == 0 {
		return uintptr(uint32(0x80004003))
	}
	*(*uintptr)(unsafe.Pointer(out)) = this
	desktopNativeWaAsyncAddRef(this)
	return 0
}

func desktopNativeWaAsyncAddRef(this uintptr) uintptr {
	o := (*desktopNativeWaAsyncCB)(unsafe.Pointer(this))
	o.Ref++
	return uintptr(o.Ref)
}

func desktopNativeWaAsyncRelease(this uintptr) uintptr {
	o := (*desktopNativeWaAsyncCB)(unsafe.Pointer(this))
	if o.Ref > 1 {
		o.Ref--
	}
	return uintptr(o.Ref)
}

func desktopNativeWaUTF16String(ptr uintptr) string {
	if ptr == 0 {
		return ""
	}
	buf := make([]uint16, 0, 256)
	for i := 0; i < 1<<20; i++ {
		v := *(*uint16)(unsafe.Pointer(ptr + uintptr(i*2)))
		if v == 0 {
			break
		}
		buf = append(buf, v)
	}
	return syscall.UTF16ToString(buf)
}

// Both ExecuteScriptCompleted and CallDevToolsProtocolMethodCompleted use the
// same ABI: Invoke(HRESULT, LPCWSTR resultJson), so one callback implementation
// safely serves both.
func desktopNativeWaAsyncInvoke(this, result, text uintptr) uintptr {
	o := (*desktopNativeWaAsyncCB)(unsafe.Pointer(this))
	out := desktopNativeWaAsyncResult{Text: desktopNativeWaUTF16String(text)}
	if int32(result) < 0 {
		out.Err = fmt.Errorf("WebView2 async call failed (0x%08X)", uint32(result))
	}
	select {
	case o.Ch <- out:
	default:
	}
	desktopNativeWaPending.Delete(this)
	return 0
}

func desktopNativeWhatsAppStart(parent uintptr, dispatch func(func()), profile string) error {
	desktopNativeWaMu.Lock()
	if desktopNativeWaStarted {
		desktopNativeWaMu.Unlock()
		return nil
	}
	desktopNativeWaStarted = true
	desktopNativeWaParent = parent
	desktopNativeWaDispatch = dispatch
	desktopNativeWaMu.Unlock()

	desktopNativeWaInitTables()
	path, err := findWebViewRuntimeDLL()
	if err != nil {
		desktopNativeWaFinishReady(err)
		return err
	}
	dll, err := syscall.LoadDLL(path)
	if err != nil {
		err = fmt.Errorf("could not load WhatsApp WebView2 runtime: %w", err)
		desktopNativeWaFinishReady(err)
		return err
	}
	proc, err := dll.FindProc("CreateWebViewEnvironmentWithOptionsInternal")
	if err != nil {
		err = fmt.Errorf("WhatsApp WebView2 runtime export missing")
		desktopNativeWaFinishReady(err)
		return err
	}

	desktopNativeWaMu.Lock()
	desktopNativeWaDLL = dll
	desktopNativeWaCreateFn = proc
	desktopNativeWaEnvCB = &desktopNativeWaCreateCB{Vtbl: &desktopNativeWaCreateTable, Kind: 1, Ref: 1}
	cb := desktopNativeWaEnvCB
	desktopNativeWaMu.Unlock()

	r, _, _ := proc.Call(1, 0, uintptr(unsafe.Pointer(wstr(profile))), 0, uintptr(unsafe.Pointer(cb)))
	if int32(r) < 0 {
		err = fmt.Errorf("WhatsApp WebView2 environment start failed (0x%08X)", uint32(r))
		desktopNativeWaFinishReady(err)
		return err
	}
	return nil
}

func desktopNativeWhatsAppWaitReady(timeout time.Duration) error {
	select {
	case <-desktopNativeWaReadyCh:
		desktopNativeWaMu.RLock()
		err := desktopNativeWaReadyErr
		core := desktopNativeWaCore
		desktopNativeWaMu.RUnlock()
		if err != nil {
			return err
		}
		if core == 0 {
			return fmt.Errorf("WhatsApp background view is not ready")
		}
		return nil
	case <-time.After(timeout):
		return fmt.Errorf("WhatsApp background view is still starting")
	}
}

func desktopNativeWhatsAppSetLayout(x, y, w, h int, rendered bool) {
	desktopNativeWaMu.Lock()
	desktopNativeWaWantedX, desktopNativeWaWantedY = x, y
	desktopNativeWaWantedW, desktopNativeWaWantedH = w, h
	desktopNativeWaWantedVisible = rendered
	dispatch := desktopNativeWaDispatch
	desktopNativeWaMu.Unlock()
	if dispatch != nil {
		dispatch(func() { desktopNativeWaApplyLayoutNow() })
	}
}

func desktopNativeWhatsAppNavigate(target string) error {
	if err := desktopNativeWhatsAppWaitReady(10 * time.Second); err != nil {
		return err
	}
	desktopNativeWaMu.RLock()
	dispatch := desktopNativeWaDispatch
	core := desktopNativeWaCore
	desktopNativeWaMu.RUnlock()
	if dispatch == nil || core == 0 {
		return fmt.Errorf("WhatsApp background view is not ready")
	}
	done := make(chan struct{}, 1)
	dispatch(func() {
		wvNavigate(core, target)
		done <- struct{}{}
	})
	select {
	case <-done:
		return nil
	case <-time.After(3 * time.Second):
		return fmt.Errorf("WhatsApp navigation timed out")
	}
}

func desktopNativeWaAsyncCall(index int, a, b string, timeout time.Duration) (string, error) {
	if err := desktopNativeWhatsAppWaitReady(10 * time.Second); err != nil {
		return "", err
	}
	desktopNativeWaMu.RLock()
	dispatch := desktopNativeWaDispatch
	core := desktopNativeWaCore
	desktopNativeWaMu.RUnlock()
	if dispatch == nil || core == 0 {
		return "", fmt.Errorf("WhatsApp background view is not ready")
	}

	ch := make(chan desktopNativeWaAsyncResult, 1)
	cb := &desktopNativeWaAsyncCB{Vtbl: &desktopNativeWaAsyncTable, Ref: 1, Ch: ch}
	ptr := uintptr(unsafe.Pointer(cb))
	desktopNativeWaPending.Store(ptr, cb)
	dispatch(func() {
		var hr uintptr
		if index == 29 { // ICoreWebView2::ExecuteScript
			hr = comCall(core, 29, uintptr(unsafe.Pointer(wstr(a))), ptr)
		} else { // ICoreWebView2::CallDevToolsProtocolMethod (vtable index 36)
			hr = comCall(core, 36, uintptr(unsafe.Pointer(wstr(a))), uintptr(unsafe.Pointer(wstr(b))), ptr)
		}
		if int32(hr) < 0 {
			desktopNativeWaPending.Delete(ptr)
			select {
			case ch <- desktopNativeWaAsyncResult{Err: fmt.Errorf("WebView2 call failed (0x%08X)", uint32(hr))}:
			default:
			}
		}
	})

	select {
	case res := <-ch:
		return res.Text, res.Err
	case <-time.After(timeout):
		desktopNativeWaPending.Delete(ptr)
		return "", fmt.Errorf("WhatsApp WebView2 call timed out")
	}
}

func desktopNativeWhatsAppEval(script string, timeout time.Duration) (string, error) {
	return desktopNativeWaAsyncCall(29, script, "", timeout)
}

func desktopNativeWhatsAppCDP(method, params string, timeout time.Duration) (string, error) {
	return desktopNativeWaAsyncCall(36, method, params, timeout)
}

// Sends a browser-trusted Enter key directly through Chromium DevTools Protocol.
// This never calls SetCursorPos/SendInput and never moves the user's desktop mouse.
func desktopNativeWhatsAppTrustedEnter() error {
	events := []string{
		`{"type":"rawKeyDown","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`, 
		`{"type":"char","key":"Enter","code":"Enter","text":"\r","unmodifiedText":"\r","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`, 
		`{"type":"keyUp","key":"Enter","code":"Enter","windowsVirtualKeyCode":13,"nativeVirtualKeyCode":13}`,
	}
	for _, params := range events {
		if _, err := desktopNativeWhatsAppCDP("Input.dispatchKeyEvent", params, 3*time.Second); err != nil {
			return err
		}
	}
	return nil
}

func desktopNativeWhatsAppDestroy() {
	desktopNativeWaMu.RLock()
	dispatch := desktopNativeWaDispatch
	ctl := desktopNativeWaCtl
	desktopNativeWaMu.RUnlock()
	if dispatch != nil && ctl != 0 {
		dispatch(func() { _ = comCall(ctl, 24) }) // ICoreWebView2Controller::Close
	}
}

func desktopNativeWhatsAppResultIsTrue(s string) bool {
	s = strings.TrimSpace(s)
	return s == "true" || s == `"true"`
}
