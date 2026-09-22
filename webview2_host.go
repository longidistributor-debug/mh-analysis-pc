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

var chSetWindowDisplayAffinityV31 = chUser32.NewProc("SetWindowDisplayAffinity")
const chWDAExcludeFromCaptureV31 = 0x00000011

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
	w := int32(r.R-r.L); h := int32(r.B-r.T-int32(barH)); if w<1 {w=1}; if h<1 {h=1}
	chMoveWindow.Call(wv2Container,0,uintptr(barH),uintptr(w),uintptr(h),1)
	if wv2Browser != nil { wv2Browser.Resize(); _=wv2Browser.NotifyParentWindowPositionChanged() }
	for _, child := range []uintptr{chWhatsappWnd,chRecordsWnd,chMT5Wnd} { if child!=0 { chMoveWindow.Call(child,0,uintptr(barH),uintptr(w),uintptr(h),1) } }
	if chSignalLinkBtn!=0 { chMoveWindow.Call(chSignalLinkBtn,600,7,145,30,1) }
}

func wv2SetDesiredView(which int) {
	chViewMu.Lock(); chDesiredView=which; chViewMu.Unlock()
	if chSignalLinkBtn!=0 { if which==2 { chShowWindow.Call(chSignalLinkBtn,chSWShow) } else { chShowWindow.Call(chSignalLinkBtn,chSWHide) } }
}
func wv2HideAuxViews(){ if chWhatsappWnd!=0{chShowWindowAsync.Call(chWhatsappWnd,chSWHide)}; if chRecordsWnd!=0{chShowWindowAsync.Call(chRecordsWnd,chSWHide)}; if chMT5Wnd!=0{chShowWindowAsync.Call(chMT5Wnd,chSWHide)} }

// V36_DIRECT_SOURCE_AUX: create each persistent child once. WhatsApp profile remains logged in.
func wv2EnsureAuxBrowser(which int) {
	if hostHWND==0{return}
	chMu.Lock(); if chStopping || (which==2&&(chWhatsappWnd!=0||chWhatsappCmd!=nil)) || (which==3&&(chRecordsWnd!=0||chRecordsCmd!=nil)){chMu.Unlock();return}; chMu.Unlock()
	profile,target,debugPort := "","",0
	if which==2 { profile,target,debugPort="WhatsAppProfile","https://web.whatsapp.com/",17879 } else if which==3 { profile,target="RecordsProfile",serverURL+"records.html" } else{return}
	cmd,wnd,err:=chLaunchBrowser(profile,target,debugPort); if err!=nil{return}
	chMu.Lock(); if chStopping { chMu.Unlock(); if cmd.Process!=nil{_ = cmd.Process.Kill()}; return }
	if which==2 {chWhatsappCmd,chWhatsappWnd=cmd,wnd} else {chRecordsCmd,chRecordsWnd=cmd,wnd}
	chAttachBrowser(wnd); chShowWindowAsync.Call(wnd,chSWHide); chMu.Unlock(); wv2Resize()
	chViewMu.Lock(); wanted:=chDesiredView; chViewMu.Unlock(); if wanted==which { chApplyDesiredBrowserView(); chResizeChildren() }
}

// V36_FIRST_CLICK: click changes desired state once; internal readiness never requires another user click.
func wv2ShowLocal(which int) {
	if wv2Browser==nil{return}; wv2SetDesiredView(which)
	if which==1 { wv2HideAuxViews(); chShowWindow.Call(wv2Container,chSWShow); _=wv2Browser.Show(); wv2Resize(); wv2Browser.Focus(); return }
	if which==2 && chWhatsappWnd==0 { go wv2EnsureAuxBrowser(2) }
	if which==3 && chRecordsWnd==0 { go wv2EnsureAuxBrowser(3) }
	// Keep analysis painted until requested child is ready; then switch automatically.
	for _,d:=range []time.Duration{0,80*time.Millisecond,200*time.Millisecond,450*time.Millisecond,900*time.Millisecond,1500*time.Millisecond,2500*time.Millisecond}{
		time.AfterFunc(d,func(){ chViewMu.Lock(); wanted:=chDesiredView; chViewMu.Unlock(); if wanted==which { chApplyDesiredBrowserView(); chResizeChildren() } })
	}
}

func wv2ButtonAllowed(id int) bool { if licAuthorized{return true}; section:="MH Analysis"; if id==idWhatsapp{section="WhatsApp"}; if id==idRecords{section="Records"}; if id==idMT5{section="MT5 System"}; if id==chIDSignalLink{section="Signal Link"}; licSetNavNotice(section); wv2ShowLocal(1); return false }
func wv2ShowMT5(){ wv2SetDesiredView(4); go func(){ if err:=chEnsureMT5Terminal(); err!=nil { messageBox(hostHWND,err.Error(),"MT5 System",0x10); wv2SetDesiredView(1) } }() }

