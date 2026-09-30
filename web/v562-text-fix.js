(()=>{
'use strict';
// V.56.30: clean UTF-8 display sanitizer. No hard-coded mojibake literals.
// This only repairs legacy cached/display text; trading, signal, EA, lot and SL logic are untouched.
const root=document.querySelector('.appShell');
if(!root)return;
const cp1252=new Map([
  [0x20AC,0x80],[0x201A,0x82],[0x0192,0x83],[0x201E,0x84],[0x2026,0x85],[0x2020,0x86],[0x2021,0x87],[0x02C6,0x88],[0x2030,0x89],[0x0160,0x8A],[0x2039,0x8B],[0x0152,0x8C],[0x017D,0x8E],
  [0x2018,0x91],[0x2019,0x92],[0x201C,0x93],[0x201D,0x94],[0x2022,0x95],[0x2013,0x96],[0x2014,0x97],[0x02DC,0x98],[0x2122,0x99],[0x0161,0x9A],[0x203A,0x9B],[0x0153,0x9C],[0x017E,0x9E],[0x0178,0x9F]
]);
function suspiciousScore(s){return (String(s).match(/[\u00C3\u00C2\u00E2\u00F0\uFFFD]/g)||[]).length;}
function decodeCp1252Utf8(s){
  const bytes=[];
  for(const ch of s){
    const cp=ch.codePointAt(0);
    if(cp<=255)bytes.push(cp);
    else if(cp1252.has(cp))bytes.push(cp1252.get(cp));
    else return null;
  }
  try{return new TextDecoder('utf-8',{fatal:true}).decode(Uint8Array.from(bytes));}catch(_){return null;}
}
function cleanText(value){
  let s=String(value??'');
  for(let i=0;i<5;i++){
    if(!suspiciousScore(s))break;
    const next=decodeCp1252Utf8(s);
    if(!next||next===s||suspiciousScore(next)>suspiciousScore(s))break;
    s=next;
  }
  return s.replace(/\uFFFD/g,'');
}
function setText(el,text){if(el&&el.textContent!==text){el.textContent=text;return true}return false}
function fixTickerIcons(){
  document.querySelectorAll('.goldIcon,.goldAsset').forEach(el=>setText(el,'●'));
  document.querySelectorAll('.btcIcon,.btcAsset').forEach(el=>setText(el,'₿'));
  document.querySelectorAll('.ethAsset').forEach(el=>setText(el,'◆'));
  document.querySelectorAll('.capTitle .globe').forEach(el=>setText(el,'◉'));
  document.querySelectorAll('.tickerCell').forEach(cell=>{
    const label=(cell.querySelector('b')?.textContent||'').trim().toUpperCase(),icon=cell.querySelector('.assetIcon');
    if(!icon)return;
    const wanted=label==='GOLD'?'●':label==='BTCUSD'?'₿':label==='ETHUSD'?'◆':label==='EURUSD'?'€':label==='USDJPY'?'¥':(label==='GBPUSD'||label==='GBPJPY')?'£':'';
    if(wanted)setText(icon,wanted);
  });
}
function fixKnownLabels(){
  const set=(sel,text)=>setText(document.querySelector(sel),text);
  set('#analyze','NEW ANALYZE');set('#reevaluate','RE-EVALUATE');set('.contextPanel h3','MARKET CONTEXT');set('.confirmationsInside h4','CONFIRMATIONS / WARNINGS');set('.topSetupPanel h3','TOP SETUP');set('.recentPanel h3','RECENT SIGNALS');set('.liveDot','Interactive');
  const footer=document.querySelector('.mhMainCopyright'),footerText='MH ANALYSIS By: Muhammad Hammad Shaukat - © All Rights Reserved 2026';if(footer)setText(footer,footerText);
  fixTickerIcons();
}
function walk(node){
  const w=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let n;
  while((n=w.nextNode())){const next=cleanText(n.nodeValue);if(next!==n.nodeValue)n.nodeValue=next;}
}
let applying=false,queued=false;
function apply(){if(applying)return;applying=true;try{fixKnownLabels();walk(root)}finally{applying=false}}
function queueApply(){if(queued)return;queued=true;setTimeout(()=>{queued=false;apply()},40)}
apply();const observer=new MutationObserver(queueApply);observer.observe(root,{subtree:true,childList:true,characterData:true});
})();
