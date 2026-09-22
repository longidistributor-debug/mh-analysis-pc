package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"

	"github.com/gorilla/websocket"
)

var (
	chUser32   = syscall.NewLazyDLL("user32.dll")
	chKernel32 = syscall.NewLazyDLL("kernel32.dll")
	chGdi32    = syscall.NewLazyDLL("gdi32.dll")
	chDwmapi   = syscall.NewLazyDLL("dwmapi.dll")
	chUxTheme  = syscall.NewLazyDLL("uxtheme.dll")

	chRegisterClassEx       = chUser32.NewProc("RegisterClassExW")
	chCreateWindowEx        = chUser32.NewProc("CreateWindowExW")
	chDefWindowProc         = chUser32.NewProc("DefWindowProcW")
	chShowWindow            = chUser32.NewProc("ShowWindow")
	chShowWindowAsync       = chUser32.NewProc("ShowWindowAsync")
	chUpdateWindow          = chUser32.NewProc("UpdateWindow")
	chGetMessage            = chUser32.NewProc("GetMessageW")
	chTranslateMessage      = chUser32.NewProc("TranslateMessage")
	chDispatchMessage       = chUser32.NewProc("DispatchMessageW")
	chPostQuitMessage       = chUser32.NewProc("PostQuitMessage")
	chGetClientRect         = chUser32.NewProc("GetClientRect")
	chMoveWindow            = chUser32.NewProc("MoveWindow")
	chDestroyWindow         = chUser32.NewProc("DestroyWindow")
	chEnumWindows           = chUser32.NewProc("EnumWindows")
	chGetWindowThreadPID    = chUser32.NewProc("GetWindowThreadProcessId")
	chGetClassName          = chUser32.NewProc("GetClassNameW")
	chIsWindowVisible       = chUser32.NewProc("IsWindowVisible")
	chSetParent             = chUser32.NewProc("SetParent")
	chGetWindowLongPtr      = chUser32.NewProc("GetWindowLongPtrW")
	chSetWindowLongPtr      = chUser32.NewProc("SetWindowLongPtrW")
	chSetWindowPos          = chUser32.NewProc("SetWindowPos")
	chSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")
	chGetForegroundWindow   = chUser32.NewProc("GetForegroundWindow")
	chBringWindowToTop      = chUser32.NewProc("BringWindowToTop")
	chSetFocus              = chUser32.NewProc("SetFocus")
	chAttachThreadInput     = chUser32.NewProc("AttachThreadInput")
	chGetCurrentThreadId    = chKernel32.NewProc("GetCurrentThreadId")
	chLoadIcon              = chUser32.NewProc("LoadIconW")
	chLoadCursor            = chUser32.NewProc("LoadCursorW")
	chGetModuleHandle       = chKernel32.NewProc("GetModuleHandleW")
	chCreateSolidBrush      = chGdi32.NewProc("CreateSolidBrush")
	chDwmSetWindowAttribute = chDwmapi.NewProc("DwmSetWindowAttribute")
	chSetWindowTheme        = chUxTheme.NewProc("SetWindowTheme")
)

const (
	chWMSize        = 0x0005
	chWMCommand     = 0x0111
	chWMClose       = 0x0010
	chWMDestroy     = 0x0002
	chWSChild       = 0x40000000
	chWSVisible     = 0x10000000
	chWSOverlapped  = 0x00CF0000
	chWSPopup       = 0x80000000
	chWSCaption     = 0x00C00000
	chWSBorder      = 0x00800000
	chWSDlgFrame    = 0x00400000
	chWSThickFrame  = 0x00040000
	chWSMinBox      = 0x00020000
	chWSMaxBox      = 0x00010000
	chWSSysMenu     = 0x00080000
	chEXDlgModal    = 0x00000001
	chEXWindowEdge  = 0x00000100
	chEXClientEdge  = 0x00000200
	chEXStaticEdge  = 0x00020000
	chEXAppWindow   = 0x00040000
	chEXToolWindow  = 0x00000080
	chSWHide        = 0
	chSWShow        = 5
	chSWMaximize    = 3
	chSWPNoZOrder   = 0x0004
	chSWPFrame      = 0x0020
	chSWPNoActivate = 0x0010
	chSWPAsync      = 0x4000
	chIDCArrow      = 32512
	idRecords       = 1103 // MH_RECORDS_V796_PATCH
	idMT5           = 1104 // MH_NATIVE_MT5_TERMINAL_V796
)

