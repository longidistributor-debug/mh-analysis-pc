//go:build windows

package main

import (
    "errors"
    "fmt"
    "os/exec"
    "path/filepath"
    "strings"
    "syscall"
    "time"
    "unsafe"
)

var (
    v36OpenProcess = chKernel32.NewProc("OpenProcess")
    v36CloseHandle = chKernel32.NewProc("CloseHandle")
    v36QueryFullProcessImageName = chKernel32.NewProc("QueryFullProcessImageNameW")
    v36GetParent = chUser32.NewProc("GetParent")
    v41GetWindowRect = chUser32.NewProc("GetWindowRect")
)

// V41: identify MT5 by its real process image. Do NOT reject a terminal window merely
// because GetParent is non-zero: for top-level owned windows Win32 GetParent can return
// the owner HWND, which was the V40 false-negative that sent the app down the wrong path.
func v36ProcessImage(pid uint32) string {
    const processQueryLimitedInformation = 0x1000
    h, _, _ := v36OpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
    if h == 0 { return "" }
    defer v36CloseHandle.Call(h)
    buf := make([]uint16, 32768)
    n := uint32(len(buf))
    ok, _, _ := v36QueryFullProcessImageName.Call(h, 0, uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&n)))
    if ok == 0 || n == 0 { return "" }
    return strings.ToLower(filepath.Base(syscall.UTF16ToString(buf[:n])))
}

func v36FindRunningMT5() uintptr {
    var found uintptr
    var bestArea int64
    cb := syscall.NewCallback(func(hwnd, _ uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND { return 1 }
        var pid uint32
        chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
        image := v36ProcessImage(pid)
        if image != "terminal64.exe" && image != "terminal.exe" { return 1 }

        // EnumWindows already enumerates top-level windows. Pick the largest real terminal
        // surface instead of an arbitrary broker splash/dialog/owned helper window.
        var r chRect
        ok, _, _ := v41GetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&r)))
        if ok == 0 { return 1 }
        w := int64(r.R - r.L)
        h := int64(r.B - r.T)
        if w < 300 || h < 200 { return 1 }
        area := w * h
        if area > bestArea {
            bestArea = area
            found = hwnd
        }
        return 1
    })
    chEnumWindows.Call(cb, 0)
    return found
}

// V41_VERIFIED_TRUE_CHILD: success means GetParent(MT5)==MH Analysis host, not merely
// that MT5 was moved over the same screen coordinates.
func v36EmbedMT5(hwnd uintptr) bool {
    if hwnd == 0 || hostHWND == 0 { return false }

    chShowWindow.Call(hwnd, chSWHide)

    // Parent first, then normalize the terminal into a genuine child window.
    chSetParent.Call(hwnd, hostHWND)
    parent, _, _ := v36GetParent.Call(hwnd)
    if parent != hostHWND { return false }

    style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
    style &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
    style |= chWSChild | chWSVisible
    chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)

    // Force non-client recalculation after changing parent/style.
    chSetWindowPos.Call(hwnd, 0, 0, uintptr(barH), 1, 1, chSWPNoZOrder|chSWPNoActivate|chSWPFrame)

    // Verify again after style mutation. Never cache/show an external terminal as embedded.
    parent, _, _ = v36GetParent.Call(hwnd)
    if parent != hostHWND {
        chShowWindow.Call(hwnd, chSWHide)
        return false
    }

    chMu.Lock()
    chMT5Wnd = hwnd
    chMu.Unlock()
    chResizeChildren()
    chApplyDesiredBrowserView()
    return true
}

func chEnsureMT5TerminalV36() error {
    // Re-use the exact embedded HWND on every later MT5 System click.
    chMu.Lock()
    existingEmbedded := chMT5Wnd
    chMu.Unlock()
    if existingEmbedded != 0 {
        parent, _, _ := v36GetParent.Call(existingEmbedded)
        if parent == hostHWND {
            chResizeChildren()
            chShowWindow.Call(existingEmbedded, chSWShow)
            chFocusEmbeddedBrowser(existingEmbedded)
            go mt5ApplyLatestQueued()
            return nil
        }
        chMu.Lock()
        if chMT5Wnd == existingEmbedded { chMT5Wnd = 0 }
        chMu.Unlock()
    }

    chMu.Lock()
    if chMT5StartingV34 { chMu.Unlock(); return nil }
    chMT5StartingV34 = true
    chMu.Unlock()
    defer func(){ chMu.Lock(); chMT5StartingV34=false; chMu.Unlock() }()

    if hwnd := v36FindRunningMT5(); hwnd != 0 {
        if !v36EmbedMT5(hwnd) { return errors.New("Installed MT5 was detected, but Windows did not allow it to become a child of MH Analysis") }
        go mt5ApplyLatestQueued()
        return nil
    }

    path, err := chMT5Executable()
    if err != nil { return err }
    cmd := exec.Command(path)
    cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow:true, CreationFlags:0x08000000}
    if err := cmd.Start(); err != nil { return fmt.Errorf("Could not start MT5: %w", err) }
    chMu.Lock(); chMT5Cmd=cmd; chMu.Unlock()

    deadline := time.Now().Add(15*time.Second)
    var hwnd uintptr
    for time.Now().Before(deadline) {
        hwnd = v36FindRunningMT5()
        if hwnd != 0 { break }
        time.Sleep(120*time.Millisecond)
    }
    if hwnd == 0 { return errors.New("MT5 started but its main terminal window could not be detected") }
    if !v36EmbedMT5(hwnd) { return errors.New("MT5 started, but Windows did not allow it to become a child of MH Analysis") }
    go mt5ApplyLatestQueued()
    return nil
}
