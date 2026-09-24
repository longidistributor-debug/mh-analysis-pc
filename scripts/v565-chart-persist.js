const fs=require('fs');
const p='web/app.js';
let s=fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n');

const ctxStart=s.indexOf('async function contextChanged(){');
if(ctxStart<0)throw new Error('contextChanged not found');
const ctxEnd=s.indexOf('\n}',ctxStart);
if(ctxEnd<0)throw new Error('contextChanged end not found');
const loadPos=s.indexOf('  loadChart();',ctxStart);
if(loadPos<0||loadPos>ctxEnd)throw new Error('contextChanged loadChart baseline not found');
const replacement=`  // V56.5: keep the last fetched chart visible while pair/timeframe selection changes.\n  // Selection remains API-silent; only NEW ANALYZE / RE-EVALUATE replaces the chart.\n  $$('.nativeTfButtons button').forEach(b=>b.classList.toggle('active',b.dataset.chartTf===timeframe));`;
s=s.slice(0,loadPos)+replacement+s.slice(loadPos+'  loadChart();'.length);

const newStart=s.indexOf('async function executeNewAnalysis(fromAuto=false){');
if(newStart<0)throw new Error('executeNewAnalysis not found');
const newGuard='  if(busy)return null;';
const newGuardPos=s.indexOf(newGuard,newStart);
if(newGuardPos<0)throw new Error('NEW ANALYZE busy guard not found');
const newInsert=newGuardPos+newGuard.length;
if(!s.slice(newInsert,newInsert+12).startsWith('loadChart();'))s=s.slice(0,newInsert)+'loadChart();'+s.slice(newInsert);

const reStart=s.indexOf('async function executeReevaluate(fromAuto=false){');
if(reStart<0)throw new Error('executeReevaluate not found');
const reBusy=s.indexOf('  busy=true;setBusy',reStart);
if(reBusy<0)throw new Error('RE-EVALUATE active-fetch block not found');
const before=s.slice(Math.max(reStart,reBusy-30),reBusy);
if(!/loadChart\(\);\s*$/.test(before))s=s.slice(0,reBusy)+'  loadChart();\n'+s.slice(reBusy);

fs.writeFileSync(p,s,'utf8');

const check=fs.readFileSync(p,'utf8');
if(!check.includes('V56.5: keep the last fetched chart visible'))throw new Error('V56.5 marker missing');
const c1=check.indexOf('async function contextChanged(){');
const c2=check.indexOf('\n}',c1);
const context=check.slice(c1,c2);
if(context.includes('loadChart();'))throw new Error('Selection still clears chart');
if(/await\s+fetchCandles\s*\(|loadContextChart\s*\(|refreshMarketCap\s*\(\s*\)/.test(context))throw new Error('Selection must remain API-silent');
if(!check.includes('if(busy)return null;loadChart();autoActionStartedAt=Date.now()'))throw new Error('NEW ANALYZE chart replacement marker missing');
const re=check.slice(check.indexOf('async function executeReevaluate(fromAuto=false){'));
if(!re.includes('loadChart();\n  busy=true;setBusy'))throw new Error('RE-EVALUATE chart replacement marker missing');
console.log('V56.5 chart persistence patch applied');
