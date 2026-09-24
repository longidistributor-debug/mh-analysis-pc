(()=>{'use strict';
let fastOn=false,running=false,callTimes=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const num=id=>{const n=Number((document.getElementById(id)?.textContent||'').replace(/[^0-9.+-]/g,''));return Number.isFinite(n)?n:0};
function dir(){const t=((document.getElementById('signalBadge')?.textContent||'')+' '+(document.getElementById('signalHeadline')?.textContent||'')).toUpperCase();if(/\bBUY\b/.test(t))return'BUY';if(/\bSELL\b/.test(t))return'SELL';return''}
async function readMode(){try{const r=await fetch('/api/mt5/modes',{cache:'no-store'});if(!r.ok)return;const j=await r.json();fastOn=!!j.fast_scalping;if(fastOn&&!running)run()}catch(_){}}
function trimCalls(){const cut=Date.now()-60000;callTimes=callTimes.filter(t=>t>cut)}
async function waitApiSlot(){while(fastOn){trimCalls();if(callTimes.length<3){callTimes.push(Date.now());return true}await sleep(Math.max(100,callTimes[0]+60000-Date.now()))}return false}
async function fresh(){if(!await waitApiSlot())return false;const b=document.getElementById('analyze');if(!b)return false;const before=document.getElementById('lastUpdate')?.textContent||'';b.disabled=false;b.click();b.disabled=true;const end=Date.now()+15000;while(Date.now()<end&&fastOn){await sleep(250);const now=document.getElementById('lastUpdate')?.textContent||'';if(now&&now!=='—'&&now!==before)return true}return false}
async function fastStatus(){try{const r=await fetch('/api/mt5/fast-status',{cache:'no-store'});if(!r.ok)return{exists:false,status:''};const j=await r.json();return{exists:!!j.exists,status:String(j.status||'').toUpperCase()}}catch(_){return{exists:false,status:''}}}
async function send(){const d=dir();if(!d)return null;const symbol=(document.querySelector('.pair.active')?.dataset?.symbol||'XAUUSD').toUpperCase();const entry=num('lvlEntry')||num('btcMarketCap');if(!(entry>0))return null;const baseline=(await fastStatus()).status;const signalId='SCALP'+Date.now();try{const r=await fetch('/api/mt5/fast-send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:'FAST_'+d,entry})});if(!r.ok)return null;return{signalId,baseline}}catch(_){return null}}
function activeStatus(s){return /OPEN|ACTIVE|RUNNING|POSITION/.test(s)&&!/CLOSED|DONE|TP|IDLE/.test(s)}
function closedStatus(s){return /CLOSED|DONE|TP|IDLE/.test(s)}
function errorStatus(s){return /ERROR|REJECT|FAILED/.test(s)}
function stopStatus(s){return /DAILY_LOSS_STOP|DAILY_PROFIT_STOP/.test(s)}
async function waitLifecycle(info){let seenOwnOpen=false;const own=String(info?.signalId||'').toUpperCase();const baseline=String(info?.baseline||'').toUpperCase();while(fastOn){const st=await fastStatus();if(st.exists){const s=st.status;const changed=s!==baseline;const isOwn=own&&s.includes(own);if(isOwn&&activeStatus(s))seenOwnOpen=true;if(isOwn&&errorStatus(s))return'finished';if(stopStatus(s))return'halt';if((seenOwnOpen||changed)&&closedStatus(s))return'finished';}await sleep(200)}return'off'}
async function run(){if(running)return;running=true;try{while(fastOn){if(await fresh()){const info=await send();if(info){const result=await waitLifecycle(info);if(result==='halt'){while(fastOn){await sleep(1000);await readMode()}break}}}if(fastOn)await sleep(50);await readMode()}}finally{running=false}}
setInterval(readMode,1000);readMode();
})();