//go:build windows

package main

import (
	"encoding/json"
	"fmt"
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
	wv2Whatsapp *edge.Chromium
	wv2Records *edge.Chromium
	wv2Container uintptr
	wv2WhatsappContainer uintptr
	wv2RecordsContainer uintptr
)

func wv2CreateContainer(parent,inst uintptr)uintptr{h,_,_:=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("STATIC"))),uintptr(unsafe.Pointer(chWstr(""))),chWSChild|chWSVisible,0,uintptr(barH),1,1,parent,0,inst,0);return h}

func wv2Resize(){
	if hostHWND==0||wv2Container==0{return};var r chRect;chGetClientRect.Call(hostHWND,uintptr(unsafe.Pointer(&r)));w:=int32(r.R-r.L);h:=int32(r.B-r.T-int32(barH));if w<1{w=1};if h<1{h=1}
	for _,c:=range []uintptr{wv2Container,wv2WhatsappContainer,wv2RecordsContainer}{if c!=0{chMoveWindow.Call(c,0,uintptr(barH),uintptr(w),uintptr(h),1)}}
	for _,b:=range []*edge.Chromium{wv2Browser,wv2Whatsapp,wv2Records}{if b!=nil{b.Resize();_=b.NotifyParentWindowPositionChanged()}}
	if chMT5Wnd!=0{chMoveWindow.Call(chMT5Wnd,0,uintptr(barH),uintptr(w),uintptr(h),1)}
	if chSignalLinkBtn!=0{chMoveWindow.Call(chSignalLinkBtn,600,7,145,30,1)}
}

func wv2SetDesiredView(which int){chViewMu.Lock();chDesiredView=which;chViewMu.Unlock();if chSignalLinkBtn!=0{if which==2{chShowWindow.Call(chSignalLinkBtn,chSWShow)}else{chShowWindow.Call(chSignalLinkBtn,chSWHide)}}}

func wv2HideAll(){
	if wv2Browser!=nil{_=wv2Browser.Hide()};if wv2Whatsapp!=nil{_=wv2Whatsapp.Hide()};if wv2Records!=nil{_=wv2Records.Hide()}
	if wv2Container!=0{chShowWindow.Call(wv2Container,chSWHide)};if wv2WhatsappContainer!=0{chShowWindow.Call(wv2WhatsappContainer,chSWHide)};if wv2RecordsContainer!=0{chShowWindow.Call(wv2RecordsContainer,chSWHide)}
	if chMT5Wnd!=0{chShowWindowAsync.Call(chMT5Wnd,chSWHide)}
}

// V36_TRUE_PERSISTENT_WEBVIEWS: WhatsApp and Records are real embedded WebView2 controls,
// not Chrome/Edge app windows that have to be discovered/re-parented after every click.
func wv2CreateAux(which int,inst uintptr) bool {
	if which==2&&wv2Whatsapp!=nil{return true};if which==3&&wv2Records!=nil{return true}
	var c *uintptr;var data,target string
	if which==2{c=&wv2WhatsappContainer;data=filepath.Join(os.Getenv("LOCALAPPDATA"),"MHAnalysis","WhatsAppWebView2");target="https://web.whatsapp.com/"}else if which==3{c=&wv2RecordsContainer;data=filepath.Join(os.Getenv("LOCALAPPDATA"),"MHAnalysis","RecordsWebView2");target=serverURL+"records.html"}else{return false}
	_=os.MkdirAll(data,0755);*c=wv2CreateContainer(hostHWND,inst);if *c==0{return false};b:=edge.NewChromium();b.DataPath=data;if !b.Embed(*c){chDestroyWindow.Call(*c);*c=0;return false};b.Navigate(target);_=b.Hide();chShowWindow.Call(*c,chSWHide)
	if which==2{wv2Whatsapp=b}else{wv2Records=b};wv2Resize();return true
}