func wv2WndProc(hwnd uintptr,msg uint32,wp,lp uintptr) uintptr {
	switch msg {
	case chWMSize: wv2Resize(); return 0
	case chWMCommand:
		id:=int(wp&0xffff); if !wv2ButtonAllowed(id){return 0}; switch id {case idAnalysis:wv2ShowLocal(1); case idWhatsapp:wv2ShowLocal(2); case idRecords:wv2ShowLocal(3); case idMT5:wv2ShowMT5(); case chIDSignalLink:chShowNativeSettingsDialog(2)}; return 0
	case wmSwitchAnalysis:wv2ShowLocal(1);return 0
	case wmSwitchWhatsApp:if licAuthorized{wv2ShowLocal(2)}else{licSetNavNotice("WhatsApp");wv2ShowLocal(1)};return 0
	case chWMOpenAPISettings:chShowNativeSettingsDialog(1);return 0
	case chWMOpenWhatsAppSettings:if licAuthorized{wv2ShowLocal(2);chShowNativeSettingsDialog(2)};return 0
	case chWMClose:chShowWindow.Call(hwnd,chSWHide);if wv2Browser!=nil{_=wv2Browser.Hide()};wv2HideAuxViews();chDestroyWindow.Call(hwnd);return 0
	case chWMDestroy:chStopBrowsers();wv2Browser=nil;chPostQuitMessage.Call(0);return 0
	}
	r,_,_:=chDefWindowProc.Call(hwnd,uintptr(msg),wp,lp);return r
}

func runWebView2Host(){
	runtime.LockOSThread();defer runtime.UnlockOSThread();inst,_,_:=chGetModuleHandle.Call(0);className:=chWstr("MHAnalysisWebView2HostV36");icon,_,_:=chLoadIcon.Call(inst,1);if icon==0{icon,_,_=chLoadIcon.Call(0,32512)};cursor,_,_:=chLoadCursor.Call(0,chIDCArrow);brush,_,_:=chCreateSolidBrush.Call(uintptr(8|(22<<8)|(26<<16)));wc:=chWndClassEx{CbSize:uint32(unsafe.Sizeof(chWndClassEx{})),LpfnWndProc:syscall.NewCallback(wv2WndProc),HInstance:inst,HIcon:icon,HCursor:cursor,HbrBackground:brush,LpszClassName:className,HIconSm:icon};if r,_,_:=chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc)));r==0{messageBox(0,"Could not initialize MH Analysis window.","MH Analysis",0x10);return};hostHWND,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(className)),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSOverlapped,100,100,1280,820,0,0,inst,0);if hostHWND==0{messageBox(0,"Could not create MH Analysis window.","MH Analysis",0x10);return};chSetWindowDisplayAffinityV31.Call(hostHWND,chWDAExcludeFromCaptureV31)
	btnAnalysis,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSChild|chWSVisible,8,7,140,30,hostHWND,idAnalysis,inst,0);btnWhatsapp,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("WhatsApp"))),chWSChild|chWSVisible,156,7,140,30,hostHWND,idWhatsapp,inst,0);btnRecords,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("Records"))),chWSChild|chWSVisible,304,7,140,30,hostHWND,idRecords,inst,0);btnMT5,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MT5 System"))),chWSChild|chWSVisible,452,7,140,30,hostHWND,idMT5,inst,0);chSignalLinkBtn,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("Signal Link"))),chWSChild,600,7,145,30,hostHWND,chIDSignalLink,inst,0)
	wv2Container=wv2CreateContainer(hostHWND,inst);data:=filepath.Join(os.Getenv("LOCALAPPDATA"),"MHAnalysis","WebView2");_=os.MkdirAll(data,0755);b:=edge.NewChromium();b.DataPath=data;wv2Browser=b;if !b.Embed(wv2Container){messageBox(hostHWND,"Microsoft Edge WebView2 Runtime is required.","MH Analysis",0x10);chDestroyWindow.Call(hostHWND);return};if err:=b.Show();err!=nil{messageBox(hostHWND,"Could not display the embedded MH Analysis view.","MH Analysis",0x10);chDestroyWindow.Call(hostHWND);return};wv2Resize();b.Navigate(serverURL);wv2SetDesiredView(1);time.Sleep(450*time.Millisecond);chShowWindow.Call(hostHWND,chSWMaximize);chUpdateWindow.Call(hostHWND);wv2Resize();b.Focus()
	// V36_PREWARM_PERSISTENT: after first paint create persistent WhatsApp and Records children once.
	go func(){time.Sleep(600*time.Millisecond);wv2EnsureAuxBrowser(2);wv2EnsureAuxBrowser(3)}()
	var m chMsg;for{r,_,_:=chGetMessage.Call(uintptr(unsafe.Pointer(&m)),0,0,0);if int32(r)<=0{break};chTranslateMessage.Call(uintptr(unsafe.Pointer(&m)));chDispatchMessage.Call(uintptr(unsafe.Pointer(&m)))}
}
