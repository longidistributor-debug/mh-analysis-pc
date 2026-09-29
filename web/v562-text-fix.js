(()=>{
'use strict';
// V56.19: conservative display sanitization only.
// No whole-page decoding or tree walking. Dynamic prices/analysis values render from their source.
// Trading, signal, EA, lot-size and SL logic are intentionally untouched.
const root=document.querySelector('.appShell');
if(!root)return;

const brokenRe=/Ã|Â|â€|â‚|ï¿½|\uFFFD/;
function looksBroken(s){return brokenRe.test(String(s||''));}
function setText(el,text){if(el&&el.textContent!==text){el.textContent=text;return true;}return false;}
function set(selector,text){return setText(document.querySelector(selector),text);}

function fixTickerIcons(){
  document.querySelectorAll('.goldIcon,.goldAsset').forEach(el=>setText(el,'●'));
  document.querySelectorAll('.btcIcon,.btcAsset').forEach(el=>setText(el,'₿'));
  document.querySelectorAll('.ethAsset').forEach(el=>setText(el,'◆'));
  document.querySelectorAll('.capTitle .globe').forEach(el=>setText(el,'◉'));
  document.querySelectorAll('.tickerCell').forEach(cell=>{
    const label=(cell.querySelector('b')?.textContent||'').trim().toUpperCase();
    const icon=cell.querySelector('.assetIcon');
    if(!icon)return;
    let wanted='';
    if(label==='GOLD')wanted='●';
    else if(label==='BTCUSD')wanted='₿';
    else if(label==='ETHUSD')wanted='◆';
    else if(label==='EURUSD')wanted='€';
    else if(label==='USDJPY')wanted='¥';
    else if(label==='GBPUSD'||label==='GBPJPY')wanted='£';
    if(wanted)setText(icon,wanted);
  });
}

function sanitizeKnownDynamicText(){
  set('#analyze','NEW ANALYZE');
  set('#reevaluate','RE-EVALUATE');
  set('.contextPanel h3','MARKET CONTEXT');
  set('.confirmationsInside h4','CONFIRMATIONS / WARNINGS');
  set('.topSetupPanel h3','TOP SETUP');
  set('.recentPanel h3','RECENT SIGNALS');
  set('.liveDot','Interactive');

  [
    '#mapRegime','#mapAdx','#mapVwap','#mapBullOb','#mapBearOb','#mapFvg','#mapEq','#mapRisk',
    '#buyScoreTop','#sellScoreTop','#signalQuality','#lastUpdate','#candleCount','#reasons',
    '#btcMarketCap','#totalMarketCap','#btcDominance','#btcChange'
  ].forEach(sel=>{
    const el=document.querySelector(sel);
    if(el&&looksBroken(el.textContent))setText(el,'—');
  });

  const footer=document.querySelector('.mhMainCopyright');
  const footerText='MH ANALYSIS By: Muhammad Hammad Shaukat - © All Rights Reserved 2026';
  if(footer&&footer.textContent!==footerText)footer.textContent=footerText;
  fixTickerIcons();
}

let queued=false;
function queueApply(){
  if(queued)return;
  queued=true;
  setTimeout(()=>{queued=false;sanitizeKnownDynamicText();},80);
}
sanitizeKnownDynamicText();
new MutationObserver(queueApply).observe(root,{subtree:true,childList:true,characterData:true});
})();
