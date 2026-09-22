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
)

// V36_MT5_NATIVE_PROCESS: broker window titles are irrelevant; identify the real terminal process.
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
    cb := syscall.NewCallback(func(hwnd, _ uintptr) uintptr {
        if hwnd == 0 || hwnd == hostHWND { return 1 }
        parent, _, _ := v36GetParent.Call(hwnd)
        if parent != 0 { return 1 }
        var pid uint32
        chGetWindowThreadPID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
        image := v36ProcessImage(pid)
        if image == "terminal64.exe" || image == "terminal.exe" {
            found = hwnd
            return 0
        }
        return 1
    })
    chEnumWindows.Call(cb, 0)
    return found
}

// V36_VERIFIED_EMBED: never report success unless SetParent actually made MT5 a child of MH Analysis.
func v36EmbedMT5(hwnd uintptr) bool {
    if hwnd == 0 || hostHWND == 0 { return false }
    chShowWindow.Call(hwnd, chSWHide)
    style, _, _ := chGetWindowLongPtr.Call(hwnd, ^uintptr(15))
    style &^= chWSPopup | chWSCaption | chWSBorder | chWSDlgFrame | chWSThickFrame | chWSMinBox | chWSMaxBox | chWSSysMenu
    style |= chWSChild | chWSVisible
    chSetWindowLongPtr.Call(hwnd, ^uintptr(15), style)
    chSetParent.Call(hwnd, hostHWND)
    parent, _, _ := v36GetParent.Call(hwnd)
    if parent != hostHWND { return false }
    chMu.Lock(); chMT5Wnd = hwnd; chMu.Unlock()
    chResizeChildren()
    chApplyDesiredBrowserView()
    return true
}

// chEnsureMT5TerminalV36 first attaches an already-running installed MT5 and only launches
// a terminal when none exists. A launched terminal is hidden until verified as embedded.
func chEnsureMT5TerminalV36() error {
    // V39_MT5_RESHOW: if MT5 is already embedded, re-show/re-parent/resize/focus the same HWND.
    chMu.Lock()
    existingEmbedded := chMT5Wnd
    chMu.Unlock()
    if existingEmbedded != 0 {
        if v36EmbedMT5(existingEmbedded) {
            chShowWindow.Call(existingEmbedded, chSWShow)
            chResizeChildren()
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
        if !v36EmbedMT5(hwnd) { return errors.New("Installed MT5 was found but Windows refused to embed it inside MH Analysis") }
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
    if hwnd == 0 { return errors.New("MT5 started but its main window could not be detected for embedding") }
    if !v36EmbedMT5(hwnd) { return errors.New("MT5 started but could not be embedded inside MH Analysis") }
    go mt5ApplyLatestQueued()
    return nil
}