type chWndClassEx struct {
	CbSize        uint32
	Style         uint32
	LpfnWndProc   uintptr
	CbClsExtra    int32
	CbWndExtra    int32
	HInstance     uintptr
	HIcon         uintptr
	HCursor       uintptr
	HbrBackground uintptr
	LpszMenuName  *uint16
	LpszClassName *uint16
	HIconSm       uintptr
}
type chPoint struct{ X, Y int32 }
type chMsg struct {
	Hwnd           uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Pt             chPoint
	LPrivate       uint32
}
type chRect struct{ L, T, R, B int32 }

var (
	chAnalysisWnd uintptr
	chWhatsappWnd uintptr
	chRecordsWnd  uintptr
	chMT5Wnd      uintptr // MH_NATIVE_MT5_TERMINAL_V796
	chAnalysisCmd *exec.Cmd
	chWhatsappCmd *exec.Cmd
	chRecordsCmd  *exec.Cmd
	chMT5Cmd      *exec.Cmd
	btnRecords    uintptr
	btnMT5        uintptr
	chBrowserPath string
	chMu          sync.Mutex
	chCDPMu       sync.Mutex
	chViewMu      sync.Mutex
	chDesiredView = 1
	chStopping    bool
)

func chWstr(s string) *uint16 {
	p, _ := syscall.UTF16PtrFromString(s)
	return p
}

func chBrowserExecutable() (string, error) {
	candidates := []string{}
	if p, err := exec.LookPath("chrome.exe"); err == nil {
		candidates = append(candidates, p)
	}
	for _, env := range []string{"PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"} {
		if base := os.Getenv(env); base != "" {
			candidates = append(candidates, filepath.Join(base, "Google", "Chrome", "Application", "chrome.exe"))
		}
	}
	if p, err := exec.LookPath("msedge.exe"); err == nil {
		candidates = append(candidates, p)
	}
	for _, env := range []string{"PROGRAMFILES", "PROGRAMFILES(X86)"} {
		if base := os.Getenv(env); base != "" {
			candidates = append(candidates, filepath.Join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
		}
	}
	for _, p := range candidates {
		if p == "" {
			continue
		}
		if st, err := os.Stat(p); err == nil && !st.IsDir() {
			return p, nil
		}
	}
	return "", errors.New("Google Chrome or Microsoft Edge was not found")
}

func chProfileDir(name string) string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	p := filepath.Join(base, "MHAnalysis", name)
	_ = os.MkdirAll(p, 0755)
	return p
}

func chLaunchBrowser(profile, target string, debugPort int) (*exec.Cmd, uintptr, error) {
	if chBrowserPath == "" {
		p, err := chBrowserExecutable()
		if err != nil {
			return nil, 0, err
		}
		chBrowserPath = p
	}
	args := []string{
		"--user-data-dir=" + chProfileDir(profile),
		"--no-first-run",
		"--no-default-browser-check",
		"--disable-session-crashed-bubble",
		"--disable-background-mode",
		"--disable-infobars",
		"--disable-translate",
		"--disable-features=TranslateUI",
		"--window-position=-32000,-32000",
		"--window-size=1280,820",
		"--kiosk",
		"--new-window",
	}
	if debugPort > 0 {
		args = append(args, fmt.Sprintf("--remote-debugging-port=%d", debugPort))
	}
	args = append(args, "--app="+target)
	cmd := exec.Command(chBrowserPath, args...)
	if err := cmd.Start(); err != nil {
		return nil, 0, err
	}
	wnd := chWaitForBrowserWindow(uint32(cmd.Process.Pid), 20*time.Second)
	if wnd == 0 {
		_ = cmd.Process.Kill()
		return nil, 0, errors.New("browser window did not appear")
	}
	chShowWindow.Call(wnd, chSWHide)
	return cmd, wnd, nil
}

