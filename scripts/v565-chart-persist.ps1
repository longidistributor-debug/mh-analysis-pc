$ErrorActionPreference='Stop'
$p='web/app.js'
$s=Get-Content -Raw $p
$s=$s -replace "`r`n","`n"

$ctx=$s.IndexOf('async function contextChanged(){')
if($ctx -lt 0){throw 'contextChanged not found'}
$ctxEnd=$s.IndexOf("`n}`",$ctx)
if($ctxEnd -lt 0){throw 'contextChanged end not found'}
$load=$s.IndexOf('  loadChart();',$ctx)
if($load -lt 0 -or $load -gt $ctxEnd){throw 'contextChanged loadChart baseline not found'}
$replacement=@'
  // V56.5: keep the last fetched chart visible while pair/timeframe selection changes.
  // Selection remains API-silent; only NEW ANALYZE / RE-EVALUATE replaces the chart.
  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));
'@
$s=$s.Remove($load,'  loadChart();'.Length)
$s=$s.Insert($load,$replacement.TrimEnd("`r","`n"))

$newStart=$s.IndexOf('async function executeNewAnalysis(fromAuto=false){')
if($newStart -lt 0){throw 'executeNewAnalysis not found'}
$newGuard='  if(busy)return null;'
$newGuardPos=$s.IndexOf($newGuard,$newStart)
if($newGuardPos -lt 0){throw 'NEW ANALYZE busy guard not found'}
$newInsert=$newGuardPos+$newGuard.Length
if($s.Substring($newInsert,[Math]::Min(12,$s.Length-$newInsert)) -notlike 'loadChart()*'){$s=$s.Insert($newInsert,'loadChart();')}

$reStart=$s.IndexOf('async function executeReevaluate(fromAuto=false){')
if($reStart -lt 0){throw 'executeReevaluate not found'}
$reBusy=$s.IndexOf('  busy=true;setBusy',$reStart)
if($reBusy -lt 0){throw 'RE-EVALUATE active-fetch block not found'}
$prefix=$s.Substring([Math]::Max($reStart,$reBusy-20),$reBusy-[Math]::Max($reStart,$reBusy-20))
if($prefix -notmatch 'loadChart\(\);\s*$'){$s=$s.Insert($reBusy,"  loadChart();`n")}

[IO.File]::WriteAllText((Join-Path $PWD $p),$s,(New-Object Text.UTF8Encoding($false)))

$check=Get-Content -Raw $p
if(-not $check.Contains('V56.5: keep the last fetched chart visible')){throw 'V56.5 marker missing'}
$ctx2=[regex]::Match($check,'async function contextChanged\(\)\{(?s:.*?)\n\}').Value
if($ctx2.Contains('loadChart();')){throw 'Selection still clears chart'}
if($ctx2.Contains('fetchCandles') -or $ctx2.Contains('loadContextChart') -or $ctx2.Contains('refreshMarketCap')){throw 'Selection must remain API-silent'}
if(-not $check.Contains('if(busy)return null;loadChart();autoActionStartedAt=Date.now()')){throw 'NEW ANALYZE chart replacement marker missing'}
$re2=$check.Substring($check.IndexOf('async function executeReevaluate(fromAuto=false){'))
if(-not $re2.Contains("loadChart();`n  busy=true;setBusy")){throw 'RE-EVALUATE chart replacement marker missing'}
