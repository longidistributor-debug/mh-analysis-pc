(()=>{'use strict';
let fastOn=false,running=false,callTimes=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const num=id=>{const n=Number((document.getElementById(id)?.textContent||'').replace(/[^0-9.+-]/g,''));return Number.isFinite(n)?n:0};
function dir(){const t=((document.getElementById('signalBadge')?.textContent||'')+' '+(document.getElementById('signalHeadline')?.textContent||'')).toUpperCase();if(/\bBUY\b/.test(t))return'BUY';if(/\bSELL\b/.test(t))return'SELL';return''}
async function readMode(){try{const r=await fetch('/api/mt5/modes',{cache:'no-store'});if(!r.ok)return;const j=await r.json();fastOn=!!j.fast_scalping;if(fastOn&&!running)run()}catch(_){}}
function trimCalls(){const cut=Date.now()-60000;callTimes=callTimes.filter(t=>t>cut)}
async function waitApiSlot(){while(fastOn){trimCalls();if(callTimes.length<3){callTimes.push(Date.now());return true}await sleep(Math.max(100,callTimes[0]+60000-Date.now()))}return false}
async function fresh(){if(!await waitApiSlot())return false;const b=document.getElementById('analyze');if(!b)return false;const before=document.getElementById('lastUpdate')?.textContent||'';b.disabled=false;b.click();const end=Date.now()+15000;while(Date.now()<end&&fastOn){await sleep(250);const now=document.getElementById('lastUpdate')?.textContent||'';if(now&&now!=='—'&&now!==before)return true}return false}
async function send(){const d=dir();if(!d)return false;const symbol=(document.querySelector('.pair.active')?.dataset?.symbol||'XAUUSD').toUpperCase();const entry=num('lvlEntry')||num('btcMarketCap');if(!(entry>0))return false;try{const r=await fetch('/api/mt5/fast-send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:'SCALP'+Date.now(),symbol,type:'FAST_'+d,entry})});return r.ok}catch(_){return false}}
async function fastStatus(){try{const r=await fetch('/api/mt5/fast-status',{cache:'no-store'});if(!r.ok)return{exists:false,status:''};const j=await r.json();return{exists:!!j.exists,status:String(j.status||'').toUpperCase()}}catch(_){return{exists:false,status:''}}}
function activeStatus(s){return /OPEN|ACTIVE|RUNNING|POSITION/.test(s)&&!/CLOSED|DONE|TP|IDLE/.test(s)}
function closedStatus(s){return /CLOSED|DONE|TP|IDLE/.test(s)}
async function waitUntilClosed(){let seenOpen=false;while(fastOn){const st=await fastStatus();if(st.exists&&activeStatus(st.status))seenOpen=true;if(seenOpen&&closedStatus(st.status))return true;await sleep(250)}return false}
async function run(){if(running)return;running=true;try{while(fastOn){if(await fresh()){if(await send())await waitUntilClosed()}if(fastOn)await sleep(50);await readMode()}}finally{running=false}}
setInterval(readMode,1000);readMode();
})();