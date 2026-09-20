$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH812Win32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd,out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd,out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT p);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd,int X,int Y,int W,int H,bool repaint);
  public struct RECT { public int Left,Top,Right,Bottom; }
  public struct POINT { public int X,Y; }
}
'@
function Main-Hwnd($p){for($i=0;$i -lt 80;$i++){$fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $fresh){throw 'EXE exited'};[IntPtr]$h=$fresh.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 200};throw 'host unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH812Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1800,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Wait-Server($p){for($i=0;$i -lt 70;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){return $u}}}catch{};Start-Sleep -Milliseconds 300};throw 'local service unavailable'}
function Direct-Chrome([IntPtr]$parentWnd){$script:found=[IntPtr]::Zero;$cb=[MH812Win32+EnumWindowsProc]{param($w,$l);if([MH812Win32]::GetParent($w) -ne $parentWnd){return $true};$cls=New-Object Text.StringBuilder 128;[void][MH812Win32]::GetClassName($w,$cls,128);if($cls.ToString().StartsWith('Chrome_WidgetWin') -and [MH812Win32]::IsWindowVisible($w)){$script:found=$w;return $false};return $true};[void][MH812Win32]::EnumChildWindows($parentWnd,$cb,[IntPtr]::Zero);return $script:found}
function Assert-Geometry([IntPtr]$h,[string]$where){
  [IntPtr]$child=Direct-Chrome $h;if($child -eq [IntPtr]::Zero){throw "$where browser child missing"}
  $style=[MH812Win32]::GetWindowLongPtr($child,-16).ToInt64();if(($style -band [int64]0x00CF0000)-ne 0){throw "$where nested frame bits remain"};if(($style -band [int64]0x40000000)-eq 0){throw "$where browser not child"}
  $cr=New-Object MH812Win32+RECT;[void][MH812Win32]::GetClientRect($h,[ref]$cr)
  $pt=New-Object MH812Win32+POINT;$pt.X=0;$pt.Y=0;[void][MH812Win32]::ClientToScreen($h,[ref]$pt)
  $r=New-Object MH812Win32+RECT;[void][MH812Win32]::GetWindowRect($child,[ref]$r)
  $expectedTop=$pt.Y+46;$expectedW=$cr.Right-$cr.Left;$expectedH=($cr.Bottom-$cr.Top)-46
  $actualW=$r.Right-$r.Left;$actualH=$r.Bottom-$r.Top
  if([Math]::Abs($r.Top-$expectedTop)-gt 3){throw "$where child top $($r.Top), expected $expectedTop"}
  if([Math]::Abs($actualW-$expectedW)-gt 4){throw "$where child width $actualW, expected $expectedW"}
  if([Math]::Abs($actualH-$expectedH)-gt 4){throw "$where child height $actualH, expected $expectedH"}
}
function Wait-Geometry([IntPtr]$h,[string]$where){for($i=0;$i -lt 30;$i++){try{Assert-Geometry $h $where;return}catch{if($i -eq 29){throw};Start-Sleep -Milliseconds 120}}}
function Run-One([string]$label){
  $p=Start-Process $exe -PassThru;$server=''
  try{
    [IntPtr]$h=Main-Hwnd $p;$server=Wait-Server $p;Start-Sleep -Milliseconds 2400;Responsive $h "$label startup";Wait-Geometry $h "$label maximized"
    [void][MH812Win32]::ShowWindow($h,9);Start-Sleep -Milliseconds 250;[void][MH812Win32]::MoveWindow($h,120,90,1040,720,$true);Start-Sleep -Milliseconds 350;Responsive $h "$label restored-small";Wait-Geometry $h "$label restored-small"
    [void][MH812Win32]::MoveWindow($h,70,55,1280,820,$true);Start-Sleep -Milliseconds 350;Responsive $h "$label restored-large";Wait-Geometry $h "$label restored-large"
    [void][MH812Win32]::ShowWindow($h,3);Start-Sleep -Milliseconds 450;Responsive $h "$label re-maximized";Wait-Geometry $h "$label re-maximized"
    Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(3);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"}
    Write-Host "PASS ${label}: responsive restore/maximize geometry and single frame"
  } finally {if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}
}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.2 responsive native-frame regression'
