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

var v5410MT5ExeBase string

var (
    v36OpenProcess = chKernel32.NewProc("OpenProcess")
    v36CloseHandle = chKernel32.NewProc("CloseHandle")
    v36QueryFullProcessImageName = chKernel32.NewProc("QueryFullProcessImageNameW")
    v36GetParent = chUser32.NewProc("GetParent")
    v41GetWindowRect = chUser32.NewProc("GetWindowRect")
    v42SetThreadDpiAwarenessContext = chUser32.NewProc("SetThreadDpiAwarenessContext")
)

func v36ProcessImage(pid uint32) string { const processQueryLimitedInformation=0x1000;h,_,_:=v36OpenProcess.Call(processQueryLimitedInformation,0,uintptr(pid));if h==0{return ""};defer v36CloseHandle.Call(h);buf:=make([]uint16,32768);n:=uint32(len(buf));ok,_,_:=v36QueryFullProcessImageName.Call(h,0,uintptr(unsafe.Pointer(&buf[0])),uintptr(unsafe.Pointer(&n)));if ok==0||n==0{return ""};return strings.ToLower(filepath.Base(syscall.UTF16ToString(buf[:n])))}
func v36FindRunningMT5() uintptr {var found uintptr;var bestArea int64;cb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{if hwnd==0||hwnd==hostHWND{return 1};var pid uint32;chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)));image:=v36ProcessImage(pid);if image!="terminal64.exe"&&image!="terminal.exe"{return 1};var r chRect;ok,_,_:=v41GetWindowRect.Call(hwnd,uintptr(unsafe.Pointer(&r)));if ok==0{return 1};w:=int64(r.R-r.L);h:=int64(r.B-r.T);if w<300||h<200{return 1};if a:=w*h;a>bestArea{bestArea=a;found=hwnd};return 1});chEnumWindows.Call(cb,0);return found}

func v36EmbedMT5(hwnd uintptr) bool {
    if hwnd==0||hostHWND==0{return false};chShowWindow.Call(hwnd,chSWHide)
    style,_,_:=chGetWindowLongPtr.Call(hwnd,^uintptr(15));style &^= chWSPopup|chWSCaption|chWSBorder|chWSDlgFrame|chWSThickFrame|chWSMinBox|chWSMaxBox|chWSSysMenu;style |= chWSChild|chWSVisible;chSetWindowLongPtr.Call(hwnd,^uintptr(15),style)
    exStyle,_,_:=chGetWindowLongPtr.Call(hwnd,^uintptr(19));exStyle &^= chEXAppWindow|chEXDlgModal|chEXWindowEdge|chEXClientEdge|chEXStaticEdge;exStyle |= chEXToolWindow;chSetWindowLongPtr.Call(hwnd,^uintptr(19),exStyle)
    systemAware:=^uintptr(1);previousDPI,_,_:=v42SetThreadDpiAwarenessContext.Call(systemAware);chSetParent.Call(hwnd,hostHWND);if previousDPI!=0{v42SetThreadDpiAwarenessContext.Call(previousDPI)}
    parent,_,_:=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide);return false}
    chSetWindowPos.Call(hwnd,0,0,uintptr(barH),1,1,chSWPNoZOrder|chSWPNoActivate|chSWPFrame);parent,_,_=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide);return false}
    exStyle,_,_=chGetWindowLongPtr.Call(hwnd,^uintptr(19));exStyle &^= chEXAppWindow;exStyle |= chEXToolWindow;chSetWindowLongPtr.Call(hwnd,^uintptr(19),exStyle);chSetWindowPos.Call(hwnd,0,0,uintptr(barH),1,1,chSWPNoZOrder|chSWPNoActivate|chSWPFrame)
    chMu.Lock();chMT5Wnd=hwnd;chMu.Unlock();chResizeChildren();return true
}