func chWaitForBrowserWindow(pid uint32, timeout time.Duration) uintptr {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if h := chFindBrowserWindow(pid); h != 0 {
			return h
		}
		time.Sleep(100 * time.Millisecond)
	}
	return 0
}

func chFindBrowserWindow(pid uint32) uintptr {
	var found uintptr
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		var wp uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))
		if wp != pid {
			return 1
		}
		vis, _, _ := chIsWindowVisible.Call(hwnd)
		if vis == 0 {
			return 1
		}
		buf := make([]uint16, 128)
		n, _, _ := chGetClassName.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
		if n == 0 {
			return 1
		}
		cls := syscall.UTF16ToString(buf)
		if strings.HasPrefix(cls, "Chrome_WidgetWin") {
			found = hwnd
			return 0
		}
		return 1
	})
	chEnumWindows.Call(cb, 0)
	return found
}

func chAttachBrowser(hwnd uintptr) {
	if hwnd == 0 || hostHWND == 0 {
		return
	}
	chShowWindow.Call(hwnd, chSWHide)
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
	style |= chWSChild | chWSVisible
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow
	exStyle |= chEXToolWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chSetParent.Call(hwnd, hostHWND)
	chFocusEmbeddedBrowser(hwnd)
	chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), 1, 1, chSWPNoZOrder|chSWPNoActivate|chSWPFrame|chSWPAsync)
}


func chFocusEmbeddedBrowser(hwnd uintptr) {
	if hwnd == 0 || hostHWND == 0 { return }
	var browserPID uint32
	browserThread, _, _ := chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&browserPID)))
	hostThread, _, _ := chGetWindowThreadPID.Call(hostHWND, 0)
	if hostThread == 0 { hostThread, _, _ = chGetCurrentThreadId.Call() }
	// V.08: keep the host/browser input queues attached for the lifetime of the
	// embedded child. This is the proven V.04 behavior where username typing worked.
	if browserThread != 0 && hostThread != 0 && browserThread != hostThread {
		chAttachThreadInput.Call(hostThread, browserThread, 1)
	}
	chSetForegroundWindow.Call(hostHWND)
	chSetFocus.Call(hwnd)
}

