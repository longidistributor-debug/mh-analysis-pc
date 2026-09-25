const fs=require('fs');
const p='web/app.js';
let s=fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n');
function must(n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

const marker='function empiricalDistanceModel(c,dir,s){';
must(marker,'advanced strategy insertion');
if(!s.includes('function v568AdvancedFamilies(c,m,s)')){
const add=`
// V56.8: six video-reference upgrades plus deeper rule-based SMC/ICT confirmation.
// These use only the already-fetched selected-timeframe candles; no extra history/API request is made.
function v568RecentSweep(c,side,s,lookback=5){
  const tr=Math.max(Number(s?.trMedian)||0,1e-9),start=Math.max(20,c.length-lookback);
  let best=null;
  for(let i=start;i<c.length;i++){
    const prior=c.slice(Math.max(0,i-24),i); if(prior.length<8)continue;
    const x=c[i];
    if(side==='LOW'){
      const level=Math.min(...prior.map(z=>z.l));
      if(x.l<level&&x.c>level){const pen=(level-x.l)/tr,reclaim=(x.c-level)/tr,str=Math.min(1,pen*.65+reclaim*.9+.2);if(!best||str>best.strength)best={index:i,level,strength:str,bar:x};}
    }else{
      const level=Math.max(...prior.map(z=>z.h));
      if(x.h>level&&x.c<level){const pen=(x.h-level)/tr,reclaim=(level-x.c)/tr,str=Math.min(1,pen*.65+reclaim*.9+.2);if(!best||str>best.strength)best={index:i,level,strength:str,bar:x};}
    }
  }
  return best;
}
function v568LiquidityState(c,m,s){
  const sp=adaptiveSpan(c.length),tr=Math.max(s.trMedian,1e-9),hs=pivots(c,true,sp),ls=pivots(c,false,sp),last=c.at(-1),tol=tr*.22;
  const recentH=hs.filter(x=>x.index>=c.length-140),recentL=ls.filter(x=>x.index>=c.length-140);
  const strength=(arr,p)=>arr.reduce((n,x)=>n+(Math.abs(x.price-p)<=tol?1:0),0);
  const highs=[...recentH].sort((a,b)=>a.price-b.price),lows=[...recentL].sort((a,b)=>a.price-b.price);
  const extHigh=highs.length?highs.at(-1).price:null,extLow=lows.length?lows[0].price:null;
  const above=highs.filter(x=>x.price>last.c),below=lows.filter(x=>x.price<last.c);
  const intHigh=above.length?above[0].price:null,intLow=below.length?below.at(-1).price:null;
  const highTarget=intHigh??extHigh??m.equalHigh??null,lowTarget=intLow??extLow??m.equalLow??null;
  return{hs:recentH,ls:recentL,extHigh,extLow,intHigh,intLow,highTarget,lowTarget,
    highStrength:highTarget==null?0:Math.min(1,strength(recentH,highTarget)/3+(m.equalHigh&&Math.abs(m.equalHigh-highTarget)<=tol?.35:0)),
    lowStrength:lowTarget==null?0:Math.min(1,strength(recentL,lowTarget)/3+(m.equalLow&&Math.abs(m.equalLow-lowTarget)<=tol?.35:0))};
}
function v568ImpulseBaseFamilies(c,m,s){
  const tr=Math.max(s.trMedian,1e-9),w=c.slice(-14); if(w.length<10)return[];
  let bestBull=0,bestBear=0,bullWhy='No qualified exhaustion/base reclaim',bearWhy='No qualified exhaustion/base rejection';
  for(let split=5;split<=9;split++){
    const imp=w.slice(Math.max(0,split-4),split),base=w.slice(split,Math.min(w.length,split+4)),conf=w.slice(Math.min(w.length,split+3)); if(imp.length<3||base.length<2||!conf.length)continue;
    const move=imp.at(-1).c-imp[0].o,mag=Math.abs(move)/tr,baseHi=Math.max(...base.map(x=>x.h)),baseLo=Math.min(...base.map(x=>x.l)),baseSpan=(baseHi-baseLo)/tr,compact=Math.max(0,1-Math.min(1,baseSpan/Math.max(mag,1e-9))),last=conf.at(-1);
    if(move<0){const failed=Math.min(...conf.map(x=>x.l))<=baseLo,rec=(last.c-baseLo)/tr,score=Math.min(1,Math.max(0,(mag-1.2)/2.2)*.45+compact*.25+(failed?.1:0)+Math.max(0,Math.min(.2,rec*.14)));if(score>bestBull){bestBull=score;bullWhy='Bearish impulse exhausted into a compact base, then price reclaimed the base';}}
    if(move>0){const failed=Math.max(...conf.map(x=>x.h))>=baseHi,rej=(baseHi-last.c)/tr,score=Math.min(1,Math.max(0,(mag-1.2)/2.2)*.45+compact*.25+(failed?.1:0)+Math.max(0,Math.min(.2,rej*.14)));if(score>bestBear){bestBear=score;bearWhy='Bullish impulse exhausted into a compact base, then price rejected the base';}}
  }
  return[fam('BUY','Video: impulse exhaustion + base reclaim',38+bestBull*57,[bullWhy,'Pattern confidence '+Math.round(bestBull*100)+'%']),fam('SELL','Video: impulse exhaustion + base rejection',38+bestBear*57,[bearWhy,'Pattern confidence '+Math.round(bestBear*100)+'%'])];
}
function v568LiquidityHierarchyFamilies(c,m,s){
  const q=v568LiquidityState(c,m,s),last=c.at(-1),bullSweep=v568RecentSweep(c,'LOW',s),bearSweep=v568RecentSweep(c,'HIGH',s),tr=Math.max(s.trMedian,1e-9);
  const hd=q.highTarget==null?9:Math.abs(q.highTarget-last.c)/tr,ld=q.lowTarget==null?9:Math.abs(last.c-q.lowTarget)/tr;
  const buyTarget=Math.max(0,1-Math.min(1,Math.abs(hd-2.5)/4)),sellTarget=Math.max(0,1-Math.min(1,Math.abs(ld-2.5)/4));
  return[fam('BUY','Liquidity hierarchy: internal → external BSL',44+(bullSweep?.strength||0)*24+q.highStrength*17+buyTarget*10,['Next buy-side pool '+(q.intHigh!=null?'internal':'external')+' • strength '+Math.round(q.highStrength*100)+'%',bullSweep?'Sell-side pool was swept/reclaimed':'No fresh sell-side sweep required']),fam('SELL','Liquidity hierarchy: internal → external SSL',44+(bearSweep?.strength||0)*24+q.lowStrength*17+sellTarget*10,['Next sell-side pool '+(q.intLow!=null?'internal':'external')+' • strength '+Math.round(q.lowStrength*100)+'%',bearSweep?'Buy-side pool was swept/rejected':'No fresh buy-side sweep required'])];
}
function v568LiquidityTargetFamilies(c,m,s){
  const q=v568LiquidityState(c,m,s),last=c.at(-1),tr=Math.max(s.trMedian,1e-9),bs=v568RecentSweep(c,'LOW',s),ss=v568RecentSweep(c,'HIGH',s);
  const bDist=q.highTarget==null?99:(q.highTarget-last.c)/tr,sDist=q.lowTarget==null?99:(last.c-q.lowTarget)/tr;
  const bReach=bDist>0&&bDist<7?1-Math.abs(Math.min(6,bDist)-2.8)/6:0,sReach=sDist>0&&sDist<7?1-Math.abs(Math.min(6,sDist)-2.8)/6:0;
  return[fam('BUY','Liquidity target sequencing / draw on BSL',40+(bs?.strength||0)*30+Math.max(0,bReach)*25,[q.highTarget!=null?'Next valid BSL objective '+two(bDist)+' median ranges away':'No valid BSL objective',bs?'Opposite SSL was already raided':'Awaiting stronger SSL raid/reclaim']),fam('SELL','Liquidity target sequencing / draw on SSL',40+(ss?.strength||0)*30+Math.max(0,sReach)*25,[q.lowTarget!=null?'Next valid SSL objective '+two(sDist)+' median ranges away':'No valid SSL objective',ss?'Opposite BSL was already raided':'Awaiting stronger BSL raid/rejection'])];
}
function v568InducementFamilies(c,m,s){
  const q=v568LiquidityState(c,m,s),last=c.at(-1),tr=Math.max(s.trMedian,1e-9),bs=v568RecentSweep(c,'LOW',s,7),ss=v568RecentSweep(c,'HIGH',s,7);
  const internalLow=q.intLow,internalHigh=q.intHigh,externalHigh=q.extHigh,externalLow=q.extLow;
  const bullInd=bs&&internalLow!=null&&Math.abs(bs.level-internalLow)<=tr*1.1&&externalHigh!=null&&externalHigh>last.c;
  const bearInd=ss&&internalHigh!=null&&Math.abs(ss.level-internalHigh)<=tr*1.1&&externalLow!=null&&externalLow<last.c;
  const bullRoom=externalHigh==null?0:Math.max(0,Math.min(1,(externalHigh-last.c)/(tr*5))),bearRoom=externalLow==null?0:Math.max(0,Math.min(1,(last.c-externalLow)/(tr*5)));
  return[fam('BUY','ICT/SMC: inducement taken before external BSL',42+(bullInd?36:0)+bullRoom*17,[bullInd?'Internal sell-side inducement was taken and reclaimed':'No confirmed internal inducement take',externalHigh!=null?'External BSL remains available':'No external BSL mapped']),fam('SELL','ICT/SMC: inducement taken before external SSL',42+(bearInd?36:0)+bearRoom*17,[bearInd?'Internal buy-side inducement was taken and rejected':'No confirmed internal inducement take',externalLow!=null?'External SSL remains available':'No external SSL mapped'])];
}
function v568ParentRangeFamilies(c,m,s){
  const tf=String(timeframe||'15m').toLowerCase(),n=({'1m':15,'5m':12,'15m':8,'30m':6,'1h':4}[tf]||8),hist=c.slice(-(n+1),-1),last=c.at(-1); if(hist.length<3)return[];
  const hi=Math.max(...hist.map(x=>x.h)),lo=Math.min(...hist.map(x=>x.l)),mid=(hi+lo)/2,rng=Math.max(hi-lo,1e-9),pos=Math.max(0,Math.min(1,(last.c-lo)/rng)),lowSweep=last.l<lo&&last.c>lo,highSweep=last.h>hi&&last.c<hi;
  const bullAlign=(1-pos)*.38+(lowSweep?.42:0)+(last.c>mid?.2:0),bearAlign=pos*.38+(highSweep?.42:0)+(last.c<mid?.2:0);
  return[fam('BUY','Parent-range alignment: discount / low sweep',40+Math.min(1,bullAlign)*55,['Synthetic parent ('+n+' '+tf+' bars) position '+Math.round(pos*100)+'%',lowSweep?'Parent low swept and reclaimed':last.c>mid?'Price reclaimed parent equilibrium':'Price remains in parent discount']),fam('SELL','Parent-range alignment: premium / high sweep',40+Math.min(1,bearAlign)*55,['Synthetic parent ('+n+' '+tf+' bars) position '+Math.round(pos*100)+'%',highSweep?'Parent high swept and rejected':last.c<mid?'Price lost parent equilibrium':'Price remains in parent premium'])];
}
function v568SweepConfirmationFamilies(c,m,s){
  const tr=Math.max(s.trMedian,1e-9),b=v568RecentSweep(c,'LOW',s,5),x=v568RecentSweep(c,'HIGH',s,5),last=c.at(-1);
  const confirm=(sw,dir)=>{if(!sw)return 0;const after=c.slice(sw.index+1);if(!after.length)return sw.index===c.length-1?sw.strength*.35:0;const bodies=after.map(z=>Math.abs(z.c-z.o)/tr),disp=Math.min(1,Math.max(...bodies)/1.25),progress=dir==='BUY'?(last.c-sw.bar.c)/tr:(sw.bar.c-last.c)/tr,prog=Math.max(0,Math.min(1,progress/1.2));return Math.min(1,sw.strength*.45+disp*.3+prog*.25)};
  const bc=confirm(b,'BUY'),sc=confirm(x,'SELL');
  return[fam('BUY','Multi-candle sweep confirmation',40+bc*55,[b?'SSL sweep confirmed across '+(c.length-b.index)+' candle(s)':'No recent SSL sweep','Reclaim/displacement confirmation '+Math.round(bc*100)+'%']),fam('SELL','Multi-candle sweep confirmation',40+sc*55,[x?'BSL sweep confirmed across '+(c.length-x.index)+' candle(s)':'No recent BSL sweep','Rejection/displacement confirmation '+Math.round(sc*100)+'%'])];
}
function v568AdvancedFamilies(c,m,s){return[...v568ImpulseBaseFamilies(c,m,s),...v568LiquidityHierarchyFamilies(c,m,s),...v568LiquidityTargetFamilies(c,m,s),...v568InducementFamilies(c,m,s),...v568ParentRangeFamilies(c,m,s),...v568SweepConfirmationFamilies(c,m,s)]}
function v568EnhancedSmcIctFamilies(c,m,s){
  const sp=adaptiveSpan(c.length),hs=pivots(c,true,sp),ls=pivots(c,false,sp),last=c.at(-1),tr=Math.max(s.trMedian,1e-9),bs=v568RecentSweep(c,'LOW',s,7),ss=v568RecentSweep(c,'HIGH',s,7),out=[];
  const recentHigh=hs.filter(x=>x.index<(bs?.index??c.length)).at(-1)?.price,recentLow=ls.filter(x=>x.index<(ss?.index??c.length)).at(-1)?.price;
  const bullMss=!!(bs&&recentHigh!=null&&last.c>recentHigh),bearMss=!!(ss&&recentLow!=null&&last.c<recentLow);
  const body=Math.abs(last.c-last.o)/tr,disp=Math.max(0,Math.min(1,body/1.25));
  out.push(fam('BUY','SMC/ICT: protected swing MSS + displacement',43+(bullMss?34:0)+disp*18,[bullMss?'SSL raid followed by bullish market-structure shift':'No fully confirmed bullish MSS','Current displacement '+Math.round(disp*100)+'%']));
  out.push(fam('SELL','SMC/ICT: protected swing MSS + displacement',43+(bearMss?34:0)+disp*18,[bearMss?'BSL raid followed by bearish market-structure shift':'No fully confirmed bearish MSS','Current displacement '+Math.round(disp*100)+'%']));
  const overlap=(a,b,c1,d)=>a!=null&&b!=null&&c1!=null&&d!=null?Math.max(0,Math.min(b,d)-Math.max(a,c1)):0;
  const bullOv=overlap(m.bullObLow,m.bullObHigh,m.fvgType==='BULLISH'?m.fvgLow:null,m.fvgType==='BULLISH'?m.fvgHigh:null),bearOv=overlap(m.bearObLow,m.bearObHigh,m.fvgType==='BEARISH'?m.fvgLow:null,m.fvgType==='BEARISH'?m.fvgHigh:null);
  const bullCon=Math.min(1,bullOv/tr),bearCon=Math.min(1,bearOv/tr);
  out.push(fam('BUY','ICT PD-array confluence: OB + FVG + displacement',42+bullCon*34+disp*16,[bullOv>0?'Bullish OB/FVG overlap is active':'No bullish OB/FVG overlap','Displacement confirmation '+Math.round(disp*100)+'%']));
  out.push(fam('SELL','ICT PD-array confluence: OB + FVG + displacement',42+bearCon*34+disp*16,[bearOv>0?'Bearish OB/FVG overlap is active':'No bearish OB/FVG overlap','Displacement confirmation '+Math.round(disp*100)+'%']));
  return out;
}

`;
s=s.replace(marker,add+marker);
}

const old='...smcIctFamilies(c,m,s),...videoFamilies(c,m,s)';
const neu='...smcIctFamilies(c,m,s),...videoFamilies(c,m,s),...v568AdvancedFamilies(c,m,s),...v568EnhancedSmcIctFamilies(c,m,s)';
if(!s.includes(neu)){
  const count=s.split(old).length-1;
  if(count<2)throw new Error('expected both analysis family lists');
  s=s.split(old).join(neu);
}

s=s.replace('SMC/ICT, structure, liquidity, momentum and video-reference evidence were ranked together.','SMC/ICT, advanced liquidity hierarchy, inducement, parent-range, sweep confirmation, structure, momentum and video-reference evidence were ranked together.');
fs.writeFileSync(p,s,'utf8');
console.log('V56.8 advanced strategy patch applied');
