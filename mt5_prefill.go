package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
 "syscall"
	"time"
	"unicode/utf16"
)

// MH_NATIVE_MT5_PREFILL_V796
// This bridge only prepares the native MT5 pending-order ticket. It deliberately
// stops before the final Place/Submit action so the user reviews the order in MT5.
type mt5OrderPrep struct {
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

var (
	mt5PrepMu       sync.RWMutex
	mt5LastPrep     mt5OrderPrep
	mt5PrepQueued   bool
	mt5AutomationMu sync.Mutex
)

func registerMT5PrefillRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/mt5/prepare", mt5PrepareHandler)
	mux.HandleFunc("/api/mt5/status", mt5StatusHandler)
}

func deriveMT5PendingType(direction string, entry, market float64) string {
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

func mt5PrepareHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodPost {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	var q mt5OrderPrep
	if err := json.NewDecoder(r.Body).Decode(&q); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	q.Symbol = strings.ToUpper(strings.TrimSpace(q.Symbol))
	q.Direction = strings.ToUpper(strings.TrimSpace(q.Direction))
	if (q.Symbol != "XAUUSD" && q.Symbol != "BTCUSDT") || (q.Direction != "BUY" && q.Direction != "SELL") || q.Entry <= 0 || q.SL <= 0 || q.TP1 <= 0 || q.MarketPrice <= 0 {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "invalid MT5 signal payload"})
		return
	}
	q.PendingType = deriveMT5PendingType(q.Direction, q.Entry, q.MarketPrice)
	q.CreatedAt = time.Now().Format(time.RFC3339)
	q.Status = "QUEUED FOR MT5 REVIEW"
	q.Error = ""

	mt5PrepMu.Lock()
	mt5LastPrep = q
	mt5PrepQueued = true
	mt5PrepMu.Unlock()

	// If the user is already on the MT5 tab, prepare immediately. Otherwise keep
	// the latest NEW ANALYZE signal queued and apply it when MT5 System is opened.
	if mt5ReadyAndVisible() {
		go mt5ApplyLatestQueued()
	}

	_ = json.NewEncoder(w).Encode(map[string]any{
		"ok":           true,
		"pending_type": q.PendingType,
		"status":       q.Status,
		"submitted":    false,
	})
}

func mt5StatusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.Method != http.MethodGet {
		http.Error(w, "method", http.StatusMethodNotAllowed)
		return
	}
	mt5PrepMu.RLock()
	v := mt5LastPrep
	queued := mt5PrepQueued
	mt5PrepMu.RUnlock()
	_ = json.NewEncoder(w).Encode(map[string]any{"order": v, "queued": queued, "submitted": false})
}

func mt5ReadyAndVisible() bool {
	chMu.Lock()
	wnd := chMT5Wnd
	cmd := chMT5Cmd
	chMu.Unlock()
	chViewMu.Lock()
	view := chDesiredView
	chViewMu.Unlock()
	return wnd != 0 && cmd != nil && cmd.Process != nil && view == 4
}

// Called by the MT5 tab after the native terminal is embedded, and by the NEW
// ANALYZE endpoint when the MT5 tab is already visible.
func mt5ApplyLatestQueued() {
	mt5AutomationMu.Lock()
	defer mt5AutomationMu.Unlock()

	mt5PrepMu.RLock()
	q := mt5LastPrep
	queued := mt5PrepQueued
	mt5PrepMu.RUnlock()
	if !queued || q.Entry <= 0 {
		return
	}
	if !mt5ReadyAndVisible() {
		return
	}

	status, err := mt5RunUIPrefill(q)
	mt5PrepMu.Lock()
	defer mt5PrepMu.Unlock()
	mt5LastPrep = q
	if err != nil {
		mt5LastPrep.Status = "MT5 PREFILL WAITING"
		mt5LastPrep.Error = err.Error()
		// Keep it queued so clicking MT5 System again can retry safely.
		mt5PrepQueued = true
		return
	}
	mt5LastPrep.Status = status
	mt5LastPrep.Error = ""
	mt5PrepQueued = false
}