func chResizeChildren() {
	if hostHWND == 0 {
		return
	}
	var r chRect
	chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
	w := int32(r.R - r.L)
	h := int32(r.B - r.T - int32(barH))
	if h < 1 {
		h = 1
	}
	if chAnalysisWnd != 0 {
		chSetWindowPos.Call(chAnalysisWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
	}
	if chWhatsappWnd != 0 {
		chSetWindowPos.Call(chWhatsappWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
	}
	if chRecordsWnd != 0 {
		chSetWindowPos.Call(chRecordsWnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
	}
	if chMT5Wnd != 0 {
		chSetWindowPos.Call(chMT5Wnd, 0, 0, uintptr(barH), uintptr(w), uintptr(h), chSWPNoZOrder|chSWPNoActivate|chSWPAsync)
	}
	if btnAnalysis != 0 {
		chMoveWindow.Call(btnAnalysis, 8, 7, 140, 30, 1)
	}
	if btnWhatsapp != 0 {
		chMoveWindow.Call(btnWhatsapp, 156, 7, 140, 30, 1)
	}
	if btnRecords != 0 {
		chMoveWindow.Call(btnRecords, 304, 7, 140, 30, 1)
	}
	if btnMT5 != 0 {
		chMoveWindow.Call(btnMT5, 452, 7, 140, 30, 1)
	}
	if chSignalLinkBtn != 0 {
		chMoveWindow.Call(chSignalLinkBtn, 600, 7, 145, 30, 1)
	}
}

func chApplyDesiredBrowserView() {
	chMu.Lock()
	analysis := chAnalysisWnd
	whatsapp := chWhatsappWnd
	records := chRecordsWnd
	mt5 := chMT5Wnd
	chMu.Unlock()

	chViewMu.Lock()
	which := chDesiredView
	chViewMu.Unlock()

	if which == 2 {
		if analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
		if records != 0 { chShowWindowAsync.Call(records, chSWHide) }
		if mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
		if whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWShow) }
		return
	}
	if which == 3 {
		if analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
		if whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
		if mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
		if records != 0 { chShowWindowAsync.Call(records, chSWShow) }
		return
	}
	if which == 4 {
		if analysis != 0 { chShowWindowAsync.Call(analysis, chSWHide) }
		if whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
		if records != 0 { chShowWindowAsync.Call(records, chSWHide) }
		if mt5 != 0 { chShowWindowAsync.Call(mt5, chSWShow) }
		return
	}
	if whatsapp != 0 { chShowWindowAsync.Call(whatsapp, chSWHide) }
	if records != 0 { chShowWindowAsync.Call(records, chSWHide) }
	if mt5 != 0 { chShowWindowAsync.Call(mt5, chSWHide) }
	if analysis != 0 { chShowWindowAsync.Call(analysis, chSWShow) }
}

func chSwitchView(which int) {
	chViewMu.Lock()
	chDesiredView = which
	chViewMu.Unlock()

	// Native button visibility is immediate and never depends on browser readiness.
	if chSignalLinkBtn != 0 {
		if which == 2 {
			chShowWindow.Call(chSignalLinkBtn, chSWShow)
		} else {
			chShowWindow.Call(chSignalLinkBtn, chSWHide)
		}
	}

	go chApplyDesiredBrowserView()
}

func chPopWhatsAppTask() (waTask, bool) {
	waMu.Lock()
	defer waMu.Unlock()
	if len(waQueue) == 0 {
		return waTask{}, false
	}
	t := waQueue[0]
	waQueue = waQueue[1:]
	return t, true
}

func chWndProc(hwnd uintptr, msg uint32, wParam, lParam uintptr) uintptr {
	switch msg {
	case chWMSize:
		chResizeChildren()
		return 0
	case chWMCommand:
		id := int(wParam & 0xffff)
		if !licAuthorized {
			section := "MH Analysis"
			switch id {
			case idWhatsapp: section = "WhatsApp"
			case idRecords: section = "Records"
			case idMT5: section = "MT5 System"
			case chIDSignalLink: section = "Signal Link"
			}
			if id == idAnalysis || id == idWhatsapp || id == idRecords || id == idMT5 || id == chIDSignalLink {
				licSetNavNotice(section)
				chSwitchView(1)
				return 0
			}
		}
		switch id {
		case idAnalysis:
			chSwitchView(1)
		case idWhatsapp:
			chSwitchView(2)
		case idRecords:
			chSwitchView(3)
		case idMT5:
			chSwitchView(4)
			go func() {
				if err := chEnsureMT5Terminal(); err != nil {
					messageBox(hostHWND, err.Error(), "MT5 System", 0x10)
				}
			}()
		case chIDSignalLink:
			chShowNativeSettingsDialog(2)
		}
		return 0
	case chWMOpenAPISettings:
		chShowNativeSettingsDialog(1)
		return 0
	case chWMOpenWhatsAppSettings:
		chSwitchView(2)
		chShowNativeSettingsDialog(2)
		return 0
	case wmSwitchAnalysis:
		chSwitchView(1)
		return 0
	case wmSwitchWhatsApp:
		chSwitchView(2)
		return 0
	case wmWhatsAppSend:
		if task, ok := chPopWhatsAppTask(); ok {
			go func() {
				_ = chSendWhatsAppViaCDP(task.target)
			}()
		}
		return 0
	case chWMClose:
		chMu.Lock()
		for _, w := range []uintptr{chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd} {
			if w != 0 { chShowWindow.Call(w, chSWHide) }
		}
		chMu.Unlock()
		chDestroyWindow.Call(hwnd)
		return 0
	case chWMDestroy:
		chStopBrowsers()
		chPostQuitMessage.Call(0)
		return 0
	}
	r, _, _ := chDefWindowProc.Call(hwnd, uintptr(msg), wParam, lParam)
	return r
}


// MH_NATIVE_MT5_TERMINAL_V796
func chMT5Executable() (string, error) {
	if p := strings.TrimSpace(os.Getenv("MH_MT5_PATH")); p != "" {
		if st, err := os.Stat(p); err == nil && !st.IsDir() { return p, nil }
		return "", fmt.Errorf("MH_MT5_PATH does not point to a valid terminal executable: %s", p)
	}
	var roots []string
	for _, e := range []string{"PROGRAMFILES", "PROGRAMFILES(X86)"} {
		if p := strings.TrimSpace(os.Getenv(e)); p != "" { roots = append(roots, p) }
	}
	if p := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); p != "" { roots = append(roots, filepath.Join(p, "Programs")) }
	candidates := []string{}
	seen := map[string]bool{}
	add := func(p string) {
		key := strings.ToLower(filepath.Clean(p)); if seen[key] { return }; seen[key] = true; candidates = append(candidates, p)
	}
	for _, root := range roots {
		add(filepath.Join(root, "MetaTrader 5", "terminal64.exe"))
		add(filepath.Join(root, "MetaTrader 5", "terminal.exe"))
		entries, _ := os.ReadDir(root)
		for _, e := range entries {
			if !e.IsDir() { continue }
			d1 := filepath.Join(root, e.Name())
			add(filepath.Join(d1, "terminal64.exe")); add(filepath.Join(d1, "terminal.exe"))
			subs, _ := os.ReadDir(d1)
			for _, se := range subs {
				if !se.IsDir() { continue }
				d2 := filepath.Join(d1, se.Name())
				add(filepath.Join(d2, "terminal64.exe")); add(filepath.Join(d2, "terminal.exe"))
			}
		}
	}
	if p, err := exec.LookPath("terminal64.exe"); err == nil { add(p) }
	if p, err := exec.LookPath("terminal.exe"); err == nil { add(p) }
	for _, p := range candidates {
		if st, err := os.Stat(p); err == nil && !st.IsDir() { return p, nil }
	}
	return "", errors.New("MetaTrader 5 terminal64.exe was not found. Install your broker's MT5 terminal, then reopen MH Analysis. If you have more than one MT5 installation, set MH_MT5_PATH to the terminal64.exe you want to use.")
}

