//go:build windows

package main

import (
 "context"
 "encoding/json"
 "fmt"
 "os"
 "path/filepath"
 "sync"
 "time"
 "unsafe"
 "github.com/jchv/go-webview2/pkg/edge"
)

const v27DispatchMessage = 0x8057
var v27Views = map[int]*edge.Chromium{}
var v27Containers = map[int]uintptr{}
var v27Creating = map[int]bool{}
var v27DispatchMu sync.Mutex
var v27Work []func()
var v27WhatsAppMu sync.Mutex
var v27Replies sync.Map

func v27Dispatch(f func()) {
 v27DispatchMu.Lock(); v27Work = append(v27Work, f); v27DispatchMu.Unlock()
 postMessage(hostHWND, v27DispatchMessage, 0, 0)
}
func v27DrainDispatch() {
 v27DispatchMu.Lock(); work := v27Work; v27Work = nil; v27DispatchMu.Unlock()
 for _, f := range work { f() }
}

// Only called on the host's UI thread. Navigation happens once per view.
func v27EnsureView(which int) error {
 if v27Views[which] != nil { return nil }
 if which != 2 && which != 3 { return fmt.Errorf("unknown view") }
 if v27Creating[which] { return fmt.Errorf("view is still starting; please retry") }
 v27Creating[which] = true
 defer delete(v27Creating, which)
 inst, _, _ := chGetModuleHandle.Call(0)
 container := wv2CreateContainer(hostHWND, inst)
 b := edge.NewChromium()
 b.DataPath = filepath.Join(os.Getenv("LOCALAPPDATA"), "MHAnalysis", "WebView2")
 b.MessageCallback = func(raw string) {
  var reply struct { ID string `json:"id"`; Status string `json:"status"` }
  if json.Unmarshal([]byte(raw), &reply) != nil { return }
  if ch, ok := v27Replies.Load(reply.ID); ok { select { case ch.(chan string) <- reply.Status: default: } }
 }
 if !b.Embed(container) { chDestroyWindow.Call(container); return fmt.Errorf("could not start embedded view") }
 v27Views[which] = b; v27Containers[which] = container
 if which == 2 { b.Navigate("https://web.whatsapp.com/") } else { b.Navigate(serverURL + "records.html") }
 return nil
}

func v27LayoutViews() {
 if hostHWND == 0 { return }
 chViewMu.Lock(); view := chDesiredView; chViewMu.Unlock()
 // Keep all pages rendered and alive offscreen so analysis timers continue.
 for which, container := range v27Containers {
  x := 0
  if which != view { x = -32000 }
  var r chRect
  chGetClientRect.Call(hostHWND, uintptr(unsafe.Pointer(&r)))
  w, h := int(r.R-r.L), int(r.B-r.T)-barH
  if w < 1 { w = 1 }; if h < 1 { h = 1 }
  chMoveWindow.Call(container, uintptr(x), uintptr(barH), uintptr(w), uintptr(h), 1)
  chShowWindow.Call(container, chSWShow)
  if b := v27Views[which]; b != nil { _ = b.Show(); b.Resize(); _ = b.NotifyParentWindowPositionChanged() }
 }
 if chMT5Wnd != 0 {
  if view == 4 { chShowWindow.Call(chMT5Wnd, chSWShow); chBringWindowToTop.Call(chMT5Wnd) } else { chShowWindow.Call(chMT5Wnd, chSWHide) }
 }
}

func v27SendWhatsApp(ctx context.Context, target, message string) error {
 v27WhatsAppMu.Lock(); defer v27WhatsAppMu.Unlock()
 if ctx.Err() != nil { return ctx.Err() }
 ready := make(chan error, 1)
 v27Dispatch(func() {
  err := v27EnsureView(2)
  if err == nil { v27LayoutViews(); v27Views[2].Navigate(target) }
  ready <- err
 })
 select { case err := <-ready: if err != nil { return err }; case <-ctx.Done(): return ctx.Err(); case <-time.After(20*time.Second): return fmt.Errorf("WhatsApp view did not start") }
 id := fmt.Sprintf("wa-%d", time.Now().UnixNano())
 replies := make(chan string, 1)
 v27Replies.Store(id, replies); defer v27Replies.Delete(id)
 idJSON, _ := json.Marshal(id); messageJSON, _ := json.Marshal(message)
 // Confirm the prefilled text matches this request before clicking. The per-page
 // marker prevents a repeated click if an acknowledgement is delayed.
 script := fmt.Sprintf(`(()=>{
 if(location.hostname!=='web.whatsapp.com')return;
 const id=%s, expected=%s;
 const report=status=>window.chrome.webview.postMessage(JSON.stringify({id,status}));
 if(window.__mhSubmitted===id){report('submitted');return;}
 const body=document.body?.innerText||'';
 if(/scan.*qr|use whatsapp on your computer|log into whatsapp/i.test(body)){report('login');return;}
 const box=document.querySelector('footer [contenteditable="true"]');
 const norm=s=>s.replace(/\r/g,'').replace(/\u00a0/g,' ').trim();
 if(!box||norm(box.innerText)!==norm(expected))return;
 const icon=document.querySelector('footer [data-icon="send"],footer [data-icon="wds-ic-send-filled"]');
 const button=icon?.closest('button')||document.querySelector('footer button[aria-label="Send"]');
 if(button&&!button.disabled){window.__mhSubmitted=id;button.click();report('submitted');}
 })()`, idJSON, messageJSON)
 ticker := time.NewTicker(500*time.Millisecond); defer ticker.Stop()
 timeout := time.NewTimer(40*time.Second); defer timeout.Stop()
 for { select {
 case <-ctx.Done(): return ctx.Err()
 case <-timeout.C: return fmt.Errorf("WhatsApp send not confirmed; open WhatsApp and check login/recipient before retrying")
 case <-ticker.C: v27Dispatch(func(){ if b:=v27Views[2]; b!=nil { b.Eval(script) } })
 case status:= <-replies:
  if status=="submitted" { return nil }
  if status=="login" { return fmt.Errorf("WhatsApp login required; open WhatsApp and scan the QR code") }
 } }
}