func wv2ShowLocal(which int){
	if wv2Browser==nil{return};wv2SetDesiredView(which);wv2HideAll()
	switch which{
	case 1:chShowWindow.Call(wv2Container,chSWShow);_=wv2Browser.Show();wv2Browser.Focus()
	case 2:if wv2Whatsapp!=nil{chShowWindow.Call(wv2WhatsappContainer,chSWShow);_=wv2Whatsapp.Show();wv2Whatsapp.Focus()}
	case 3:if wv2Records!=nil{chShowWindow.Call(wv2RecordsContainer,chSWShow);_=wv2Records.Show();wv2Records.Focus()}
	}
	wv2Resize()
}

func wv2ButtonAllowed(id int)bool{if licAuthorized{return true};section:="MH Analysis";if id==idWhatsapp{section="WhatsApp"};if id==idRecords{section="Records"};if id==idMT5{section="MT5 System"};if id==chIDSignalLink{section="Signal Link"};licSetNavNotice(section);wv2ShowLocal(1);return false}

// V36_MT5_ROUTE: installed/running MT5 is attached inside the host; no legacy external route.
func wv2ShowMT5(){wv2SetDesiredView(4);wv2HideAll();go func(){if err:=chEnsureMT5TerminalV36();err!=nil{messageBox(hostHWND,err.Error(),"MT5 System",0x10);wv2ShowLocal(1);return};wv2Resize()}()}

// V36_WA_FANOUT: the same queue used by /api/send-whatsapp is consumed by the
// persistent embedded WhatsApp WebView2. Navigation + DOM injection happen without
// switching the user's current screen or requiring a second click.
func wv2ProcessWhatsAppQueueV36(){
	if wv2Whatsapp==nil{return}
	waMu.Lock();if len(waQueue)==0{waMu.Unlock();return};t:=waQueue[0];waQueue=waQueue[1:];waMu.Unlock()
	wv2Whatsapp.Navigate(t.target);msgJSON,_:=json.Marshal(t.message)
	for _,delay:=range []time.Duration{2*time.Second,4*time.Second,7*time.Second,11*time.Second,16*time.Second}{d:=delay;time.AfterFunc(d,func(){if wv2Whatsapp==nil{return};script:=fmt.Sprintf(`(()=>{const msg=%s;const key='mh-v36-'+btoa(unescape(encodeURIComponent(msg))).slice(0,32);if(window[key])return true;const box=document.querySelector('footer [contenteditable="true"]')||document.querySelector('[contenteditable="true"][data-tab]');if(!box)return false;box.focus();document.execCommand('selectAll',false,null);document.execCommand('insertText',false,msg);box.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:msg}));const send=document.querySelector('[data-icon="send"]')?.closest('button')||document.querySelector('button[aria-label="Send"]');if(send){send.click();window[key]=true;return true;}box.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));window[key]=true;return true;})()`,string(msgJSON));wv2Whatsapp.Eval(script)})}
	// Continue queued fan-out after the current message has had time to send.
	time.AfterFunc(18*time.Second,func(){postMessage(hostHWND,wmWhatsAppSend,0,0)})
}

func wv2WndProc(hwnd uintptr,msg uint32,wp,lp uintptr)uintptr{
	switch msg{
	case chWMSize:wv2Resize();return 0
	case chWMCommand:id:=int(wp&0xffff);if !wv2ButtonAllowed(id){return 0};switch id{case idAnalysis:wv2ShowLocal(1);case idWhatsapp:wv2ShowLocal(2);case idRecords:wv2ShowLocal(3);case idMT5:wv2ShowMT5();case chIDSignalLink:chShowNativeSettingsDialog(2)};return 0
	case wmSwitchAnalysis:wv2ShowLocal(1);return 0
	case wmSwitchWhatsApp:if licAuthorized{wv2ShowLocal(2)}else{licSetNavNotice("WhatsApp");wv2ShowLocal(1)};return 0
	case wmWhatsAppSend:wv2ProcessWhatsAppQueueV36();return 0
	case chWMOpenAPISettings:chShowNativeSettingsDialog(1);return 0
	case chWMOpenWhatsAppSettings:if licAuthorized{wv2ShowLocal(2);chShowNativeSettingsDialog(2)};return 0
	case chWMClose:wv2HideAll();chDestroyWindow.Call(hwnd);return 0
	case chWMDestroy:wv2Browser=nil;wv2Whatsapp=nil;wv2Records=nil;chStopBrowsers();chPostQuitMessage.Call(0);return 0
	};r,_,_:=chDefWindowProc.Call(hwnd,uintptr(msg),wp,lp);return r
}

