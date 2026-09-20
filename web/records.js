(()=>{
'use strict';
const $=s=>document.querySelector(s);
let records=[];
let selectedDate='';
let monthCursor=new Date();monthCursor.setDate(1);
let filterFrom='';
let filterTo='';
let filterTF='all';

const pad=n=>String(n).padStart(2,'0');
const dateKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const todayKey=()=>dateKey(new Date());
const fmtNum=v=>{const n=Number(v);if(!Number.isFinite(n))return'—';return Math.abs(n)>=100?n.toFixed(2):n.toFixed(5)};
const fmtPL=v=>{const n=Number(v);if(!Number.isFinite(n))return'—';return `${n>0?'+':''}${n.toFixed(2)}`};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const timeLabel=t=>{if(!t)return'—';try{return new Date(Number(t)*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}catch{return'—'}};
const isCurrentMonth=d=>{const n=new Date();return d.getFullYear()===n.getFullYear()&&d.getMonth()===n.getMonth()};
const monthAfterCurrent=d=>{const n=new Date();return d.getFullYear()>n.getFullYear()||(d.getFullYear()===n.getFullYear()&&d.getMonth()>n.getMonth())};

function resultClass(x){
  const s=String(x.status||'').toUpperCase();
  if(s==='TP HIT'||s==='MANUAL +POSITIVE'||s==='CLOSED +POSITIVE')return'WIN';
  if(s==='SL HIT'||s==='MANUAL -NEGATIVE'||s==='CLOSED -NEGATIVE')return'LOSS';
  if(s==='BREAK EVEN'||s==='MANUAL BREAK EVEN')return'BE';
  return'';
}
function subsetSummary(list){
  const s={total_signals:list.length,orders_placed:0,activated:0,wins:0,losses:0,break_even:0,manual_close:0,cancelled:0,pending:0,accuracy:0};
  for(const x of list){
    if(Number(x.pending_placed_at)>0||Number(x.order_ticket)>0)s.orders_placed++;
    if(Number(x.activated_at)>0||Number(x.entry_at)>0||Number(x.position_id)>0)s.activated++;
    if(x.manual_close)s.manual_close++;
    if(x.cancelled)s.cancelled++;
    const r=resultClass(x);if(r==='WIN')s.wins++;else if(r==='LOSS')s.losses++;else if(r==='BE')s.break_even++;
  }
  const closed=s.wins+s.losses+s.break_even;
  s.accuracy=closed?Math.round((s.wins*1000)/closed)/10:0;
  s.pending=Math.max(0,s.total_signals-s.wins-s.losses-s.break_even-s.cancelled);
  return s;
}
function statCard(label,value,cls=''){return `<div class="statCard ${cls}"><small>${label}</small><b>${value}</b></div>`}
function filteredRecords(){
  return records.filter(x=>{
    const d=String(x.local_date||'');
    if(filterFrom&&d<filterFrom)return false;
    if(filterTo&&d>filterTo)return false;
    if(filterTF!=='all'&&String(x.timeframe)!==filterTF)return false;
    return true;
  });
}
function renderRangeInfo(){
  const parts=[];
  if(filterFrom||filterTo)parts.push(`${filterFrom||'START'} → ${filterTo||todayKey()}`);else parts.push('ALL SAVED DATES');
  parts.push(filterTF==='all'?'ALL TIMEFRAMES':filterTF.toUpperCase());
  const n=filteredRecords().length;parts.push(`${n} SIGNAL${n===1?'':'S'}`);
  $('#rangeInfo').textContent=parts.join(' • ');
}
function renderOverall(){
  const s=subsetSummary(filteredRecords());
  $('#overallStats').innerHTML=[
    statCard('TOTAL SIGNALS',s.total_signals,'cyan'),
    statCard('ORDERS PLACED',s.orders_placed),
    statCard('ACTIVATED',s.activated),
    statCard('WINS',s.wins,'green'),
    statCard('LOSSES',s.losses,'red'),
    statCard('BREAK EVEN',s.break_even,'gold'),
    statCard('MANUAL CLOSE',s.manual_close,'cyan'),
    statCard('CANCELLED',s.cancelled,'red'),
    statCard('PENDING',s.pending),
    statCard('ACCURACY',`${Number(s.accuracy||0).toFixed(1)}%`,'gold')
  ].join('');
  renderRangeInfo();
}
function monthRecords(){
  const y=monthCursor.getFullYear(),m=monthCursor.getMonth();
  return filteredRecords().filter(x=>{const d=new Date(`${x.local_date}T00:00:00`);return d.getFullYear()===y&&d.getMonth()===m});
}
function renderCalendar(){
  if(monthAfterCurrent(monthCursor)){const n=new Date();monthCursor=new Date(n.getFullYear(),n.getMonth(),1)}
  const y=monthCursor.getFullYear(),m=monthCursor.getMonth(),today=todayKey();
  $('#monthTitle').textContent=monthCursor.toLocaleDateString([],{month:'long',year:'numeric'}).toUpperCase();
  $('#nextMonth').disabled=isCurrentMonth(monthCursor);
  const first=new Date(y,m,1),days=new Date(y,m+1,0).getDate(),offset=first.getDay();
  const byDay={};for(const x of monthRecords())(byDay[x.local_date]??=[]).push(x);
  const cells=[];for(let i=0;i<offset;i++)cells.push('<div class="calendarCell blank"></div>');
  for(let d=1;d<=days;d++){
    const k=`${y}-${pad(m+1)}-${pad(d)}`,list=byDay[k]||[],s=subsetSummary(list),isToday=k===today,sel=k===selectedDate,future=k>today;
    const checked=list.filter(x=>x.last_mt5_event||x.last_checked_at).length;
    cells.push(`<button class="calendarCell ${list.length?'hasSignals':''} ${isToday?'today':''} ${sel?'selected':''} ${future?'futureDay':''}" data-day="${k}" type="button" ${future?'disabled':''}><span class="dayNum">${d}</span><span class="dayMeta"><span class="count">${list.length?`${list.length} SIGNAL${list.length===1?'':'S'}`:''}</span><span class="outcomes">${checked?`${s.wins}W • ${s.losses}L • ${s.break_even}BE`:''}</span></span></button>`);
  }
  $('#calendarGrid').innerHTML=cells.join('');
  document.querySelectorAll('[data-day]:not([disabled])').forEach(b=>b.addEventListener('click',()=>{selectedDate=b.dataset.day;renderCalendar();renderDay()}));
}
function statusClass(s){
  s=String(s||'').toUpperCase();
  if(s==='TP HIT'||s.includes('+POSITIVE'))return'tp';
  if(s==='SL HIT'||s.includes('-NEGATIVE')||s.includes('REJECTED'))return'sl';
  if(s.includes('BREAK EVEN'))return'be';
  if(s.includes('CANCEL')||s.includes('EXPIRED'))return'amb';
  if(s==='OPEN'||s.includes('PARTIAL')||s==='PENDING PLACED')return'open';
  return'wait';
}
function renderDay(){
  if(!selectedDate)selectedDate=todayKey();
  const list=filteredRecords().filter(x=>x.local_date===selectedDate).sort((a,b)=>b.created_at-a.created_at),s=subsetSummary(list);
  const date=new Date(`${selectedDate}T00:00:00`);
  $('#selectedDayTitle').textContent=date.toLocaleDateString([],{weekday:'long',day:'2-digit',month:'long',year:'numeric'}).toUpperCase();
  $('#dayAccuracy').innerHTML=`${Number(s.accuracy||0).toFixed(1)}%<small>DAY ACCURACY</small>`;
  $('#dayStats').innerHTML=[
    `<div class="dayStat"><small>SIGNALS</small><b>${s.total_signals}</b></div>`,
    `<div class="dayStat"><small>PLACED</small><b>${s.orders_placed}</b></div>`,
    `<div class="dayStat"><small>ACTIVATED</small><b>${s.activated}</b></div>`,
    `<div class="dayStat win"><small>WINS</small><b>${s.wins}</b></div>`,
    `<div class="dayStat loss"><small>LOSSES</small><b>${s.losses}</b></div>`,
    `<div class="dayStat be"><small>BREAK EVEN</small><b>${s.break_even}</b></div>`,
    `<div class="dayStat"><small>MANUAL</small><b>${s.manual_close}</b></div>`,
    `<div class="dayStat loss"><small>CANCELLED</small><b>${s.cancelled}</b></div>`,
    `<div class="dayStat"><small>PENDING</small><b>${s.pending}</b></div>`
  ].join('');
  const tfs=['1m','5m','15m','30m','1h'];
  $('#timeframeBreakdown').innerHTML=tfs.map(tf=>`<div class="tfBox"><b>${list.filter(x=>x.timeframe===tf).length}</b><span>${tf.toUpperCase()}</span></div>`).join('');
  $('#tradeListTitle').textContent=`${date.toLocaleDateString([],{day:'2-digit',month:'short',year:'numeric'})} • SIGNALS`;
  $('#tradeCountPill').textContent=`${list.length} SIGNAL${list.length===1?'':'S'}`;
  const tbody=$('#tradeRows');
  tbody.innerHTML=list.map(x=>{
    const closed=Number(x.closed_at)>0||resultClass(x)||x.cancelled;
    const pl=closed&&!x.cancelled?fmtPL(x.realized_profit):'—';
    const manual=x.manual_close?(String(x.manual_result||'YES').replace('_',' ')):'—';
    return `<tr title="${esc(x.note||'')}"><td>${esc(x.local_time||timeLabel(x.created_at))}</td><td>${esc(x.symbol)}</td><td>${esc(x.timeframe)}</td><td class="${x.direction==='BUY'?'sigBuy':'sigSell'}">${esc(x.direction)}</td><td>${fmtNum(x.entry)}</td><td>${fmtNum(x.sl)}</td><td>${fmtNum(x.tp1)}</td><td>${fmtNum(x.tp2)}</td><td>${Math.round(Number(x.score)||0)}/100</td><td><span class="resultPill ${statusClass(x.status)}">${esc(x.status||'SIGNAL GENERATED')}</span></td><td class="${Number(x.realized_profit)>0?'plPos':Number(x.realized_profit)<0?'plNeg':''}">${pl}</td><td>${esc(manual)}</td><td>${x.last_checked_at?timeLabel(x.last_checked_at):'—'}</td></tr>`;
  }).join('');
  $('#emptyDay').classList.toggle('show',!list.length);
}
function chooseInitialDay(){
  const visible=filteredRecords();
  if(visible.some(x=>x.local_date===todayKey())){selectedDate=todayKey();return}
  if(visible.length){selectedDate=visible[0].local_date;const d=new Date(`${selectedDate}T00:00:00`);monthCursor=new Date(d.getFullYear(),d.getMonth(),1);return}
  selectedDate=todayKey();
}
function renderAll(){renderOverall();renderCalendar();renderDay()}
async function loadRecords(preserve=true){
  try{
    const r=await fetch('/api/records-v2',{cache:'no-store'});if(!r.ok)throw new Error(`Records ${r.status}`);
    const j=await r.json();records=Array.isArray(j.records)?j.records:[];
    if(!preserve||!selectedDate)chooseInitialDay();
    renderAll();
    const msg=j.warning?`Local MT5 sync warning: ${j.warning}`:`Local MT5 synced • ${j.events_matched||0}/${j.events_read||0} event rows matched • 0 external market API calls.`;
    $('#checkState').className=`checkState ${j.warning?'warn':'good'}`;$('#checkState').textContent=msg;
    $('#lastRefresh').textContent=`Records refreshed ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;
  }catch(e){$('#checkState').className='checkState bad';$('#checkState').textContent=`Records unavailable: ${e.message}`}
}
async function runSync(){
  const b=$('#syncBtn'),state=$('#checkState');b.disabled=true;b.textContent='SYNCING MT5…';state.className='checkState';state.textContent='Reading local MT5 trade events • no market API request.';
  try{
    const r=await fetch('/api/records-v2/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),j=await r.json();
    if(!r.ok)throw new Error(j.error||`Sync ${r.status}`);
    records=Array.isArray(j.records)?j.records:records;renderAll();
    state.className='checkState good';state.textContent=`MT5 synced • ${j.events_matched||0}/${j.events_read||0} event rows matched • 0 external market API calls.`;
  }catch(e){state.className='checkState bad';state.textContent=e.message}
  finally{b.disabled=false;b.textContent='↻ SYNC MT5'}
}
function applyFilters(){
  const from=$('#fromDate').value,to=$('#toDate').value,tf=$('#tfFilter').value||'all';
  if(from&&to&&from>to){$('#checkState').className='checkState bad';$('#checkState').textContent='FROM date cannot be after TO date.';return}
  filterFrom=from;filterTo=to;filterTF=tf;
  if(filterTo&&filterTo>todayKey())filterTo=todayKey();
  if(filterFrom){const d=new Date(`${filterFrom}T00:00:00`);monthCursor=new Date(d.getFullYear(),d.getMonth(),1)}
  chooseInitialDay();renderAll();
}
function resetFilters(){
  filterFrom='';filterTo='';filterTF='all';$('#fromDate').value='';$('#toDate').value='';$('#tfFilter').value='all';
  const n=new Date();monthCursor=new Date(n.getFullYear(),n.getMonth(),1);selectedDate=todayKey();renderAll();
}
async function resetSelectedRecords(){
  let payload,label;
  if(filterFrom||filterTo){payload={from:filterFrom,to:filterTo,timeframe:filterTF};label=`${filterFrom||'START'} → ${filterTo||todayKey()}${filterTF!=='all'?` • ${filterTF.toUpperCase()}`:''}`}
  else{payload={date:selectedDate,timeframe:filterTF};label=`${selectedDate}${filterTF!=='all'?` • ${filterTF.toUpperCase()}`:''}`}
  if(!confirm(`Delete saved Records for ${label}?\n\nThis resets MH Analysis records only. It does not delete MT5 account history.`))return;
  const b=$('#resetRecords');b.disabled=true;
  try{
    const r=await fetch('/api/records-v2/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),j=await r.json();
    if(!r.ok)throw new Error(j.error||`Reset ${r.status}`);
    records=Array.isArray(j.records)?j.records:records;renderAll();
    $('#checkState').className='checkState good';$('#checkState').textContent=`Reset complete • ${j.deleted||0} saved record(s) deleted.`;
  }catch(e){$('#checkState').className='checkState bad';$('#checkState').textContent=e.message}
  finally{b.disabled=false}
}

const max=todayKey();$('#fromDate').max=max;$('#toDate').max=max;
$('#syncBtn').addEventListener('click',runSync);
$('#applyFilter').addEventListener('click',applyFilters);
$('#resetFilter').addEventListener('click',resetFilters);
$('#resetRecords').addEventListener('click',resetSelectedRecords);
$('#prevMonth').addEventListener('click',()=>{monthCursor=new Date(monthCursor.getFullYear(),monthCursor.getMonth()-1,1);renderCalendar()});
$('#nextMonth').addEventListener('click',()=>{if(isCurrentMonth(monthCursor))return;monthCursor=new Date(monthCursor.getFullYear(),monthCursor.getMonth()+1,1);if(monthAfterCurrent(monthCursor)){const n=new Date();monthCursor=new Date(n.getFullYear(),n.getMonth(),1)}renderCalendar()});
$('#todayMonth').addEventListener('click',()=>{const n=new Date();monthCursor=new Date(n.getFullYear(),n.getMonth(),1);selectedDate=todayKey();renderCalendar();renderDay()});
loadRecords(false);
setInterval(()=>loadRecords(true),5000);
})();
