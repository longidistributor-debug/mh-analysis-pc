(()=>{
'use strict';
const controlIds=['mhSlAdjustment','mhProgressiveV1','mhFastScalping'];
function findTopMt5Tab(){
  const candidates=[...document.querySelectorAll('button,a,[role="button"],.option,.navItem,.tab')];
  return candidates.find(e=>{
    const t=(e.textContent||'').trim();
    if(!/^MH\s*MT5$/i.test(t))return false;
    const r=e.getBoundingClientRect();
    return r.width>0&&r.height>0&&r.top>=0&&r.top<180;
  })||null;
}
function move(){
  const anchor=findTopMt5Tab();if(!anchor)return false;
  const controls=controlIds.map(id=>document.getElementById(id)).filter(Boolean);if(controls.length!==controlIds.length)return false;
  let wrap=document.getElementById('mhV553Mt5Placement');
  if(!wrap){
    wrap=document.createElement('span');
    wrap.id='mhV553Mt5Placement';
    wrap.style.cssText='display:inline-flex;align-items:center;gap:8px;margin-left:8px;vertical-align:middle;white-space:nowrap;flex-wrap:nowrap;position:static;transform:none;';
  }
  anchor.insertAdjacentElement('afterend',wrap);
  controls.forEach(x=>{x.style.position='static';x.style.transform='none';x.style.margin='0';wrap.appendChild(x);});
  return true;
}
let tries=0;const timer=setInterval(()=>{if(move()||++tries>80)clearInterval(timer)},100);
new MutationObserver(()=>move()).observe(document.documentElement,{childList:true,subtree:true});
})();
