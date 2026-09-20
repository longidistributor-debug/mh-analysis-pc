$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MH815Win32 {
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd,int X,int Y,int W,int H,bool repaint);
}
'@
function Main-Hwnd($p){for($i=0;$i -lt 100;$i++){$fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $fresh){throw 'EXE exited'};[IntPtr]$h=$fresh.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 160};throw 'host unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH815Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1800,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Wait-Server($p){for($i=0;$i -lt 80;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/records.html" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200 -and $r.Content.Contains('MH ANALYSIS • RECORDS')){return $u}}}catch{};Start-Sleep -Milliseconds 250};throw 'records local service unavailable'}
function Check-Records-API([string]$u,[string]$where){$view=Invoke-RestMethod "$u/api/native-view" -Method Get -TimeoutSec 3;if([int]$view.view -ne 1){throw "$where unexpected initial native view"};$page=Invoke-WebRequest "$u/records.html" -UseBasicParsing -TimeoutSec 3;if(-not $page.Content.Contains('MH Analysis Records')){throw "$where records page missing"};try{$r=Invoke-WebRequest "$u/api/records-v2" -UseBasicParsing -TimeoutSec 3;if($r.StatusCode -ne 200){throw "$where records API status $($r.StatusCode)"}}catch{if($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -ge 500){throw "$where records API failed: $_"}}}
function Run-One([string]$label){$p=Start-Process $exe -PassThru;try{[IntPtr]$h=Main-Hwnd $p;$u=Wait-Server $p;Start-Sleep -Milliseconds 1200;Responsive $h "$label startup";Check-Records-API $u $label;[void][MH815Win32]::ShowWindow($h,9);Start-Sleep -Milliseconds 160;[void][MH815Win32]::MoveWindow($h,100,80,1040,720,$true);Start-Sleep -Milliseconds 320;Responsive $h "$label resized";Invoke-WebRequest ($u+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(5);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"};Write-Host "PASS ${label}: Records page/API available, host responsive, clean EXIT"}finally{if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.5 Records inline regression'
