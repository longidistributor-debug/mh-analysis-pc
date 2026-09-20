$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH814Win32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd,out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd,out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT p);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd,int X,int Y,int W,int H,bool repaint);
  public struct RECT { public int Left,Top,Right,Bottom; }
  public struct POINT { public int X,Y; }
}
'@
function Main-Hwnd($p){for($i=0;$i -lt 80;$i++){$fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $fresh){throw 'EXE exited'};[IntPtr]$h=$fresh.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 200};throw 'host unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH814Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1800,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Wait-Server($p){for($i=0;$i -lt 70;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/records.html" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200 -and $r.Content.Contains('MH ANALYSIS')){return $u}}}catch{};Start-Sleep -Milliseconds 300};throw 'records local service unavailable'}
function Find-Visible-Records([IntPtr]$parentWnd){$script:found=[IntPtr]::Zero;$cb=[MH814Win32+EnumWindowsProc]{param($w,$l);if([MH814Win32]::GetParent($w) -ne $parentWnd){return $true};if(-not [MH814Win32]::IsWindowVisible($w)){return $true};$cls=New-Object Text.StringBuilder 128;[void][MH814Win32]::GetClassName($w,$cls,128);if(-not $cls.ToString().StartsWith('Chrome_WidgetWin')){return $true};$title=New-Object Text.StringBuilder 256;[void][MH814Win32]::GetWindowText($w,$title,256);if($title.ToString() -like '*Records*'){$script:found=$w;return $false};return $true};[void][MH814Win32]::EnumChildWindows($parentWnd,$cb,[IntPtr]::Zero);return $script:found}
function Assert-Records([IntPtr]$h,[string]$where){[IntPtr]$child=Find-Visible-Records $h;if($child -eq [IntPtr]::Zero){throw "$where Records browser not visible"};$cr=New-Object MH814Win32+RECT;[void][MH814Win32]::GetClientRect($h,[ref]$cr);$r=New-Object MH814Win32+RECT;[void][MH814Win32]::GetWindowRect($child,[ref]$r);$pt=New-Object MH814Win32+POINT;$pt.X=0;$pt.Y=0;[void][MH814Win32]::ClientToScreen($h,[ref]$pt);$actualW=$r.Right-$r.Left;if([Math]::Abs($actualW-($cr.Right-$cr.Left))-gt 5){throw "$where Records width mismatch"};if($r.Bottom-$r.Top -lt 300){throw "$where Records child too short"}}
function Wait-Records([IntPtr]$h,[string]$where){for($i=0;$i -lt 80;$i++){try{Assert-Records $h $where;return}catch{if($i -eq 79){throw};Start-Sleep -Milliseconds 150}}}
function Click-Tab([IntPtr]$h,[int]$id){[void][MH814Win32]::SendMessage($h,0x0111,[IntPtr]$id,[IntPtr]::Zero)}
function Run-One([string]$label){$p=Start-Process $exe -PassThru;$server='';try{[IntPtr]$h=Main-Hwnd $p;$server=Wait-Server $p;Start-Sleep -Milliseconds 1200;Responsive $h "$label startup";Click-Tab $h 1003;Wait-Records $h "$label records-first";Responsive $h "$label records-first";
  [void][MH814Win32]::ShowWindow($h,9);Start-Sleep -Milliseconds 180;[void][MH814Win32]::MoveWindow($h,120,90,1040,720,$true);Start-Sleep -Milliseconds 250;Wait-Records $h "$label records-small";
  Click-Tab $h 1001;Start-Sleep -Milliseconds 180;Click-Tab $h 1003;Wait-Records $h "$label records-return";Responsive $h "$label records-return";
  Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(3);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"};Write-Host "PASS ${label}: Records visible, responsive, reusable"}finally{if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.4 Records view regression'
