$ErrorActionPreference='Stop'
$env:MH_SMOKE_TEST='1'
$exe=Join-Path $PWD 'dist\MH Analysis.exe'

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class MHClickTest {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr parent, int id);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int index);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd,uint Msg,IntPtr wParam,IntPtr lParam);
}
'@

function Text-Of([IntPtr]$h){$b=New-Object Text.StringBuilder 1024;[void][MHClickTest]::GetWindowText($h,$b,1024);$b.ToString()}
function Class-Of([IntPtr]$h){$b=New-Object Text.StringBuilder 128;[void][MHClickTest]::GetClassName($h,$b,128);$b.ToString()}
function Main-Hwnd($p){for($i=0;$i -lt 60;$i++){$f=Get-Process -Id $p.Id -ErrorAction SilentlyContinue;if(-not $f){throw 'EXE exited'};[IntPtr]$h=$f.MainWindowHandle;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 200};throw 'main window unavailable'}
function Wait-Server($p){for($i=0;$i -lt 60;$i++){try{$ls=Get-NetTCPConnection -State Listen -OwningProcess $p.Id -ErrorAction Stop|Where-Object{$_.LocalAddress -eq '127.0.0.1'}|Select-Object -First 1;if($ls){$u="http://127.0.0.1:$($ls.LocalPort)";if((Invoke-WebRequest "$u/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200){return $u}}}catch{};Start-Sleep -Milliseconds 300};throw 'server unavailable'}
function Top-ByTitle([uint32]$procId,[string]$title){$script:hit=[IntPtr]::Zero;$cb=[MHClickTest+EnumWindowsProc]{param($w,$l)[uint32]$wp=0;[void][MHClickTest]::GetWindowThreadProcessId($w,[ref]$wp);if($wp -eq $procId -and (Text-Of $w) -eq $title){$script:hit=$w;return $false};return $true};[void][MHClickTest]::EnumWindows($cb,[IntPtr]::Zero);$script:hit}
function Wait-Top([uint32]$procId,[string]$title){for($i=0;$i -lt 50;$i++){$h=Top-ByTitle $procId $title;if($h -ne [IntPtr]::Zero){return $h};Start-Sleep -Milliseconds 120};throw "dialog not found: $title"}
function Visible([IntPtr]$p,[int]$id){$h=[MHClickTest]::GetDlgItem($p,$id);$h -ne [IntPtr]::Zero -and [MHClickTest]::IsWindowVisible($h)}
function Click([IntPtr]$p,[int]$id){$b=[MHClickTest]::GetDlgItem($p,$id);if($b -eq [IntPtr]::Zero){throw "control missing: $id"};[void][MHClickTest]::SendMessage($b,0x00F5,[IntPtr]::Zero,[IntPtr]::Zero)}
function Assert-Editable([IntPtr]$edit,[string]$expected){if($edit -eq [IntPtr]::Zero){throw 'edit missing'};if((Class-Of $edit) -ne 'Edit'){throw 'settings field is not standard Win32 EDIT'};$style=[MHClickTest]::GetWindowLongPtr($edit,-16).ToInt64();if(($style -band 0x0800)-ne 0){throw 'settings EDIT is read-only'};if(($style -band 0x0020)-ne 0){throw 'settings EDIT unexpectedly password-masked'};if((Text-Of $edit) -ne $expected){throw "settings value did not load into editable field"}}
function Settings($s){Invoke-RestMethod ($s+'/api/settings') -Method Get -TimeoutSec 3}
function Seed-Settings($s,[string]$api,[string]$wa){$b=@{api_key=$api;whatsapp_link=$wa}|ConvertTo-Json -Compress;Invoke-RestMethod ($s+'/api/settings') -Method Post -ContentType 'application/json' -Body $b -TimeoutSec 3|Out-Null}

$p=Start-Process $exe -PassThru
$server=''
try {
  [IntPtr]$main=Main-Hwnd $p;$server=Wait-Server $p;Seed-Settings $server '' '';Start-Sleep -Milliseconds 500
  if(-not (Visible $main 1001) -or -not (Visible $main 1002) -or (Visible $main 1003)){throw 'initial shell button state wrong'}
  Write-Host 'PASS initial only MH Analysis + WhatsApp'

  [MHClickTest]::PostMessage($main,0x0111,[IntPtr]1002,[IntPtr]::Zero)|Out-Null;Start-Sleep -Milliseconds 350
  if(-not (Visible $main 1003)){throw 'Signal Link not visible on WhatsApp'}
  Write-Host 'PASS WhatsApp shows Signal Link'
  [MHClickTest]::PostMessage($main,0x0111,[IntPtr]1001,[IntPtr]::Zero)|Out-Null;Start-Sleep -Milliseconds 250
  if(Visible $main 1003){throw 'Signal Link not hidden on Analysis'}
  Write-Host 'PASS Analysis hides Signal Link'

  Seed-Settings $server 'TESTKEY123' ''
  Invoke-WebRequest ($server+'/api/open-api-settings') -Method Post -UseBasicParsing -TimeoutSec 3|Out-Null
  $api=Wait-Top ([uint32]$p.Id) 'API Access Key'
  $edit=[MHClickTest]::GetDlgItem($api,2101)
  Assert-Editable $edit 'TESTKEY123'
  Click $api 2001;Start-Sleep -Milliseconds 500
  $st=Settings $server;if(-not $st.has_api_key){throw 'API SAVE real button click did not persist'}
  Write-Host 'PASS API dialog: standard editable field + SAVE real button click persisted'

  Seed-Settings $server 'TESTKEY123' 'https://wa.me/923434824609'
  [MHClickTest]::PostMessage($main,0x0111,[IntPtr]1002,[IntPtr]::Zero)|Out-Null;Start-Sleep -Milliseconds 300
  Click $main 1003
  $wa=Wait-Top ([uint32]$p.Id) 'WhatsApp Signal Link'
  $waEdit=[MHClickTest]::GetDlgItem($wa,2101)
  Assert-Editable $waEdit 'https://wa.me/923434824609'
  Click $wa 2001;Start-Sleep -Milliseconds 500
  $st=Settings $server
  if(-not $st.has_whatsapp -or $st.whatsapp_link -ne 'https://wa.me/923434824609'){throw 'Signal Link SAVE real button click did not persist'}
  Write-Host 'PASS Signal Link dialog: standard editable field + SAVE persisted for Get Signal'

  [MHClickTest]::PostMessage($main,0x0111,[IntPtr]1001,[IntPtr]::Zero)|Out-Null;Start-Sleep -Milliseconds 250
  if(Visible $main 1003){throw 'Signal Link remained on Analysis'}
  $js=(Invoke-WebRequest ($server+'/app.js') -UseBasicParsing -TimeoutSec 3).Content
  if($js.Contains('window.prompt(')){throw 'browser prompt remains'}
  if(-not $js.Contains('backendSettings.has_whatsapp')){throw 'Get Signal saved-link guard missing'}
  Write-Host 'PASS COMPLETE native editable settings + conditional Signal Link + saved Get Signal state'
  Seed-Settings $server '' ''
} finally {
  if($server){try{Invoke-WebRequest ($server+'/api/shutdown') -UseBasicParsing -TimeoutSec 2|Out-Null}catch{}}
  for($i=0;$i -lt 20 -and -not $p.HasExited;$i++){Start-Sleep -Milliseconds 250}
  if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue}
  Remove-Item Env:MH_SMOKE_TEST -ErrorAction SilentlyContinue
}
