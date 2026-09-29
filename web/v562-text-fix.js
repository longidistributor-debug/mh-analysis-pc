(()=>{
'use strict';
// V56.20: wording-only display correction.
// No ticker, moving price bar, scrolling, dynamic values, analysis data, trading, EA, lot-size or SL logic is touched.
function set(selector,text){
  const el=document.querySelector(selector);
  if(el&&el.textContent!==text)el.textContent=text;
}
set('#analyze','NEW ANALYZE');
set('#reevaluate','RE-EVALUATE');
set('.contextPanel h3','MARKET CONTEXT');
set('.confirmationsInside h4','CONFIRMATIONS / WARNINGS');
set('.topSetupPanel h3','TOP SETUP');
set('.recentPanel h3','RECENT SIGNALS');
set('.liveDot','Interactive');
const footer=document.querySelector('.mhMainCopyright');
if(footer)footer.textContent='MH ANALYSIS By: Muhammad Hammad Shaukat - © All Rights Reserved 2026';
})();
