(async()=>{
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
let symbol='XAUUSD', timeframe='15m', busy=false;
let chartDecision=null;
let lwChart=null, candleSeries=null, volumeSeries=null, chartResizeObserver=null, markerPlugin=null;
let signalPriceLines=[];
let publicGoldPrice=null;
let autoSignalEnabled=false, autoSignalTimer=null, autoCountdownTimer=null, autoSignalNextAt=0, autoSignalRunning=false, autoSignalNextAction='NEW';
let autoActionStartedAt=0;
const AUTO_REEVAL_DELAY=5*60*1000;
const AUTO_NEW_AFTER_REEVAL_DELAY=10*60*1000;
const AUTO_RETRY_NO_SIGNAL_DELAY=5*60*1000;
const STORAGE_AUTO='mhAutoSignalEnabledV796';
const STORAGE_LOT_SIZE='mhLotSizeEnabledV551';
const STORAGE_PARTIAL_TP='mhPartialTpEnabledV551';
let lotSizeEnabled=localStorage.getItem(STORAGE_LOT_SIZE)==='1';
let partialTpEnabled=localStorage.getItem(STORAGE_PARTIAL_TP)==='1';
let backendSettings={has_api_key:false,whatsapp_link:'',has_whatsapp:false};
const candleCache=new Map();
const fetchInFlight=new Map();
const active = new Map();
const activeStorageKey=k=>`mh-active-signal-v797:${k}`;
function persistActiveSignal(k,obj){try{if(obj?.signal)localStorage.setItem(activeStorageKey(k),JSON.stringify({signal:obj.signal,state:obj.state||'PENDING'}));else localStorage.removeItem(activeStorageKey(k))}catch(e){}}
function restoreActiveSignal(k){if(active.has(k))return active.get(k);try{const raw=localStorage.getItem(activeStorageKey(k));if(!raw)return null;const x=JSON.parse(raw);if(x?.signal){const obj={signal:x.signal,state:x.state||'PENDING',candles:[]};active.set(k,obj);return obj}}catch(e){}return null}
const lastDecision = new Map();
const keyFor=()=>`${symbol}|${timeframe}`;
const cacheStorageKey=k=>`mh-lightweight-candles:${k}`;
function normalizeCandle(x){const c={t:Number(x?.t),o:Number(x?.o),h:Number(x?.h),l:Number(x?.l),c:Number(x?.c),v:Number(x?.v||0)};return Number.isFinite(c.t)&&Number.isFinite(c.o)&&Number.isFinite(c.h)&&Number.isFinite(c.l)&&Number.isFinite(c.c)?c:null}
function persistCandles(k,arr){try{localStorage.setItem(cacheStorageKey(k),JSON.stringify((arr||[]).slice(-300)))}catch(e){}}
function restoreCandles(k){try{const raw=localStorage.getItem(cacheStorageKey(k));if(!raw)return[];const arr=(JSON.parse(raw)||[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.t-b.t).slice(-300);if(arr.length)candleCache.set(k,arr);return arr}catch(e){return[]}}
function mergeCandles(base,extra){const byT=new Map();for(const x of [...(base||[]),...(extra||[])]){const c=normalizeCandle(x);if(c)byT.set(c.t,c)}return [...byT.values()].sort((a,b)=>a.t-b.t).slice(-300)}

function fmt(v){ if(v==null||!Number.isFinite(v)) return '-'; return Math.abs(v)>=100 ? v.toFixed(2) : v.toFixed(5); }
function avg(a){return a.length?a.reduce((x,y)=>x+y,0)/a.length:0}
function median(a){const s=a.filter(Number.isFinite).slice().sort((x,y)=>x-y);if(!s.length)return 0;const m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2}
function quantile(a,q=.5){const s=a.filter(Number.isFinite).slice().sort((x,y)=>x-y);if(!s.length)return 0;q=Math.max(0,Math.min(1,q));const pos=(s.length-1)*q,lo=Math.floor(pos),hi=Math.ceil(pos);return lo===hi?s[lo]:s[lo]+(s[hi]-s[lo])*(pos-lo)}
function rank01(x,a){const v=a.filter(Number.isFinite);if(!v.length)return .5;return Math.max(0,Math.min(1,v.filter(y=>y<=x).length/v.length))}
function ema(v,p){if(!v.length)return[];p=Math.max(1,Math.min(p,v.length));const k=2/(p+1),o=[v[0]];for(let i=1;i<v.length;i++)o.push(v[i]*k+o[i-1]*(1-k));return o}
function sma(v,p){p=Math.max(1,Math.min(p,v.length));return avg(v.slice(-p))}
function rsi(v,p=14){if(v.length<2)return 50;p=Math.max(1,Math.min(p,v.length-1));let g=0,l=0;for(let i=v.length-p;i<v.length;i++){const d=v[i]-v[i-1];if(d>0)g+=d;else l-=d}if(l<1e-12)return 100;const rs=g/l;return 100-100/(1+rs)}
function trueRanges(c){if(!c.length)return[];const o=[c[0].h-c[0].l];for(let i=1;i<c.length;i++){const x=c[i],p=c[i-1].c;o.push(Math.max(x.h-x.l,Math.abs(x.h-p),Math.abs(x.l-p)))}return o}
function atr(c,p=14){return avg(trueRanges(c).slice(-Math.min(p,c.length)))}
function pivots(c,high,span){const out=[];if(c.length<span*2+3)return out;for(let i=span;i<c.length-span;i++){const p=high?c[i].h:c[i].l;let ok=true;for(let j=i-span;j<=i+span;j++){if(j===i)continue;const q=high?c[j].h:c[j].l;if(high?q>p:q<p){ok=false;break}}if(ok)out.push({index:i,price:p})}return out}
function adaptiveSpan(n){return Math.max(2,Math.min(10,Math.round(Math.sqrt(Math.max(16,n))/2)))}
function zoneMid(lo,hi){return lo==null||hi==null?null:(lo+hi)/2}
function distZone(p,lo,hi){return p<lo?lo-p:p>hi?p-hi:0}
function smooth(x){return Math.max(0,Math.min(99,x))}
function two(x){return Number(x).toFixed(2)}

function calcDMI(c,p=14){if(c.length<p+2)return{adx:0,plus:50,minus:50};let trs=[],plusDM=[],minusDM=[];for(let i=1;i<c.length;i++){const up=c[i].h-c[i-1].h,dn=c[i-1].l-c[i].l;plusDM.push(up>dn&&up>0?up:0);minusDM.push(dn>up&&dn>0?dn:0);trs.push(Math.max(c[i].h-c[i].l,Math.abs(c[i].h-c[i-1].c),Math.abs(c[i].l-c[i-1].c)))}
 const dx=[];for(let i=p-1;i<trs.length;i++){const tr=avg(trs.slice(i-p+1,i+1))||1e-9;const pl=100*avg(plusDM.slice(i-p+1,i+1))/tr;const mi=100*avg(minusDM.slice(i-p+1,i+1))/tr;dx.push(100*Math.abs(pl-mi)/Math.max(pl+mi,1e-9))}const i=trs.length-1,tr=avg(trs.slice(-p))||1e-9;return{adx:avg(dx.slice(-p)),plus:100*avg(plusDM.slice(-p))/tr,minus:100*avg(minusDM.slice(-p))/tr}}
function recentFvg(c){let out=null;for(let i=Math.max(2,c.length-40);i<c.length;i++){if(c[i].l>c[i-2].h)out={type:'BULLISH',low:c[i-2].h,high:c[i].l,created:i};if(c[i].h<c[i-2].l)out={type:'BEARISH',low:c[i].h,high:c[i-2].l,created:i}}if(!out)return null;let fill=0;const w=out.high-out.low;if(w<=0)return null;for(let i=out.created+1;i<c.length;i++){if(out.type==='BULLISH'){fill=Math.max(fill,(out.high-c[i].l)/w)}else fill=Math.max(fill,(c[i].h-out.low)/w)}return{...out,fillPct:Math.max(0,Math.min(100,Math.round(fill*100)))}}
function orderBlock(c,bull){const trMed=median(trueRanges(c).slice(-120))||1e-9;const bodies=c.map(x=>Math.abs(x.c-x.o)/trMed);const cut=bodies.slice().sort((a,b)=>a-b)[Math.floor(bodies.length*.7)]||.5;for(let i=c.length-5;i>=Math.max(2,c.length-80);i--){const x=c[i],opp=bull?x.c<x.o:x.c>x.o;if(!opp)continue;const after=c.slice(i+1,Math.min(c.length,i+4));const displaced=after.some(y=>Math.abs(y.c-y.o)/trMed>=cut&&(bull?y.c>x.h:y.c<x.l));if(!displaced)continue;return bull?{low:x.l,high:Math.max(x.o,x.c)}:{low:Math.min(x.o,x.c),high:x.h}}return null}
function divergence(c){if(c.length<40)return null;const span=adaptiveSpan(c.length),lows=pivots(c,false,span),highs=pivots(c,true,span),closes=c.map(x=>x.c);if(lows.length>=2){const a=lows[lows.length-2],b=lows[lows.length-1];const r1=rsi(closes.slice(0,a.index+1),14),r2=rsi(closes.slice(0,b.index+1),14);if(b.price<a.price&&r2>r1)return'Bullish RSI divergence'}if(highs.length>=2){const a=highs[highs.length-2],b=highs[highs.length-1];const r1=rsi(closes.slice(0,a.index+1),14),r2=rsi(closes.slice(0,b.index+1),14);if(b.price>a.price&&r2<r1)return'Bearish RSI divergence'}return null}
function equalLevel(c,high){const ps=pivots(c,high,adaptiveSpan(c.length)),tr=median(trueRanges(c).slice(-120))||1e-9;if(ps.length<2)return null;for(let i=ps.length-1;i>0;i--){for(let j=i-1;j>=Math.max(0,i-5);j--){if(Math.abs(ps[i].price-ps[j].price)<=tr*.18)return(ps[i].price+ps[j].price)/2}}return null}
function calcAdaptiveVwap(c){const w=c.slice(-Math.min(120,c.length));if(!w.length)return null;let vSum=0,pv=0;for(const x of w){const v=Math.max(0,Number(x.v)||0),typ=(x.h+x.l+x.c)/3;vSum+=v;pv+=typ*v}if(vSum>0)return pv/vSum;/* Some commodity/FX history feeds omit volume. Use a stable typical-price fallback instead of showing a broken dash. */return avg(w.map(x=>(x.h+x.l+x.c)/3))}
function marketMap(c){const d=calcDMI(c),fvg=recentFvg(c),bullOb=orderBlock(c,true),bearOb=orderBlock(c,false),eqh=equalLevel(c,true),eql=equalLevel(c,false),div=divergence(c);return{adx:d.adx,plusDi:d.plus,minusDi:d.minus,vwap:calcAdaptiveVwap(c),fvgType:fvg?.type||null,fvgLow:fvg?.low??null,fvgHigh:fvg?.high??null,fvgFillPct:fvg?.fillPct||0,bullObLow:bullOb?.low??null,bullObHigh:bullOb?.high??null,bearObLow:bearOb?.low??null,bearObHigh:bearOb?.high??null,equalHigh:eqh,equalLow:eql,divergence:div}}

function stats(c){const trs=trueRanges(c),med=Math.max(median(trs),1e-9),mad=Math.max(median(trs.map(x=>Math.abs(x-med))),1e-9);const ranges=c.map(x=>Math.max(x.h-x.l,1e-9)),bodies=c.map(x=>Math.abs(x.c-x.o));const bodyRank=Math.round(rank01(bodies.at(-1),bodies)*100),rangeRank=Math.round(rank01(ranges.at(-1),ranges)*100);const pressure=[];for(let i=1;i<c.length;i++)pressure.push((c[i].c-c[i-1].c)/med);const pMed=median(pressure),pMad=median(pressure.map(x=>Math.abs(x-pMed)));const uncertainty=Math.max(.35,pMad*100/Math.sqrt(Math.max(1,pressure.length)));const root=Math.round(Math.sqrt(c.length)),fast=Math.max(8,Math.min(Math.max(8,Math.floor(c.length/4)),root)),slow=Math.max(fast+2,Math.min(Math.max(fast+2,Math.floor(c.length/2)),root*2+Math.round(mad/med)));return{trMedian:med,trMad:mad,bodyRank,rangeRank,pressureUncertainty:uncertainty,fastWindow:fast,slowWindow:slow}}
function timeframeRiskProfile(tf,s){
  const profiles={
    '1m': {riskMin:.55,riskMax:1.35,tp1Min:.90,tp1Max:2.20,tp2Min:1.40,tp2Max:3.20},
    '5m': {riskMin:.60,riskMax:1.50,tp1Min:1.00,tp1Max:2.50,tp2Min:1.60,tp2Max:3.60},
    '15m':{riskMin:.70,riskMax:1.70,tp1Min:1.10,tp1Max:2.80,tp2Min:1.80,tp2Max:4.00},
    '20m':{riskMin:.72,riskMax:1.80,tp1Min:1.15,tp1Max:3.00,tp2Min:1.90,tp2Max:4.20},
    '30m':{riskMin:.75,riskMax:1.90,tp1Min:1.20,tp1Max:3.20,tp2Min:2.00,tp2Max:4.50},
    '1h': {riskMin:.80,riskMax:2.10,tp1Min:1.25,tp1Max:3.50,tp2Min:2.10,tp2Max:5.00}
  };
  const p=profiles[String(tf||'').toLowerCase()]||profiles['15m'],tr=Math.max(Number(s?.trMedian)||0,1e-9);
  return{...p,tr,riskFloor:tr*p.riskMin,riskCap:tr*p.riskMax,tp1Floor:tr*p.tp1Min,tp1Cap:tr*p.tp1Max,tp2Floor:tr*p.tp2Min,tp2Cap:tr*p.tp2Max};
}
function clampDistance(v,lo,hi){return Math.min(Math.max(Number(v)||0,Math.max(Number(lo)||0,1e-9)),Math.max(Number(hi)||0,Math.max(Number(lo)||0,1e-9)))}
function chooseObjectiveBounded(entry,objs,desired,dir,minDist,maxDist){
  const valid=[...new Set(objs.filter(Number.isFinite))].filter(x=>{
    const dist=Math.abs(x-entry);
    return (dir==='BUY'?x>entry+minDist:x<entry-minDist)&&dist<=maxDist;
  });
  if(!valid.length)return null;
  return valid.sort((a,b)=>Math.abs(Math.abs(a-entry)-desired)-Math.abs(Math.abs(b-entry)-desired))[0];
}
function fam(direction,name,score,reasons){return{direction,name,score:smooth(score),reasons}}
function trendFamilies(c,m,s){const close=c.map(x=>x.c),fast=ema(close,s.fastWindow).at(-1),slow=ema(close,s.slowWindow).at(-1),cut=Math.min(s.fastWindow,Math.max(2,Math.floor(s.fastWindow/3))),prevFast=ema(close.slice(0,-cut),s.fastWindow).at(-1)??fast;const trend=Math.max(-4,Math.min(4,(fast-slow)/s.trMedian)),slope=Math.max(-4,Math.min(4,(fast-prevFast)/s.trMedian)),den=Math.max(m.plusDi+m.minusDi,1e-9),dmi=Math.max(-1,Math.min(1,(m.plusDi-m.minusDi)/den));return[fam('BUY','Trend / pullback continuation',50+trend*9+slope*6+dmi*22,[`Adaptive fast-vs-slow strength ${two(trend)}`,`DMI balance ${(dmi*100).toFixed(1)}`]),fam('SELL','Trend / pullback continuation',50-trend*9-slope*6-dmi*22,[`Adaptive fast-vs-slow strength ${two(-trend)}`,`DMI balance ${(-dmi*100).toFixed(1)}`])];}
function structureFamilies(c,m,s){const sp=adaptiveSpan(c.length),hs=pivots(c,true,sp),ls=pivots(c,false,sp),h=hs.at(-1)?.price,l=ls.at(-1)?.price,last=c.at(-1);const pos=h!=null&&l!=null&&h>l?Math.max(0,Math.min(1,(last.c-l)/(h-l))):.5,up=h!=null?Math.max(0,last.c-h)/s.trMedian:0,dn=l!=null?Math.max(0,l-last.c)/s.trMedian:0;return[fam('BUY','Adaptive market structure',35+pos*38+up*18-dn*22,[`Swing position ${Math.round(pos*100)}%`,`Same-timeframe adaptive pivots`]),fam('SELL','Adaptive market structure',35+(1-pos)*38+dn*18-up*22,[`Bearish swing position ${Math.round((1-pos)*100)}%`,`Same-timeframe adaptive pivots`])];}
function liquidityFamilies(c,m,s){const sp=adaptiveSpan(c.length),hs=pivots(c,true,sp),ls=pivots(c,false,sp),last=c.at(-1),low=ls.filter(x=>x.price<=last.c).sort((a,b)=>b.price-a.price)[0]?.price,high=hs.filter(x=>x.price>=last.c).sort((a,b)=>a.price-b.price)[0]?.price,lower=Math.min(last.o,last.c)-last.l,upper=last.h-Math.max(last.o,last.c),bull=low!=null&&last.l<low&&last.c>low?rank01(lower,c.map(x=>Math.max(0,Math.min(x.o,x.c)-x.l))):0,bear=high!=null&&last.h>high&&last.c<high?rank01(upper,c.map(x=>Math.max(0,x.h-Math.max(x.o,x.c)))):0,bObj=m.equalHigh&&m.equalHigh>last.c?1:high!=null?.65:.35,sObj=m.equalLow&&m.equalLow<last.c?1:low!=null?.65:.35;return[fam('BUY','Liquidity sweep / rotation',42+bull*45+bObj*13,[`Sell-side reclaim rank ${Math.round(bull*100)}`,`Opposing liquidity quality ${Math.round(bObj*100)}`]),fam('SELL','Liquidity sweep / rotation',42+bear*45+sObj*13,[`Buy-side rejection rank ${Math.round(bear*100)}`,`Opposing liquidity quality ${Math.round(sObj*100)}`])];}
function breakoutFamilies(c,m,s){const sp=adaptiveSpan(c.length),base=c.slice(0,-1),h=pivots(base,true,sp).at(-1)?.price,l=pivots(base,false,sp).at(-1)?.price,last=c.at(-1),body=Math.abs(last.c-last.o),bs=rank01(body,c.map(x=>Math.abs(x.c-x.o))),rs=rank01(last.h-last.l,c.map(x=>x.h-x.l)),up=h!=null?Math.max(0,last.c-h)/s.trMedian:0,dn=l!=null?Math.max(0,l-last.c)/s.trMedian:0,cl=(last.c-last.l)/Math.max(last.h-last.l,1e-9);return[fam('BUY','Breakout / acceptance',35+bs*25+rs*15+cl*12+up*18,[`Body percentile ${Math.round(bs*100)}`,`Close acceptance ${Math.round(cl*100)}%`]),fam('SELL','Breakout / acceptance',35+bs*25+rs*15+(1-cl)*12+dn*18,[`Body percentile ${Math.round(bs*100)}`,`Bearish close acceptance ${Math.round((1-cl)*100)}%`])];}
function reversalFamilies(c,m,s){const last=c.at(-1),range=Math.max(last.h-last.l,1e-9),lower=(Math.min(last.o,last.c)-last.l)/range,upper=(last.h-Math.max(last.o,last.c))/range,lr=rank01(lower,c.map(x=>(Math.min(x.o,x.c)-x.l)/Math.max(x.h-x.l,1e-9))),ur=rank01(upper,c.map(x=>(x.h-Math.max(x.o,x.c))/Math.max(x.h-x.l,1e-9))),db=m.divergence?.toLowerCase().includes('bull')?1:0,ds=m.divergence?.toLowerCase().includes('bear')?1:0;return[fam('BUY','Reversal / rejection',38+lr*42+db*20,[`Lower-wick rejection rank ${Math.round(lr*100)}`,m.divergence||'No RSI divergence required']),fam('SELL','Reversal / rejection',38+ur*42+ds*20,[`Upper-wick rejection rank ${Math.round(ur*100)}`,m.divergence||'No RSI divergence required'])];}
function zoneFamilies(c,m,s){const p=c.at(-1).c,distSamples=c.slice(-120).map(x=>Math.abs(x.c-p));const zs=(lo,hi)=>lo==null||hi==null?44:smooth(82-rank01(distZone(p,lo,hi),distSamples)*38),bo=zs(m.bullObLow,m.bullObHigh),be=zs(m.bearObLow,m.bearObHigh),bf=m.fvgType==='BULLISH'?45+(100-m.fvgFillPct)*.45:42,sf=m.fvgType==='BEARISH'?45+(100-m.fvgFillPct)*.45:42;return[fam('BUY','Order block / FVG reaction',(bo+bf)/2,[`Bull OB proximity ${Math.round(bo)}`,`Bull FVG quality ${Math.round(bf)}`]),fam('SELL','Order block / FVG reaction',(be+sf)/2,[`Bear OB proximity ${Math.round(be)}`,`Bear FVG quality ${Math.round(sf)}`])];}
function momentumFamilies(c,m,s){const rets=[];for(let i=1;i<c.length;i++)rets.push((c[i].c-c[i-1].c)/Math.max(s.trMedian,1e-9));const sh=avg(rets.slice(-Math.min(s.fastWindow,rets.length))),rank=rank01(sh,rets)*2-1,last=c.at(-1),cl=(last.c-last.l)/Math.max(last.h-last.l,1e-9);return[fam('BUY','Momentum / candle pressure',50+rank*32+(cl-.5)*26,[`Relative return pressure ${(rank*100).toFixed(1)}`,`Body percentile ${s.bodyRank}; range ${s.rangeRank}`]),fam('SELL','Momentum / candle pressure',50-rank*32+(.5-cl)*26,[`Relative return pressure ${(-rank*100).toFixed(1)}`,`Body percentile ${s.bodyRank}; range ${s.rangeRank}`])];}

function projectedTrendline(c,dir,s){const sp=Math.max(2,adaptiveSpan(c.length)-1),ps=pivots(c,dir==='SELL',sp);if(ps.length<2)return null;for(let j=ps.length-1;j>0;j--){const p2=ps[j],p1=ps.slice(0,j).reverse().find(x=>p2.index-x.index>=4);if(!p1)continue;const slope=(p2.price-p1.price)/(p2.index-p1.index),ordered=dir==='SELL'?p2.price<p1.price:p2.price>p1.price;if(!ordered)continue;return p2.price+slope*((c.length-1)-p2.index)}return null}
function videoFamilies(c,m,s){const last=c.at(-1),range=Math.max(last.h-last.l,1e-9),body=Math.abs(last.c-last.o),lowW=Math.min(last.o,last.c)-last.l,upW=last.h-Math.max(last.o,last.c),close=c.map(x=>x.c),e20=ema(close,20).at(-1),e50=ema(close,50).at(-1),mac=ema(close,12).at(-1)-ema(close,26).at(-1),macPrev=ema(close.slice(0,-1),12).at(-1)-ema(close.slice(0,-1),26).at(-1),rr=rsi(close,14),bullMom=(e20>=e50&&mac>=macPrev&&rr>=48)||last.c>last.o,bearMom=(e20<=e50&&mac<=macPrev&&rr<=52)||last.c<last.o;const out=[];
 const btl=projectedTrendline(c,'BUY',s),stl=projectedTrendline(c,'SELL',s);if(btl!=null){const d=Math.abs(last.l-btl)/s.trMedian;out.push(fam('BUY','Video: trendline third-touch / retest',75-35*Math.min(1,d),[`Projected support distance ${two(d)} median range`]))}if(stl!=null){const d=Math.abs(last.h-stl)/s.trMedian;out.push(fam('SELL','Video: trendline third-touch / retest',75-35*Math.min(1,d),[`Projected resistance distance ${two(d)} median range`]))}
 const lowRank=rank01(lowW,c.map(x=>Math.max(0,Math.min(x.o,x.c)-x.l))),upRank=rank01(upW,c.map(x=>Math.max(0,x.h-Math.max(x.o,x.c))));out.push(fam('BUY','Video: dominant wick reclaim',40+lowRank*45+(bullMom?10:0),[`Lower-wick relative rank ${Math.round(lowRank*100)}`]));out.push(fam('SELL','Video: dominant wick reclaim',40+upRank*45+(bearMom?10:0),[`Upper-wick relative rank ${Math.round(upRank*100)}`]));
 const recent=c.slice(-18,-1),hi=Math.max(...recent.map(x=>x.h)),lo=Math.min(...recent.map(x=>x.l)),span=(hi-lo)/s.trMedian;const compress=Math.max(0,1-Math.abs(span-2)/3);out.push(fam('BUY','Video: compression sweep / reclaim',42+compress*18+(last.l<lo&&last.c>lo?35:0),[`Compression quality ${Math.round(compress*100)}`]));out.push(fam('SELL','Video: compression sweep / rejection',42+compress*18+(last.h>hi&&last.c<hi?35:0),[`Compression quality ${Math.round(compress*100)}`]));
 return out;}

function aggregate(fs){if(!fs.length)return[50,[]];const r=fs.slice().sort((a,b)=>b.score-a.score),top=r.slice(0,5),weights=top.map((_,i)=>top.length-i),score=top.reduce((s,x,i)=>s+x.score*weights[i],0)/weights.reduce((a,b)=>a+b,0);return[score,r]}

function smcIctFamilies(c,m,s){
  const sp=adaptiveSpan(c.length),hs=pivots(c,true,sp),ls=pivots(c,false,sp),last=c.at(-1),prev=c.at(-2)||last;
  const h1=hs.at(-1)?.price,h2=hs.at(-2)?.price,l1=ls.at(-1)?.price,l2=ls.at(-2)?.price;
  const bullBos=h1!=null?Math.max(0,(last.c-h1)/s.trMedian):0,bearBos=l1!=null?Math.max(0,(l1-last.c)/s.trMedian):0;
  const priorBear=h1!=null&&h2!=null&&l1!=null&&l2!=null&&h1<h2&&l1<l2;
  const priorBull=h1!=null&&h2!=null&&l1!=null&&l2!=null&&h1>h2&&l1>l2;
  const chochBull=priorBear&&h1!=null&&last.c>h1?1:0,chochBear=priorBull&&l1!=null&&last.c<l1?1:0;
  const rangeHi=h1??Math.max(...c.slice(-Math.min(80,c.length)).map(x=>x.h)),rangeLo=l1??Math.min(...c.slice(-Math.min(80,c.length)).map(x=>x.l));
  const pos=rangeHi>rangeLo?Math.max(0,Math.min(1,(last.c-rangeLo)/(rangeHi-rangeLo))):.5;
  const disp=rank01(Math.abs(last.c-last.o),c.map(x=>Math.abs(x.c-x.o))),rng=rank01(last.h-last.l,c.map(x=>x.h-x.l));
  const bullRaid=l1!=null&&last.l<l1&&last.c>l1?1:0,bearRaid=h1!=null&&last.h>h1&&last.c<h1?1:0;
  const bullPd=(1-pos),bearPd=pos;
  const bullArray=(m.bullObLow!=null?1:0)+(m.fvgType==='BULLISH'&&m.fvgFillPct<100?1:0);
  const bearArray=(m.bearObLow!=null?1:0)+(m.fvgType==='BEARISH'&&m.fvgFillPct<100?1:0);
  return[
    fam('BUY','SMC: BOS / CHoCH structure',42+Math.min(2,bullBos)*16+chochBull*18+bullPd*14,[`BOS pressure ${two(bullBos)} median range`,chochBull?'Bullish CHoCH detected':`Dealing-range discount ${Math.round(bullPd*100)}%`]),
    fam('SELL','SMC: BOS / CHoCH structure',42+Math.min(2,bearBos)*16+chochBear*18+bearPd*14,[`BOS pressure ${two(bearBos)} median range`,chochBear?'Bearish CHoCH detected':`Dealing-range premium ${Math.round(bearPd*100)}%`]),
    fam('BUY','ICT: liquidity raid / displacement / PD array',38+bullRaid*24+disp*13+rng*8+bullPd*9+bullArray*4,[bullRaid?'Sell-side liquidity raid reclaimed':'Liquidity raid not required',`Displacement ${Math.round(disp*100)} • bullish PD arrays ${bullArray}`]),
    fam('SELL','ICT: liquidity raid / displacement / PD array',38+bearRaid*24+disp*13+rng*8+bearPd*9+bearArray*4,[bearRaid?'Buy-side liquidity raid rejected':'Liquidity raid not required',`Displacement ${Math.round(disp*100)} • bearish PD arrays ${bearArray}`])
  ];
}

function empiricalDistanceModel(c,dir,s){
  const w=c.slice(-Math.min(180,c.length)),trs=trueRanges(w).filter(x=>x>0),sp=adaptiveSpan(w.length);
  const pts=[...pivots(w,true,sp),...pivots(w,false,sp)].sort((a,b)=>a.index-b.index),swings=[];
  for(let i=1;i<pts.length;i++){const d=Math.abs(pts[i].price-pts[i-1].price);if(d>0)swings.push(d)}
  const wicks=w.map(x=>dir==='BUY'?Math.max(0,Math.min(x.o,x.c)-x.l):Math.max(0,x.h-Math.max(x.o,x.c))).filter(x=>x>=0);
  const closeMoves=[];for(let i=1;i<w.length;i++)closeMoves.push(Math.abs(w[i].c-w[i-1].c));
  const tr25=quantile(trs,.25)||s.trMedian*.6,tr50=quantile(trs,.5)||s.trMedian,tr75=quantile(trs,.75)||s.trMedian*1.4;
  const wick50=quantile(wicks,.5)||s.trMedian*.15,move50=quantile(closeMoves,.5)||s.trMedian*.35;
  const swing50=quantile(swings,.5)||Math.max(tr75*1.6,s.trMedian*1.8),swing75=quantile(swings,.75)||Math.max(swing50*1.35,tr75*2.2);
  return{riskTypical:Math.max(tr25+wick50,tr50*.8),riskUpper:Math.max(tr75+wick50,tr50),rewardTypical:Math.max(swing50,tr75),rewardStretch:Math.max(swing75,swing50+tr50),entryTolerance:Math.max(move50+wick50,tr25*.7),noise:Math.max(wick50,quantile(wicks,.65)||0,s.trMedian-s.trMad)};
}
function chooseObjective(entry,objs,desired,dir,minDist=0){const valid=[...new Set(objs.filter(Number.isFinite))].filter(x=>dir==='BUY'?x>entry+minDist:x<entry-minDist);if(!valid.length)return null;return valid.sort((a,b)=>Math.abs(Math.abs(a-entry)-desired)-Math.abs(Math.abs(b-entry)-desired))[0]}
function structuralInvalidation(entry,dir,lows,highs,m,model){if(dir==='BUY'){const vals=[lows.filter(x=>x<entry).at(-1),m.bullObLow,m.fvgType==='BULLISH'?m.fvgLow:null].filter(x=>x!=null&&x<entry);return vals.length?Math.max(...vals):entry-model.riskTypical}else{const vals=[highs.filter(x=>x>entry)[0],m.bearObHigh,m.fvgType==='BEARISH'?m.fvgHigh:null].filter(x=>x!=null&&x>entry);return vals.length?Math.min(...vals):entry+model.riskTypical}}

function buildSignal(sym,tf,c,m,s,dir,buyScore,sellScore,ranked){
  const last=c.at(-1),sp=adaptiveSpan(c.length),highs=[...new Set(pivots(c,true,sp).map(x=>x.price))].sort((a,b)=>a-b),lows=[...new Set(pivots(c,false,sp).map(x=>x.price))].sort((a,b)=>a-b),model=empiricalDistanceModel(c,dir,s),profile=timeframeRiskProfile(tf,s),candidates=[];
  const add=(reason,p,bonus=0)=>{if(Number.isFinite(p)&&(dir==='BUY'?p<=last.c+model.entryTolerance:p>=last.c-model.entryTolerance))candidates.push({reason,p,bonus})};
  if(dir==='BUY'){add('bull order-block reaction',zoneMid(m.bullObLow,m.bullObHigh),3);if(m.fvgType==='BULLISH')add('bull FVG reaction',zoneMid(m.fvgLow,m.fvgHigh),2);add('nearest adaptive support/liquidity',lows.filter(x=>x<=last.c).at(-1),1)}
  else{add('bear order-block reaction',zoneMid(m.bearObLow,m.bearObHigh),3);if(m.fvgType==='BEARISH')add('bear FVG reaction',zoneMid(m.fvgLow,m.fvgHigh),2);add('nearest adaptive resistance/liquidity',highs.filter(x=>x>=last.c)[0],1)}
  candidates.push({reason:'current live price',p:last.c,bonus:0});
  const allOpp=dir==='BUY'?[...highs,m.equalHigh,m.bearObLow,m.bearObHigh].filter(Number.isFinite):[...lows,m.equalLow,m.bullObLow,m.bullObHigh].filter(Number.isFinite);
  const desiredTp1=clampDistance(model.rewardTypical,profile.tp1Floor,profile.tp1Cap),desiredTp2=clampDistance(model.rewardStretch,Math.max(profile.tp2Floor,desiredTp1*1.25),profile.tp2Cap);
  const rankedCandidates=candidates.map(x=>{
    const invalid=structuralInvalidation(x.p,dir,lows,highs,m,model),rawSl=dir==='BUY'?invalid-model.noise:invalid+model.noise,rawRisk=Math.max(Math.abs(x.p-rawSl),1e-9),risk=clampDistance(rawRisk,profile.riskFloor,profile.riskCap),sl0=dir==='BUY'?x.p-risk:x.p+risk;
    const obj=chooseObjectiveBounded(x.p,allOpp,desiredTp1,dir,Math.max(model.noise*.35,profile.tp1Floor*.25),profile.tp1Cap),reward=Math.max(obj!=null?Math.abs(obj-x.p):desiredTp1,1e-9);
    const riskFit=Math.abs(Math.log(risk/Math.max(clampDistance(model.riskTypical,profile.riskFloor,profile.riskCap),1e-9))),rewardFit=Math.abs(Math.log(reward/Math.max(desiredTp1,1e-9))),drift=Math.abs(last.c-x.p)/Math.max(desiredTp1,1e-9),oversizePenalty=rawRisk>profile.riskCap?Math.min(3,(rawRisk/profile.riskCap)-1):0;
    return{...x,invalid,sl0,risk,rawRisk,fit:riskFit+rewardFit*.7+drift*.25+oversizePenalty-x.bonus*.08};
  }).sort((a,b)=>a.fit-b.fit);
  const chosen=rankedCandidates[0],entry=chosen.p,sl=chosen.sl0;
  const tp1Obj=chooseObjectiveBounded(entry,allOpp,desiredTp1,dir,Math.max(model.noise*.35,profile.tp1Floor*.25),profile.tp1Cap),tp1=tp1Obj??(dir==='BUY'?entry+desiredTp1:entry-desiredTp1);
  const further=allOpp.filter(x=>dir==='BUY'?x>tp1:x<tp1),tp2Obj=chooseObjectiveBounded(entry,further,desiredTp2,dir,Math.abs(tp1-entry)*1.05,profile.tp2Cap),tp2=tp2Obj??(dir==='BUY'?entry+desiredTp2:entry-desiredTp2);
  const score=dir==='BUY'?buyScore:sellScore,risk=Math.max(Math.abs(entry-sl),1e-9),rr1=Math.abs(tp1-entry)/risk,rr2=Math.abs(tp2-entry)/risk,reasons=ranked.slice(0,7).flatMap(f=>[`${f.name} ${Math.round(f.score)}/100`,f.reasons[0]]).filter(Boolean).slice(0,14);
  return{id:crypto.randomUUID(),symbol:sym,timeframe:tf,direction:dir,entry,sl,tp1,tp2,score,bullScore:buyScore,bearScore:sellScore,createdAt:Date.now(),createdCandleTime:last.t,createdMarketPrice:last.c,status:'PENDING',reasons,setupReason:`${dir} • BEST CURRENT SETUP: ${ranked[0]?.name||'Composite market structure'}. ${chosen.reason} selected the entry. SMC/ICT, structure, liquidity, momentum and video-reference evidence were ranked together.`,slReason:`SL uses the selected structural invalidation plus current ${tf} wick/range behavior, bounded by the measured ${tf} risk envelope (${two(profile.riskMin)}–${two(profile.riskMax)} median true-ranges); no fixed pip distance is used.`,tp1Reason:`TP1 uses reachable opposing structure/liquidity inside the measured ${tf} target envelope. Current computed R:R ${two(rr1)}R.`,tp2Reason:`TP2 uses the next reachable structure/liquidity objective inside the measured ${tf} stretch envelope. Current computed R:R ${two(rr2)}R.`,distanceModel:{...model,timeframeProfile:profile}};
}

function managedReconfirmedLevelsV552(prev,fresh,c){
  if(!prev||!fresh||prev.direction!==fresh.direction)return fresh;
  const last=c.at(-1),s=stats(c),model=empiricalDistanceModel(c,prev.direction,s),profile=timeframeRiskProfile(prev.timeframe||timeframe,s);
  const freshRisk=clampDistance(Math.abs(fresh.entry-fresh.sl),profile.riskFloor,profile.riskCap),freshTp1=clampDistance(Math.abs(fresh.tp1-fresh.entry),profile.tp1Floor,profile.tp1Cap),freshTp2=clampDistance(Math.abs(fresh.tp2-fresh.entry),Math.max(profile.tp2Floor,freshTp1*1.25),profile.tp2Cap);
  let sl=prev.direction==='BUY'?prev.entry-freshRisk:prev.entry+freshRisk;
  let tp1=prev.direction==='BUY'?prev.entry+freshTp1:prev.entry-freshTp1;
  let tp2=prev.direction==='BUY'?prev.entry+freshTp2:prev.entry-freshTp2;
  const originalRisk=Math.max(Math.abs(prev.entry-prev.sl),1e-9),move=prev.direction==='BUY'?last.c-prev.entry:prev.entry-last.c;
  if(prev.direction==='BUY'){
    sl=Math.max(Number(prev.sl),sl);
    if(move>=originalRisk)sl=Math.max(sl,prev.entry);
    sl=Math.min(sl,last.c-Math.max(model.noise*.25,profile.riskFloor*.12));
  }else{
    sl=Math.min(Number(prev.sl),sl);
    if(move>=originalRisk)sl=Math.min(sl,prev.entry);
    sl=Math.max(sl,last.c+Math.max(model.noise*.25,profile.riskFloor*.12));
  }
  return{...fresh,entry:prev.entry,sl,tp1,tp2,managedLevels:true,previousLevels:{sl:prev.sl,tp1:prev.tp1,tp2:prev.tp2}};
}
function protectOnReversalV552(prev,c){
  const last=c.at(-1),s=stats(c),model=empiricalDistanceModel(c,prev.direction,s),profile=timeframeRiskProfile(prev.timeframe||timeframe,s),gap=Math.max(model.noise*.35,profile.riskFloor*.18);
  let sl=Number(prev.sl);
  if(prev.direction==='BUY'){const candidate=last.c-gap;if(candidate>sl)sl=Math.min(candidate,last.c-gap*.5)}
  else{const candidate=last.c+gap;if(candidate<sl)sl=Math.max(candidate,last.c+gap*.5)}
  return{...prev,sl,managedLevels:true,reversalProtection:true,previousLevels:{sl:prev.sl,tp1:prev.tp1,tp2:prev.tp2}};
}

function adaptiveExpiryBars(c){const sp=adaptiveSpan(c.length),pts=[...pivots(c,true,sp),...pivots(c,false,sp)].sort((a,b)=>a.index-b.index),gaps=[];for(let i=1;i<pts.length;i++){const g=pts[i].index-pts[i-1].index;if(g>0)gaps.push(g)}if(!gaps.length)return Math.max(3,Math.round(Math.sqrt(c.length)));const med=median(gaps),mad=median(gaps.map(x=>Math.abs(x-med)));return Math.max(3,Math.round(med+mad))}
function signalBarsAge(c,s){let idx=c.findIndex(x=>Number(x.t)>=Number(s.createdCandleTime));if(idx<0)idx=Math.max(0,c.length-adaptiveExpiryBars(c));return Math.max(0,c.length-1-idx)}
function signalEntryActivation(c,s){
  const entry=Number(s?.entry),createdT=Number(s?.createdCandleTime),createdPx=Number(s?.createdMarketPrice);
  if(!Number.isFinite(entry)||!Number.isFinite(createdT)||!Array.isArray(c)||!c.length)return null;
  const signalIdx=c.findIndex(x=>Number(x.t)===createdT),eps=Math.max(Math.abs(entry)*1e-10,1e-9);
  // If the pending entry was effectively at the live price when the signal was created,
  // treat it as immediately activated. Never use the signal candle's pre-signal wick.
  if(Number.isFinite(createdPx)&&Math.abs(createdPx-entry)<=eps)return{index:signalIdx>=0?signalIdx:Math.max(0,c.findIndex(x=>Number(x.t)>createdT)-1),immediate:true};
  // Otherwise only candles strictly AFTER the signal candle are allowed to activate it.
  // This prevents an earlier wick from the same candle from pretending the pending order filled.
  const start=c.findIndex(x=>Number(x.t)>createdT);
  if(start<0)return null;
  for(let i=start;i<c.length;i++){
    const x=c[i];
    if(Number(x.l)<=entry&&Number(x.h)>=entry)return{index:i,immediate:false};
  }
  return null;
}
function signalTouched(c,s,field){
  const p=Number(s?.[field]);if(!Number.isFinite(p))return false;
  const activation=signalEntryActivation(c,s);
  if(!activation)return false; // pending order never filled after this signal, so SL/TP cannot be hit
  const dir=String(s?.direction||'').toUpperCase(),i=Math.max(0,activation.index),a=c[i];
  // On the activation candle, OHLC high/low ordering is unknown. Only the candle's
  // closing/current price is safe evidence after entry activation; older intrabar extremes
  // may have happened before the order filled.
  if(a&&Number.isFinite(Number(a.c))){
    const q=Number(a.c);
    if(field==='sl'){
      if(dir==='BUY'?q<=p:q>=p)return true;
    }else if(dir==='BUY'?q>=p:q<=p)return true;
  }
  // From the NEXT candle onward, the whole OHLC range is definitely post-entry.
  const w=c.slice(i+1);
  if(field==='sl')return dir==='BUY'?w.some(x=>Number(x.l)<=p):w.some(x=>Number(x.h)>=p);
  return dir==='BUY'?w.some(x=>Number(x.h)>=p):w.some(x=>Number(x.l)<=p);
}
function classifyReconfirmation(prev,fresh,c){if(!prev||!fresh||prev.direction!==fresh.direction)return null;if(signalTouched(c,prev,'sl')||signalTouched(c,prev,'tp1'))return null;const model=empiricalDistanceModel(c,prev.direction,stats(c)),d=Math.abs(Number(prev.entry)-Number(fresh.entry));if(d>model.entryTolerance)return null;const age=signalBarsAge(c,prev),life=adaptiveExpiryBars(c);return{distance:d,tolerance:model.entryTolerance,age,life}}
function preserveReconfirmedSignal(prev,fresh,meta,c){const managed=managedReconfirmedLevelsV552(prev,fresh,c);return{...managed,id:prev.id,createdAt:prev.createdAt,createdCandleTime:prev.createdCandleTime,reconfirmedAt:Date.now(),reconfirmed:true,previousScore:prev.score,reconfirmMeta:meta,setupReason:`RECONFIRMED ${fresh.direction} • Earlier setup remains active. Entry is preserved, while SL/TP are re-managed from fresh same-timeframe structure, volatility, indications and video-reference evidence. ${fresh.setupReason}`}}

function analyze(c,prev){
  c=c.slice(-300);const m=marketMap(c);if(c.length<60)return{signal:null,map:m,buyScore:0,sellScore:0,bestFamily:'-',runnerUpFamily:'-',explanation:`Only ${c.length} candles are available; need at least 60 direct ${timeframe} candles.`,reasons:[],warnings:[]};
  const s=stats(c),families=[...trendFamilies(c,m,s),...structureFamilies(c,m,s),...liquidityFamilies(c,m,s),...breakoutFamilies(c,m,s),...reversalFamilies(c,m,s),...zoneFamilies(c,m,s),...momentumFamilies(c,m,s),...smcIctFamilies(c,m,s),...videoFamilies(c,m,s)];
  const [buy,bf]=aggregate(families.filter(x=>x.direction==='BUY')),[sell,sf]=aggregate(families.filter(x=>x.direction==='SELL')),buyScore=Math.round(buy),sellScore=Math.round(sell),edge=Math.abs(buy-sell),bestDir=buy>=sell?'BUY':'SELL',winner=bestDir==='BUY'?bf:sf,loser=bestDir==='BUY'?sf:bf,best=winner[0]?.name||'Composite market structure',runner=winner[1]?.name||loser[0]?.name||'-',reasons=winner.slice(0,6).flatMap(f=>[`${f.name} ${Math.round(f.score)}/100`,...f.reasons.slice(0,2)]).filter(Boolean),warnings=[];
  if(m.fvgType&&m.fvgFillPct>=90)warnings.push(`Latest ${m.fvgType} FVG is almost fully mitigated.`);
  const minEdge=Math.max(4.5,s.pressureUncertainty*.75),winnerScore=Math.max(buyScore,sellScore);if(winnerScore<57||edge<=minEdge)return{signal:null,map:m,buyScore,sellScore,bestFamily:best,runnerUpFamily:runner,explanation:`No clear current directional edge: BUY ${buyScore} vs SELL ${sellScore}; difference ${two(edge)} is inside this timeframe's measured uncertainty ${two(s.pressureUncertainty)}.`,reasons,warnings};
  let signal=buildSignal(symbol,timeframe,c,m,s,bestDir,buyScore,sellScore,winner);const recon=classifyReconfirmation(prev,signal,c);if(recon)signal=preserveReconfirmedSignal(prev,signal,recon,c);
  const reconText=signal.reconfirmed?` This is a reconfirmation of the earlier ${signal.direction} setup: entry-zone drift ${fmt(recon.distance)} is within current adaptive relevance ${fmt(recon.tolerance)}; entry is preserved while protective SL/TP are refreshed from current ${timeframe} structure.`:'';
  return{signal,map:m,buyScore,sellScore,bestFamily:best,runnerUpFamily:runner,explanation:`${bestDir} is the strongest CURRENT ${timeframe} thesis. BUY ${buyScore} vs SELL ${sellScore}; edge ${two(edge)} is larger than measured same-timeframe uncertainty ${two(s.pressureUncertainty)}. Best family: ${best}.${reconText}`,reasons,warnings};
}
function refreshReason(prev,d){const fresh=d.signal;if(!prev&&!fresh)return d.explanation;if(!prev&&fresh)return`Fresh analysis found ${fresh.direction} as the best current setup. ${d.explanation}`;if(prev&&!fresh)return`The earlier ${prev.direction} setup is not being reissued. Fresh analysis no longer has a clear directional edge. ${d.explanation}`;if(fresh.direction!==prev.direction)return`The earlier ${prev.direction} setup is no longer the best current thesis. Fresh ranking changed to ${fresh.direction}. ${d.explanation}`;if(fresh.reconfirmed){const mv=(fresh.score??0)-(fresh.previousScore??prev.score??0);return`RECONFIRMED, NOT A NEW DUPLICATE: this ${fresh.direction} signal was already issued. Fresh ${timeframe} data still supports the same structure; the original entry is retained and SL/TP are re-managed from current timeframe structure/volatility. Quality ${fresh.previousScore??prev.score} -> ${fresh.score}${mv?` (${mv>0?'+':''}${mv})`:''}. ${d.explanation}`;}const same=Number(prev.createdCandleTime)===Number(fresh.createdCandleTime),move=fresh.score-prev.score;return`${same?'The same latest candle snapshot was analysed again from its newest OHLC state.':'A newer same-timeframe candle snapshot was analysed.'} ${fresh.direction} remains strongest, but this is a materially refreshed setup rather than the same entry zone. Quality ${prev.score} -> ${fresh.score}${move?` (${move>0?'+':''}${move})`:''}. ${d.explanation}`}


const recentSession=(()=>{try{const x=JSON.parse(localStorage.getItem('mh-recent-signals-stable')||'[]');return Array.isArray(x)?x.slice(0,6):[]}catch(e){return[]}})();
function setDataState(kind,text){
  const top=$('#restState'),detail=$('#restDetail');
  top.className=`statusPill ${kind}`;top.textContent=`MH Analysis By MHammadS • Data • ${text}`;
  detail.className=kind;detail.textContent=text;
}
function setContextMeta(count,source='Market history'){
  $('#candleCount').textContent=count?`${count} • ${timeframe}`:'—';
  $('#dataSource').textContent=source;
  $('#lastUpdate').textContent=new Date().toLocaleString();
}
function savedApiKey(){return backendSettings.has_api_key?'stored':''}
async function refreshBackendSettings(){try{const r=await fetch('/api/settings',{cache:'no-store'}),j=await r.json();if(r.ok)backendSettings=j;return backendSettings}catch(_){return backendSettings}}
async function fetchCandles(targetSymbol=symbol,targetTimeframe=timeframe,{allowCacheFallback=true,reason='refresh'}={}){
  await refreshBackendSettings();
  const accessKey=savedApiKey();
  if(!accessKey)throw new Error('Save your Access Key first.');
  const requestKey=`${targetSymbol}|${targetTimeframe}`;
  if(fetchInFlight.has(requestKey))return fetchInFlight.get(requestKey);
  const job=(async()=>{
    if(requestKey===keyFor())setDataState('warn',reason==='chart'?'Loading chart…':'Refreshing…');
    let r;
    try{
      r=await fetch('/api/history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:targetSymbol,period:targetTimeframe,reason}),cache:'no-store'});
    }catch(e){
      const cached=candleCache.get(requestKey)||restoreCandles(requestKey)||[];
      if(allowCacheFallback&&cached.length>=60){
        if(requestKey===keyFor()){setDataState('warn',`Offline cache • ${cached.length}`);setContextMeta(cached.length,'Local cached history');setChartData(cached,false)}
        return{candles:cached.slice(-300),meta:{source:'cache fallback'},fromCache:true};
      }
      if(requestKey===keyFor())setDataState('bad','Network failed');
      throw new Error(`History connection failed. ${e.message||e}`);
    }
    const j=await r.json().catch(()=>({}));
    if(!r.ok){
      const cached=candleCache.get(requestKey)||restoreCandles(requestKey)||[];
      if(allowCacheFallback&&cached.length>=60){
        if(requestKey===keyFor()){setDataState('warn',`Data ${r.status} • cached ${cached.length}`);setContextMeta(cached.length,'Local cached history');setChartData(cached,false)}
        return{candles:cached.slice(-300),meta:{source:'cache fallback'},fromCache:true};
      }
      if(requestKey===keyFor())setDataState('bad',`Failed ${r.status}`);
      throw new Error(j.error||`HTTP ${r.status}`);
    }
    const out=(j.candles||[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.t-b.t).slice(-300);
    if(out.length<60){if(requestKey===keyFor())setDataState('bad',`Only ${out.length} candles`);throw new Error(`Only ${out.length} usable candles were received; at least 60 are needed.`)}
    candleCache.set(requestKey,out);persistCandles(requestKey,out);
    if(requestKey===keyFor()){
      setChartData(out,reason==='chart');
      setDataState('good',`${out.length} candles`);
      setContextMeta(out.length,'Market history • Chart');
      $('#nativeFeedStatus').textContent=`${out.length} candles loaded • ${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
    }
    return{candles:out,meta:j.meta||{},fromCache:false};
  })().finally(()=>fetchInFlight.delete(requestKey));
  fetchInFlight.set(requestKey,job);return job;
}
async function loadContextChart(){
  const k=keyFor(),cached=candleCache.get(k)||restoreCandles(k)||[];
  if(cached.length){setChartData(cached,true);setContextMeta(cached.length,'Local cached history');$('#nativeFeedStatus').textContent=`Cached ${cached.length} candles • refreshing…`}
  if(!savedApiKey()){
    setDataState('neutralDot','Access key not saved');
    $('#nativeFeedStatus').textContent=cached.length?`Cached ${cached.length} candles • save API key for fresh data`:'Save Access Key to load chart';
    return cached;
  }
  try{return (await fetchCandles(symbol,timeframe,{allowCacheFallback:true,reason:'chart'})).candles}catch(e){showError(e.message);return cached}
}
async function candlesForAnalysis(){
  // Exactly one fresh history request is used for a manual analysis/re-evaluation.
  // The SAME returned candles update the chart and feed the analysis engine.
  return fetchCandles(symbol,timeframe,{allowCacheFallback:false,reason:'analysis'});
}

async function detectNewsRisk(c){
  const trs=trueRanges(c),base=Math.max(median(trs.slice(-120)),1e-9),recent=Math.max(...trs.slice(-3),0),ratio=recent/base;
  let api={high:false,events:[],source:''};
  try{const r=await fetch('/api/news-risk',{cache:'no-store'});if(r.ok)api=await r.json()}catch(_){ }
  const eventNames=Array.isArray(api.events)?api.events.filter(Boolean):[];
  const empiricalHigh=ratio>=2.6;
  const high=!!api.high||empiricalHigh;
  const label=eventNames.length?eventNames.join(' / '):(empiricalHigh?'Abnormal candle volatility detected':'');
  return{high,label,events:eventNames,ratio,calendarHigh:!!api.high,empiricalHigh};
}
function applyNewsRisk(d,risk){
  d.newsRisk=risk;
  if(!risk?.high)return d;
  d.blockedSignal=d.signal||null;
  d.signal=null;
  const event=risk.label||'High-impact economic volatility';
  d.warnings=[`NEWS RISK: ${event}`,...(d.warnings||[])];
  d.explanation=`HIGH VOLATILITY / NEWS RISK — ${event}. No new signal is issued during this risk window. Trade at your own risk.`;
  return d;
}

function inferDetails(d){
  const m=d.map||{},sig=d.signal;
  const regime=m.adx>=28?'TRENDING':m.adx<=16?'RANGING':'MIXED';
  const spread=Math.abs((m.plusDi||0)-(m.minusDi||0));
  const strength=spread>=25?'Strong':spread>=12?'Moderate':'Balanced';
  const vol=(m.fvgType&&m.fvgFillPct<50)?'Active':'Normal';
  const structure=sig?`${sig.direction==='BUY'?'Bullish':'Bearish'} bias`:'Neutral / contested';
  const pressure=d.buyScore>d.sellScore?'Buyers':d.sellScore>d.buyScore?'Sellers':'Balanced';
  return{regime,strength,vol,structure,pressure};
}
function renderTopMap(d){
  const m=d.map||{},x=inferDetails(d),sig=d.signal;
  $('#mapRegime').textContent=x.regime;$('#mapRegime').className=sig?(sig.direction==='BUY'?'good':'bad'):'warn';
  $('#mapAdx').textContent=Number.isFinite(m.adx)?m.adx.toFixed(1):'—';$('#mapVwap').textContent=fmt(m.vwap);
  $('#mapBullOb').textContent=m.bullObLow!=null?'Yes':'No';$('#mapBullOb').className=m.bullObLow!=null?'good':'';
  $('#mapBearOb').textContent=m.bearObLow!=null?'Yes':'No';$('#mapBearOb').className=m.bearObLow!=null?'bad':'';
  const fvgMapText=m.fvgType?`${m.fvgType==='BULLISH'?'B':'S'} ${fmt(m.fvgLow)}–${fmt(m.fvgHigh)} • ${m.fvgFillPct}%`:'No active';
  $('#mapFvg').textContent=fvgMapText;$('#mapFvg').title=fvgMapText;
  const eqMapText=`H ${m.equalHigh!=null?fmt(m.equalHigh):'No EQH'} / L ${m.equalLow!=null?fmt(m.equalLow):'No EQL'}`;
  $('#mapEq').textContent=eqMapText;$('#mapEq').title=eqMapText;
  $('#mapDiv').textContent=m.divergence||'No';
  $('#buyScoreTop').textContent=d.buyScore??'—';$('#sellScoreTop').textContent=d.sellScore??'—';

  $('#detailRegime').textContent=x.regime;$('#detailTrend').textContent=x.strength;$('#detailVol').textContent=x.vol;$('#detailStructure').textContent=x.structure;$('#detailPressure').textContent=x.pressure;
  $('#indAdx').textContent=Number.isFinite(m.adx)?m.adx.toFixed(1):'—';
  $('#indDi').textContent=(Number.isFinite(m.plusDi)&&Number.isFinite(m.minusDi))?`${m.plusDi.toFixed(1)} / ${m.minusDi.toFixed(1)}`:'—';
  $('#indVwap').textContent=fmt(m.vwap);
  $('#indOb').textContent=`Bull ${m.bullObLow!=null?'Yes':'No'} • Bear ${m.bearObLow!=null?'Yes':'No'}`;
  $('#indFvg').textContent=m.fvgType?`${m.fvgType} ${m.fvgFillPct}% filled`:'No active FVG';
  $('#indDiv').textContent=m.divergence||'No';
  const ranked=d._ranked||[];
  const smc=ranked.find(x=>String(x.name||'').startsWith('SMC:'));
  const ict=ranked.find(x=>String(x.name||'').startsWith('ICT:'));
  const volRatio=Number(d.newsRisk?.ratio);
  const mapRiskLabel=d.newsRisk?.high?'HIGH':(Number.isFinite(volRatio)?(volRatio>=1.6?'MEDIUM':'LOW'):'—');
  if($('#mapRisk')){$('#mapRisk').textContent=mapRiskLabel==='—'?'—':`${mapRiskLabel} ${Number.isFinite(volRatio)?volRatio.toFixed(2)+'×':''}`.trim();$('#mapRisk').className=mapRiskLabel==='HIGH'?'bad':mapRiskLabel==='MEDIUM'?'warn':mapRiskLabel==='LOW'?'good':'';}
  if($('#indSmc'))$('#indSmc').textContent=smc?`${Math.round(smc.score)}/100 • ${(smc.reasons&&smc.reasons[0])||smc.name}`:'—';
  if($('#indIct'))$('#indIct').textContent=ict?`${Math.round(ict.score)}/100 • ${(ict.reasons&&ict.reasons[0])||ict.name}`:'—';
  if($('#indRisk'))$('#indRisk').textContent=d.newsRisk?.high?`NEWS RISK • ${d.newsRisk.label||'high-impact volatility'}`:(Number.isFinite(volRatio)?`${volRatio.toFixed(2)}× median true range`:'Normal');
  if($('#detailRisk'))$('#detailRisk').textContent=d.newsRisk?.high?'NEWS RISK / NO NEW TRADE':(sig?`Model edge ${Math.abs((d.buyScore||0)-(d.sellScore||0)).toFixed(1)} pts`:'WAIT / NO TRADE');

  $('#lvlEntry').textContent=sig?fmt(sig.entry):'—';
  $('#lvlSl').textContent=sig?fmt(sig.sl):'—';
  $('#lvlTp1').textContent=sig?fmt(sig.tp1):'—';
  $('#lvlTp2').textContent=sig?fmt(sig.tp2):'—';
  $('#lvlEq').textContent=`${m.equalHigh!=null?fmt(m.equalHigh):'—'} / ${m.equalLow!=null?fmt(m.equalLow):'—'}`;
  const zones=[];
  if(m.bullObLow!=null)zones.push(`Bull OB ${fmt(m.bullObLow)}–${fmt(m.bullObHigh)}`);
  if(m.bearObLow!=null)zones.push(`Bear OB ${fmt(m.bearObLow)}–${fmt(m.bearObHigh)}`);
  if(m.fvgLow!=null)zones.push(`${m.fvgType||'FVG'} ${fmt(m.fvgLow)}–${fmt(m.fvgHigh)}`);
  $('#lvlZones').textContent=zones.join(' • ')||'—';
}
function renderTopSetups(d){
  const rows=[],source=(d._ranked||[]).slice(0,3);
  if(source.length){source.forEach((f,i)=>rows.push(`<div class="rankRow"><span>${i+1}. ${escapeHtml(f.name)} (${f.direction})</span><b>${Math.round(f.score)}</b></div>`))}
  else if(d.bestFamily&&d.bestFamily!=='-'){rows.push(`<div class="rankRow"><span>1. ${escapeHtml(d.bestFamily)}</span><b>${d.signal?.score??Math.max(d.buyScore,d.sellScore)}</b></div>`);if(d.runnerUpFamily&&d.runnerUpFamily!=='-')rows.push(`<div class="rankRow"><span>2. ${escapeHtml(d.runnerUpFamily)}</span><b>—</b></div>`)}
  $('#topSetups').className='rankList';$('#topSetups').innerHTML=rows.join('')||'No ranking yet.';
}

async function loadRecentSignalsV5413(){
  const ctl=new AbortController(),kill=setTimeout(()=>ctl.abort(),1200);
  try{
    const r=await fetch('/api/records-v2?fast=1',{cache:'no-store',signal:ctl.signal});if(!r.ok)throw new Error('records unavailable');
    const j=await r.json();
    const rows=(Array.isArray(j?.records)?j.records:[]).slice().sort((a,b)=>Number(b?.created_at||0)-Number(a?.created_at||0)).slice(0,6).map(x=>{
      const ts=Number(x?.created_at||0)*1000;
      const t=String(x?.local_time||'').trim()||(ts?new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'—');
      const label=String(x?.direction||'').trim().toUpperCase()||'NO EDGE';
      return {time:t,timeframe:String(x?.timeframe||'—'),label,score:Math.round(Number(x?.score)||0),state:String(x?.status||''),key:String(x?.signal_id||x?.id||`${ts}|${label}`)};
    });
    if(rows.length){
      recentSession.splice(0,recentSession.length,...rows);
      try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(e){}
      savePersistentUICacheV5411({recent:recentSession});
    }
    renderRecentSignals();
    return rows.length;
  }catch(e){renderRecentSignals();return 0}
  finally{clearTimeout(kill)}
}
function renderRecentSignals(){
  const previous=recentSession.slice(0,5);
  $('#recentSignals').className='recentList';
  $('#recentSignals').innerHTML=previous.length?previous.map(x=>`<div class="recentRow"><span>${x.time}</span><span class="recentTf">${x.timeframe||'—'}</span><b class="${x.label==='BUY'?'good':x.label==='SELL'?'bad':'warn'}">${x.label}</b><span>${Math.round(Number(x.score)||0)}/100</span></div>`).join(''):'No recent signals yet.';
}
// MH_SAME_SIGNAL_GUARD_V30
async function checkSameSignalV30(d){
  const sig=d?.signal;if(!sig){d._sameActiveSignal=false;return null}
  try{
    const r=await fetch('/api/records-v2/duplicate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2})});
    const j=await r.json();d._sameActiveSignal=!!j.duplicate;d._sameSignalStatus=j.existing_status||'';return j;
  }catch(_){d._sameActiveSignal=false;return null}
}
function sameSignalMessageV30(d){
  const s=d?.signal;return s?`SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL. ${symbol} ${timeframe} ${s.direction} • Entry ${fmt(s.entry)} • SL ${fmt(s.sl)} • TP1 ${fmt(s.tp1)} • TP2 ${fmt(s.tp2)}.`:'NO NEW SIGNAL';
}
async function captureSignalRecordV30(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const id=`MH${Date.now()}${Math.floor(Math.random()*900+100)}`;
  const r=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:id,symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,score:sig.score,setup:d.bestFamily||sig.setupReason||'',action:'NEW'})});
  return r.json().catch(()=>null);
}

async function captureSignalRecordV796(d,state='NEW'){
  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW')return;
  try{
    await fetch('/api/records/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,
      score:sig.score,setup:d.bestFamily||sig.setupReason||'',action:'NEW'
    })});
  }catch(e){}
}
function addRecent(d,state='NEW'){
  const sig=d.signal,now=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),label=d.newsRisk?.high?'NEWS RISK':(sig?sig.direction:'NO EDGE'),score=sig?.score??Math.max(d.buyScore||0,d.sellScore||0);
  const key=`${symbol}|${timeframe}|${label}|${score}|${state}`;
  if(recentSession[0]?.key!==key)recentSession.unshift({time:now,timeframe,label,score,state,key});
  if(recentSession.length>6)recentSession.length=6;
  try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(e){}
  savePersistentUICacheV5411({recent:recentSession});
  // V36: Records are written only by the canonical V2 fanout.
  renderRecentSignals();
}
function updateSignalHeadline(d){
  const el=$('#signalHeadline'),sig=d?.signal;
  if(!el)return;
  if(!sig){el.className='signalHeadline';el.textContent='NO ACTIVE SIGNAL';return}
  const rr=Math.abs(sig.tp1-sig.entry)/Math.max(Math.abs(sig.entry-sig.sl),1e-9);
  el.className=`signalHeadline moving ${sig.direction==='BUY'?'buyHeadline':'sellHeadline'}`;
  el.textContent=`${sig.direction} ${sig.score}/100 • ENTRY ${fmt(sig.entry)} • SL ${fmt(sig.sl)} • TP1 ${fmt(sig.tp1)} • TP2 ${fmt(sig.tp2)} • RR ${rr.toFixed(2)} : 1 • ${d.bestFamily||'Best current setup'}   `;
}
function escapeHtml(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function renderDecision(d,reason,mode='NEW'){
  lastDecision.set(keyFor(),d);chartDecision=d;renderSignalLevels();const sig=d.signal,b=$('#signalBadge'),q=$('#signalQuality'),plan=$('#plan'),card=$('#signalCard');
  if(sig){
    const isBuy=sig.direction==='BUY';
    b.className=`signalBadge ${isBuy?'buy':'sell'}`;b.textContent=`${isBuy?'↗':'↘'} ${sig.direction} SIGNAL`;
    card.className=`panel signalPanel ${isBuy?'buyState':'sellState'}`;
    q.className=isBuy?'good':'bad';q.textContent=`${sig.score} / 100 • ${d.bestFamily}`;
    plan.className='plan';
    const risk=Math.max(Math.abs(sig.entry-sig.sl),1e-9),rr1=Math.abs(sig.tp1-sig.entry)/risk,rr2=Math.abs(sig.tp2-sig.entry)/risk;
    plan.innerHTML=`<div class="kv"><b>ENTRY</b><span>${fmt(sig.entry)}</span><b>SL</b><span>${fmt(sig.sl)}</span><b>TP1</b><span>${fmt(sig.tp1)}</span><b>TP2</b><span>${fmt(sig.tp2)}</span><b>RR (TP1)</b><span>${rr1.toFixed(2)} : 1</span><b>RR (TP2)</b><span>${rr2.toFixed(2)} : 1</span></div><div><b>CURRENT SETUP</b><br>${escapeHtml(sig.setupReason)}</div>`;
  } else {
    const newsBlocked=!!d.newsRisk?.high;
    b.className='signalBadge neutral';b.textContent=newsBlocked?'⚠ NEWS RISK • NO SIGNAL':'NO CLEAR EDGE';card.className='panel signalPanel neutralState';q.className='warn';q.textContent=newsBlocked?'HIGH IMPACT / VOLATILITY':`BUY ${d.buyScore} • SELL ${d.sellScore}`;plan.className='plan muted';plan.textContent=newsBlocked?d.explanation:'Fresh ranking found no statistically clear directional edge. The previous signal is not blindly reused.';
  }
  $('#analysisStatusHeading').textContent=mode==='REEVAL'?'RE-EVALUATE SIGNAL':(d?._sameActiveSignal?'SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL':'NEW ANALYSIS');
  $('#explanation').className='detailText';$('#explanation').textContent=reason||d.explanation;
  $('#reasons').className='detailText';$('#reasons').textContent=[...d.reasons,...d.warnings].map(x=>`• ${x}`).join('\n')||'—';
  renderTopMap(d);renderTopSetups(d);if(mode!=='VIEW')addRecent(d,mode);updateSignalHeadline(d);
}
function buildRankedForUi(c,d){try{const m=d.map,s=stats(c),fs=[...trendFamilies(c,m,s),...structureFamilies(c,m,s),...liquidityFamilies(c,m,s),...breakoutFamilies(c,m,s),...reversalFamilies(c,m,s),...zoneFamilies(c,m,s),...momentumFamilies(c,m,s),...smcIctFamilies(c,m,s),...videoFamilies(c,m,s)];const dir=d.signal?.direction||(d.buyScore>=d.sellScore?'BUY':'SELL');return fs.filter(x=>x.direction===dir).sort((a,b)=>b.score-a.score)}catch(e){return[]}}
function setBusy(on,msg=''){['#analyze','#reevaluate'].forEach(x=>$(x).disabled=on);if(on){$('#explanation').className='detailText muted';$('#explanation').textContent=msg}}
function showError(msg){
  $('#signalBadge').className='signalBadge neutral';$('#signalBadge').textContent='ANALYSIS UNAVAILABLE';$('#signalQuality').textContent='—';
  $('#analysisStatusHeading').textContent='ANALYSIS STATUS';
  $('#explanation').className='detailText bad';$('#explanation').textContent=msg;
}



function savePersistentUICacheV5411(delta){
  try{fetch('/api/ui-cache',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(delta),cache:'no-store'}).catch(()=>{})}catch(e){}
}
async function loadPersistentUICacheV5411(){
  try{
    const r=await fetch('/api/ui-cache',{cache:'no-store'}); if(!r.ok)return false;
    const j=await r.json();
    if(j?.ticker)applyTickerCacheV549(j.ticker);
    if(Array.isArray(j?.calendar)&&j.calendar.length){
      const root=$('#economicCalendarLocal');
      if(root&&typeof renderEconomicCalendarV546==='function')renderEconomicCalendarV546(root,j.calendar);
    }
    if(Array.isArray(j?.recent)&&j.recent.length){
      recentSession.splice(0,recentSession.length,...j.recent.slice(0,6));
      try{localStorage.setItem('mh-recent-signals-stable',JSON.stringify(recentSession))}catch(_){}
      renderRecentSignals();
    }
    return true;
  }catch(e){return false}
}
function applyTickerCacheV549(j){
  try{
    if(Number.isFinite(Number(j?.gold_usd))&&Number(j.gold_usd)>0){publicGoldPrice=Number(j.gold_usd);$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`}
    if(Number.isFinite(Number(j?.btc_usd)))$('#tickerBTC').textContent=`$${Number(j.btc_usd).toLocaleString(undefined,{maximumFractionDigits:2})}`;
    if(Number.isFinite(Number(j?.eth_usd)))$('#tickerETH').textContent=`$${Number(j.eth_usd).toLocaleString(undefined,{maximumFractionDigits:2})}`;
    if(Number.isFinite(Number(j?.eurusd)))$('#tickerEURUSD').textContent=Number(j.eurusd).toFixed(5);
    if(Number.isFinite(Number(j?.usdjpy)))$('#tickerUSDJPY').textContent=Number(j.usdjpy).toFixed(3);
    if(Number.isFinite(Number(j?.gbpusd)))$('#tickerGBPUSD').textContent=Number(j.gbpusd).toFixed(5);
    if(Number.isFinite(Number(j?.gbpjpy)))$('#tickerGBPJPY').textContent=Number(j.gbpjpy).toFixed(3);
    const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
    document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>{if(vals[i])el.textContent=vals[i]});
  }catch(e){}
}
function primeTickerV549(){
  try{const c=JSON.parse(localStorage.getItem('mh-public-ticker-stable')||'null');if(c)applyTickerCacheV549(c)}catch(e){}
  try{const cached=(candleCache.get('XAUUSD|15m')||restoreCandles('XAUUSD|15m')||[]);if(cached.length&&(!$('#tickerGold').textContent||$('#tickerGold').textContent==='—')){$('#tickerGold').textContent=`$${fmt(Number(cached.at(-1).c))}`}}catch(e){}
  const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
  document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>el.textContent=vals[i]||'—');
}
async function refreshPublicTicker(){
  try{
    const cached=(candleCache.get('XAUUSD|15m')||candleCache.get(keyFor())||[]).map(normalizeCandle).filter(Boolean);
    if(cached.length){publicGoldPrice=Number(cached.at(-1).c);if(Number.isFinite(publicGoldPrice))$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`}
    const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
    document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>{if(vals[i]!=null)el.textContent=vals[i]});
  }catch(e){}
  try{
    const r=await fetch('/api/public-ticker',{cache:'no-store'}),j=await r.json();
    if(r.ok){
      try{localStorage.setItem('mh-public-ticker-stable',JSON.stringify(j));applyTickerCacheV549(j)}catch(e){}
      savePersistentUICacheV5411({ticker:j});
      if(Number.isFinite(Number(j.gold_usd))&&Number(j.gold_usd)>0){publicGoldPrice=Number(j.gold_usd);$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`;if(symbol==='XAUUSD')renderGoldMetrics();}
      if(Number.isFinite(Number(j.btc_usd)))$('#tickerBTC').textContent=`$${Number(j.btc_usd).toLocaleString(undefined,{maximumFractionDigits:2})}${Number.isFinite(Number(j.btc_change_24h))?` • ${Number(j.btc_change_24h)>=0?'+':''}${Number(j.btc_change_24h).toFixed(2)}%`:''}`;
      if(Number.isFinite(Number(j.eth_usd)))$('#tickerETH').textContent=`$${Number(j.eth_usd).toLocaleString(undefined,{maximumFractionDigits:2})}${Number.isFinite(Number(j.eth_change_24h))?` • ${Number(j.eth_change_24h)>=0?'+':''}${Number(j.eth_change_24h).toFixed(2)}%`:''}`;
      if(Number.isFinite(Number(j.eurusd)))$('#tickerEURUSD').textContent=Number(j.eurusd).toFixed(5);
      if(Number.isFinite(Number(j.usdjpy)))$('#tickerUSDJPY').textContent=Number(j.usdjpy).toFixed(3);
      if(Number.isFinite(Number(j.gbpusd)))$('#tickerGBPUSD').textContent=Number(j.gbpusd).toFixed(5);
      const gbpJpy=Number.isFinite(Number(j.gbpjpy))?Number(j.gbpjpy):((Number.isFinite(Number(j.gbpusd))&&Number.isFinite(Number(j.usdjpy)))?Number(j.gbpusd)*Number(j.usdjpy):NaN);
      if(Number.isFinite(gbpJpy))$('#tickerGBPJPY').textContent=gbpJpy.toFixed(3);
    }
  }catch(e){}
  try{
    const g=(candleCache.get('XAUUSD|15m')||candleCache.get(keyFor())||[]).map(normalizeCandle).filter(Boolean);
    if(g.length&&symbol==='XAUUSD')$('#tickerGold').textContent=`$${fmt(g.at(-1).c)}`;
    else{
      const any=[...candleCache.entries()].find(([k,v])=>k.startsWith('XAUUSD|')&&v?.length)?.[1]||[];
      if(any.length)$('#tickerGold').textContent=`$${fmt(any.at(-1).c)}`;
    }
  }catch(e){}
  try{
    const vals=['tickerGold','tickerBTC','tickerETH','tickerEURUSD','tickerUSDJPY','tickerGBPUSD','tickerGBPJPY'].map(id=>document.getElementById(id)?.textContent||'—');
    document.querySelectorAll('.tickerClone .tickerCell span').forEach((el,i)=>{ if(vals[i]!=null) el.textContent=vals[i]; });
  }catch(e){}
}

function primeMovingTickerV547(){
  try{
    const bar=document.querySelector('.movingTicker');
    if(bar){bar.style.visibility='visible';bar.style.opacity='1'}
  }catch(e){}
}
function capFmt(v){const n=Number(v);if(!Number.isFinite(n))return'—';if(n>=1e12)return`$${(n/1e12).toFixed(2)}T`;if(n>=1e9)return`$${(n/1e9).toFixed(2)}B`;if(n>=1e6)return`$${(n/1e6).toFixed(2)}M`;return`$${n.toLocaleString(undefined,{maximumFractionDigits:0})}`}
function setTopMetricLabels(title,a,b,c,d){$('#marketDataTitle').textContent=title;$('#metric1Label').textContent=a;$('#metric2Label').textContent=b;$('#metric3Label').textContent=c;$('#metric4Label').textContent=d}
function renderGoldMetrics(){
  setTopMetricLabels('GOLD DATA','PRICE','24H HIGH','24H LOW','24H CHANGE');
  const arr=(candleCache.get(keyFor())||restoreCandles(keyFor())||[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.t-b.t);
  if(!arr.length){
    $('#btcMarketCap').textContent=Number.isFinite(publicGoldPrice)?`$${fmt(publicGoldPrice)}`:'—';
    $('#totalMarketCap').textContent='—';$('#btcDominance').textContent='—';$('#btcChange').textContent='—';$('#btcChange').className='';
    if(Number.isFinite(publicGoldPrice))$('#tickerGold').textContent=`$${fmt(publicGoldPrice)}`;
    return;
  }
  const last=arr.at(-1),cut=last.t-86400,day=arr.filter(x=>x.t>=cut),w=day.length?day:arr.slice(-Math.min(arr.length,96)),first=w[0],hi=Math.max(...w.map(x=>x.h)),lo=Math.min(...w.map(x=>x.l)),base=Number(first?.o)||Number(first?.c)||last.c,ch=base?((last.c-base)/base)*100:0;
  $('#btcMarketCap').textContent=`$${fmt(last.c)}`;$('#totalMarketCap').textContent=`$${fmt(hi)}`;$('#btcDominance').textContent=`$${fmt(lo)}`;const el=$('#btcChange');el.textContent=`${ch>=0?'+':''}${ch.toFixed(2)}%`;el.className=ch>=0?'good':'bad';$('#tickerGold').textContent=`$${fmt(last.c)}`;
}
async function refreshMarketCap(){if(symbol==='XAUUSD'){renderGoldMetrics();return}setTopMetricLabels('CRYPTO DATA','BTC M.CAP','TOTAL CRYPTO','BTC.D','BTC 24H');try{const r=await fetch('/api/marketcap',{cache:'no-store'}),j=await r.json();if(!r.ok)throw new Error();$('#btcMarketCap').textContent=capFmt(j.btc_market_cap);$('#totalMarketCap').textContent=capFmt(j.total_market_cap);$('#btcDominance').textContent=Number.isFinite(Number(j.btc_dominance))?`${Number(j.btc_dominance).toFixed(1)}%`:'—';const ch=Number(j.btc_change_24h),el=$('#btcChange');el.textContent=Number.isFinite(ch)?`${ch>=0?'+':''}${ch.toFixed(2)}%`:'—';el.className=Number.isFinite(ch)?(ch>=0?'good':'bad'):''}catch(e){$('#btcMarketCap').textContent='Unavailable';$('#totalMarketCap').textContent='—';$('#btcDominance').textContent='—';$('#btcChange').textContent='—'}}


function lotForSignalScore(score){
  if(!lotSizeEnabled)return 0.02;
  const n=Math.max(0,Math.min(100,Number(score)||0));
  if(n>=95)return 0.06;
  if(n>=90)return 0.05;
  if(n>=85)return 0.05;
  if(n>=80)return 0.04;
  if(n>=70)return 0.04;
  if(n>=65)return 0.03;
  return 0.02;
}
function updateTradeModeButtons(){
  const lot=$('#lotSizeToggle'),pt=$('#partialTpToggle');
  if(lot){lot.className=`autoSignalToggle ${lotSizeEnabled?'on':'off'}`;lot.textContent=`Lot Size: ${lotSizeEnabled?'ON':'OFF'}`;}
  if(pt){pt.className=`autoSignalToggle ${partialTpEnabled?'on':'off'}`;pt.textContent=`Partial TP: ${partialTpEnabled?'ON':'OFF'}`;}
}
function setLotSizeEnabled(on){lotSizeEnabled=!!on;localStorage.setItem(STORAGE_LOT_SIZE,lotSizeEnabled?'1':'0');updateTradeModeButtons();}
function setPartialTpEnabled(on){partialTpEnabled=!!on;localStorage.setItem(STORAGE_PARTIAL_TP,partialTpEnabled?'1':'0');updateTradeModeButtons();}
function normalizeWhatsAppNumber(raw){return String(raw||'').replace(/\D/g,'')}
function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||d?.originalSignal||null;
  const isRe=action==='RE-EVALUATE';
  const statusValue=isRe?'Re-Evaluate':(sig?'Signal generated':'No clear edge');
  const reason=isRe?(d?.explanation||status||d?.bestFamily||sig?.setupReason||'Market re-evaluation'):'';
  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusValue}`];
  if(isRe){lines.push('',`*Reason:* ${reason}`,'')}
  else{lines.push('')}
  lines.push(`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,'');
  if(sig){
    const dot=sig.direction==='SELL'?'🔴':'🟢';
    const selectedLot=lotForSignalScore(sig.score);lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Lot:* ${selectedLot.toFixed(2)} (${lotSizeEnabled?'Score Auto':'Fixed'})`,`*Partial TP:* ${partialTpEnabled?'ON':'OFF'}`,`*Setup:* ${d?.bestFamily||sig?.setupReason||'Best current setup'}`);
  }else{
    lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*Entry:* —`,`*SL:* —`,`*TP1:* —`,`*TP2:* —`,`*Score:* —`,`*Setup:* No clear edge`);
  }
  return lines.join('\n');
}
async function sendDecisionWhatsApp(d,action,status=''){
  const message=decisionWhatsAppMessage(d,action,status);
  await refreshBackendSettings();
  if(!backendSettings.has_whatsapp)throw new Error('WhatsApp Signal Link is not saved. Open the WhatsApp tab and set Signal Link.');
  const r=await fetch('/api/send-whatsapp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
  let j={};try{j=await r.json()}catch(_){ }
  if(!r.ok)throw new Error(j.error||'WhatsApp queue failed');
  return j;
}
function setAutoStatus(text,kind=''){const el=$('#autoSignalStatus');if(!el)return;el.textContent=text;el.className=`autoSignalStatus ${kind}`.trim()}
function actionLabel(a){return a==='REEVAL'?'RE-EVALUATE':'NEW ANALYZE'}
const FIXED_PHASE_MS=15*60*1000;
const FIXED_REEVAL_OFFSET=5*60*1000;
function fixedPhaseInfo(at=Date.now()){
  const d=new Date(at),minute=d.getMinutes(),phase=Math.floor(minute/15)+1,startMinute=(phase-1)*15,endMinute=phase*15;
  const cycleStart=new Date(d.getFullYear(),d.getMonth(),d.getDate(),d.getHours(),startMinute,0,0).getTime();
  return{phase,startMinute,endMinute,cycleStart,reevalAt:cycleStart+FIXED_REEVAL_OFFSET,nextCycleAt:cycleStart+FIXED_PHASE_MS,label:`1H Phase ${phase}/4 • ${String(startMinute).padStart(2,'0')}:00–${String(endMinute).padStart(2,'0')}:00`};
}
function fixedRemain(ms){const v=Math.max(0,ms),m=Math.floor(v/60000),sec=Math.floor((v%60000)/1000);return`${m}:${String(sec).padStart(2,'0')}`}
function fixedPhaseElapsed(info=fixedPhaseInfo()){return fixedRemain(Math.min(FIXED_PHASE_MS,Math.max(0,Date.now()-info.cycleStart)))}
function nextFixedAutoEvent(now=Date.now(),allowCatchup=false){
  const info=fixedPhaseInfo(now),epsilon=1500;
  if(Math.abs(now-info.cycleStart)<=epsilon)return{action:'NEW',at:now,info};
  if(now<info.reevalAt){
    if(allowCatchup)return{action:'NEW',at:now,info,catchup:true};
    return{action:'REEVAL',at:info.reevalAt,info};
  }
  if(Math.abs(now-info.reevalAt)<=epsilon)return{action:'REEVAL',at:now,info};
  return{action:'NEW',at:info.nextCycleAt,info};
}
function updateAutoButton(){
  const b=$('#autoSignalToggle');if(!b)return;
  b.className=`autoSignalToggle ${autoSignalEnabled?'on':'off'}`;
  if(!autoSignalEnabled){b.textContent='Get Signal: OFF';setAutoStatus('Manual only');return}
  const info=fixedPhaseInfo(),left=Math.max(0,autoSignalNextAt-Date.now());
  b.textContent=`Get Signal: ON • ${fixedRemain(left)}`;
  setAutoStatus(`${info.label} • Elapsed ${fixedPhaseElapsed(info)} / 15:00 • Next ${actionLabel(autoSignalNextAction)} in ${fixedRemain(left)}`,'good');
}
function stopAutoTimers(){if(autoSignalTimer){clearTimeout(autoSignalTimer);autoSignalTimer=null}if(autoCountdownTimer){clearInterval(autoCountdownTimer);autoCountdownTimer=null}}
function scheduleAutoAt(action,targetMs){
  stopAutoTimers();if(!autoSignalEnabled){updateAutoButton();return}
  const now=Date.now(),safeTarget=Math.max(Number(targetMs)||now,now+50),delay=safeTarget-now;
  autoSignalNextAction=action;autoSignalNextAt=safeTarget;
  autoSignalTimer=setTimeout(()=>runScheduledAutoAction(action),delay);
  autoCountdownTimer=setInterval(updateAutoButton,1000);updateAutoButton();
}
function scheduleNextFixedEvent(allowCatchup=false){
  if(!autoSignalEnabled)return;
  const ev=nextFixedAutoEvent(Date.now(),allowCatchup);
  if(ev.at<=Date.now()+100)scheduleAutoAt(ev.action,Date.now()+100);
  else scheduleAutoAt(ev.action,ev.at);
}
function scheduleAfterCompletedFixedAction(action,at=Date.now()){
  if(!autoSignalEnabled)return;
  const info=fixedPhaseInfo(at),kind=String(action||'').toUpperCase();
  if(kind.includes('RE-EVALUATE')){scheduleAutoAt('NEW',info.nextCycleAt);return}
  if(at<info.reevalAt-250){scheduleAutoAt('REEVAL',info.reevalAt);return}
  scheduleAutoAt('NEW',info.nextCycleAt);
}
async function autoSendAndSchedule(d,action,status=''){
  if(!autoSignalEnabled)return;
  const completedAt=Date.now();
  try{
    setAutoStatus(`${fixedPhaseInfo(completedAt).label} • Sending ${action.toLowerCase()}…`,'warn');
    await sendDecisionWhatsApp(d,action,status);
  }catch(e){setAutoStatus(e.message,'bad')}
  scheduleAfterCompletedFixedAction(action,completedAt);
}
async function setAutoSignalEnabled(on){
  if(on){
    await refreshBackendSettings();
    if(!backendSettings.has_whatsapp){
      autoSignalEnabled=false;localStorage.setItem(STORAGE_AUTO,'0');stopAutoTimers();updateAutoButton();
      setAutoStatus('Set WhatsApp destination first','bad');
      const saved=await openWhatsappSettingsPrompt();
      if(!saved)return;
      await refreshBackendSettings();
    }
    if(!backendSettings.has_api_key){
      autoSignalEnabled=false;localStorage.setItem(STORAGE_AUTO,'0');stopAutoTimers();updateAutoButton();
      setAutoStatus('Access key missing • add it from KEYS','bad');return;
    }
  }
  autoSignalEnabled=!!on;localStorage.setItem(STORAGE_AUTO,autoSignalEnabled?'1':'0');
  if(autoSignalEnabled){
    stopAutoTimers();
    const ev=nextFixedAutoEvent(Date.now(),true);
    if(ev.catchup){setAutoStatus(`${ev.info.label} • Catch-up NEW ANALYZE now, then fixed RE-EVALUATE at +05`,'good');scheduleAutoAt('NEW',Date.now()+120);}
    else scheduleAutoAt(ev.action,ev.at<=Date.now()?Date.now()+120:ev.at);
  }else{stopAutoTimers();autoSignalNextAt=0;updateAutoButton()}
}
async function runScheduledAutoAction(action){
  if(!autoSignalEnabled)return;
  if(autoSignalRunning||busy){scheduleAutoAt(action,Date.now()+10000);return}
  autoSignalRunning=true;
  try{
    if(action==='REEVAL')await executeReevaluate(true);
    else await executeNewAnalysis(true);
  }finally{autoSignalRunning=false;if(autoSignalEnabled&&autoSignalNextAt<=Date.now()+250)scheduleNextFixedEvent(false)}
}
async function sendUniqueSignalToEAV30(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);
  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);
  const baseSignalId=`MH${Date.now()}_${symbol}_${timeframe}`,selectedLot=lotForSignalScore(sig.score),signalId=partialTpEnabled?`${baseSignalId}__PT1_${Number(sig.tp1).toFixed(10)}`:baseSignalId,finalTp=partialTpEnabled?Number(sig.tp2):Number(sig.tp1);
  try{
    const r=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:finalTp,lot:selectedLot,expiry:0})});
    let j={};try{j=await r.json()}catch(_){ }
    if(!r.ok)throw new Error(j.error||`EA bridge HTTP ${r.status}`);
    setAutoStatus(`MT5 pending sent to EA • ${pending}`,'good');
    return j;
  }catch(e){
    console.warn('MT5 EA pending bridge failed',e);
    setAutoStatus(`MT5 pending failed • ${e.message||e}`,'bad');
    return null;
  }
}
function derivePendingTypeV30(direction,entry,market){
  direction=String(direction||'').toUpperCase();
  if(direction==='BUY')return entry<=market?'BUY_LIMIT':'BUY_STOP';
  return entry>=market?'SELL_LIMIT':'SELL_STOP';
}

