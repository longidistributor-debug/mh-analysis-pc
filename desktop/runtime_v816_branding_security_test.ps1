$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MH816Win32 {
  [DllImport("user32.dll")] public static extern bool GetWindowDisplayAffinity(IntPtr hWnd, out uint affinity);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int cmd);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd,int x,int y,int w,int h,bool repaint);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
}
'@

function Main-Hwnd($p){for($i=0;$i -lt 100;$i++){$f=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $f){throw 'EXE exited'};[IntPtr]$h=$f.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 160};throw 'main window unavailable'}
function Wait-Server($p){for($i=0;$i -lt 80;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){return $u}}}catch{};Start-Sleep -Milliseconds 250};throw 'local service unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH816Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1800,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Assert-Protected([IntPtr]$h,[string]$where){for($i=0;$i -lt 30;$i++){[uint32]$a=0;if([MH816Win32]::GetWindowDisplayAffinity($h,[ref]$a) -and $a -eq 0x11){return};Start-Sleep -Milliseconds 120};throw "$where host does not have WDA_EXCLUDEFROMCAPTURE"}
function Assert-Icon([IntPtr]$h,[string]$where){$big=[MH816Win32]::SendMessage($h,0x007F,[IntPtr]1,[IntPtr]::Zero);$small=[MH816Win32]::SendMessage($h,0x007F,[IntPtr]0,[IntPtr]::Zero);if($big -eq [IntPtr]::Zero -and $small -eq [IntPtr]::Zero){throw "$where MH icon missing"}}
function Run-One([string]$label){$p=Start-Process $exe -PassThru;try{[IntPtr]$h=Main-Hwnd $p;$u=Wait-Server $p;Assert-Protected $h $label;Assert-Icon $h $label;Responsive $h "$label startup";[void][MH816Win32]::ShowWindow($h,9);Start-Sleep -Milliseconds 120;[void][MH816Win32]::MoveWindow($h,110,80,1050,720,$true);Start-Sleep -Milliseconds 350;Responsive $h "$label resized";Invoke-WebRequest ($u+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(5);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"};Write-Host "PASS ${label}: MH icon + capture exclusion + responsive host + clean EXIT"}finally{if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.6 branding/security regression'
