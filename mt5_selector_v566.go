//go:build windows

package main

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"unicode/utf16"
	"unsafe"
)

const (
	wmMT5SelectedV566 = 0x8F5A
	v566IDBrowse      = 5661
	v566IDUse         = 5662
	v566IDCancel      = 5663
	v566IDPath        = 5664
	v566ESReadOnly    = 0x0800
)

var (
	v566Comdlg32           = syscall.NewLazyDLL("comdlg32.dll")
	v566GetOpenFileNameW   = v566Comdlg32.NewProc("GetOpenFileNameW")
	v566SelectorDialog     uintptr
	v566SelectorPath       uintptr
	v566SelectorClassReady bool
	v566SelectorBrush      uintptr
	v566MT5SelectionConfirmed bool
)

type v566OpenFileName struct {
	LStructSize       uint32
	HwndOwner         uintptr
	HInstance         uintptr
	LpstrFilter       *uint16
	LpstrCustomFilter *uint16
	NMaxCustFilter    uint32
	NFilterIndex      uint32
	LpstrFile         *uint16
	NMaxFile          uint32
	LpstrFileTitle    *uint16
	NMaxFileTitle     uint32
	LpstrInitialDir   *uint16
	LpstrTitle        *uint16
	Flags             uint32
	NFileOffset       uint16
	NFileExtension    uint16
	LpstrDefExt       *uint16
	LCustData         uintptr
	LpfnHook          uintptr
	LpTemplateName    *uint16
	PvReserved        uintptr
	DwReserved        uint32
	FlagsEx           uint32
}

func v566UTF16Multi(s string) []uint16 {
	u := utf16.Encode([]rune(s))
	return append(u, 0)
}

func v566NormalizeMT5Path(p string) string {
	p = strings.Trim(strings.TrimSpace(p), "\"")
	if p == "" { return "" }
	if a, err := filepath.Abs(p); err == nil { p = a }
	return filepath.Clean(p)
}

func v566ValidateMT5Path(p string) (string, error) {
	p = v566NormalizeMT5Path(p)
	if p == "" { return "", errors.New("Select the MT5 terminal executable first.") }
	base := strings.ToLower(filepath.Base(p))
	if base != "terminal64.exe" && base != "terminal.exe" {
		return "", errors.New("Please select the broker MT5 terminal64.exe (or terminal.exe).")
	}
	st, err := os.Stat(p)
	if err != nil || st.IsDir() { return "", errors.New("The selected MT5 executable is not available.") }
	return p, nil
}

func v566SelectedMT5Path() (string, error) {
	v := getSettings()
	return v566ValidateMT5Path(v.MT5Path)
}

func v566SaveMT5Path(p string) error {
	p, err := v566ValidateMT5Path(p)
	if err != nil { return err }
	settingsMu.Lock()
	cfg.MT5Path = p
	settingsMu.Unlock()
	return saveSettings()
}

func v566ProcessFullPath(pid uint32) string {
	const processQueryLimitedInformation = 0x1000
	h, _, _ := v36OpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
	if h == 0 { return "" }
	defer v36CloseHandle.Call(h)
	buf := make([]uint16, 32768)
	n := uint32(len(buf))
	ok, _, _ := v36QueryFullProcessImageName.Call(h, 0, uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&n)))
	if ok == 0 || n == 0 { return "" }
	return v566NormalizeMT5Path(syscall.UTF16ToString(buf[:n]))
}

func v566SamePath(a, b string) bool {
	a = v566NormalizeMT5Path(a)
	b = v566NormalizeMT5Path(b)
	return a != "" && b != "" && strings.EqualFold(a, b)
}

func v566WindowMatchesPath(hwnd uintptr, path string) bool {
	if hwnd == 0 { return false }
	var pid uint32
	chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
	return pid != 0 && v566SamePath(v566ProcessFullPath(pid), path)
}

func v566FindWindowForPath(path string) uintptr {
	path = v566NormalizeMT5Path(path)
	if path == "" { return 0 }
	var found uintptr
	var bestArea int64
	cb := syscall.NewCallback(func(hwnd, _ uintptr) uintptr {
		if hwnd == 0 || hwnd == hostHWND { return 1 }
		var pid uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
		if pid == 0 || !v566SamePath(v566ProcessFullPath(pid), path) { return 1 }
		var r chRect
		ok, _, _ := v41GetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&r)))
		if ok == 0 { return 1 }
		w, h := int64(r.R-r.L), int64(r.B-r.T)
		if w < 80 || h < 60 { return 1 }
		if area := w*h; area > bestArea { bestArea = area; found = hwnd }
		return 1
	})
	chEnumWindows.Call(cb, 0)
	return found
}