func chFindProcessWindow(pid uint32) uintptr {
	var found uintptr
	cb := syscall.NewCallback(func(hwnd, lparam uintptr) uintptr {
		var wp uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))
		if wp != pid { return 1 }
		vis, _, _ := chIsWindowVisible.Call(hwnd)
		if vis == 0 { return 1 }
		found = hwnd
		return 0
	})
	chEnumWindows.Call(cb, 0)
	return found
}

func chWaitForProcessWindow(pid uint32, timeout time.Duration) uintptr {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if h := chFindProcessWindow(pid); h != 0 { return h }
		time.Sleep(120 * time.Millisecond)
	}
	return 0
}

func chEnsureMT5Terminal() error {
	chMu.Lock()
	if chMT5Wnd != 0 {
		chMu.Unlock(); chApplyDesiredBrowserView(); /* V.27: EA bridge handles new signals; navigation never submits/retries an order. */; return nil // MH_NATIVE_MT5_PREFILL_V796
	}
	if chMT5Cmd != nil {
		chMu.Unlock(); return nil
	}
	chMu.Unlock()

	path, err := chMT5Executable()
	if err != nil { return err }
	cmd := exec.Command(path)
	if err := cmd.Start(); err != nil { return fmt.Errorf("Could not start MT5: %w", err) }

	chMu.Lock()
	if chStopping {
		chMu.Unlock(); _ = cmd.Process.Kill(); return errors.New("MH Analysis is closing")
	}
	chMT5Cmd = cmd
	chMu.Unlock()

	wnd := chWaitForProcessWindow(uint32(cmd.Process.Pid), 35*time.Second)
	if wnd == 0 {
		chMu.Lock(); if chMT5Cmd == cmd { chMT5Cmd = nil }; chMu.Unlock()
		return errors.New("MT5 started but its main window could not be embedded. Close any separately running MT5 instance and try again.")
	}
	chShowWindow.Call(wnd, chSWHide)
	chAttachBrowser(wnd)
	chMu.Lock()
	if chStopping {
		chMu.Unlock(); _ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run(); return errors.New("MH Analysis is closing")
	}
	chMT5Wnd = wnd
	chMu.Unlock()
	chResizeChildren()
	chApplyDesiredBrowserView()
	/* V.27: EA bridge handles new signals; navigation never submits/retries an order. */ // MH_NATIVE_MT5_PREFILL_V796
	return nil
}

