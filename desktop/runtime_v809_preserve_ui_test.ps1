$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MH809Win32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam,uint flags,uint timeout,out IntPtr result);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
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
  [IntPtr]$ok=[MH809Win32]::SendMessageTimeout($h,0,[IntPtr]::Zero,[IntPtr]::Zero,2,1600,[ref]$r)
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

function Child-Info([IntPtr]$parentHwnd){
  $list=New-Object System.Collections.ArrayList
  $cb=[MH809Win32+EnumWindowsProc]{param($w,$l)
    $cls=New-Object Text.StringBuilder 128
    [void][MH809Win32]::GetClassName($w,$cls,128)
    $txt=New-Object Text.StringBuilder 256
    [void][MH809Win32]::GetWindowText($w,$txt,256)
    $r=New-Object MH809Win32+RECT
    [void][MH809Win32]::GetWindowRect($w,[ref]$r)
    [void]$list.Add([pscustomobject]@{H=$w;Class=$cls.ToString();Text=$txt.ToString();Visible=[MH809Win32]::IsWindowVisible($w);L=$r.Left;T=$r.Top;R=$r.Right;B=$r.Bottom})
    return $true
  }
  [void][MH809Win32]::EnumChildWindows($parentHwnd,$cb,[IntPtr]::Zero)
  return @($list)
}

function Assert-NativeToolbar([IntPtr]$h,[string]$where){
  $children=Child-Info $h
  foreach($name in @('MH Analysis','WhatsApp','Records','MT5 System')){
    $b=$children|Where-Object{$_.Class -eq 'Button' -and $_.Text -eq $name -and $_.Visible}|Select-Object -First 1
    if(-not $b){throw "$where missing visible native button: $name"}
  }
}

function Visible-Chrome([IntPtr]$h){
  return (Child-Info $h|Where-Object{$_.Class.StartsWith('Chrome_WidgetWin') -and $_.Visible}|Select-Object -First 1)
}

function Assert-ContentBelowToolbar([IntPtr]$h,[string]$where){
  $child=Visible-Chrome $h
  if(-not $child){throw "$where visible embedded Chromium child not found"}
  $pt=New-Object MH809Win32+POINT;$pt.X=0;$pt.Y=0
  [void][MH809Win32]::ClientToScreen($h,[ref]$pt)
  $rc=New-Object MH809Win32+RECT
  [void][MH809Win32]::GetClientRect($h,[ref]$rc)
  $clientW=$rc.Right-$rc.Left;$clientH=$rc.Bottom-$rc.Top
  $barH=46
  $expectTop=$pt.Y+$barH
  if([Math]::Abs($child.T-$expectTop) -gt 3){throw "$where content top=$($child.T), expected=$expectTop; native toolbar is being covered/cut"}
  if([Math]::Abs($child.L-$pt.X) -gt 3){throw "$where content left mismatch"}
  if([Math]::Abs(($child.R-$child.L)-$clientW) -gt 4){throw "$where content width mismatch"}
  if([Math]::Abs(($child.B-$child.T)-($clientH-$barH)) -gt 4){throw "$where content height mismatch; footer/scroll viewport can be clipped"}
  $style=[MH809Win32]::GetWindowLongPtr($child.H,-16).ToInt64()
  $ex=[MH809Win32]::GetWindowLongPtr($child.H,-20).ToInt64()
  if(($style -band 0x40000000) -eq 0){throw "$where browser is not WS_CHILD"}
  if(($style -band 0x00CC0000) -ne 0){throw ('browser frame styles remain: 0x{0:X}' -f $style)}
  if(($ex -band 0x00060301) -ne 0){throw ('browser extended frame styles remain: 0x{0:X}' -f $ex)}
}

function Signal-Link-Visible([IntPtr]$h){
  $x=Child-Info $h|Where-Object{$_.Class -eq 'Button' -and $_.Text -eq 'Signal Link'}|Select-Object -First 1
  return [bool]($x -and $x.Visible)
}

function Run-One([string]$label){
  $p=Start-Process $exe -PassThru
  $server=''
  try{
    [IntPtr]$h=Main-Hwnd $p
    $server=Wait-Server $p
    Responsive $h "$label startup"
    Assert-NativeToolbar $h "$label startup"

    # Analysis browser must be an app-mode child, not kiosk/maximized over toolbar.
    $bp=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object{($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and $_.CommandLine -match '--app=http://127\.0\.0\.1:\d+/'}|Select-Object -First 1
    if(-not $bp){throw "$label Analysis --app browser process missing"}
    if($bp.CommandLine -match '--kiosk'){throw "$label kiosk regression detected"}

    $ready=$false
    for($i=0;$i -lt 80;$i++){
      try{Assert-ContentBelowToolbar $h "$label Analysis";$ready=$true;break}catch{}
      Responsive $h "$label browser load"
      Start-Sleep -Milliseconds 250
    }
    if(-not $ready){Assert-ContentBelowToolbar $h "$label Analysis final"}
    if(Signal-Link-Visible $h){throw "$label Signal Link must be hidden on MH Analysis"}

    # WhatsApp: native tab remains visible, its embedded view occupies the same
    # below-toolbar rectangle, and Signal Link becomes visible exactly here.
    [MH809Win32]::PostMessage($h,0x0111,[IntPtr]1002,[IntPtr]::Zero)|Out-Null
    Start-Sleep -Milliseconds 700
    Responsive $h "$label WhatsApp switch"
    Assert-NativeToolbar $h "$label WhatsApp switch"
    Assert-ContentBelowToolbar $h "$label WhatsApp"
    if(-not (Signal-Link-Visible $h)){throw "$label Signal Link did not appear on WhatsApp"}

    # Records button must still route and remain responsive. Do not touch MT5 in CI,
    # because the hosted runner may not have a broker terminal installed.
    [MH809Win32]::PostMessage($h,0x0111,[IntPtr]1005,[IntPtr]::Zero)|Out-Null
    Start-Sleep -Milliseconds 700
    Responsive $h "$label Records switch"
    Assert-NativeToolbar $h "$label Records switch"

    [MH809Win32]::PostMessage($h,0x0111,[IntPtr]1001,[IntPtr]::Zero)|Out-Null
    Start-Sleep -Milliseconds 450
    Responsive $h "$label Analysis return"
    Assert-NativeToolbar $h "$label Analysis return"
    Assert-ContentBelowToolbar $h "$label Analysis return"
    if(Signal-Link-Visible $h){throw "$label Signal Link stayed visible after returning to MH Analysis"}

    # User's reported EXIT failure was a blank four-button shell + Not Responding.
    # /api/shutdown must make the host disappear/process exit promptly.
    Invoke-WebRequest ($server+'/api/shutdown') -Method Post -UseBasicParsing -TimeoutSec 2|Out-Null
    $deadline=[DateTime]::UtcNow.AddSeconds(3)
    while(-not $p.HasExited -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100}
    if(-not $p.HasExited){
      Responsive $h "$label EXIT timeout"
      throw "$label EXIT left native shell alive longer than 3 seconds"
    }
    Write-Host "PASS $label native tabs + Signal Link + exact content bounds + responsive instant EXIT"
  } finally {
    if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue}
    Start-Sleep -Seconds 2
  }
}

Run-One 'first-open'
Run-One 'restart'
Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
Write-Host 'PASS V80.9: original native views preserved, content below toolbar, restart and EXIT responsive'
