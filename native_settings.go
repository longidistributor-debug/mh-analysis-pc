package main

import (
	"strings"
	"syscall"
	"unsafe"
)

var (
	chSettingsUser32 = syscall.NewLazyDLL("user32.dll")
	chSettingsGdi32  = syscall.NewLazyDLL("gdi32.dll")

	chSettingsGetWindowTextLength = chSettingsUser32.NewProc("GetWindowTextLengthW")
	chSettingsGetWindowText       = chSettingsUser32.NewProc("GetWindowTextW")
	chSettingsSetWindowText       = chSettingsUser32.NewProc("SetWindowTextW")
	chSettingsSetFocus            = chSettingsUser32.NewProc("SetFocus")
	chSettingsGetWindowRect       = chSettingsUser32.NewProc("GetWindowRect")
	chSettingsGetDlgItem          = chSettingsUser32.NewProc("GetDlgItem")
	chSettingsSendMessage         = chSettingsUser32.NewProc("SendMessageW")
	chSettingsSetBkMode           = chSettingsGdi32.NewProc("SetBkMode")
	chSettingsSetTextColor        = chSettingsGdi32.NewProc("SetTextColor")
)

const (
	chWMOpenAPISettings      = 0x8010
	chWMOpenWhatsAppSettings = 0x8011
	chWMColorStatic          = 0x0138
	chIDSignalLink           = 1003
	chIDSettingsSave         = 2001
	chIDSettingsClear        = 2002
	chIDSettingsCancel       = 2003
	chIDSettingsEdit         = 2101
	chIDSettingsEdit2        = 2102
	chESAutoHScroll          = 0x0080
	chWSTabStop              = 0x00010000
	chEMSetSel               = 0x00B1
)

var (
	chSignalLinkBtn   uintptr
	chSettingsDialog  uintptr
	chSettingsEdit    uintptr
	chSettingsEdit2   uintptr
	chSettingsMode    int
	chSettingsClassOK bool
	chSettingsBrush   uintptr
)

func chWindowText(hwnd uintptr) string {
	if hwnd == 0 {
		return ""
	}
	n, _, _ := chSettingsGetWindowTextLength.Call(hwnd)
	if n == 0 {
		return ""
	}
	buf := make([]uint16, int(n)+1)
	chSettingsGetWindowText.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), n+1)
	return syscall.UTF16ToString(buf)
}

func chSaveNativeSetting(mode int, value string) error {
	return chSaveNativeSettings(mode, value, "")
}

func chSaveNativeSettings(mode int, value1, value2 string) error {
	value1 = strings.TrimSpace(value1)
	value2 = strings.TrimSpace(value2)
	settingsMu.Lock()
	if mode == 1 {
		cfg.APIKey = value1
	} else if mode == 2 {
		cfg.WhatsAppLink = value1
		cfg.WhatsAppLink2 = value2
	}
	settingsMu.Unlock()
	return saveSettings()
}

func chSettingsEditFor(hwnd uintptr) uintptr {
	if hwnd != 0 {
		if h, _, _ := chSettingsGetDlgItem.Call(hwnd, chIDSettingsEdit); h != 0 {
			return h
		}
	}
	return chSettingsEdit
}

func chSettingsWndProc(hwnd uintptr, msg uint32, wParam, lParam uintptr) uintptr {
	switch msg {
	case chWMCommand:
		id := int(wParam & 0xffff)
		switch id {
		case chIDSettingsSave:
			edit := chSettingsEditFor(hwnd)
			if edit == 0 { messageBox(hwnd, "Could not read setting field.", "MH Analysis", 0x10); return 0 }
			value2 := ""
			if chSettingsMode == 2 && chSettingsEdit2 != 0 { value2 = chWindowText(chSettingsEdit2) }
			if err := chSaveNativeSettings(chSettingsMode, chWindowText(edit), value2); err != nil {
				messageBox(hwnd, "Could not save setting: "+err.Error(), "MH Analysis", 0x10)
				return 0
			}
			chDestroyWindow.Call(hwnd)
			return 0
		case chIDSettingsClear:
			if err := chSaveNativeSettings(chSettingsMode, "", ""); err != nil {
				messageBox(hwnd, "Could not clear setting: "+err.Error(), "MH Analysis", 0x10)
				return 0
			}
			chDestroyWindow.Call(hwnd)
			return 0
		case chIDSettingsCancel:
			chDestroyWindow.Call(hwnd)
			return 0
		}
	case chWMClose:
		chDestroyWindow.Call(hwnd)
		return 0
	case chWMDestroy:
		if hwnd == chSettingsDialog {
			chSettingsDialog = 0
			chSettingsEdit = 0
			chSettingsEdit2 = 0
			chSettingsMode = 0
		}
		return 0
	case chWMColorStatic:
		if chSettingsBrush != 0 {
			chSettingsSetBkMode.Call(wParam, 1)
			chSettingsSetTextColor.Call(wParam, 0x00FFFFFF)
			return chSettingsBrush
		}
	}
	r, _, _ := chDefWindowProc.Call(hwnd, uintptr(msg), wParam, lParam)
	return r
}

