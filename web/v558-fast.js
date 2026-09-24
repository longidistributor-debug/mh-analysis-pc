(()=>{'use strict';
let fastOn=false,running=false,lastCycle=-1;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const num=id=>{const n=Number((document.getElementById(id)?.textContent||'').replace(/[^0-9.+-]/g,''));return Number.isFinite(n)?n:0};
function dir(){const t=((document.getElementById('signalBadge')?.textContent||'')+' '+(document.getElementById('signalHeadline')?.textContent||'')).toUpperCase();if(/\\bBUY\\b/.test(t))return'BUY';if(/\\bSELL\\b/.test(t))return'SELL';return''}
async function readMode(){try{const r=await fetch('/api/mt5/modes',{cache:'no-store'});if(!r.ok)return;const j=await r.json();fastOn=!!j.fast_scalping;if(fastOn&&!running)run()}catch(_){}}
async function fresh(){const b=document.getElementById('analyze');if(!b)return false;const before=document.getElementById('lastUpdate')?.textContent||'';b.click();const end=Date.now()+15000;while(Date.now()<end&&fastOn){await sleep(250);const now=document.getElementById('lastUpdate')?.textContent||'';if(now&&now!=='—'&&now!==before)return true}return false}
async function send(){const d=dir();if(!d)return false;const symbol=(document.querySelector('.pair.active')?.dataset?.symbol||'XAUUSD').toUpperCase();const entry=num('lvlEntry')||num('btcMarketCap');if(!(entry>0))return false;try{const r=await fetch('/api/mt5/fast-send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:'SCALP'+Date.now(),symbol,type:'FAST_'+d,entry})});return r.ok}catch(_){return false}}
async function run(){if(running)return;running=true;try{while(fastOn){const now=new Date(),cycle=Math.floor(now.getTime()/900000);if(cycle!==lastCycle){lastCycle=cycle;if(await fresh())await send()}await sleep(1000);await readMode()}}finally{running=false}}
setInterval(readMode,1200);readMode();
})();