func runChromeHost() {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	inst, _, _ := chGetModuleHandle.Call(0)
	className := chWstr("MHAnalysisEmbeddedShell")
	icon, _, _ := chLoadIcon.Call(inst, 1)
	if icon == 0 {
		icon, _, _ = chLoadIcon.Call(0, 32512)
	}
	cursor, _, _ := chLoadCursor.Call(0, chIDCArrow)
	themeBrush, _, _ := chCreateSolidBrush.Call(uintptr(8 | (22 << 8) | (26 << 16)))
	wc := chWndClassEx{
		CbSize:        uint32(unsafe.Sizeof(chWndClassEx{})),
		LpfnWndProc:   syscall.NewCallback(chWndProc),
		HInstance:     inst,
		HIcon:         icon,
		HCursor:       cursor,
		HbrBackground: themeBrush,
		LpszClassName: className,
		HIconSm:       icon,
	}
	if r, _, _ := chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc))); r == 0 {
		messageBox(0, "Could not initialize MH Analysis window.", "MH Analysis", 0x10)
		return
	}
	hostHWND, _, _ = chCreateWindowEx.Call(
		0,
		uintptr(unsafe.Pointer(className)),
		uintptr(unsafe.Pointer(chWstr("MH Analysis"))),
		chWSOverlapped,
		100, 100, 1280, 820,
		0, 0, inst, 0,
	)
	if hostHWND == 0 {
		messageBox(0, "Could not create MH Analysis window.", "MH Analysis", 0x10)
		return
	}
	btnAnalysis, _, _ = chCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("MH Analysis"))),
		chWSChild|chWSVisible, 8, 7, 140, 30, hostHWND, idAnalysis, inst, 0,
	)
	btnWhatsapp, _, _ = chCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("WhatsApp"))),
		chWSChild|chWSVisible, 156, 7, 140, 30, hostHWND, idWhatsapp, inst, 0,
	)
	btnRecords, _, _ = chCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Records"))),
		chWSChild|chWSVisible, 304, 7, 140, 30, hostHWND, idRecords, inst, 0,
	)
	btnMT5, _, _ = chCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("MT5 System"))),
		chWSChild|chWSVisible, 452, 7, 140, 30, hostHWND, idMT5, inst, 0,
	)
	chSignalLinkBtn, _, _ = chCreateWindowEx.Call(
		0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("Signal Link"))),
		chWSChild, 600, 7, 145, 30, hostHWND, chIDSignalLink, inst, 0,
	)
	dark := int32(1)
	if chDwmSetWindowAttribute.Find() == nil {
		chDwmSetWindowAttribute.Call(hostHWND, 20, uintptr(unsafe.Pointer(&dark)), unsafe.Sizeof(dark))
	}
	if chSetWindowTheme.Find() == nil {
		darkTheme := chWstr("DarkMode_Explorer")
		chSetWindowTheme.Call(btnAnalysis, uintptr(unsafe.Pointer(darkTheme)), 0)
		chSetWindowTheme.Call(btnWhatsapp, uintptr(unsafe.Pointer(darkTheme)), 0)
		chSetWindowTheme.Call(btnRecords, uintptr(unsafe.Pointer(darkTheme)), 0)
		chSetWindowTheme.Call(btnMT5, uintptr(unsafe.Pointer(darkTheme)), 0)
		chSetWindowTheme.Call(chSignalLinkBtn, uintptr(unsafe.Pointer(darkTheme)), 0)
	}
	chShowWindow.Call(hostHWND, chSWMaximize)
	chUpdateWindow.Call(hostHWND)

	// Start browsers asynchronously so host message handling never blocks.
	go func() {
		time.Sleep(150 * time.Millisecond)
		analysisDebugPort := 0
		if os.Getenv("MH_SMOKE_TEST") == "1" {
			analysisDebugPort = 17880
		}
		cmd, wnd, err := chLaunchBrowser("AnalysisProfile", serverURL, analysisDebugPort)
		if err != nil {
			return
		}
		chMu.Lock()
		if chStopping {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
			return
		}
		chAnalysisCmd, chAnalysisWnd = cmd, wnd
		chAttachBrowser(chAnalysisWnd)
		chMu.Unlock()
		chResizeChildren()
		chApplyDesiredBrowserView()
	}()

	go func() {
		time.Sleep(1000 * time.Millisecond)
		cmd, wnd, err := chLaunchBrowser("WhatsAppProfile", "https://web.whatsapp.com/", 17879)
		if err != nil {
			return
		}
		chMu.Lock()
		if chStopping {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
			return
		}
		chWhatsappCmd, chWhatsappWnd = cmd, wnd
		chAttachBrowser(chWhatsappWnd)
		chShowWindowAsync.Call(chWhatsappWnd, chSWHide)
		chMu.Unlock()
		chResizeChildren()
		chApplyDesiredBrowserView()
	}()

	go func() {
		time.Sleep(1300 * time.Millisecond)
		recordsDebugPort := 0
		if os.Getenv("MH_SMOKE_TEST") == "1" { recordsDebugPort = 17881 }
		cmd, wnd, err := chLaunchBrowser("RecordsProfile", serverURL+"records.html", recordsDebugPort)
		if err != nil { return }
		chMu.Lock()
		if chStopping {
			chMu.Unlock()
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
			return
		}
		chRecordsCmd, chRecordsWnd = cmd, wnd
		chAttachBrowser(chRecordsWnd)
		chShowWindowAsync.Call(chRecordsWnd, chSWHide)
		chMu.Unlock()
		chResizeChildren()
		chApplyDesiredBrowserView()
	}()

	var m chMsg
	for {
		r, _, _ := chGetMessage.Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) <= 0 {
			break
		}
		chTranslateMessage.Call(uintptr(unsafe.Pointer(&m)))
		chDispatchMessage.Call(uintptr(unsafe.Pointer(&m)))
	}
}

