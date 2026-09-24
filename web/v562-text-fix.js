(()=>{
'use strict';
// V56.2+ text-rendering cleanup. Bismillah area is intentionally untouched.
const root=document.querySelector('.appShell');
if(!root)return;

function cleanText(value){
  let s=String(value??'');
  const replacements=[
    [/\u2014/g,'-'],[/\u2013/g,'-'],[/\u2022/g,' - '],[/\u2026/g,'...'],
    [/\u00e2\u20ac\u201d/g,'-'],[/\u00e2\u20ac\u201c/g,'-'],[/\u00e2\u20ac\u00a2/g,' - '],[/\u00e2\u20ac\u00a6/g,'...'],
    [/\u00e2\u2020\u00bb/g,''],[/\u00e2\u2014\u00b4/g,''],[/\u00e2\u2014\u00b7/g,''],
    [/\u00f0\u0178\u008f\u0086/g,''],
    [/\u00e2\u201a\u00ac/g,'EUR'],[/\u00c2\u00a5/g,'JPY'],[/\u00c2\u00a3/g,'GBP'],[/\u00c2\u00a9/g,'(c)']
  ];
  for(const [re,to] of replacements)s=s.replace(re,to);
  return s;
}

function set(selector,text){const el=document.querySelector(selector);if(el&&el.textContent!==text)el.textContent=text;}
function putIcon(el,text){if(el&&el.textContent!==text)el.textContent=text;}
function restoreIcons(){
  putIcon(document.querySelector('.pair[data-symbol="XAUUSD"] .pairIcon'),'\u25c6');
  putIcon(document.querySelector('.pair[data-symbol="BTCUSDT"] .pairIcon'),'\u20bf');
  const iconMap={GOLD:'\u25c6',BTCUSD:'\u20bf',ETHUSD:'\u25c6',EURUSD:'\u20ac',USDJPY:'\u00a5',GBPUSD:'\u00a3',GBPJPY:'\u00a3'};
  document.querySelectorAll('.tickerCell').forEach(cell=>{
    const code=String(cell.querySelector('b')?.textContent||'').trim().toUpperCase();
    const icon=cell.querySelector('.assetIcon');
    if(iconMap[code])putIcon(icon,iconMap[code]);
  });
  putIcon(document.querySelector('.capTitle .globe'),'\u25ce');
}
function fixKnownLabels(){
  set('#analyze','NEW ANALYZE');
  set('#reevaluate','RE-EVALUATE');
  set('.contextPanel h3','MARKET CONTEXT');
  set('.confirmationsInside h4','CONFIRMATIONS / WARNINGS');
  set('.topSetupPanel h3','TOP SETUP');
  set('.recentPanel h3','RECENT SIGNALS');
  set('.liveDot','Interactive');
  const footer=document.querySelector('.mhMainCopyright');
  if(footer)footer.innerHTML='MH ANALYSIS By: Muhammad Hammad Shaukat - &copy; All Rights Reserved 2026';
  restoreIcons();
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
function apply(){fixKnownLabels();walk(root);}
apply();
new MutationObserver(()=>apply()).observe(root,{subtree:true,childList:true,characterData:true});
})();
