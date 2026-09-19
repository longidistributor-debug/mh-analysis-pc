package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type exnessOrderPrep struct {
	Symbol      string  `json:"symbol"`
	Timeframe   string  `json:"timeframe"`
	Direction   string  `json:"direction"`
	PendingType string  `json:"pending_type"`
	Entry       float64 `json:"entry"`
	SL          float64 `json:"sl"`
	TP1         float64 `json:"tp1"`
	TP2         float64 `json:"tp2"`
	MarketPrice float64 `json:"market_price"`
	Score       int     `json:"score"`
	Setup       string  `json:"setup"`
	CreatedAt   string  `json:"created_at"`
	Status      string  `json:"status"`
	Error       string  `json:"error,omitempty"`
}

var exnessMu sync.RWMutex
var exnessLast exnessOrderPrep

func registerExnessRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/exness/prepare", exnessPrepareHandler)
	mux.HandleFunc("/api/exness/status", exnessStatusHandler)
}

func derivePendingType(direction string, entry, market float64) string {
	direction = strings.ToUpper(strings.TrimSpace(direction))
	if direction == "BUY" {
		if entry <= market {
			return "BUY LIMIT"
		}
		return "BUY STOP"
	}
	if entry >= market {
		return "SELL LIMIT"
	}
	return "SELL STOP"
}

func exnessPrepareHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q exnessOrderPrep
	if err := json.NewDecoder(r.Body).Decode(&q); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	if q.Symbol != "XAUUSD" || (q.Direction != "BUY" && q.Direction != "SELL") || q.Entry <= 0 || q.SL <= 0 || q.TP1 <= 0 || q.MarketPrice <= 0 {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "invalid XAUUSD signal payload"})
		return
	}
	q.PendingType = derivePendingType(q.Direction, q.Entry, q.MarketPrice)
	q.CreatedAt = time.Now().Format(time.RFC3339)
	q.Status = "QUEUED FOR EXNESS PREFILL"
	exnessMu.Lock()
	exnessLast = q
	exnessMu.Unlock()
	go func(prep exnessOrderPrep) {
		status, err := exnessPrefillOrder(prep)
		exnessMu.Lock()
		exnessLast = prep
		if err != nil {
			exnessLast.Status = "PREFILL WAITING"
			exnessLast.Error = err.Error()
		} else {
			exnessLast.Status = status
			exnessLast.Error = ""
		}
		exnessMu.Unlock()
	}(q)
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "pending_type": q.PendingType, "status": q.Status})
}

func exnessStatusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	exnessMu.RLock()
	v := exnessLast
	exnessMu.RUnlock()
	_ = json.NewEncoder(w).Encode(v)
}

func exnessPageSocket() (string, error) {
	client := &http.Client{Timeout: 2 * time.Second}
	var last error
	for i := 0; i < 24; i++ {
		resp, err := client.Get("http://127.0.0.1:17882/json/list")
		if err == nil {
			var pages []chCDPPage
			decErr := json.NewDecoder(resp.Body).Decode(&pages)
			_ = resp.Body.Close()
			if decErr == nil {
				for _, p := range pages {
					if p.Type == "page" && p.WebSocketDebuggerURL != "" && strings.Contains(strings.ToLower(p.URL), "exness") {
						return p.WebSocketDebuggerURL, nil
					}
				}
			} else {
				last = decErr
			}
		} else {
			last = err
		}
		time.Sleep(250 * time.Millisecond)
	}
	if last == nil {
		last = fmt.Errorf("Exness browser page is not ready")
	}
	return "", last
}

func exnessPrefillOrder(prep exnessOrderPrep) (string, error) {
	wsURL, err := exnessPageSocket()
	if err != nil {
		return "", err
	}
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		return "", err
	}
	defer conn.Close()
	payload, _ := json.Marshal(prep)
	js := fmt.Sprintf(`(async()=>{
const p=%s;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const visible=e=>!!(e&&e.getBoundingClientRect().width&&e.getBoundingClientRect().height);
const txt=e=>String((e&&e.innerText)||'').replace(/\s+/g,' ').trim();
const body=txt(document.body).toLowerCase();
if(/log in|login|sign in/.test(body)&&document.querySelector('input[type="password"]')) return JSON.stringify({status:'LOGIN REQUIRED'});
if(!/(xau\s*\/\s*usd|xauusd|gold)/i.test(body)) return JSON.stringify({status:'OPEN GOLD / XAUUSD FIRST'});
function clickText(words){
  const all=[...document.querySelectorAll('button,[role="button"],[role="option"],[role="menuitem"],div,span')].filter(visible);
  for(const w of words){const low=w.toLowerCase();const e=all.find(x=>txt(x).toLowerCase()===low)||all.find(x=>txt(x).toLowerCase().includes(low));if(e){e.click();return true;}}
  return false;
}
function setNative(input,value){
  const proto=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
  const d=Object.getOwnPropertyDescriptor(proto,'value');
  if(d&&d.set)d.set.call(input,String(value));else input.value=String(value);
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));
}
function findInput(keys){
  const inputs=[...document.querySelectorAll('input,textarea')].filter(visible);
  for(const i of inputs){
    const meta=[i.name,i.id,i.placeholder,i.getAttribute('aria-label'),i.getAttribute('data-testid'),txt(i.parentElement),txt(i.closest('label'))].filter(Boolean).join(' ').toLowerCase();
    if(keys.some(k=>meta.includes(k)))return i;
  }
  return null;
}
clickText(['New order','Trade']);
await sleep(350);
clickText(['Pending order','Pending']);
await sleep(250);
clickText([p.pending_type,p.pending_type.replace(' ','-')]);
await sleep(250);
const price=findInput(['open price','order price','entry price','price']);
const sl=findInput(['stop loss','stoploss',' sl ']);
const tp=findInput(['take profit','takeprofit',' tp ']);
if(price)setNative(price,p.entry);
if(sl)setNative(sl,p.sl);
if(tp)setNative(tp,p.tp1);
await sleep(200);
const out={status:(price&&sl&&tp)?'READY FOR USER CONFIRMATION':'PARTIAL PREFILL',pending_type:p.pending_type,entry:!!price,sl:!!sl,tp1:!!tp,submitted:false};
return JSON.stringify(out);
})()`, string(payload))
	msg, err := chCDPCommand(conn, 1, "Runtime.evaluate", map[string]any{"expression": js, "returnByValue": true, "awaitPromise": true})
	if err != nil {
		return "", err
	}
	value := chEvalValue(msg)
	if strings.TrimSpace(value) == "" {
		return "", fmt.Errorf("Exness terminal returned no prefill status")
	}
	var out struct {
		Status string `json:"status"`
	}
	if json.Unmarshal([]byte(value), &out) == nil && out.Status != "" {
		return out.Status, nil
	}
	return value, nil
}
