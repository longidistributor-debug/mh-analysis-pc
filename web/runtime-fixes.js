(()=>{
'use strict';
const $=s=>document.querySelector(s);const $$=s=>[...document.querySelectorAll(s)];

// EA handoff is fire-and-forget. WhatsApp fanout must never wait for MT5/EA.
const mhNativeFetch=window.fetch.bind(window);
window.fetch=function(input,init){
  const url=typeof input==='string'?input:String(input?.url||'');
  if(url==='/api/mt5/ea/send'||url.endsWith('/api/mt5/ea/send')){
    mhNativeFetch(input,init).then(async r=>{if(!r.ok){let detail='';try{detail=await r.text()}catch(_){}console.warn('MT5 EA background handoff failed',r.status,detail)}}).catch(e=>console.warn('MT5 EA background handoff unavailable',e));
    return Promise.resolve(new Response(JSON.stringify({ok:true,queued:true,background:true}),{status:202,headers:{'Content-Type':'application/json'}}));
  }
  return mhNativeFetch(input,init);
};

function ensureLegacyTargets(){if(!$('#mapDiv')){const el=document.createElement('span');el.id='mapDiv';el.hidden=true;document.body.appendChild(el)}}
function activateAnalysisTab(name){$$('#analysisTabs button').forEach(btn=>btn.classList.toggle('activeTab',btn.dataset.tab===name));$$('.tabPane').forEach(p=>p.classList.toggle('activePane',p.dataset.pane===name))}
function installAnalysisTabs(){const tabs=$('#analysisTabs');if(!tabs)return;$$('#analysisTabs button').forEach(btn=>btn.type='button');tabs.addEventListener('click',e=>{const btn=e.target.closest('button[data-tab]');if(btn)activateAnalysisTab(btn.dataset.tab)})}
function cleanAnalysisError(){const el=$('#explanation');if(!el)return;const txt=String(el.textContent||'');const cleaned=txt.replace(/\s*Response:\s*map\[[^\]]*\]\.?\s*$/i,'').trim();if(cleaned!==txt)el.textContent=cleaned}
function watchAnalysisUpdates(){const targets=['#signalCard','#explanation','#topSetups','#buyScoreTop','#sellScoreTop'].map($).filter(Boolean);if(!targets.length)return;let timer=0;const refresh=()=>{clearTimeout(timer);timer=setTimeout(cleanAnalysisError,20)};const observer=new MutationObserver(refresh);targets.forEach(t=>observer.observe(t,{subtree:true,childList:true,characterData:true,attributes:true}));window.__mhRuntimeDetailsObserver=observer;cleanAnalysisError()}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function impactClass(v){const s=String(v||'').trim().toLowerCase();if(s.includes('high'))return'high';if(s==='low')return'low';return'medium'}
function isAllowedImpact(v){const s=String(v||'').trim().toLowerCase();return s==='high'||s==='medium'||s==='med'||s==='low'}
function eventMeta(e){const parts=[];if(e.actual)parts.push(`Act: ${esc(e.actual)}`);if(e.forecast)parts.push(`Fcst: ${esc(e.forecast)}`);if(e.previous)parts.push(`Prev: ${esc(e.previous)}`);return parts.join(' • ')}

let mhCalendarHTML='';
function renderCalendar(data){
  const host=$('#mhEconomicCalendar');if(!host)return false;
  const rawDays=Array.isArray(data?.days)?data.days:[];
  const days=rawDays.map(day=>({...day,events:(Array.isArray(day.events)?day.events:[]).filter(e=>isAllowedImpact(e.impact))})).filter(day=>day.events.length>0).slice(0,3);
  if(!days.length)return false;
  mhCalendarHTML=days.map((day,idx)=>`<section class="mhCalDay" data-day-index="${idx+1}"><div class="mhCalDate"><span>${esc(day.label||day.date)}</span><small>DAY ${idx+1} / ${days.length}</small></div>${day.events.map(e=>`<div class="mhCalEvent"><div class="mhCalTime">${esc(e.time)}</div><div class="mhCalImpact ${impactClass(e.impact)}">${esc(String(e.impact||'Medium').replace(/^med$/i,'Medium'))}</div><div class="mhCalBody"><div class="mhCalTitle">${esc(e.title||'Economic event')}</div><div class="mhCalMeta">${eventMeta(e)}</div></div><div class="mhCalCountry">${esc(e.country)}</div></div>`).join('')}</section>`).join('');
  host.innerHTML=mhCalendarHTML;host.scrollTop=0;return true;
}
async function loadEconomicCalendar(){
  const host=$('#mhEconomicCalendar');if(!host)return;
  try{
    const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),5000);
    const r=await fetch('/api/economic-calendar',{cache:'no-store',signal:ctl.signal});clearTimeout(kill);
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    if(!renderCalendar(data)&&!mhCalendarHTML)host.innerHTML='<div class="mhCalEmpty">Loading economic calendar…</div>';
  }catch(_){
    // Never replace already-rendered calendar with an error page. Keep retrying in background.
    if(mhCalendarHTML)host.innerHTML=mhCalendarHTML;else host.innerHTML='<div class="mhCalEmpty">Loading economic calendar…</div>';
  }
}

const mhTickerLast={};
function setTicker(id,v,digits=5){const el=$(id);const n=Number(v);if(el&&Number.isFinite(n)&&n>0){const text=n.toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});el.textContent=text;mhTickerLast[id]=text}}
function restoreTicker(){for(const [id,text] of Object.entries(mhTickerLast)){const el=$(id);if(el)el.textContent=text}}
async function refreshMovingPrices(){
  restoreTicker();
  try{
    const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),4500);
    const r=await fetch('/api/public-ticker',{cache:'no-store',signal:ctl.signal});clearTimeout(kill);if(!r.ok)return;const d=await r.json();
    setTicker('#tickerGold',d.gold_usd,2);setTicker('#tickerBTC',d.btc_usd,2);setTicker('#tickerETH',d.eth_usd,2);setTicker('#tickerEURUSD',d.eurusd,5);setTicker('#tickerUSDJPY',d.usdjpy,3);setTicker('#tickerGBPUSD',d.gbpusd,5);
    const gbp=Number(d.gbpusd),jpy=Number(d.usdjpy);if(Number.isFinite(gbp)&&Number.isFinite(jpy)&&gbp>0&&jpy>0)setTicker('#tickerGBPJPY',gbp*jpy,3);
  }catch(_){}
}

function installEconomicCalendar(){const crop=$('.calendarCrop');if(!crop)return;crop.innerHTML='<div id="mhEconomicCalendar" class="mhCalendarScroll"><div class="mhCalEmpty">Loading economic calendar…</div></div>';loadEconomicCalendar();setTimeout(loadEconomicCalendar,1000);setTimeout(loadEconomicCalendar,3000);setInterval(loadEconomicCalendar,60*1000)}
function fastOnlineRefresh(){loadEconomicCalendar();refreshMovingPrices();setTimeout(refreshMovingPrices,500);setTimeout(loadEconomicCalendar,900)}
function boot(){ensureLegacyTargets();installAnalysisTabs();watchAnalysisUpdates();installEconomicCalendar();refreshMovingPrices();setTimeout(refreshMovingPrices,350);setTimeout(refreshMovingPrices,1200);setInterval(refreshMovingPrices,15*1000);window.addEventListener('online',fastOnlineRefresh)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
