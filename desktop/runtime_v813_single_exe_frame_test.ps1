$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH813Win32 {
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
  [DllImport("user32.dll")] public static extern int GetWindowRgnBox(IntPtr hWnd,out RECT r);
  public struct RECT { public int Left,Top,Right,Bottom; }
  public struct POINT { public int X,Y; }
}
'@
function Main-Hwnd($p){for($i=0;$i -lt 80;$i++){$fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $fresh){throw 'EXE exited'};[IntPtr]$h=$fresh.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 200};throw 'host unavailable'}
function Responsive([IntPtr]$h,[string]$where){[IntPtr]$r=[IntPtr]::Zero;[IntPtr]$ok=[MH813Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1800,[ref]$r);if($ok -eq [IntPtr]::Zero){throw "Not Responding at $where"}}
function Wait-Server($p){for($i=0;$i -lt 70;$i++){if($p.HasExited){throw 'EXE exited startup'};try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";$r=Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2;if($r.StatusCode -eq 200){return $u}}}catch{};Start-Sleep -Milliseconds 300};throw 'local service unavailable'}
function Direct-Chrome([IntPtr]$parentWnd){$script:found=[IntPtr]::Zero;$cb=[MH813Win32+EnumWindowsProc]{param($w,$l);if([MH813Win32]::GetParent($w) -ne $parentWnd){return $true};$cls=New-Object Text.StringBuilder 128;[void][MH813Win32]::GetClassName($w,$cls,128);if($cls.ToString().StartsWith('Chrome_WidgetWin') -and [MH813Win32]::IsWindowVisible($w)){$script:found=$w;return $false};return $true};[void][MH813Win32]::EnumChildWindows($parentWnd,$cb,[IntPtr]::Zero);return $script:found}
function Assert-SingleExe([IntPtr]$h,[string]$where){
  [IntPtr]$child=Direct-Chrome $h;if($child -eq [IntPtr]::Zero){throw "$where browser child missing"}
  $style=[MH813Win32]::GetWindowLongPtr($child,-16).ToInt64();if(($style -band [int64]0x00CF0000)-ne 0){throw "$where native nested frame bits remain"};if(($style -band [int64]0x40000000)-eq 0){throw "$where browser not WS_CHILD"}
  $cr=New-Object MH813Win32+RECT;[void][MH813Win32]::GetClientRect($h,[ref]$cr)
  $pt=New-Object MH813Win32+POINT;$pt.X=0;$pt.Y=0;[void][MH813Win32]::ClientToScreen($h,[ref]$pt)
  $r=New-Object MH813Win32+RECT;[void][MH813Win32]::GetWindowRect($child,[ref]$r)
  $expectedW=$cr.Right-$cr.Left;$actualW=$r.Right-$r.Left;if([Math]::Abs($actualW-$expectedW)-gt 4){throw "$where width $actualW expected $expectedW"}
  $region=New-Object MH813Win32+RECT;$kind=[MH813Win32]::GetWindowRgnBox($child,[ref]$region);if($kind -eq 0){throw "$where crop region missing"};if($region.Top -lt 20){throw "$where crop too small top=$($region.Top)"}
  # Exact user issue guard: the first visible row below the native toolbar must not be a light Chrome app caption.
  $sampleW=[Math]::Min(900,[Math]::Max(200,$expectedW-120));$sx=$pt.X+60;$sy=$pt.Y+54
  $bmp=New-Object Drawing.Bitmap $sampleW,2;$g=[Drawing.Graphics]::FromImage($bmp)
  try{$g.CopyFromScreen($sx,$sy,0,0,$bmp.Size);$light=0;$total=$sampleW*2;for($yy=0;$yy -lt 2;$yy++){for($xx=0;$xx -lt $sampleW;$xx++){$c=$bmp.GetPixel($xx,$yy);if($c.R -gt 160 -and $c.G -gt 175 -and $c.B -gt 185){$light++}}};$ratio=$light/[double]$total;if($ratio -gt .35){throw ("$where inner Chrome title bar still visible ratio={0:P0}" -f $ratio)}}finally{$g.Dispose();$bmp.Dispose()}
}
function Wait-SingleExe([IntPtr]$h,[string]$where){for($i=0;$i -lt 35;$i++){try{Assert-SingleExe $h $where;return}catch{if($i -eq 34){throw};Start-Sleep -Milliseconds 140}}}
function Run-One([string]$label){$p=Start-Process $exe -PassThru;$server='';try{[IntPtr]$h=Main-Hwnd $p;$server=Wait-Server $p;Start-Sleep -Milliseconds 2600;Responsive $h "$label startup";Wait-SingleExe $h "$label maximized";[void][MH813Win32]::ShowWindow($h,9);Start-Sleep -Milliseconds 250;[void][MH813Win32]::MoveWindow($h,120,90,1040,720,$true);Start-Sleep -Milliseconds 400;Responsive $h "$label restored";Wait-SingleExe $h "$label restored";[void][MH813Win32]::ShowWindow($h,3);Start-Sleep -Milliseconds 500;Responsive $h "$label remax";Wait-SingleExe $h "$label remax";Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null;$deadline=[DateTime]::UtcNow.AddSeconds(3);while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100};if(-not $p.HasExited){throw "$label EXIT timeout"};Write-Host "PASS ${label}: only outer EXE frame visible and resize remains responsive"}finally{if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue};Start-Sleep -Seconds 2}}
Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.3 single EXE frame + responsive regression'
