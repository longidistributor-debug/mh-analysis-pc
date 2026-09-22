const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
const start=source.indexOf('async function handoffNewSignalV27');
const end=source.indexOf('async function executeNewAnalysis',start);
async function run(saved,signal=true){
 const calls=[];
 const ctx={crypto:{randomUUID:()=> 'test-27'},symbol:'XAUUSD',timeframe:'15m',keyFor:()=> 'XAUUSD|15m',candleCache:new Map([['XAUUSD|15m',[{c:2500}]]]),fetch:async(url,opts)=>{calls.push({url,data:JSON.parse(opts.body)});return{ok:true,json:async()=>calls.length===1?saved:{ok:true}}}};
 vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
 let error;
 try{await ctx.handoffNewSignalV27({signal:signal?{direction:'BUY',entry:2490,sl:2480,tp1:2510,tp2:2520}:null})}catch(e){error=e}
 return {calls,error};
}
(async()=>{
 const good=await run({ok:true,saved:true});assert.equal(good.error,undefined);assert.equal(good.calls.length,2);
 assert.equal(good.calls[0].url,'/api/records-v2/capture');assert.equal(good.calls[1].url,'/api/mt5/ea/send');
 assert.equal(good.calls[0].data.signal_id,good.calls[1].data.signal_id);assert.equal(good.calls[1].data.type,'BUY_LIMIT');
 const failed=await run({ok:true,saved:false});assert.ok(failed.error);assert.equal(failed.calls.length,1);
 const empty=await run({ok:true},false);assert.equal(empty.calls.length,0);
 const reevaluate=source.slice(source.indexOf('async function executeReevaluate'),source.indexOf('async function runAnalyze'));
 assert.ok(!reevaluate.includes('handoffNewSignalV27'));
 const host=fs.readFileSync('webview2_host.go','utf8');
 const navigation=host.slice(host.indexOf('func wv2ShowLocal'),host.indexOf('func wv2ButtonAllowed'));
 assert.ok(!navigation.includes('.Navigate('));
 assert.ok(!host.includes('go mt5ApplyLatestQueued()'));
 console.log('V.27 handoff tests passed: shared ID, records failure blocks EA, no-edge and re-evaluation create no order, navigation preserves pages.');
})().catch(e=>{console.error(e);process.exit(1)});
