$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MHWin32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd,out RECT r);
  public struct RECT { public int Left,Top,Right,Bottom; }
}
'@

function Main-Hwnd($p){
  for($i=0;$i -lt 50;$i++){
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
  [IntPtr]$ok=[MHWin32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,2000,[ref]$r)
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
    Start-Sleep -Milliseconds 350
  }
  throw 'local service unavailable'
}

function Chrome-Child([IntPtr]$parentHwnd){
  $script:foundChild=[IntPtr]::Zero
  $cb=[MHWin32+EnumWindowsProc]{param($w,$l)
    $sb=New-Object Text.StringBuilder 128
    [void][MHWin32]::GetClassName($w,$sb,128)
    if($sb.ToString().StartsWith('Chrome_WidgetWin')){$script:foundChild=$w;return $false}
    return $true
  }
  [void][MHWin32]::EnumChildWindows($parentHwnd,$cb,[IntPtr]::Zero)
  return $script:foundChild
}

function Save-Shot([IntPtr]$h,[string]$name){
  $r=New-Object MHWin32+RECT
  [void][MHWin32]::GetWindowRect($h,[ref]$r)
  $w=[Math]::Max(1,$r.Right-$r.Left);$hh=[Math]::Max(1,$r.Bottom-$r.Top)
  $bmp=New-Object Drawing.Bitmap $w,$hh
  $g=[Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.Left,$r.Top,0,0,(New-Object Drawing.Size $w,$hh))
  $bmp.Save((Join-Path $PWD "dist\$name"),[Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose();$bmp.Dispose()
}

function Run-One([string]$label,[string]$shot){
  $p=Start-Process $exe -PassThru
  $server=''
  try{
    [IntPtr]$h=Main-Hwnd $p
    # A visible HWND can exist a few milliseconds before its message loop begins.
    # Treat the app as user-ready only when its local service is reachable, then
    # require the native shell to answer immediately and throughout browser startup.
    $server=Wait-Server $p
    Responsive $h "$label ready"
    if($server -eq 'http://127.0.0.1:17878'){throw 'fixed port returned'}
    $html=(Invoke-WebRequest "$server/" -UseBasicParsing -TimeoutSec 3).Content
    $js=(Invoke-WebRequest "$server/app.js" -UseBasicParsing -TimeoutSec 3).Content
    if($html -notmatch 'runtime-fixes.js'){throw 'runtime UI assets missing'}
    foreach($m in @('FIXED_PHASE_MS=15*60*1000','scheduleAutoAt','*Entry:*','*TP1:*','*SL:*')){if(-not $js.Contains($m)){throw "missing $m"}}

    [IntPtr]$child=[IntPtr]::Zero
    for($i=0;$i -lt 80;$i++){
      $child=Chrome-Child $h
      if($child -ne [IntPtr]::Zero){break}
      Responsive $h "$label while browser loads"
      Start-Sleep -Milliseconds 250
    }
    if($child -eq [IntPtr]::Zero){throw 'embedded browser child not found'}

    $style=[MHWin32]::GetWindowLongPtr($child,-16).ToInt64()
    $ex=[MHWin32]::GetWindowLongPtr($child,-20).ToInt64()
    if(($style -band 0x40000000) -eq 0){throw 'browser is not WS_CHILD'}
    if(($style -band 0x00CC0000) -ne 0){throw ('browser frame styles still present: 0x{0:X}' -f $style)}
    if(($ex -band 0x00060301) -ne 0){throw ('browser extended frame styles still present: 0x{0:X}' -f $ex)}

    $bp=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object{($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and $_.CommandLine -match '--app=http://127\.0\.0\.1:\d+/'}|Select-Object -First 1
    if(-not $bp -or $bp.CommandLine -notmatch '--kiosk'){throw 'frameless kiosk launch is not active'}

    [MHWin32]::PostMessage($h,0x0111,[IntPtr]1002,[IntPtr]::Zero)|Out-Null
    Start-Sleep -Seconds 1
    Responsive $h "$label WhatsApp button"
    [MHWin32]::PostMessage($h,0x0111,[IntPtr]1001,[IntPtr]::Zero)|Out-Null
    Start-Sleep -Milliseconds 600
    Responsive $h "$label Analysis button"
    Save-Shot $h $shot
    Write-Host "PASS $label dynamic=$server no-frame responsive"
  } finally {
    if($server){try{Invoke-WebRequest ($server+'/api/shutdown') -UseBasicParsing -TimeoutSec 2|Out-Null}catch{}}
    for($i=0;$i -lt 24 -and -not $p.HasExited;$i++){Start-Sleep -Milliseconds 250}
    if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue}
    Start-Sleep -Seconds 2
  }
}

Run-One 'first-open' 'outer-first.png'
Run-One 'restart' 'outer-restart.png'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS complete: startup + button switching + no frame styles + restart'
