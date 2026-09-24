(()=>{
'use strict';
const $=s=>document.querySelector(s);
let renderSeq=0;
let applying=false;
const snapshots=new Map();

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
  setLabels('CRYPTO DATA','BTC M.CAP','TOTAL CRYPTO','BTC.D','BTC 24H');
  if(!restore('BTCUSDT'))setValues('-','-','-','-');
  try{
    const r=await fetch('/api/marketcap',{cache:'no-store'});const j=await r.json();
    if(seq!==renderSeq||activeSymbol()!=='BTCUSDT'||!r.ok)return;
    const ch=Number(j.btc_change_24h);
    setValues(
      capFmt(j.btc_market_cap),
      capFmt(j.total_market_cap),
      Number.isFinite(Number(j.btc_dominance))?`${Number(j.btc_dominance).toFixed(1)}%`:'-',
      Number.isFinite(ch)?`${ch>=0?'+':''}${ch.toFixed(2)}%`:'-',
      Number.isFinite(ch)?(ch>=0?'good':'bad'):''
    );
    snapshot('BTCUSDT');
  }catch(_){
    if(seq===renderSeq&&activeSymbol()==='BTCUSDT'&&!snapshots.has('BTCUSDT'))setValues('Unavailable','-','-','-');
  }
}
async function renderSelected(){
  const seq=++renderSeq;
  const sym=activeSymbol();
  if(sym==='BTCUSDT'||sym==='BTCUSD')await renderBTC(seq);else await renderGold(seq);
}

const cap=$('.capGrid');
if(cap)new MutationObserver(()=>{if(!applying)snapshot();}).observe(cap,{subtree:true,childList:true,characterData:true});
snapshot();
document.querySelectorAll('.pair').forEach(btn=>btn.addEventListener('click',()=>{snapshot();setTimeout(renderSelected,0);},true));
})();