func chStopBrowsers() {
	// Mark shutdown first so browser goroutines that finish late cannot escape cleanup.
	chMu.Lock()
	chStopping = true
	cmds := []*exec.Cmd{chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd}
	chAnalysisCmd, chWhatsappCmd, chRecordsCmd, chMT5Cmd = nil, nil, nil, nil
	chAnalysisWnd, chWhatsappWnd, chRecordsWnd, chMT5Wnd = 0, 0, 0, 0
	chMu.Unlock()

	// Never hold the UI mutex while waiting for taskkill.
	for _, cmd := range cmds {
		if cmd != nil && cmd.Process != nil {
			_ = exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run()
		}
	}
}

type chCDPPage struct {
	Type                 string `json:"type"`
	URL                  string `json:"url"`
	WebSocketDebuggerURL string `json:"webSocketDebuggerUrl"`
}

func chCDPPageSocket() (string, error) {
	client := &http.Client{Timeout: 2 * time.Second}
	var last error
	for i := 0; i < 40; i++ {
		resp, err := client.Get("http://127.0.0.1:17879/json/list")
		if err == nil {
			var pages []chCDPPage
			if decErr := json.NewDecoder(resp.Body).Decode(&pages); decErr == nil {
				_ = resp.Body.Close()
				for _, p := range pages {
					if p.Type == "page" && p.WebSocketDebuggerURL != "" {
						return p.WebSocketDebuggerURL, nil
					}
				}
			} else {
				_ = resp.Body.Close()
			}
		} else {
			last = err
		}
		time.Sleep(250 * time.Millisecond)
	}
	if last == nil {
		last = errors.New("WhatsApp browser DevTools page was not available")
	}
	return "", last
}