func chEnsureSettingsClass() bool {
	if chSettingsClassOK {
		return true
	}
	inst, _, _ := chGetModuleHandle.Call(0)
	cursor, _, _ := chLoadCursor.Call(0, chIDCArrow)
	if chSettingsBrush == 0 {
		chSettingsBrush, _, _ = chCreateSolidBrush.Call(uintptr(8 | (22 << 8) | (26 << 16)))
	}
	wc := chWndClassEx{
		CbSize:        uint32(unsafe.Sizeof(chWndClassEx{})),
		LpfnWndProc:   syscall.NewCallback(chSettingsWndProc),
		HInstance:     inst,
		HCursor:       cursor,
		HbrBackground: chSettingsBrush,
		LpszClassName: chWstr("MHAnalysisSettingsDialog"),
	}
	if r, _, _ := chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc))); r == 0 {
		return false
	}
	chSettingsClassOK = true
	return true
}

func chShowNativeSettingsDialog(mode int) {
	if mode != 1 && mode != 2 {
		return
	}
	if chSettingsDialog != 0 {
		if chSettingsMode == mode {
			chShowWindow.Call(chSettingsDialog, chSWShow)
			chSetForegroundWindow.Call(chSettingsDialog)
			if edit := chSettingsEditFor(chSettingsDialog); edit != 0 {
				chSettingsSetFocus.Call(edit)
				chSettingsSendMessage.Call(edit, chEMSetSel, 0, ^uintptr(0))
			}
			return
		}
		chDestroyWindow.Call(chSettingsDialog)
	}
	if !chEnsureSettingsClass() {
		return
	}

	title := "API Access Key"
	label := "API Access Key"
	v := getSettings()
	value := v.APIKey
	value2 := ""
	if mode == 2 {
		title = "WhatsApp Signal Links"
		label = "WhatsApp Signal Link / Number 1"
		value = v.WhatsAppLink
		value2 = v.WhatsAppLink2
	}

	const dlgW int32 = 680
	dlgH := int32(235)
	if mode == 2 { dlgH = 315 }
	x, y := int32(120), int32(120)
	if hostHWND != 0 {
		var rr chRect
		if ok, _, _ := chSettingsGetWindowRect.Call(hostHWND, uintptr(unsafe.Pointer(&rr))); ok != 0 {
			x = rr.L + (rr.R-rr.L-dlgW)/2
			y = rr.T + (rr.B-rr.T-dlgH)/2
			if x < 0 {
				x = 0
			}
			if y < 0 {
				y = 0
			}
		}
	}

	inst, _, _ := chGetModuleHandle.Call(0)
	chSettingsMode = mode
	chSettingsDialog, _, _ = chCreateWindowEx.Call(
		0,
		uintptr(unsafe.Pointer(chWstr("MHAnalysisSettingsDialog"))),
		uintptr(unsafe.Pointer(chWstr(title))),
		chWSOverlapped|chWSVisible,
		uintptr(x), uintptr(y), uintptr(dlgW), uintptr(dlgH),
		hostHWND, 0, inst, 0,
	)
	if chSettingsDialog == 0 {
		chSettingsMode = 0
		return
	}

	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("STATIC"))), uintptr(unsafe.Pointer(chWstr(label))), chWSChild|chWSVisible, 20, 22, 620, 24, chSettingsDialog, 0, inst, 0)
	chSettingsEdit, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("EDIT"))), uintptr(unsafe.Pointer(chWstr(value))), chWSChild|chWSVisible|chWSBorder|chWSTabStop|chESAutoHScroll, 20, 52, 620, 34, chSettingsDialog, chIDSettingsEdit, inst, 0)
	buttonY := uintptr(105)
	if mode == 2 {
		chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("STATIC"))), uintptr(unsafe.Pointer(chWstr("WhatsApp Signal Link / Number 2"))), chWSChild|chWSVisible, 20, 100, 620, 24, chSettingsDialog, 0, inst, 0)
		chSettingsEdit2, _, _ = chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("EDIT"))), uintptr(unsafe.Pointer(chWstr(value2))), chWSChild|chWSVisible|chWSBorder|chWSTabStop|chESAutoHScroll, 20, 130, 620, 34, chSettingsDialog, chIDSettingsEdit2, inst, 0)
		buttonY = 185
	} else {
		chSettingsEdit2 = 0
	}
	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("SAVE"))), chWSChild|chWSVisible|chWSTabStop, 20, buttonY, 150, 36, chSettingsDialog, chIDSettingsSave, inst, 0)
	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("CLEAR"))), chWSChild|chWSVisible|chWSTabStop, 180, buttonY, 150, 36, chSettingsDialog, chIDSettingsClear, inst, 0)
	chCreateWindowEx.Call(0, uintptr(unsafe.Pointer(chWstr("BUTTON"))), uintptr(unsafe.Pointer(chWstr("CANCEL"))), chWSChild|chWSVisible|chWSTabStop, 340, buttonY, 150, 36, chSettingsDialog, chIDSettingsCancel, inst, 0)

	dark := int32(1)
	if chDwmSetWindowAttribute.Find() == nil {
		chDwmSetWindowAttribute.Call(chSettingsDialog, 20, uintptr(unsafe.Pointer(&dark)), unsafe.Sizeof(dark))
	}
	chShowWindow.Call(chSettingsDialog, chSWShow)
	chUpdateWindow.Call(chSettingsDialog)
	chSetForegroundWindow.Call(chSettingsDialog)
	if chSettingsEdit != 0 {
		chSettingsSetFocus.Call(chSettingsEdit)
		chSettingsSendMessage.Call(chSettingsEdit, chEMSetSel, 0, ^uintptr(0))
	}
}