func runWebView2Host(){
	runtime.LockOSThread();defer runtime.UnlockOSThread();inst,_,_:=chGetModuleHandle.Call(0);className:=chWstr("MHAnalysisWebView2HostV36");icon,_,_:=chLoadIcon.Call(inst,1);if icon==0{icon,_,_=chLoadIcon.Call(0,32512)};cursor,_,_:=chLoadCursor.Call(0,chIDCArrow);brush,_,_:=chCreateSolidBrush.Call(uintptr(8|(22<<8)|(26<<16)));wc:=chWndClassEx{CbSize:uint32(unsafe.Sizeof(chWndClassEx{})),LpfnWndProc:syscall.NewCallback(wv2WndProc),HInstance:inst,HIcon:icon,HCursor:cursor,HbrBackground:brush,LpszClassName:className,HIconSm:icon};if r,_,_:=chRegisterClassEx.Call(uintptr(unsafe.Pointer(&wc)));r==0{messageBox(0,"Could not initialize MH Analysis window.","MH Analysis",0x10);return};hostHWND,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(className)),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSOverlapped,100,100,1280,820,0,0,inst,0);if hostHWND==0{messageBox(0,"Could not create MH Analysis window.","MH Analysis",0x10);return};chSetWindowDisplayAffinityV31.Call(hostHWND,chWDAExcludeFromCaptureV31)
	btnAnalysis,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MH Analysis"))),chWSChild|chWSVisible,8,7,140,30,hostHWND,idAnalysis,inst,0);btnWhatsapp,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("WhatsApp"))),chWSChild|chWSVisible,156,7,140,30,hostHWND,idWhatsapp,inst,0);btnRecords,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("Records"))),chWSChild|chWSVisible,304,7,140,30,hostHWND,idRecords,inst,0);btnMT5,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("MT5 System"))),chWSChild|chWSVisible,452,7,140,30,hostHWND,idMT5,inst,0);chSignalLinkBtn,_,_=chCreateWindowEx.Call(0,uintptr(unsafe.Pointer(chWstr("BUTTON"))),uintptr(unsafe.Pointer(chWstr("Signal Link"))),chWSChild,600,7,145,30,hostHWND,chIDSignalLink,inst,0)
	wv2Container=wv2CreateContainer(hostHWND,inst);data:=filepath.Join(os.Getenv("LOCALAPPDATA"),"MHAnalysis","WebView2");_=os.MkdirAll(data,0755);b:=edge.NewChromium();b.DataPath=data;wv2Browser=b;if !b.Embed(wv2Container){messageBox(hostHWND,"Microsoft Edge WebView2 Runtime is required.","MH Analysis",0x10);chDestroyWindow.Call(hostHWND);return};b.Navigate(serverURL);_=b.Show();wv2SetDesiredView(1);wv2Resize();time.Sleep(250*time.Millisecond);chShowWindow.Call(hostHWND,chSWMaximize);chUpdateWindow.Call(hostHWND);wv2Resize();b.Focus()
	// Create both auxiliary controllers once on the UI thread. Their profiles persist login/session.
	if !wv2CreateAux(2,inst){messageBox(hostHWND,"Could not initialize embedded WhatsApp.","MH Analysis",0x10)}
	if !wv2CreateAux(3,inst){messageBox(hostHWND,"Could not initialize Records view.","MH Analysis",0x10)}
	wv2ShowLocal(1)
	var m chMsg;for{r,_,_:=chGetMessage.Call(uintptr(unsafe.Pointer(&m)),0,0,0);if int32(r)<=0{break};chTranslateMessage.Call(uintptr(unsafe.Pointer(&m)));chDispatchMessage.Call(uintptr(unsafe.Pointer(&m)))}
}
