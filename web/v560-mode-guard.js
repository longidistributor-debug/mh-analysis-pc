(()=>{
'use strict';

const $=s=>document.querySelector(s);
let lastFast=null;
let saved=null;
let savedSL=null;
let applying=false;

function isOn(id){
  const b=$(id);return !!b && /\bON\b/i.test(String(b.textContent||''));
}
function clickIf(id,wantOn){
  const b=$(id);if(!b)return;
  if(isOn(id)!==!!wantOn)b.click();
}
function remove20m(){
  const sel=$('#timeframe');
  if(sel){[...sel.options].filter(o=>String(o.value||o.textContent).toLowerCase()==='20m').forEach(o=>o.remove());}
  document.querySelectorAll('[data-chart-tf="20m"]').forEach(x=>x.remove());
}
function forceM1(){
  const sel=$('#timeframe');
  if(sel&&sel.value!=='1m'){
    sel.value='1m';
    sel.dispatchEvent(new Event('change',{bubbles:true}));
  }
  const one=document.querySelector('[data-chart-tf="1m"]');
  if(one&&!one.classList.contains('active'))one.click();
}
function setNormalControlsLocked(locked){
  ['#autoSignalToggle','#lotSizeToggle','#partialTpToggle','#analyze','#reevaluate','#timeframe'].forEach(id=>{
    const el=$(id);if(el)el.disabled=!!locked;
  });
  document.querySelectorAll('.nativeTfButtons button').forEach(b=>b.disabled=!!locked);
}
function saveNormalState(slState){
  if(saved)return;
  saved={auto:isOn('#autoSignalToggle'),lot:isOn('#lotSizeToggle'),partial:isOn('#partialTpToggle')};
  savedSL=!!slState;
}
function pauseNormalMode(slState){
  saveNormalState(slState);
  clickIf('#autoSignalToggle',false);
  clickIf('#lotSizeToggle',false);
  clickIf('#partialTpToggle',false);
  forceM1();
  setNormalControlsLocked(true);
  const st=$('#autoSignalStatus');if(st)st.textContent='Fast Scalping active • normal signal controls paused';
}
async function restoreNormalMode(){
  setNormalControlsLocked(false);
  if(saved){
    clickIf('#lotSizeToggle',saved.lot);
    clickIf('#partialTpToggle',saved.partial);
    clickIf('#autoSignalToggle',saved.auto);
  }
  if(savedSL!==null){
    try{await fetch('/api/mt5/modes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sl_adjustment:!!savedSL})});}catch(_){}
  }
  saved=null;savedSL=null;
}
async function sync(){
  if(applying)return;
  applying=true;
  try{
    remove20m();
    const r=await fetch('/api/mt5/modes',{cache:'no-store'});if(!r.ok)return;
    const j=await r.json();const fast=!!j.fast_scalping;
    if(fast){pauseNormalMode(j.sl_adjustment);}
    else if(lastFast===true){await restoreNormalMode();}
    lastFast=fast;
  }catch(_){
  }finally{applying=false;}
}

function boot(){remove20m();sync();setInterval(sync,800);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