func chCDPCommand(conn *websocket.Conn, id int, method string, params any) (map[string]any, error) {
	req := map[string]any{"id": id, "method": method}
	if params != nil {
		req["params"] = params
	}
	if err := conn.WriteJSON(req); err != nil {
		return nil, err
	}
	_ = conn.SetReadDeadline(time.Now().Add(6 * time.Second))
	for {
		var msg map[string]any
		if err := conn.ReadJSON(&msg); err != nil {
			return nil, err
		}
		if n, ok := msg["id"].(float64); ok && int(n) == id {
			if e, ok := msg["error"]; ok {
				return msg, fmt.Errorf("DevTools error: %v", e)
			}
			return msg, nil
		}
	}
}

func chEvalValue(msg map[string]any) string {
	res, _ := msg["result"].(map[string]any)
	inner, _ := res["result"].(map[string]any)
	if v, ok := inner["value"].(string); ok {
		return v
	}
	return ""
}

func chSendWhatsAppViaCDP(target string) error {
	chCDPMu.Lock()
	defer chCDPMu.Unlock()
	wsURL, err := chCDPPageSocket()
	if err != nil {
		return err
	}
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		return err
	}
	defer conn.Close()
	id := 1
	if _, err = chCDPCommand(conn, id, "Page.enable", map[string]any{}); err != nil {
		return err
	}
	id++
	if _, err = chCDPCommand(conn, id, "Page.navigate", map[string]any{"url": target}); err != nil {
		return err
	}
	id++
	js := `(() => {
		const body=(document.body && document.body.innerText)||'';
		if(/scan.*qr|use whatsapp on your computer/i.test(body)) return 'login';
		const candidates=[...document.querySelectorAll('button')];
		let b=candidates.find(x => ((x.getAttribute('aria-label')||'').toLowerCase()==='send'));
		if(!b){
			const icon=document.querySelector('span[data-icon="send"], span[data-testid="send"]');
			if(icon) b=icon.closest('button') || icon.parentElement;
		}
		if(b && !b.disabled){ b.click(); return 'sent'; }
		return 'wait';
	})()`
	for i := 0; i < 50; i++ {
		time.Sleep(400 * time.Millisecond)
		msg, e := chCDPCommand(conn, id, "Runtime.evaluate", map[string]any{"expression": js, "returnByValue": true, "awaitPromise": true})
		id++
		if e != nil {
			continue
		}
		switch chEvalValue(msg) {
		case "sent":
			return nil
		case "login":
			return errors.New("WhatsApp login is required")
		}
	}
	return errors.New("WhatsApp send button was not ready")
}
