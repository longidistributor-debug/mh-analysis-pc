$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH810Win32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hWnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
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

function Main-Hwnd($p){
  for($i=0;$i -lt 60;$i++){
    $fresh=Get-Process -Id $p.Id -ErrorAction SilentlyContinue
    if(-not $fresh){throw 'EXE exited before native window was ready'}
    [IntPtr]$h=$fresh.MainWindowHandle
    if($h -ne [IntPtr]::Zero){return $h}
    Start-Sleep -Milliseconds 200
  }
  throw 'native main window unavailable'
}

function Responsive([IntPtr]$h,[string]$where){
  [IntPtr]$r=[IntPtr]::Zero
  [IntPtr]$ok=[MH810Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1600,[ref]$r)
  if($ok -eq [IntPtr]::Zero){throw "EXE Not Responding at $where"}
}

function Wait-Server($p){
  for($i=0;$i -lt 60;$i++){
    if($p.HasExited){throw "EXE exited startup code=$($p.ExitCode)"}
    try{
      $ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1
      if($ls){
        $u="http://127.0.0.1:$($ls.LocalPort)"
        $r=Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2
        if($r.StatusCode -eq 200){return $u}
      }
    }catch{}
    Start-Sleep -Milliseconds 300
  }
  throw 'local service unavailable'
}

function Direct-Chrome([IntPtr]$host){
  $script:found=[IntPtr]::Zero
  $cb=[MH810Win32+EnumWindowsProc]{param($w,$l)
    if([MH810Win32]::GetParent($w) -ne $host){return $true}
    $cls=New-Object Text.StringBuilder 128
    [void][MH810Win32]::GetClassName($w,$cls,128)
    if($cls.ToString().StartsWith('Chrome_WidgetWin') -and [MH810Win32]::IsWindowVisible($w)){
      $script:found=$w
      return $false
    }
    return $true
  }
  [void][MH810Win32]::EnumChildWindows($host,$cb,[IntPtr]::Zero)
  return $script:found
}

function Assert-Host-Frame([IntPtr]$h){
  $s=[MH810Win32]::GetWindowLongPtr($h,-16).ToInt64()
  foreach($pair in @(
    @{Name='CAPTION';Bit=0x00C00000},
    @{Name='SYSMENU';Bit=0x00080000},
    @{Name='MINIMIZEBOX';Bit=0x00020000},
    @{Name='MAXIMIZEBOX';Bit=0x00010000}
  )){
    if(($s -band [int64]$pair.Bit) -eq 0){throw "outer EXE missing $($pair.Name)"}
  }
}

function Assert-Single-Frame([IntPtr]$h,[string]$where){
  [IntPtr]$child=Direct-Chrome $h
  if($child -eq [IntPtr]::Zero){throw "$where direct embedded Chromium child not found"}
  $s=[MH810Win32]::GetWindowLongPtr($child,-16).ToInt64()
  $bad=[int64]0x00CF0000 # caption/border/thick/min/max/sysmenu frame family
  if(($s -band $bad) -ne 0){throw ('{0} inner browser still owns Windows frame styles: 0x{1:X}' -f $where,$s)}
  if(($s -band [int64]0x40000000) -eq 0){throw "$where inner browser is not WS_CHILD"}

  $hostRect=New-Object MH810Win32+RECT
  [void][MH810Win32]::GetClientRect($h,[ref]$hostRect)
  $pt=New-Object MH810Win32+POINT;$pt.X=0;$pt.Y=0
  [void][MH810Win32]::ClientToScreen($h,[ref]$pt)
  $r=New-Object MH810Win32+RECT
  [void][MH810Win32]::GetWindowRect($child,[ref]$r)
  $expectTop=$pt.Y+46
  if([Math]::Abs($r.Top-$expectTop) -gt 3){throw "$where child top=$($r.Top) expected=$expectTop"}

  $txt=New-Object Text.StringBuilder 256
  [void][MH810Win32]::GetWindowText($child,$txt,256)
  # A child may still have a window title string internally; the critical rule is
  # that no non-client caption/min/max/close frame is present.
}

function Run-One([string]$label){
  $p=Start-Process $exe -PassThru
  $server=''
  try{
    [IntPtr]$h=Main-Hwnd $p
    $server=Wait-Server $p
    Responsive $h "$label startup"
    Assert-Host-Frame $h
    $ok=$false
    for($i=0;$i -lt 80;$i++){
      try{Assert-Single-Frame $h $label;$ok=$true;break}catch{}
      Responsive $h "$label browser load"
      Start-Sleep -Milliseconds 250
    }
    if(-not $ok){Assert-Single-Frame $h "$label final"}
    Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null
    $deadline=[DateTime]::UtcNow.AddSeconds(3)
    while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100}
    if(-not $p.HasExited){throw "$label EXIT timeout"}
    Write-Host "PASS $label: only outer MH Analysis EXE owns minimize/maximize/close"
  } finally {
    if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue}
    Start-Sleep -Seconds 2
  }
}

Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V81.0 single native frame regression'