func v566FindSelectedMT5Window() uintptr {
	path, err := v566SelectedMT5Path()
	if err != nil { return 0 }
	return v566FindWindowForPath(path)
}

func v566FindWindowForPID(pid uint32) uintptr {
	if pid == 0 { return 0 }
	var found uintptr
	var bestArea int64
	cb := syscall.NewCallback(func(hwnd, _ uintptr) uintptr {
		var wp uint32
		chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&wp)))
		if wp != pid { return 1 }
		var r chRect
		ok, _, _ := v41GetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&r)))
		if ok == 0 { return 1 }
		w, h := int64(r.R-r.L), int64(r.B-r.T)
		if w < 80 || h < 60 { return 1 }
		if area := w*h; area > bestArea { bestArea = area; found = hwnd }
		return 1
	})
	chEnumWindows.Call(cb, 0)
	return found
}

func v566BrowseMT5Executable(owner uintptr) (string, bool) {
	buf := make([]uint16, 32768)
	current := chWindowText(v566SelectorPath)
	if current != "" {
		u := utf16.Encode([]rune(current))
		if len(u) >= len(buf) { u = u[:len(buf)-1] }
		copy(buf, u)
	}
	filter := v566UTF16Multi("MetaTrader 5 Terminal (*.exe)\x00*.exe\x00All Files (*.*)\x00*.*\x00")
	title, _ := syscall.UTF16PtrFromString("Select the exact MT5 terminal executable")
	defExt, _ := syscall.UTF16PtrFromString("exe")
	ofn := v566OpenFileName{
		LStructSize: uint32(unsafe.Sizeof(v566OpenFileName{})),
		HwndOwner: owner,
		LpstrFilter: &filter[0],
		NFilterIndex: 1,
		LpstrFile: &buf[0],
		NMaxFile: uint32(len(buf)),
		LpstrTitle: title,
		Flags: 0x00001000 | 0x00000800 | 0x00080000 | 0x00000008,
		LpstrDefExt: defExt,
	}
	ok, _, _ := v566GetOpenFileNameW.Call(uintptr(unsafe.Pointer(&ofn)))
	if ok == 0 { return "", false }
	p := syscall.UTF16ToString(buf)
	if _, err := v566ValidateMT5Path(p); err != nil {
		messageBox(owner, err.Error(), "MH MT5", 0x10)
		return "", false
	}
	return v566NormalizeMT5Path(p), true
}

func v566SelectorWndProc(hwnd uintptr, msg uint32, wParam, lParam uintptr) uintptr {
	switch msg {
	case chWMCommand:
		id := int(wParam & 0xffff)
		switch id {
		case v566IDBrowse:
			if p, ok := v566BrowseMT5Executable(hwnd); ok && v566SelectorPath != 0 {
				chSettingsSetWindowText.Call(v566SelectorPath, uintptr(unsafe.Pointer(chWstr(p))))
			}
			return 0
		case v566IDUse:
			p := chWindowText(v566SelectorPath)
			if err := v566SaveMT5Path(p); err != nil {
				messageBox(hwnd, err.Error(), "MH MT5", 0x10)
				return 0
			}
			v566MT5SelectionConfirmed = true
			chDestroyWindow.Call(hwnd)
			postMessage(hostHWND, wmMT5SelectedV566, 0, 0)
			return 0
		case v566IDCancel:
			chDestroyWindow.Call(hwnd)
			return 0
		}
	case chWMClose:
		chDestroyWindow.Call(hwnd)
		return 0
	case chWMDestroy:
		if hwnd == v566SelectorDialog { v566SelectorDialog = 0; v566SelectorPath = 0 }
		return 0
	case chWMColorStatic:
		if v566SelectorBrush != 0 {
			chSettingsSetBkMode.Call(wParam, 1)
			chSettingsSetTextColor.Call(wParam, 0x00FFFFFF)
			return v566SelectorBrush
		}
	}
	r, _, _ := chDefWindowProc.Call(hwnd, uintptr(msg), wParam, lParam)
	return r
}

func v566EnsureSelectorClass() bool {
	if v566SelectorClassReady { return true }
	inst, _, _ := chGetModuleHandle.Call(0)
	cursor, _, _ := chLoadCursor.Call(0, chIDCArrow)
	if v566SelectorBrush == 0 { v566SelectorBrush, _, _ = chCreateSolidBrush.Call(uintptr(8 | (22 << 8) | (26 << 16))) }
	wc := chWndClassEx{
		CbSize: uint32(unsafe.Sizeof(chWndClassEx{})),
		LpfnWndProc: syscall.NewCallback(v566SelectorWndProc),
		HInstance: inst,
		HCursor: cursor,
		HbrBackground: v566SelectorBrush,
		LpszClassName: chWstr("MHAnalysisMT5SelectorV566"),
	}
	if r, _, _ := chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc))); r == 0 { return false }
	v566SelectorClassReady = true
	return true
}

