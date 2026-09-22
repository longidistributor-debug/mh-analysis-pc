(()=>{
'use strict';
let busy=false,timer=0;
function ensureNotice(){let n=document.getElementById('mhLoginNavNotice');if(n)return n;n=document.createElement('div');n.id='mhLoginNavNotice';n.className='mhLoginNavNotice';const card=document.querySelector('.mhLicenseCard');if(card)card.appendChild(n);return n}
async function poll(){if(busy)return;const overlay=document.getElementById('mhLicenseOverlay');if(!overlay||!overlay.classList.contains('show'))return;busy=true;try{const r=await fetch('/api/license/nav-notice',{cache:'no-store'});if(!r.ok)return;const j=await r.json();if(j.notice&&j.message){const n=ensureNotice();n.textContent=j.message+' Please enter your username and password.';n.classList.add('show');clearTimeout(timer);timer=setTimeout(()=>n.classList.remove('show'),1800)}}catch{}finally{busy=false}}
setInterval(poll,350);

// V.27 SIGNAL FAN-OUT FIX
// app.js owns the analysis model. When it renders a successful NEW ANALYSIS,
// this lightweight bridge fans that exact rendered signal out to the local
// Records store and the MT5 pending-order queue. Re-evaluations never create a
// duplicate record/order.
let bridgeBusy=false;
let bridgeTimer=0;
let lastBridgeToken='';
function txt(id){return (document.getElementById(id)?.textContent||'').trim()}
function num(v){const m=String(v||'').replace(/,/g,'').match(/-?\d+(?:\.\d+)?/);return m?Number(m[0]):NaN}
function currentMarket(symbol,entry){
  const raw=symbol==='BTCUSDT'?txt('tickerBTC'):txt('tickerGold');
  const v=num(raw);
  return Number.isFinite(v)&&v>0?v:entry;
}
function parseSignal(){
  if(txt('analysisStatusHeading')!=='NEW ANALYSIS')return null;
  const badge=txt('signalBadge').toUpperCase();
  const direction=badge.includes('BUY')?'BUY':badge.includes('SELL')?'SELL':'';
  if(!direction)return null;
  const pair=(txt('currentPair')||'').split('•').map(x=>x.trim());
  const symbol=(pair[0]||'').toUpperCase();
  const timeframe=pair[1]||'';
  const entry=num(txt('lvlEntry')),sl=num(txt('lvlSl')),tp1=num(txt('lvlTp1')),tp2=num(txt('lvlTp2'));
  if(!symbol||!timeframe||![entry,sl,tp1,tp2].every(v=>Number.isFinite(v)&&v>0))return null;
  const score=num(txt('signalQuality'));
  const quality=txt('signalQuality');
  const setup=(quality.split('•').slice(1).join('•').trim()||txt('signalHeadline')||'MH Analysis signal').slice(0,240);
  return{symbol,timeframe,direction,entry,sl,tp1,tp2,score:Number.isFinite(score)?score:0,setup,market_price:currentMarket(symbol,entry)};
}
async function postJSON(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let j={};try{j=await r.json()}catch{}
  if(!r.ok)throw new Error(j.error||`${url} HTTP ${r.status}`);
  return j;
}
async function fanOutNewSignal(){
  if(bridgeBusy)return;
  const s=parseSignal();if(!s)return;
  // One renderDecision call causes one heading mutation. Token also blocks any
  // accidental duplicate observer callback from the same render burst.
  const token=[s.symbol,s.timeframe,s.direction,s.entry,s.sl,s.tp1,s.tp2,txt('lastUpdate')].join('|');
  if(token===lastBridgeToken)return;
  lastBridgeToken=token;
  bridgeBusy=true;
  const signalId=`MH${Date.now()}${Math.floor(Math.random()*900+100)}`;
  try{
    await Promise.allSettled([
      postJSON('/api/records-v2/capture',{
        signal_id:signalId,symbol:s.symbol,timeframe:s.timeframe,direction:s.direction,
        entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,score:s.score,setup:s.setup,action:'NEW'
      }),
      postJSON('/api/mt5/prepare',{
        symbol:s.symbol,timeframe:s.timeframe,direction:s.direction,
        entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,market_price:s.market_price,
        score:Math.round(s.score),setup:s.setup
      })
    ]);
  }finally{bridgeBusy=false}
}
function scheduleFanOut(){clearTimeout(bridgeTimer);bridgeTimer=setTimeout(fanOutNewSignal,80)}
function installSignalBridge(){
  const h=document.getElementById('analysisStatusHeading');
  if(!h)return setTimeout(installSignalBridge,250);
  new MutationObserver(scheduleFanOut).observe(h,{childList:true,characterData:true,subtree:true});
}
installSignalBridge();
})();