async function prepareMT5SignalV796(d,state='NEW'){
  const sig=d?.signal;
  if(!sig||String(state).toUpperCase()!=='NEW')return;
  const arr=candleCache.get(keyFor())||[];
  const market=Number(arr.at(-1)?.c);
  if(!Number.isFinite(market)||market<=0)return;
  try{
    const r=await fetch('/api/mt5/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,
      market_price:market,score:sig.score,setup:d.bestFamily||sig.setupReason||''
    })});
    if(!r.ok){const t=await r.text();throw new Error(t||`HTTP ${r.status}`)}
  }catch(e){console.warn('MT5 prefill queue failed',e)}
}
async function readMT5ActiveStateV552(sym=symbol){
  try{const r=await fetch(`/api/mt5/ea/active?symbol=${encodeURIComponent(sym)}`,{cache:'no-store'}),j=await r.json();return r.ok?j:null}catch(_){return null}
}
async function applyActiveTradeSafetyV552(d){
  const sig=d?.signal;if(!sig)return d;
  const st=await readMT5ActiveStateV552(symbol);if(!st?.active)return d;
  const activeDir=String(st.direction||'').toUpperCase(),newDir=String(sig.direction||'').toUpperCase();
  if(activeDir&&activeDir!=='MIXED'&&activeDir!==newDir){
    d.blockedSignal=sig;d.signal=null;d._reversalBlocked=true;d._activeTradeState=st;
    d.warnings=[`ACTIVE TRADE SAFETY: MT5 has active ${activeDir}. Fresh analysis detected ${newDir}, but no reverse signal/order will be issued until the current position/pending order is resolved.`,...(d.warnings||[])];
    d.explanation=`REVERSAL WARNING — fresh analysis currently favors ${newDir}, while MT5 still reports active ${activeDir}. Re-evaluation remains active for protection/SL management; reverse execution is locked until the current exposure is resolved.`;
  }
  return d;
}
async function manageExistingMT5TradeV552(original,managed,status=''){
  if(!original||!managed||original.direction!==managed.direction)return null;
  const changed=Math.abs(Number(original.sl)-Number(managed.sl))>1e-9||Math.abs(Number(original.tp1)-Number(managed.tp1))>1e-9;
  if(!changed)return null;
  const st=await readMT5ActiveStateV552(symbol);if(!st?.active||String(st.direction||'').toUpperCase()!==String(managed.direction||'').toUpperCase())return null;
  try{
    const r=await fetch('/api/mt5/ea/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({manage_id:`MHM${Date.now()}_${symbol}_${timeframe}`,symbol,direction:managed.direction,sl:Number(managed.sl),tp:partialTpEnabled?Number(managed.tp2):Number(managed.tp1),tp1:Number(managed.tp1),tp2:Number(managed.tp2),partial_tp:partialTpEnabled,reason:status||'RE-EVALUATE'})});
    const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||`EA manage HTTP ${r.status}`);
    setAutoStatus(`MT5 active trade management queued • SL ${fmt(managed.sl)} • TP ${fmt(managed.tp1)}`,'good');return j;
  }catch(e){console.warn('MT5 active trade management failed',e);setAutoStatus(`MT5 manage failed • ${e.message||e}`,'bad');return null}
}