func v54EmbedMT5WithRetry(hwnd uintptr, wait time.Duration) bool { deadline:=time.Now().Add(wait);for time.Now().Before(deadline){if hwnd==0{hwnd=v36FindRunningMT5()};if hwnd!=0&&v36EmbedMT5(hwnd){return true};time.Sleep(250*time.Millisecond)};return false }
func v545EmbedStartedMT5Fast(wait time.Duration) bool { deadline:=time.Now().Add(wait);for time.Now().Before(deadline){if hwnd:=v36FindRunningMT5();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if v36EmbedMT5(hwnd){return true}};time.Sleep(10*time.Millisecond)};return false }
func v5410IsMT5Image(image string) bool { image=strings.ToLower(strings.TrimSpace(image));return image=="terminal64.exe"||image=="terminal.exe"||(v5410MT5ExeBase!=""&&image==v5410MT5ExeBase) }
func v5410FindMT5Candidate() uintptr {var found uintptr;var bestArea int64;cb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{if hwnd==0||hwnd==hostHWND{return 1};var pid uint32;chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)));if !v5410IsMT5Image(v36ProcessImage(pid)){return 1};var r chRect;ok,_,_:=v41GetWindowRect.Call(hwnd,uintptr(unsafe.Pointer(&r)));if ok==0{return 1};w:=int64(r.R-r.L);h:=int64(r.B-r.T);if w<80||h<60{return 1};if a:=w*h;a>bestArea{bestArea=a;found=hwnd};return 1});chEnumWindows.Call(cb,0);return found}
func v546HideAllMT5TopLevel(){cb:=syscall.NewCallback(func(hwnd,_ uintptr)uintptr{if hwnd==0||hwnd==hostHWND{return 1};var pid uint32;chGetWindowThreadPID.Call(hwnd,uintptr(unsafe.Pointer(&pid)));if v5410IsMT5Image(v36ProcessImage(pid)){parent,_,_:=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide)}};return 1});chEnumWindows.Call(cb,0)}
func v546EmbedOnlyMT5(wait time.Duration) bool {deadline:=time.Now().Add(wait);for time.Now().Before(deadline){v546HideAllMT5TopLevel();if hwnd:=v5410FindMT5Candidate();hwnd!=0{chShowWindow.Call(hwnd,chSWHide);if v36EmbedMT5(hwnd){return true}};time.Sleep(20*time.Millisecond)};return false}

// MT5 may create its top-level frame before the terminal has completed its first
// layout/paint. Do not expose that half-initialized child. Keep it embedded and
// hidden briefly, require a stable host parent and usable rectangle, then force a
// frame/redraw before the UI switches to MH MT5.
func v55WaitMT5RenderReady(wait time.Duration) bool {
    deadline:=time.Now().Add(wait)
    stable:=0
    for time.Now().Before(deadline) {
        chMu.Lock(); hwnd:=chMT5Wnd; chMu.Unlock()
        if hwnd!=0 {
            parent,_,_:=v36GetParent.Call(hwnd)
            var r chRect
            ok,_,_:=v41GetWindowRect.Call(hwnd,uintptr(unsafe.Pointer(&r)))
            if parent==hostHWND && ok!=0 && (r.R-r.L)>200 && (r.B-r.T)>150 { stable++ } else { stable=0 }
            if stable>=4 {
                chSetWindowPos.Call(hwnd,0,0,uintptr(barH),uintptr(r.R-r.L),uintptr(r.B-r.T),chSWPNoActivate|chSWPFrame)
                chRedrawWindowV5414.Call(hwnd,0,0,0x0001|0x0080|0x0100)
                chUpdateWindow.Call(hwnd)
                time.Sleep(180*time.Millisecond)
                return true
            }
        }
        time.Sleep(80*time.Millisecond)
    }
    return false
}