func mt5RunUIPrefill(q mt5OrderPrep) (string, error) {
	chMu.Lock()
	cmd := chMT5Cmd
	wnd := chMT5Wnd
	chMu.Unlock()
	if cmd == nil || cmd.Process == nil || wnd == 0 {
		return "", fmt.Errorf("MT5 terminal is not ready")
	}
	payload, _ := json.Marshal(q)
	payload64 := base64.StdEncoding.EncodeToString(payload)

	ps := `
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MHMT5U32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, UIntPtr wParam, IntPtr lParam);
}
'@

function Out-Result([bool]$ok,[string]$status,[string]$detail='') {
  [pscustomobject]@{ok=$ok;status=$status;detail=$detail;submitted=$false} | ConvertTo-Json -Compress
}
function N($e) { try { return [string]$e.Current.Name } catch { return '' } }
function All($root,$ct) {
  $c=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,$ct)
  return $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$c)
}
function Value-Of($e) {
  try { $p=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); return [string]$p.Current.Value } catch { return '' }
}
function Set-Value($e,[string]$v) {
  if($null -eq $e){ return $false }
  try { $p=$e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); $p.SetValue($v); return $true } catch { return $false }
}
function Select-Item([System.Windows.Automation.AutomationElement]$dialog,[int]$pid,[string]$wanted) {
  $combos=All $dialog ([System.Windows.Automation.ControlType]::ComboBox)
  for($i=0;$i -lt $combos.Count;$i++){
    $c=$combos.Item($i)
    try { $ep=$c.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern); $ep.Expand() } catch { try{$c.SetFocus()}catch{} }
    Start-Sleep -Milliseconds 120
    $root=[System.Windows.Automation.AutomationElement]::RootElement
    $pc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$pid)
    $procEls=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$pc)
    $hit=$null
    for($j=0;$j -lt $procEls.Count;$j++){
      $e=$procEls.Item($j)
      if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::ListItem){continue}
      if((N $e).Trim().ToUpperInvariant() -eq $wanted.Trim().ToUpperInvariant()){ $hit=$e; break }
    }
    if($null -ne $hit){
      try { $sp=$hit.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern); $sp.Select(); return $true } catch {
        try { $hit.SetFocus(); (New-Object -ComObject WScript.Shell).SendKeys('{ENTER}'); return $true } catch {}
      }
    }
    try { $ep=$c.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern); $ep.Collapse() } catch {}
  }
  return $false
}
function Edit-For([System.Windows.Automation.AutomationElement]$dialog,[string]$rx) {
  $edits=All $dialog ([System.Windows.Automation.ControlType]::Edit)
  for($i=0;$i -lt $edits.Count;$i++){
    $e=$edits.Item($i); if((N $e) -match $rx){ return $e }
  }
  $texts=All $dialog ([System.Windows.Automation.ControlType]::Text)
  for($i=0;$i -lt $texts.Count;$i++){
    $t=$texts.Item($i); if((N $t) -notmatch $rx){continue}
    try{$tr=$t.Current.BoundingRectangle}catch{continue}
    $best=$null; $bestScore=1e9
    for($j=0;$j -lt $edits.Count;$j++){
      $e=$edits.Item($j); try{$er=$e.Current.BoundingRectangle}catch{continue}
      $dy=[Math]::Abs(($er.Top+$er.Height/2)-($tr.Top+$tr.Height/2))
      if($dy -gt 32){continue}
      $dx=$er.Left-$tr.Right
      if($dx -lt -20){continue}
      $score=$dy+[Math]::Abs($dx)/10
      if($score -lt $bestScore){$best=$e;$bestScore=$score}
    }
    if($null -ne $best){return $best}
  }
  return $null
}

$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:MH_MT5_PREFILL)) | ConvertFrom-Json
$pidNum=[int]$env:MH_MT5_PID
$hwnd=[IntPtr]([long]$env:MH_MT5_HWND)
[MHMT5U32]::ShowWindow($hwnd,5) | Out-Null
[MHMT5U32]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 180
# F9 opens MT5's native New Order ticket. No submit key/button is ever invoked.
[MHMT5U32]::PostMessage($hwnd,0x0100,[UIntPtr]0x78,[IntPtr]0) | Out-Null
[MHMT5U32]::PostMessage($hwnd,0x0101,[UIntPtr]0x78,[IntPtr]0) | Out-Null

$root=[System.Windows.Automation.AutomationElement]::RootElement
$pc=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$pidNum)
$dialog=$null
for($try=0;$try -lt 35 -and $null -eq $dialog;$try++){
  Start-Sleep -Milliseconds 120
  $wins=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$pc)
  for($i=0;$i -lt $wins.Count;$i++){
    $w=$wins.Item($i)
    if($w.Current.ControlType -ne [System.Windows.Automation.ControlType]::Window){continue}
    $nm=N $w
    $buttons=All $w ([System.Windows.Automation.ControlType]::Button)
    $hasPlace=$false
    for($b=0;$b -lt $buttons.Count;$b++){ if((N $buttons.Item($b)) -match '(?i)\bPlace\b'){ $hasPlace=$true; break } }
    if($hasPlace -or $nm -match '(?i)\b(New\s+)?Order\b'){ $dialog=$w; break }
  }
}
if($null -eq $dialog){ Out-Result $false 'ORDER TICKET NOT FOUND' 'MT5 did not expose the native order dialog'; exit 0 }
try{$dialog.SetFocus()}catch{}

# Verify the order ticket is on the same asset family. Broker suffixes such as
# BTCUSDm / XAUUSD.a are accepted; a different asset is not modified.
$family = if(([string]$p.symbol).ToUpperInvariant().StartsWith('BTC')){'BTC'}else{'XAU|GOLD'}
$parts=New-Object System.Collections.Generic.List[string]
$parts.Add((N $dialog))
$allEls=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
for($i=0;$i -lt $allEls.Count;$i++){
  $e=$allEls.Item($i); $n=N $e; if($n){$parts.Add($n)}
  if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::ComboBox){$v=Value-Of $e;if($v){$parts.Add($v)}}
}
$joined=($parts -join ' ')
if($joined -notmatch $family){ Out-Result $false 'SYMBOL CHECK REQUIRED' ("Open the matching MT5 symbol first. Analysis symbol: "+$p.symbol); exit 0 }

if(-not (Select-Item $dialog $pidNum 'Pending Order')){ Out-Result $false 'PENDING MODE NOT FOUND' 'Could not switch the MT5 order ticket to Pending Order'; exit 0 }
Start-Sleep -Milliseconds 300
if(-not (Select-Item $dialog $pidNum ([string]$p.pending_type))){ Out-Result $false 'PENDING TYPE NOT FOUND' ("Could not select "+$p.pending_type); exit 0 }
Start-Sleep -Milliseconds 250

$entry=Edit-For $dialog '(?i)\bPrice\b'
$sl=Edit-For $dialog '(?i)Stop\s*Loss|\bS\s*/\s*L\b'
$tp=Edit-For $dialog '(?i)Take\s*Profit|\bT\s*/\s*P\b'
$okEntry=Set-Value $entry ([string]::Format([Globalization.CultureInfo]::InvariantCulture,'{0:0.########}',$p.entry))
$okSL=Set-Value $sl ([string]::Format([Globalization.CultureInfo]::InvariantCulture,'{0:0.########}',$p.sl))
$okTP=Set-Value $tp ([string]::Format([Globalization.CultureInfo]::InvariantCulture,'{0:0.########}',$p.tp1))
if(-not ($okEntry -and $okSL -and $okTP)){
  Out-Result $false 'PARTIAL MT5 PREFILL' ("Entry="+$okEntry+", SL="+$okSL+", TP="+$okTP); exit 0
}

# Deliberately stop here. The Place button remains untouched for user review.
Out-Result $true 'READY FOR USER CONFIRMATION' ("$($p.pending_type) • Entry $($p.entry) • SL $($p.sl) • TP1 $($p.tp1)")
`

	enc := encodePowerShellCommand(ps)
	psCmd := exec.Command("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc)
	psCmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	psCmd.Env = append(os.Environ(),
		"MH_MT5_PREFILL="+payload64,
		"MH_MT5_PID="+strconv.Itoa(cmd.Process.Pid),
		"MH_MT5_HWND="+strconv.FormatUint(uint64(wnd), 10),
	)
	out, err := psCmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("MT5 prefill automation failed: %v (%s)", err, strings.TrimSpace(string(out)))
	}
	lines := strings.Split(strings.ReplaceAll(string(out), "\r\n", "\n"), "\n")
	last := ""
	for _, line := range lines {
		if strings.TrimSpace(line) != "" {
			last = strings.TrimSpace(line)
		}
	}
	if last == "" {
		return "", fmt.Errorf("MT5 prefill returned no status")
	}
	var res struct {
		OK     bool   `json:"ok"`
		Status string `json:"status"`
		Detail string `json:"detail"`
	}
	if err := json.Unmarshal([]byte(last), &res); err != nil {
		return "", fmt.Errorf("MT5 prefill returned unreadable status: %s", last)
	}
	if !res.OK {
		if res.Detail != "" {
			return res.Status, fmt.Errorf("%s: %s", res.Status, res.Detail)
		}
		return res.Status, fmt.Errorf("%s", res.Status)
	}
	if res.Status == "" {
		res.Status = "READY FOR USER CONFIRMATION"
	}
	return res.Status, nil
}

func encodePowerShellCommand(s string) string {
	u := utf16.Encode([]rune(s))
	b := make([]byte, len(u)*2)
	for i, v := range u {
		b[i*2] = byte(v)
		b[i*2+1] = byte(v >> 8)
	}
	return base64.StdEncoding.EncodeToString(b)
}