// V36_CANONICAL_SIGNAL_FANOUT: one signal id, one record, one EA pending handoff.
async function dispatchUniqueSignalV36(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const baseSignalId=`MH${Date.now()}_${symbol}_${timeframe}`,selectedLot=lotForSignalScore(sig.score),signalId=partialTpEnabled?`${baseSignalId}__PT1_${Number(sig.tp1).toFixed(10)}`:baseSignalId,finalTp=partialTpEnabled?Number(sig.tp2):Number(sig.tp1);
  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);
  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);
  const recordPayload={signal_id:signalId,symbol,timeframe,direction:sig.direction,entry:Number(sig.entry),sl:Number(sig.sl),tp1:Number(sig.tp1),tp2:Number(sig.tp2),score:Number(sig.score)||0,setup:d.bestFamily||sig.setupReason||'',action:'NEW'};
  const rr=await fetch('/api/records-v2/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(recordPayload)});
  let rj={};try{rj=await rr.json()}catch(_){}
  if(!rr.ok)throw new Error(rj.error||`Records HTTP ${rr.status}`);
  if(rj.duplicate||rj.same_signal){d._sameActiveSignal=true;d._sameSignalStatus=rj.existing_status||'';setAutoStatus('Same signal still active • no duplicate Record / MT5 pending','warn');return rj;}
  const er=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:finalTp,lot:selectedLot,expiry:0})});
  let ej={};try{ej=await er.json()}catch(_){}
  if(!er.ok)throw new Error(ej.error||`EA bridge HTTP ${er.status}`);
  try{await prepareMT5SignalV796(d,'NEW')}catch(_){}
  setAutoStatus(`Signal recorded • MT5 pending sent • ${pending} • Lot ${selectedLot.toFixed(2)} • Partial TP ${partialTpEnabled?'ON':'OFF'}`,'good');
  return {record:rj,ea:ej,signal_id:signalId};
}
async function executeNewAnalysis(fromAuto=false){
  if(busy)return null;autoActionStartedAt=Date.now();busy=true;setBusy(true,`${fromAuto?'AUTO • ':''}NEW ANALYZE • fetching one fresh candle snapshot…`);
  try{
    const k=keyFor(),prev=(active.get(k)||restoreActiveSignal(k))?.signal||null;
    const f=await candlesForAnalysis(),c=f.candles,d=analyze(c,null),newsRisk=await detectNewsRisk(c);
    applyNewsRisk(d,newsRisk);
    await applyActiveTradeSafetyV552(d);
    d._ranked=buildRankedForUi(c,d);let reason=refreshReason(prev,d);
    if(d.signal){const same=await checkSameSignalV30(d);if(same?.duplicate)reason=sameSignalMessageV30(d);}
    if(d.signal){const obj={signal:d.signal,state:d.signal.reconfirmed?'RECONFIRMED':'PENDING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else if(d._reversalBlocked&&prev){const obj={signal:prev,state:'REVERSAL WARNING',candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
    renderDecision(d,reason,'NEW');busy=false;setBusy(false);
    if(d.signal&&!d._sameActiveSignal){dispatchUniqueSignalV36(d).catch(e=>console.warn('Background Record/EA handoff failed',e));} // V546_BACKGROUND_FANOUT
    if(autoSignalEnabled)await autoSendAndSchedule(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));
    else{
      try{
        await sendDecisionWhatsApp(d,'NEW ANALYSIS',d.newsRisk?.high?'NEWS RISK — no signal':(d.signal?'Signal generated':'No clear edge'));
        if(d._sameActiveSignal)setAutoStatus('NEW ANALYZE queued to WhatsApp • same signal active • no duplicate Record / MT5 pending','good');
        else setAutoStatus('NEW ANALYZE queued to WhatsApp','good');
      }catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}
    }
    return d;
  }catch(e){
    showError(e.message);if(autoSignalEnabled){setAutoStatus('Analysis failed • staying on fixed 15m clock','bad');scheduleFixedAfterDecision(null,'NEW ANALYSIS',autoActionStartedAt||Date.now())}return null;
  }finally{busy=false;setBusy(false)}
}
async function executeReevaluate(fromAuto=false){
  if(busy)return null;autoActionStartedAt=Date.now();const k=keyFor(),a=active.get(k)||restoreActiveSignal(k);
  if(!a){
    const msg=`No active ${symbol} ${timeframe} signal. RE-EVALUATE skipped; NEW ANALYZE will run at the next fixed phase boundary.`;
    if(!fromAuto)showError(msg);
    const skipped={signal:null,buyScore:0,sellScore:0,explanation:msg};
    try{
      await refreshBackendSettings();
      if(backendSettings.has_whatsapp){
        await sendDecisionWhatsApp(skipped,'RE-EVALUATE','Skipped — no active signal');
        if(!autoSignalEnabled)setAutoStatus('RE-EVALUATE status sent to WhatsApp','good');
      }
    }catch(e){setAutoStatus(`WhatsApp send failed • ${e.message||e}`,'bad')}
    if(autoSignalEnabled){
      setAutoStatus(`${fixedPhaseInfo(autoActionStartedAt).label} • Re-evaluation skipped`,'warn');
      scheduleFixedAfterDecision(null,'RE-EVALUATE',autoActionStartedAt);
    }
    return null;
  }
  busy=true;setBusy(true,`${fromAuto?'AUTO • ':''}RE-EVALUATE • testing the original signal against fresh data…`);
  try{
    const f=await candlesForAnalysis(),c=f.candles,s=a.signal,current=analyze(c,s),newsRisk=await detectNewsRisk(c),age=signalBarsAge(c,s),life=adaptiveExpiryBars(c),last=c.at(-1),model=empiricalDistanceModel(c,s.direction,stats(c));
    current.newsRisk=newsRisk;
    current._ranked=buildRankedForUi(c,current);current.originalSignal=s;let status='',keep=false,displayOriginal=false;
    const slHit=signalTouched(c,s,'sl'),tp2Hit=signalTouched(c,s,'tp2'),tp1Hit=signalTouched(c,s,'tp1'),same=current.signal?.direction===s.direction,opposite=current.signal&&current.signal.direction!==s.direction;
    const favorable=s.direction==='BUY'?last.c>=s.entry:last.c<=s.entry,entryRelevant=Math.abs(last.c-s.entry)<=model.entryTolerance;
    if(newsRisk.high){status=`NEWS RISK — ${newsRisk.label||'high-impact volatility'}. Existing setup is not freshly revalidated. No new trade signal; trade at your own risk.`;keep=true;displayOriginal=true;}
    else if(slHit){status='INVALID — original structural invalidation / SL was breached';}
    else if(tp2Hit){status='TARGET REACHED — TP2 reached';}
    else if(tp1Hit&&same){status='TP1 REACHED — existing trade remains structurally valid toward TP2';keep=true;displayOriginal=true;}
    else if(opposite){status=`REVERSAL WARNING — fresh data now ranks ${current.signal.direction} above the original ${s.direction}; reverse execution remains locked while the active trade/pending order exists`;keep=true;displayOriginal=true;current.signal=protectOnReversalV552(s,c);}
    else if(!same&&age>life){status=`EXPIRED — ${age} bars old versus an adaptive structure lifecycle of about ${life} bars, and fresh data no longer confirms the original side`;}
    else if(same&&age>life&&!entryRelevant&&favorable){status='STILL VALID FOR AN EXISTING TRADE — ORIGINAL ENTRY EXPIRED FOR A NEW ENTRY';keep=true;displayOriginal=true;}
    else if(same){status='STILL VALID — original structure remains supported by fresh data';keep=true;displayOriginal=true;}
    else{status='WEAKENING — no fresh opposite signal, but directional confirmation is no longer clear';keep=true;displayOriginal=true;}
    if(displayOriginal){const sideScore=s.direction==='BUY'?current.buyScore:current.sellScore;if(same&&current.signal)current.signal={...current.signal,score:sideScore,status};else current.signal={...(current.signal||s),score:sideScore,status};current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Age ${age} bars; adaptive lifecycle ${life} bars.`}
    else{current.signal=null;current.explanation=`Re-evaluation tested the ORIGINAL ${s.direction} signal, not a new trade. ${status}. Fresh ranking: BUY ${current.buyScore} vs SELL ${current.sellScore}. Run NEW ANALYZE if you want a new setup.`}
    if(keep){const obj={signal:displayOriginal?current.signal:s,state:status,candles:c};active.set(k,obj);persistActiveSignal(k,obj)}else{active.delete(k);persistActiveSignal(k,null)}
    renderDecision(current,`RE-EVALUATE SIGNAL: ${status}. ${current.explanation}`,'REEVAL');busy=false;setBusy(false);
    if(keep&&displayOriginal&&current.signal)await manageExistingMT5TradeV552(s,current.signal,status);
    if(autoSignalEnabled)await autoSendAndSchedule(current,'RE-EVALUATE',status);
    else{
      try{await sendDecisionWhatsApp(current,'RE-EVALUATE',status);setAutoStatus('RE-EVALUATE queued to WhatsApp','good')}catch(e){setAutoStatus(`WhatsApp queue failed • ${e.message||e}`,'bad')}
    }
    return current;
  }catch(e){showError(e.message);if(autoSignalEnabled){setAutoStatus('Re-evaluate failed • staying on fixed quarter-hour boundary','bad');scheduleFixedAfterDecision(null,'RE-EVALUATE',autoActionStartedAt||Date.now())}return null}
  finally{busy=false;setBusy(false)}
}
async function runAnalyze(){return executeNewAnalysis(false)}
async function runReevaluate(){return executeReevaluate(false)}

function setupLightweightChart(){
  const container=$('#priceChart');
  if(!container)return;
  if(typeof LightweightCharts==='undefined'){
    $('#chartEmpty').classList.remove('hidden');$('#chartEmpty').textContent='Chart library could not load. Check internet connection.';return;
  }
  if(lwChart){try{lwChart.remove()}catch(e){};lwChart=null;candleSeries=null;volumeSeries=null}
  lwChart=LightweightCharts.createChart(container,{
    layout:{background:{type:'solid',color:'#050a0d'},textColor:'#a9bbb5',fontFamily:'Segoe UI, Arial, sans-serif',fontSize:11,attributionLogo:false},
    grid:{vertLines:{color:'#102721'},horzLines:{color:'#102721'}},
    crosshair:{mode:LightweightCharts.CrosshairMode?.Normal??0},
    rightPriceScale:{borderColor:'#1a3a33',scaleMargins:{top:.08,bottom:.06}},
    timeScale:{borderColor:'#1a3a33',timeVisible:true,secondsVisible:false,rightOffset:4,barSpacing:7,minBarSpacing:2},
    handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:true},
    handleScale:{axisPressedMouseMove:true,mouseWheel:true,pinch:true},
    kineticScroll:{mouse:true,touch:true},
    localization:{priceFormatter:p=>fmt(Number(p))}
  });
  candleSeries=lwChart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#00c7a3',downColor:'#ff455d',wickUpColor:'#00c7a3',wickDownColor:'#ff455d',borderVisible:false,priceLineVisible:true,lastValueVisible:true});
  volumeSeries=null;
  if(window.ResizeObserver){chartResizeObserver?.disconnect?.();chartResizeObserver=new ResizeObserver(entries=>{const r=entries[0]?.contentRect;if(r&&lwChart)lwChart.resize(Math.max(1,Math.floor(r.width)),Math.max(1,Math.floor(r.height)))});chartResizeObserver.observe(container)}
}
function renderLoadedMap(arr){
  try{
    if(!arr?.length)return;
    const m=marketMap(arr),reg=m.adx>=28?'TRENDING':m.adx<=16?'RANGING':'MIXED';
    const trs=trueRanges(arr),base=Math.max(median(trs.slice(-120)),1e-9),recent=Math.max(...trs.slice(-3),0),ratio=recent/base;
    const risk=ratio>=2.6?'HIGH':ratio>=1.6?'MEDIUM':'LOW';
    $('#mapRegime').textContent=reg;$('#mapRegime').className=reg==='TRENDING'?'good':reg==='RANGING'?'warn':'';
    $('#mapAdx').textContent=Number.isFinite(m.adx)?m.adx.toFixed(1):'—';
    $('#mapVwap').textContent=fmt(m.vwap);
    $('#mapBullOb').textContent=m.bullObLow!=null?'Yes':'No';$('#mapBullOb').className=m.bullObLow!=null?'good':'';
    $('#mapBearOb').textContent=m.bearObLow!=null?'Yes':'No';$('#mapBearOb').className=m.bearObLow!=null?'bad':'';
    const fvgText=m.fvgType?`${m.fvgType==='BULLISH'?'B':'S'} ${fmt(m.fvgLow)}–${fmt(m.fvgHigh)} • ${m.fvgFillPct}%`:'No active';
    $('#mapFvg').textContent=fvgText;$('#mapFvg').title=fvgText;
    const eqText=`H ${m.equalHigh!=null?fmt(m.equalHigh):'No EQH'} / L ${m.equalLow!=null?fmt(m.equalLow):'No EQL'}`;
    $('#mapEq').textContent=eqText;$('#mapEq').title=eqText;
    if($('#mapRisk')){$('#mapRisk').textContent=`${risk} ${ratio.toFixed(2)}×`;$('#mapRisk').className=risk==='HIGH'?'bad':risk==='MEDIUM'?'warn':'good'}
    $('#mapDiv').textContent=m.divergence||'No';
  }catch(e){}
}
function setChartData(arr,fit=false){
  arr=(arr||[]).map(normalizeCandle).filter(Boolean).sort((a,b)=>a.t-b.t).slice(-300);
  const empty=$('#chartEmpty');
  if(!lwChart||!candleSeries)setupLightweightChart();
  if(!candleSeries){empty?.classList.remove('hidden');return}
  if(!arr.length){empty?.classList.remove('hidden');empty.textContent='No candle data loaded.';candleSeries.setData([]);drawRsiChart($('#rsiCanvas'),[]);return}
  empty?.classList.add('hidden');
  candleSeries.setData(arr.map(x=>({time:Math.floor(x.t),open:x.o,high:x.h,low:x.l,close:x.c})));
  drawRsiChart($('#rsiCanvas'),arr);
  renderLoadedMap(arr);
  renderSignalLevels();
  if(fit)lwChart.timeScale().fitContent();
  if(symbol==='XAUUSD')renderGoldMetrics();
}
function clearSignalLevels(){
  if(candleSeries){for(const line of signalPriceLines){try{candleSeries.removePriceLine(line)}catch(e){}}}
  signalPriceLines=[];
  try{markerPlugin?.setMarkers([])}catch(e){}
}
function renderSignalLevels(){
  if(!candleSeries)return;clearSignalLevels();
  const d=lastDecision.get(keyFor()),sig=d?.signal;if(!sig)return;
  const isBuy=sig.direction==='BUY';
  const mk=(title,price,color,width=1)=>candleSeries.createPriceLine({price:Number(price),color,lineWidth:width,lineStyle:LightweightCharts.LineStyle?.Dashed??2,axisLabelVisible:true,title});
  signalPriceLines.push(mk('ENTRY',sig.entry,isBuy?'#30e89a':'#ff5b70',2));
  signalPriceLines.push(mk('SL',sig.sl,'#ff455d',2));
  signalPriceLines.push(mk('TP1',sig.tp1,'#35df97',1));
  signalPriceLines.push(mk('TP2',sig.tp2,'#35df97',1));
  const arr=candleCache.get(keyFor())||[];
  if(arr.length&&typeof LightweightCharts.createSeriesMarkers==='function'){
    const markerTime=Math.floor(arr.at(-1).t);
    const markers=[{time:markerTime,position:isBuy?'belowBar':'aboveBar',color:isBuy?'#30e89a':'#ff455d',shape:isBuy?'arrowUp':'arrowDown',text:`${sig.direction} ${Math.round(sig.score)}/100`}];
    try{if(markerPlugin)markerPlugin.setMarkers(markers);else markerPlugin=LightweightCharts.createSeriesMarkers(candleSeries,markers)}catch(e){}
  }
}
function canvasSize(canvas){if(!canvas)return{w:0,h:0,d:1};const r=canvas.getBoundingClientRect(),d=Math.max(1,Math.min(2,window.devicePixelRatio||1)),w=Math.max(1,Math.floor(r.width*d)),h=Math.max(1,Math.floor(r.height*d));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}return{w,h,d}}
function drawLine(ctx,x1,y1,x2,y2,color,width=1,dash=[]){ctx.save();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.restore()}
function drawRsiChart(canvas,arr){
  if(!canvas)return;
  const {w,h,d}=canvasSize(canvas),ctx=canvas.getContext('2d');
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#050a0d';ctx.fillRect(0,0,w,h);
  ctx.font=`${9*d}px Segoe UI`;
  if(!arr.length){ctx.fillStyle='#b6c5c1';ctx.fillText('RSI (14) —',8*d,13*d);return;}
  const closes=arr.map(x=>x.c),vals=[];
  for(let i=0;i<closes.length;i++)vals.push(i<14?50:rsi(closes.slice(0,i+1),14));
  const y=v=>6*d+(100-v)/100*(h-12*d),x=i=>8*d+i*(w-16*d)/Math.max(1,vals.length-1);
  [75,30].forEach(v=>{
    drawLine(ctx,8*d,y(v),w-8*d,y(v),'#f0c94d',0.75*d,[]);
    ctx.fillStyle='#d8c77c';ctx.font=`${8*d}px Segoe UI`;ctx.fillText(String(v),w-25*d,y(v)-3*d);
  });
  ctx.strokeStyle='#8b6bd6';ctx.lineWidth=1.2*d;ctx.beginPath();
  vals.forEach((v,i)=>{const xx=x(i),yy=y(v);if(i===0)ctx.moveTo(xx,yy);else ctx.lineTo(xx,yy)});ctx.stroke();
  const current=vals.at(-1);
  ctx.fillStyle='#dbe7e3';ctx.font=`${9*d}px Segoe UI`;ctx.fillText(`RSI (14) ${current.toFixed(2)}`,8*d,13*d);
}
function loadChart(){
  $('#chartLabel').textContent=`${symbol} • ${timeframe}`;
  $('#currentPair').textContent=`${symbol} • ${timeframe}`;
  $('#nativeSymbol').textContent=symbol;
  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));
  if(!lwChart||!candleSeries)setupLightweightChart();
  try{candleSeries?.setData([])}catch(_){}
  try{volumeSeries?.setData([])}catch(_){}
  try{drawRsiChart($('#rsiCanvas'),[])}catch(_){}
  clearSignalLevels();
  const empty=$('#chartEmpty');
  if(empty){empty.classList.remove('hidden');empty.textContent='Press NEW ANALYZE or RE-EVALUATE to load this timeframe.';}
  const feed=$('#nativeFeedStatus');if(feed)feed.textContent='Ready • no market request yet';
}
function setupChartControls(){
  $$('.nativeTfButtons button').forEach(b=>b.onclick=()=>{const tf=b.dataset.chartTf;if(tf===timeframe)return;timeframe=tf;$('#timeframe').value=tf;contextChanged()});
  $$('#analysisTabs button').forEach(btn=>btn.onclick=()=>{
    $$('#analysisTabs button').forEach(x=>x.classList.toggle('activeTab',x===btn));
    $$('.tabPane').forEach(p=>p.classList.toggle('activePane',p.dataset.pane===btn.dataset.tab));
  });
}
function resetViewForContext(){
  // Manual pair/timeframe browsing is VIEW-ONLY. Never restore an old decision
  // into the newly selected context and never imply that fresh market data was
  // requested. The screen remains blank until an explicit analysis action.
  $('#signalCard').className='panel signalPanel neutralState';$('#signalBadge').className='signalBadge neutral';$('#signalBadge').textContent='NO ANALYSIS';$('#signalQuality').textContent='—';
  $('#plan').className='plan muted';$('#plan').textContent=`${symbol} ${timeframe} selected. Press NEW ANALYZE to request fresh data, or RE-EVALUATE an existing signal.`;
  ['#mapRegime','#mapAdx','#mapVwap','#mapBullOb','#mapBearOb','#mapFvg','#mapEq','#mapDiv','#buyScoreTop','#sellScoreTop'].forEach(id=>$(id).textContent='—');
  if($('#mapRisk')){$('#mapRisk').textContent='—';$('#mapRisk').className=''}
  $('#analysisStatusHeading').textContent='ANALYSIS STATUS';
  $('#explanation').className='detailText muted';$('#explanation').textContent='Manual selection only • no market/API request has been made.';
  $('#reasons').className='detailText';$('#reasons').textContent='—';$('#topSetups').textContent='No ranking yet.';
  chartDecision=null;updateSignalHeadline(null);clearSignalLevels();
}
function normalizeSupportedTimeframeV554(){
  if(timeframe==='20m'){
    timeframe='15m';
    const sel=$('#timeframe');if(sel)sel.value='15m';
  }
}
async function contextChanged(){
  normalizeSupportedTimeframeV554();
  loadChart();
  resetViewForContext();
  const feed=$('#nativeFeedStatus');
  if(feed)feed.textContent=`${symbol} ${timeframe} selected • press NEW ANALYZE or RE-EVALUATE`;
}

async function saveBackendSetting(payload){const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw new Error('Could not save setting.');await refreshBackendSettings();return backendSettings}
async function refreshAfterNativeSettings(kind){
  for(let i=0;i<40;i++){
    await new Promise(r=>setTimeout(r,250));
    try{
      await refreshBackendSettings();
      if(kind==='api'&&backendSettings.has_api_key){setDataState('neutralDot','Key saved');return true}
      if(kind==='whatsapp'&&backendSettings.has_whatsapp){setAutoStatus('Signal Link saved','good');return true}
    }catch(_){}
  }
  return false;
}
async function openNativeApiSettings(){
  try{
    const r=await fetch('/api/open-api-settings',{method:'POST'});
    if(!r.ok)throw new Error('Could not open API settings.');
    refreshAfterNativeSettings('api');
  }catch(e){showError('Could not open API Key: '+(e.message||e))}
}
async function openWhatsappSettingsPrompt(){
  try{
    const r=await fetch('/api/open-whatsapp-settings',{method:'POST'});
    if(!r.ok)throw new Error('Could not open Signal Link settings.');
    setAutoStatus('Save Signal Link, then press Get Signal again','warn');
    refreshAfterNativeSettings('whatsapp');
    return false;
  }catch(e){setAutoStatus('Could not open Signal Link','bad');return false}
}

function escapeCalendarTextV545(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderEconomicCalendarV546(root,days){if(!root||!Array.isArray(days)||!days.length)return false;root.innerHTML=days.map(day=>`<div class="calDayV545"><div class="calDateV545">${escapeCalendarTextV545(day.label||day.date)}</div>${(day.events||[]).map(ev=>{const imp=String(ev.impact||'').toLowerCase();return `<div class="calEventV545"><span class="calTimeV545">${escapeCalendarTextV545(ev.time)}</span><span class="calCountryV545">${escapeCalendarTextV545(ev.country)}</span><span class="calImpactV545 ${imp}">${escapeCalendarTextV545(ev.impact)}</span><span class="calTitleV545">${escapeCalendarTextV545(ev.title)}</span></div>`}).join('')}</div>`).join('');return true}
function primeEconomicCalendarV551(){
  const root=$('#economicCalendarLocal');if(!root)return false;
  try{
    const cached=JSON.parse(localStorage.getItem('mh-economic-calendar-stable')||localStorage.getItem('mh-economic-calendar-v546')||localStorage.getItem('mh-economic-calendar-v545')||'null');
    if(cached?.days?.length)return renderEconomicCalendarV546(root,cached.days);
  }catch(_){}
  return !!root.querySelector('.calDayV545');
}
async function loadEconomicCalendarV545(){
  const root=$('#economicCalendarLocal');if(!root)return;
  try{const cached=JSON.parse(localStorage.getItem('mh-economic-calendar-stable')||localStorage.getItem('mh-economic-calendar-v546')||localStorage.getItem('mh-economic-calendar-v545')||'null');if(cached?.days)renderEconomicCalendarV546(root,cached.days)}catch(e){}
  const ctl=new AbortController();const kill=setTimeout(()=>ctl.abort(),3200);
  try{const r=await fetch('/api/economic-calendar',{cache:'no-store',signal:ctl.signal});const j=await r.json();if(!r.ok)throw new Error('Calendar unavailable');const days=Array.isArray(j.days)?j.days:[];if(days.length){renderEconomicCalendarV546(root,days);try{localStorage.setItem('mh-economic-calendar-stable',JSON.stringify({days,at:Date.now()}))}catch(e){}
      savePersistentUICacheV5411({calendar:days});}else if(!root.children.length)root.innerHTML='<div class="calendarLoading">No upcoming calendar events.</div>'}catch(e){if(!root.querySelector('.calDayV545'))root.innerHTML='<div class="calendarLoading">Calendar data refreshing…</div>';setTimeout(loadEconomicCalendarV545,1500)}finally{clearTimeout(kill)}
}
$('#openKey').onclick=openNativeApiSettings;
const supportBtn=$('#openWhatsappTab');if(supportBtn)supportBtn.onclick=async()=>{try{await fetch('/api/open-whatsapp',{method:'POST'})}catch(_){}};
$('#analyze').onclick=runAnalyze;$('#reevaluate').onclick=runReevaluate;$('#autoSignalToggle').onclick=()=>setAutoSignalEnabled(!autoSignalEnabled);const lotBtn=$('#lotSizeToggle');if(lotBtn)lotBtn.onclick=()=>setLotSizeEnabled(!lotSizeEnabled);const ptBtn=$('#partialTpToggle');if(ptBtn)ptBtn.onclick=()=>setPartialTpEnabled(!partialTpEnabled);updateTradeModeButtons();$('#exitApp').onclick=async()=>{try{await fetch('/api/shutdown',{method:'POST'})}catch(e){}window.close()};
$$('.pair').forEach(b=>b.onclick=()=>{$$('.pair').forEach(x=>x.classList.remove('active'));b.classList.add('active');symbol=b.dataset.symbol;contextChanged()});
$('#timeframe').onchange=e=>{timeframe=e.target.value;contextChanged()};

// V55.1 startup: last-known UI values paint BEFORE any awaited backend work.
// This removes the old 2–3 minute blank ticker/calendar caused by waiting for Records/MT5 sync.
primeTickerV549();
primeMovingTickerV547();
renderRecentSignals();
primeEconomicCalendarV551();
setupLightweightChart();setupChartControls();loadChart();
const startupUICacheV551=loadPersistentUICacheV5411().then(()=>{primeTickerV549();renderRecentSignals();primeEconomicCalendarV551()}).catch(()=>false);
loadRecentSignalsV5413().catch(()=>0);
loadEconomicCalendarV545().catch(()=>{});
refreshPublicTicker();
refreshMarketCap();
requestAnimationFrame(()=>refreshPublicTicker());setTimeout(refreshPublicTicker,250);setTimeout(refreshPublicTicker,900);setTimeout(refreshPublicTicker,1800);
// v79.6 credentials are stored by native Windows settings dialogs, not editable HTML fields.
await refreshBackendSettings();
if(backendSettings.has_api_key){setDataState('neutralDot','Key saved')}else setDataState('neutralDot','Access key not saved');
autoSignalEnabled=localStorage.getItem(STORAGE_AUTO)==='1';
void startupUICacheV551;
setInterval(refreshMarketCap,60000);setInterval(refreshPublicTicker,60000);setInterval(loadEconomicCalendarV545,60*60*1000);
if(autoSignalEnabled){stopAutoTimers();const ev=nextFixedAutoEvent(Date.now(),true);if(ev.catchup)scheduleAutoAt('NEW',Date.now()+120);else scheduleAutoAt(ev.action,ev.at<=Date.now()?Date.now()+120:ev.at);}else updateAutoButton();
})();