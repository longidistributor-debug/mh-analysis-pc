(()=>{
'use strict';
// V56.17: display-only repair for legacy mojibake text and missing market-ticker symbols.
// Important: every DOM write is change-only and observer work is debounced so the
// updater/login UI can never be starved by a self-triggering MutationObserver loop.
// Trading, signal, EA, lot-size and SL logic are intentionally untouched.
const root=document.querySelector('.appShell');
if(!root)return;

function cleanText(value){
  let s=String(value??'');
  const exact=[
    ['ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â','—'],
    ['ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¢','•'],
    ['ÃƒÂ¢Ã¢â‚¬Â Ã‚Â»',''],
    ['ÃƒÂ¢Ã¢â‚¬â€Ã‚Â´',''],
    ['ÃƒÂ¢Ã¢â‚¬â€Ã‚Â',''],
    ['ÃƒÂ¢Ã¢â‚¬â€Ã…Â½',''],
    ['ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬','€'],
    ['Ãƒâ€šÃ‚Â¥','¥'],
    ['Ãƒâ€šÃ‚Â£','£'],
    ['ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¿','₿']
  ];
  for(const [from,to] of exact)s=s.split(from).join(to);
  const replacements=[
    [/\u2014/g,'—'],[/\u2013/g,'-'],[/\u2022/g,' • '],[/\u2026/g,'...'],
    [/\u00e2\u20ac\u201d/g,'—'],[/\u00e2\u20ac\u201c/g,'-'],[/\u00e2\u20ac\u00a2/g,' • '],[/\u00e2\u20ac\u00a6/g,'...'],
    [/\u00e2\u2020\u00bb/g,''],[/\u00e2\u2014\u00b4/g,''],[/\u00e2\u2014\u00b7/g,''],
    [/\u00f0\u0178\u008f\u0086/g,''],
    [/\u00e2\u201a\u00ac/g,'€'],[/\u00c2\u00a5/g,'¥'],[/\u00c2\u00a3/g,'£'],[/\u00c2\u00a9/g,'©'],
    [/Ã¢â‚¬â€/g,'—'],[/Ã¢â‚¬Â¢/g,' • '],[/Ã¢â‚¬Â¦/g,'...'],
    [/Ã¢â€šÂ¬/g,'€'],[/Â¥/g,'¥'],[/Â£/g,'£'],[/Â©/g,'©']
  ];
  for(const [re,to] of replacements)s=s.replace(re,to);
  if(/Ãƒ|Ã‚|Ã¢|Â¬|Â¢|Â|Âƒ/.test(s)){
    s=s.replace(/Ãƒ/g,'').replace(/Ã‚/g,'').replace(/Ã¢/g,'').replace(/Â¬/g,'').replace(/Â¢/g,'').replace(/Â/g,'').replace(/Âƒ/g,'');
  }
  return s;
}

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

function fixKnownLabels(){
  set('#analyze','NEW ANALYZE');
  set('#reevaluate','RE-EVALUATE');
  set('.contextPanel h3','MARKET CONTEXT');
  set('.confirmationsInside h4','CONFIRMATIONS / WARNINGS');
  set('.topSetupPanel h3','TOP SETUP');
  set('.recentPanel h3','RECENT SIGNALS');
  set('.liveDot','Interactive');
  ['#mapRegime','#mapAdx','#mapVwap','#mapBullOb','#mapBearOb','#mapFvg','#mapEq','#mapRisk',
   '#buyScoreTop','#sellScoreTop','#signalQuality','#lastUpdate','#candleCount','#reasons',
   '#btcMarketCap','#totalMarketCap','#btcDominance','#btcChange']
    .forEach(sel=>{const el=document.querySelector(sel);if(el&&/Ã|Â/.test(el.textContent))setText(el,'—');});
  const footer=document.querySelector('.mhMainCopyright');
  const footerText='MH ANALYSIS By: Muhammad Hammad Shaukat - © All Rights Reserved 2026';
  if(footer&&footer.textContent!==footerText)footer.textContent=footerText;
  fixTickerIcons();
}

function walk(node){
  const w=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
  let n;
  while((n=w.nextNode())){
    const parent=n.parentElement;
    if(!parent||parent.closest('.bismillahArea'))continue;
    const next=cleanText(n.nodeValue);
    if(next!==n.nodeValue)n.nodeValue=next;
  }
}

let applying=false,queued=false;
function apply(){
  if(applying)return;
  applying=true;
  try{fixKnownLabels();walk(root);}finally{applying=false;}
}
function queueApply(){
  if(queued)return;
  queued=true;
  setTimeout(()=>{queued=false;apply();},40);
}
apply();
const observer=new MutationObserver(queueApply);
observer.observe(root,{subtree:true,childList:true,characterData:true});
})();