func v566ShowMT5Selector() {
	if v566SelectorDialog != 0 {
		chShowWindow.Call(v566SelectorDialog, chSWShow)
		chSetForegroundWindow.Call(v566SelectorDialog)
		return
	}
	if !v566EnsureSelectorClass() { return }

	const dlgW int32 = 760
	const dlgH int32 = 270
	x, y := int32(120), int32(120)
	if hostHWND != 0 {
		var rr chRect
		if ok, _, _ := chSettingsGetWindowRect.Call(hostHWND, uintptr(unsafe.Pointer(&rr))); ok != 0 {
			x = rr.L + (rr.R-rr.L-dlgW)/2
			y = rr.T + (rr.B-rr.T-dlgH)/2
			if x < 0 { x = 0 }; if y < 0 { y = 0 }
		}
	}
	inst, _, _ := chGetModuleHandle.Call(0)
	v566SelectorDialog, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("MHAnalysisMT5SelectorV566"))), uintptr(unsafe.Pointer(chWstr("MH MT5 - Select Terminal"))), chWSOverlapped|chWSVisible, uintptr(x), uintptr(y), uintptr(dlgW), uintptr(dlgH), hostHWND, 0, inst, 0)
	if v566SelectorDialog == 0 { return }

	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("STATIC"))), uintptr(unsafe.Pointer(chWstr("Select the exact MT5 terminal that MH Analysis may embed."))), chWSChild|chWSVisible, 22, 20, 700, 24, v566SelectorDialog, 0, inst, 0)
	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("STATIC"))), uintptr(unsafe.Pointer(chWstr("All other MT5 terminals will remain independent and will not be hidden, minimized, closed, or re-parented."))), chWSChild|chWSVisible, 22, 48, 700, 24, v566SelectorDialog, 0, inst, 0)
	value := getSettings().MT5Path
	v566SelectorPath, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("EDIT"))), uintptr(unsafe.Pointer(chWstr(value))), chWSChild|chWSVisible|chWSBorder|v566ESReadOnly, 22, 82, 700, 34, v566SelectorDialog, v566IDPath, inst, 0)
	browse, _, _ := chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("SELECT EXE"))), chWSChild|chWSVisible|chWSTabStop, 22, 138, 180, 38, v566SelectorDialog, v566IDBrowse, inst, 0)
	use, _, _ := chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("USE SELECTED"))), chWSChild|chWSVisible|chWSTabStop, 214, 138, 180, 38, v566SelectorDialog, v566IDUse, inst, 0)
	cancel, _, _ := chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("CANCEL"))), chWSChild|chWSVisible|chWSTabStop, 406, 138, 180, 38, v566SelectorDialog, v566IDCancel, inst, 0)

	dark := int32(1)
	if chDwmSetWindowAttribute.Find() == nil { chDwmSetWindowAttribute.Call(v566SelectorDialog, 20, uintptr(unsafe.Pointer(&dark)), unsafe.Sizeof(dark)) }
	if chSetWindowTheme.Find() == nil {
		theme := chWstr("DarkMode_Explorer")
		for _, h := range []uintptr{browse, use, cancel, v566SelectorPath} { if h != 0 { chSetWindowTheme.Call(h, uintptr(unsafe.Pointer(theme)), 0) } }
	}
	chShowWindow.Call(v566SelectorDialog, chSWShow)
	chUpdateWindow.Call(v566SelectorDialog)
	chSetForegroundWindow.Call(v566SelectorDialog)
}

func v566RestoreStandaloneMT5(hwnd uintptr) {
	if hwnd == 0 { return }
	chSetParent.Call(hwnd, 0)
	style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
	style &^= chWSChild
	style |= chWSOverlapped | chWSVisible
	chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
	exStyle, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(19))
	exStyle &^= chEXToolWindow
	exStyle |= chEXAppWindow
	chSetWindowLongPtr.Call(hwnd, ^uintptr(19), exStyle)
	chSetWindowPos.Call(hwnd, 0, 80, 80, 1280, 820, chSWPNoZOrder|chSWPNoActivate|chSWPFrame)
	chShowWindow.Call(hwnd, chSWShow)
}
