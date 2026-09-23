(()=>{
'use strict';
// MH_EA_REVERSAL_GUARD_V798
// Additive only: does not replace or modify the existing analysis engine.
// The Go bridge remains the hard enforcement point; this layer keeps the UI aware.
let activeState={active:false,direction:'',trades:[]};
let lastBlocked='';
const normSymbol=s=>String(s||'').toUpperCase()==='BTCUSDT'?'BTCUSD':String(s||'').toUpperCase();
const currentSymbol=()=>normSymbol(document.querySelector('.pair.active')?.dataset?.symbol||document.querySelector('#nativeSymbol')?.textContent||'XAUUSD');
function showLock(j){
  const dir=j?.active_direction||activeState.direction||'';
  const req=j?.requested_direction||'';
  const msg=`REVERSAL LOCK: MT5 has active ${dir||'trade/pending'} exposure. ${req?req+' ':''}handoff blocked until the active position/pending order is resolved.`;
  if(msg===lastBlocked)return; lastBlocked=msg;
  const exp=document.querySelector('#explanation'); if(exp){exp.className='detailText bad';exp.textContent=msg}
  const reasons=document.querySelector('#reasons'); if(reasons){const old=String(reasons.textContent||'').trim();reasons.textContent=(old&&old!=='—'?old+'\n':'')+msg}
  const risk=document.querySelector('#riskBanner'); if(risk){risk.textContent=msg;risk.classList.remove('neutralRisk')}
  console.warn('MH EA reversal lock',j||activeState);
}
async function refreshActive(){
  try{
    const s=currentSymbol();
    const r=await window.fetch(`/api/mt5/ea/active?symbol=${encodeURIComponent(s)}`,{cache:'no-store'});
    const j=await r.json(); if(!r.ok)return;
    activeState={active:!!j.active,direction:String(j.direction||''),trades:Array.isArray(j.trades)?j.trades:[]};
    window.MHEAActiveState=activeState;
  }catch(_){ }
}
const nativeFetch=window.fetch.bind(window);
window.fetch=async function(input,init){
  const r=await nativeFetch(input,init);
  try{
    const url=typeof input==='string'?input:String(input?.url||'');
    if(url.includes('/api/mt5/ea/send')&&r.status===409){
      const j=await r.clone().json();
      if(j?.code==='ACTIVE_TRADE_REVERSAL_LOCK'||j?.blocked)showLock(j);
    }
  }catch(_){ }
  return r;
};
window.MHEAReversalGuard={refresh:refreshActive,getState:()=>activeState};
refreshActive(); setInterval(refreshActive,2000);
})();
