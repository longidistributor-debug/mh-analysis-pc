$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH811Win32 {
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
  public struct RECT { public int Left,Top,Right,Bottom; }
  public struct POINT { public int X,Y; }
}
'@
function Main-Hwnd($p){for($i=0;$i -lt 80;$i++){$fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $fresh){throw 'EXE exited'};[IntPtr]$h=$fresh.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 200};throw 'host unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH811Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1600,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Wait-Server($p){for($i=0;$i -lt 70;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){return $u}}}catch{};Start-Sleep -Milliseconds 300};throw 'local service unavailable'}
function Direct-Chrome([IntPtr]$parentWnd){$script:found=[IntPtr]::Zero;$cb=[MH811Win32+EnumWindowsProc]{param($w,$l);if([MH811Win32]::GetParent($w) -ne $parentWnd){return $true};$cls=New-Object Text.StringBuilder 128;[void][MH811Win32]::GetClassName($w,$cls,128);if($cls.ToString().StartsWith('Chrome_WidgetWin') -and [MH811Win32]::IsWindowVisible($w)){$script:found=$w;return $false};return $true};[void][MH811Win32]::EnumChildWindows($parentWnd,$cb,[IntPtr]::Zero);return $script:found}
function Assert-Host-Frame([IntPtr]$h){$s=[MH811Win32]::GetWindowLongPtr($h,-16).ToInt64();foreach($b in @(0x00C00000,0x00080000,0x00020000,0x00010000)){if(($s -band [int64]$b)-eq 0){throw 'outer EXE frame control missing'}}}
function Assert-No-Nested-Frame([IntPtr]$h,[string]$where){[IntPtr]$child=Direct-Chrome $h;if($child -eq [IntPtr]::Zero){throw "$where browser child missing"};$s=[MH811Win32]::GetWindowLongPtr($child,-16).ToInt64();if(($s -band [int64]0x00CF0000)-ne 0){throw ('nested native frame bits remain 0x{0:X}' -f $s)};if(($s -band [int64]0x40000000)-eq 0){throw 'browser not child'};$pt=New-Object MH811Win32+POINT;$pt.X=0;$pt.Y=0;[void][MH811Win32]::ClientToScreen($h,[ref]$pt);$r=New-Object MH811Win32+RECT;[void][MH811Win32]::GetWindowRect($child,[ref]$r);$expected=$pt.Y+46;if([Math]::Abs($r.Top-$expected)-gt 3){throw "$where browser top $($r.Top), expected $expected"};
  # Visual guard for the exact user-reported light nested Chromium title bar.
  $w=[Math]::Min(900,[Math]::Max(100,$r.Right-$r.Left-120));$x=$r.Left+60;$y=$r.Top+8;$bmp=New-Object Drawing.Bitmap $w,1;$g=[Drawing.Graphics]::FromImage($bmp);try{$g.CopyFromScreen($x,$y,0,0,$bmp.Size);$bright=0;for($i=0;$i -lt $w;$i++){$c=$bmp.GetPixel($i,0);if((([int]$c.R+[int]$c.G+[int]$c.B)/3)-gt 175){$bright++}};$ratio=$bright/[double]$w;if($ratio -gt 0.55){throw ("$where visual nested titlebar detected, bright-row ratio={0:P0}" -f $ratio)}}finally{$g.Dispose();$bmp.Dispose()}}
function Run-One([string]$label){$p=Start-Process $exe -PassThru;$server='';try{[IntPtr]$h=Main-Hwnd $p;$server=Wait-Server $p;Responsive $h "$label startup";Assert-Host-Frame $h;Start-Sleep -Milliseconds 2600;$ok=$false;for($i=0;$i -lt 30;$i++){try{Assert-No-Nested-Frame $h $label;$ok=$true;break}catch{if($i -eq 29){throw};Start-Sleep -Milliseconds 200}};if(-not $ok){throw "$label nested frame check failed"};Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(3);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"};Write-Host "PASS ${label}: one EXE frame, no nested browser titlebar"}finally{if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.1 hard single-frame visual regression'
