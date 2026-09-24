(()=>{
'use strict';
const controlIds=['mhSlAdjustment','mhFastScalping'];
function findAnchor(){
  for(const id of ['mhMt5','mhMT5','mhMt5Toggle','mhMT5Toggle','openMt5','openMT5','mt5Toggle','mhMt5Options']){const e=document.getElementById(id);if(e)return e;}
  return [...document.querySelectorAll('button,a,[role="button"],.option,.navItem,.tab')].find(e=>/\bMH\s*MT5\b/i.test(e.textContent||''))||null;
}
function move(){
  const anchor=findAnchor();if(!anchor)return false;
  const controls=controlIds.map(id=>document.getElementById(id)).filter(Boolean);if(!controls.length)return false;
  let wrap=document.getElementById('mhV557Mt5Placement');
  if(!wrap){wrap=document.createElement('span');wrap.id='mhV557Mt5Placement';wrap.style.cssText='display:inline-flex;align-items:center;gap:8px;margin-left:8px;vertical-align:middle';}
  anchor.insertAdjacentElement('afterend',wrap);controls.forEach(x=>wrap.appendChild(x));return true;
}
move();new MutationObserver(move).observe(document.documentElement,{childList:true,subtree:true});
})();
