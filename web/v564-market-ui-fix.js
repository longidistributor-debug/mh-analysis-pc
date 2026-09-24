(()=>{
'use strict';
const $=s=>document.querySelector(s);
let renderSeq=0;
let applying=false;
let syncingContext=false;
const snapshots=new Map();
const timeframeSelect=$('#timeframe');
let stableTimeframe=String(timeframeSelect?.value||'15m');

function activeSymbol(){return String($('.pair.active')?.dataset?.symbol||'XAUUSD').toUpperCase();}
function metricEls(){return ['btcMarketCap','totalMarketCap','btcDominance','btcChange'].map(id=>document.getElementById(id));}
function setLabels(title,a,b,c,d){
  const vals=[['marketDataTitle',title],['metric1Label',a],['metric2Label',b],['metric3Label',c],['metric4Label',d]];
  for(const [id,text] of vals){const el=document.getElementById(id);if(el&&el.textContent!==text)el.textContent=text;}
}
function snapshot(sym=activeSymbol()){
  if(applying)return;
  const els=metricEls();
  if(els.some(Boolean))snapshots.set(sym,{labels:[
    $('#marketDataTitle')?.textContent||'', $('#metric1Label')?.textContent||'', $('#metric2Label')?.textContent||'', $('#metric3Label')?.textContent||'', $('#metric4Label')?.textContent||''
  ],values:els.map(el=>el?.textContent||''),classes:els.map(el=>el?.className||'')});
}
function restore(sym){
  const s=snapshots.get(sym);if(!s)return false;
  applying=true;
  try{
    const ids=['marketDataTitle','metric1Label','metric2Label','metric3Label','metric4Label'];
    ids.forEach((id,i)=>{const el=document.getElementById(id);if(el)el.textContent=s.labels[i]||'';});
    metricEls().forEach((el,i)=>{if(el){el.textContent=s.values[i]||'';el.className=s.classes[i]||'';}});
  }finally{applying=false;}
  return true;
}
function capFmt(v){const n=Number(v);if(!Number.isFinite(n))return'-';if(n>=1e12)return`$${(n/1e12).toFixed(2)}T`;if(n>=1e9)return`$${(n/1e9).toFixed(2)}B`;if(n>=1e6)return`$${(n/1e6).toFixed(2)}M`;return`$${n.toLocaleString(undefined,{maximumFractionDigits:0})}`;}
function money(v,d=2){const n=Number(v);return Number.isFinite(n)?`$${n.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d})}`:'-';}
function setValues(a,b,c,d,changeClass=''){
  applying=true;
  try{
    const vals=[a,b,c,d];metricEls().forEach((el,i)=>{if(el)el.textContent=vals[i];});
    const ch=$('#btcChange');if(ch)ch.className=changeClass;
  }finally{applying=false;}
}
async function renderGold(seq){
  setLabels('GOLD DATA','PRICE','24H HIGH','24H LOW','24H CHANGE');
  const had=restore('XAUUSD');
  if(!had)setValues('-','-','-','-');
  try{
    const r=await fetch('/api/public-ticker',{cache:'no-store'});const j=await r.json();
    if(seq!==renderSeq||activeSymbol()!=='XAUUSD'||!r.ok)return;
    const price=Number(j.gold_usd);
    if(Number.isFinite(price)){
      const els=metricEls();applying=true;try{if(els[0])els[0].textContent=money(price,2);}finally{applying=false;}
    }
    snapshot('XAUUSD');
  }catch(_){}
}
async function renderBTC(seq){
  setLabels('BTC DATA','PRICE','BTC M.CAP','BTC.D','24H CHANGE');
  if(!restore('BTCUSDT'))setValues('-','-','-','-');
  try{
    const [pr,mr]=await Promise.all([
      fetch('/api/public-ticker',{cache:'no-store'}),
      fetch('/api/marketcap',{cache:'no-store'})
    ]);
    const pj=await pr.json(),mj=await mr.json();
    if(seq!==renderSeq||!['BTCUSDT','BTCUSD'].includes(activeSymbol())||!pr.ok)return;
    const price=Number(pj.btc_usd);
    const ch=Number.isFinite(Number(pj.btc_change_24h))?Number(pj.btc_change_24h):Number(mj.btc_change_24h);
    setValues(
      money(price,2),
      mr.ok?capFmt(mj.btc_market_cap):'-',
      mr.ok&&Number.isFinite(Number(mj.btc_dominance))?`${Number(mj.btc_dominance).toFixed(1)}%`:'-',
      Number.isFinite(ch)?`${ch>=0?'+':''}${ch.toFixed(2)}%`:'-',
      Number.isFinite(ch)?(ch>=0?'good':'bad'):''
    );
    snapshot('BTCUSDT');
  }catch(_){
    if(seq===renderSeq&&['BTCUSDT','BTCUSD'].includes(activeSymbol())&&!snapshots.has('BTCUSDT'))setValues('Unavailable','-','-','-');
  }
}
async function renderSelected(){
  const seq=++renderSeq;
  const sym=activeSymbol();
  if(sym==='BTCUSDT'||sym==='BTCUSD')await renderBTC(seq);else await renderGold(seq);
}

// A context switch during an in-flight analysis used to let a GOLD candle result
// finish after BTC was selected (or vice versa). Keep the selected pair/timeframe
// fixed until the current NEW ANALYZE / RE-EVALUATE request has completely ended.
function analysisBusy(){
  const disabled=!!($('#analyze')?.disabled||$('#reevaluate')?.disabled);
  if(!disabled)return false;
  const text=String($('#explanation')?.textContent||'').toLowerCase();
  return text.includes('fetching one fresh candle snapshot')||text.includes('testing the original signal against fresh data');
}
function showContextLocked(){
  const feed=$('#nativeFeedStatus');
  if(feed)feed.textContent='Current analysis is finishing - pair/timeframe kept locked for signal safety';
}
document.addEventListener('click',e=>{
  const target=e.target instanceof Element?e.target:null;
  if(!target)return;
  const contextButton=target.closest('.pair,.nativeTfButtons button');
  if(contextButton&&analysisBusy()){
    e.preventDefault();e.stopImmediatePropagation();showContextLocked();
  }
},true);
if(timeframeSelect){
  timeframeSelect.addEventListener('change',e=>{
    if(analysisBusy()){
      e.preventDefault();e.stopImmediatePropagation();timeframeSelect.value=stableTimeframe;showContextLocked();return;
    }
    stableTimeframe=String(timeframeSelect.value||stableTimeframe);
  },true);
}

// Before every manual NEW ANALYZE / RE-EVALUATE, re-apply the visibly selected
// pair and timeframe to app.js so the request can never use a stale hidden context.
function syncVisibleContext(){
  if(syncingContext||analysisBusy())return;
  syncingContext=true;
  try{
    const pair=$('.pair.active');
    if(pair)pair.click();
    if(timeframeSelect){
      stableTimeframe=String(timeframeSelect.value||stableTimeframe);
      timeframeSelect.dispatchEvent(new Event('change',{bubbles:true}));
      document.querySelectorAll('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',String(b.dataset.chartTf||'')===stableTimeframe));
    }
  }finally{syncingContext=false;}
}
['analyze','reevaluate'].forEach(id=>{
  const btn=document.getElementById(id);
  if(btn)btn.addEventListener('click',()=>{if(!btn.disabled)syncVisibleContext();},true);
});

const cap=$('.capGrid');
if(cap)new MutationObserver(()=>{if(!applying)snapshot();}).observe(cap,{subtree:true,childList:true,characterData:true});
snapshot();
document.querySelectorAll('.pair').forEach(btn=>btn.addEventListener('click',()=>{
  if(analysisBusy())return;
  snapshot();setTimeout(renderSelected,0);
},true));
setInterval(()=>{
  if(!analysisBusy()&&timeframeSelect)stableTimeframe=String(timeframeSelect.value||stableTimeframe);
},300);
})();