// Maintenance is deliberately low-frequency. The old 8-12 ms hide/embed guard
// continuously disturbed MT5 painting and could leave the embedded terminal blank.
func v55MaintainMT5Embed(wait time.Duration) {
    deadline:=time.Now().Add(wait)
    for time.Now().Before(deadline) {
        v546HideAllMT5TopLevel()
        chMu.Lock();hwnd:=chMT5Wnd;chMu.Unlock()
        if hwnd!=0 {parent,_,_:=v36GetParent.Call(hwnd);if parent!=hostHWND{chShowWindow.Call(hwnd,chSWHide);_=v36EmbedMT5(hwnd)}}
        time.Sleep(350*time.Millisecond)
    }
    v546HideAllMT5TopLevel()
}

func v55MT5HideGuard(stop <-chan struct{}) {ticker:=time.NewTicker(120*time.Millisecond);defer ticker.Stop();for{select{case<-stop:v546HideAllMT5TopLevel();return;case<-ticker.C:v546HideAllMT5TopLevel()}}}

func chEnsureMT5TerminalV36() error {
    chMu.Lock();existingEmbedded:=chMT5Wnd;chMu.Unlock()
    if existingEmbedded!=0 {
        parent,_,_:=v36GetParent.Call(existingEmbedded)
        if parent==hostHWND {
            chResizeChildren()
            if !v55WaitMT5RenderReady(2*time.Second){return errors.New("Embedded MT5 is still initializing. Please click MH MT5 again in a moment.")}
            go v55MaintainMT5Embed(5*time.Second);go mt5ApplyLatestQueued();return nil
        }
        chShowWindow.Call(existingEmbedded,chSWHide);chMu.Lock();if chMT5Wnd==existingEmbedded{chMT5Wnd=0};chMu.Unlock()
    }
    chMu.Lock();if chMT5StartingV34{chMu.Unlock();return nil};chMT5StartingV34=true;chMu.Unlock();defer func(){chMu.Lock();chMT5StartingV34=false;chMu.Unlock()}()
    v546HideAllMT5TopLevel()
    if hwnd:=v5410FindMT5Candidate();hwnd!=0 {
        stop:=make(chan struct{});go v55MT5HideGuard(stop);ok:=v546EmbedOnlyMT5(5*time.Second);close(stop)
        if !ok{return errors.New("Installed MT5 was detected, but Windows refused child embedding. MH Analysis kept the standalone MT5 window hidden. Make sure MH Analysis and MT5 use the same Windows privilege level.")}
        if !v55WaitMT5RenderReady(3*time.Second){return errors.New("MT5 embedded but did not become render-ready.")}
        go v55MaintainMT5Embed(8*time.Second);go mt5ApplyLatestQueued();return nil
    }
    path,err:=chMT5Executable();if err!=nil{return err};v5410MT5ExeBase=strings.ToLower(filepath.Base(path))
    stop:=make(chan struct{});go v55MT5HideGuard(stop);cmd:=exec.Command(path);cmd.SysProcAttr=&syscall.SysProcAttr{HideWindow:true,CreationFlags:0x08000000}
    if err:=cmd.Start();err!=nil{close(stop);return fmt.Errorf("Could not start MT5: %w",err)}
    chMu.Lock();chMT5Cmd=cmd;chMu.Unlock();ok:=v546EmbedOnlyMT5(20*time.Second);close(stop)
    if !ok {_=cmd.Process.Kill();chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMu.Unlock();v546HideAllMT5TopLevel();return errors.New("MT5 could not be embedded inside MH Analysis. The MH-started standalone terminal was closed instead of being left open.")}
    if !v55WaitMT5RenderReady(4*time.Second){_=cmd.Process.Kill();chMu.Lock();if chMT5Cmd==cmd{chMT5Cmd=nil};chMT5Wnd=0;chMu.Unlock();return errors.New("MT5 started but its embedded view did not become render-ready.")}
    go v55MaintainMT5Embed(10*time.Second);go mt5ApplyLatestQueued();return nil
}
