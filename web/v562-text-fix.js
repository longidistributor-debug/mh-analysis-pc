(()=>{
'use strict';
// V56.18: display-only repair for legacy/dynamic mojibake and missing ticker symbols.
// All DOM writes are change-only and observer work is debounced.
// Trading, signal, EA, lot-size and SL logic are intentionally untouched.
const root=document.querySelector('.appShell');
if(!root)return;

const cp1252=new Map([
  [0x20AC,0x80],[0x201A,0x82],[0x0192,0x83],[0x201E,0x84],[0x2026,0x85],[0x2020,0x86],[0x2021,0x87],
  [0x02C6,0x88],[0x2030,0x89],[0x0160,0x8A],[0x2039,0x8B],[0x0152,0x8C],[0x017D,0x8E],[0x2018,0x91],
  [0x2019,0x92],[0x201C,0x93],[0x201D,0x94],[0x2022,0x95],[0x2013,0x96],[0x2014,0x97],[0x02DC,0x98],
  [0x2122,0x99],[0x0161,0x9A],[0x203A,0x9B],[0x0153,0x9C],[0x017E,0x9E],[0x0178,0x9F]
]);
const utf8=new TextDecoder('utf-8',{fatal:true});

function mojibakeScore(s){
  const m=String(s||'').match(/Ãƒ|Ã‚|Ã¢|Â|â€|â‚|ï¿½|\uFFFD/g);
  return m?m.length:0;
}
function decodeCp1252Utf8Once(value){
  const s=String(value??'');
  const bytes=[];
  for(const ch of s){
    const cp=ch.codePointAt(0);
    if(cp<=0xFF)bytes.push(cp);
    else if(cp1252.has(cp))bytes.push(cp1252.get(cp));
    else return s;
  }
  try{return utf8.decode(new Uint8Array(bytes));}catch(_){return s;}
}
function repairEncoding(value){
  let s=String(value??'');
  if(!mojibakeScore(s))return s;
  for(let i=0;i<4;i++){
    const next=decodeCp1252Utf8Once(s);
    if(next===s)break;
    if(mojibakeScore(next)<=mojibakeScore(s))s=next;else break;
    if(!mojibakeScore(s))break;
  }
  return s;
}
function cleanText(value){
  let s=repairEncoding(value);
  const replacements=[
    [/\u00e2\u20ac\u201d/g,'—'],[/\u00e2\u20ac\u201c/g,'-'],[/\u00e2\u20ac\u00a2/g,' • '],[/\u00e2\u20ac\u00a6/g,'...'],
    [/Ã¢â‚¬â€/g,'—'],[/Ã¢â‚¬Â¢/g,' • '],[/Ã¢â‚¬Â¦/g,'...'],[/Ã¢â€šÂ¬/g,'€'],[/Â¥/g,'¥'],[/Â£/g,'£'],[/Â©/g,'©']
  ];
  for(const [re,to] of replacements)s=s.replace(re,to);
  // If a legacy placeholder remains corrupted after decode, show a clean dash instead of garbage.
  if(mojibakeScore(s)&&s.trim().length<40)s='—';
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
    .forEach(sel=>{const el=document.querySelector(sel);if(el&&mojibakeScore(el.textContent))setText(el,'—');});
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
  setTimeout(()=>{queued=false;apply();},60);
}
apply();
new MutationObserver(queueApply).observe(root,{subtree:true,childList:true,characterData:true});
})();
