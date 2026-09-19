(()=>{
'use strict';
const $=s=>document.querySelector(s);
let records=[];
let summary={};
let selectedDate='';
let monthCursor=new Date();
monthCursor.setDate(1);

const pad=n=>String(n).padStart(2,'0');
const dateKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const todayKey=()=>dateKey(new Date());
const fmtNum=v=>{const n=Number(v);if(!Number.isFinite(n))return'—';return Math.abs(n)>=100?n.toFixed(2):n.toFixed(5)};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const timeLabel=t=>{if(!t)return'—';try{return new Date(Number(t)*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}catch{return'—'}};

function subsetSummary(list){
  const s={total_signals:list.length,total_trades:0,wins:0,losses:0,break_even:0,tp_hits:0,sl_hits:0,ambiguous:0,pending:0,accuracy:0};
  for(const x of list){
    if(x.entry_at)s.total_trades++;
    if(x.tp_hit)s.tp_hits++;
    if(x.sl_hit)s.sl_hits++;
    if(x.status==='TP2 HIT')s.wins++;
    else if(x.status==='SL HIT')s.losses++;
    else if(x.status==='BREAK EVEN')s.break_even++;
    else if(x.status==='AMBIGUOUS')s.ambiguous++;
  }
  const closed=s.wins+s.losses+s.break_even;
  s.accuracy=closed?Math.round((s.wins*1000)/closed)/10:0;
  s.pending=Math.max(0,s.total_signals-s.wins-s.losses-s.break_even-s.ambiguous);
  return s;
}

function statCard(label,value,cls=''){
  return `<div class="statCard ${cls}"><small>${label}</small><b>${value}</b></div>`;
}

function renderOverall(){
  const s=summary||{};
  $('#overallStats').innerHTML=[
    statCard('TOTAL SIGNALS',s.total_signals??0,'cyan'),
    statCard('TOTAL TRADES',s.total_trades??0),
    statCard('WINS',s.wins??0,'green'),
    statCard('LOSSES',s.losses??0,'red'),
    statCard('BREAK EVEN',s.break_even??0,'gold'),
    statCard('TP HITS',s.tp_hits??0,'green'),
    statCard('SL HITS',s.sl_hits??0,'red'),
    statCard('OVERALL ACCURACY',`${Number(s.accuracy||0).toFixed(1)}%`,'gold')
  ].join('');
}

function monthRecords(){
  const y=monthCursor.getFullYear(),m=monthCursor.getMonth();
  return records.filter(x=>{const d=new Date(`${x.local_date}T00:00:00`);return d.getFullYear()===y&&d.getMonth()===m});
}

function renderCalendar(){
  const y=monthCursor.getFullYear(),m=monthCursor.getMonth();
  $('#monthTitle').textContent=monthCursor.toLocaleDateString([],{month:'long',year:'numeric'}).toUpperCase();
  const first=new Date(y,m,1),days=new Date(y,m+1,0).getDate(),offset=first.getDay();
  const byDay={};
  for(const x of monthRecords())(byDay[x.local_date]??=[]).push(x);
  const cells=[];
  for(let i=0;i<offset;i++)cells.push('<div class="calendarCell blank"></div>');
  for(let d=1;d<=days;d++){
    const k=`${y}-${pad(m+1)}-${pad(d)}`,list=byDay[k]||[],s=subsetSummary(list),today=k===todayKey(),sel=k===selectedDate;
    const checked=list.filter(x=>x.last_checked_at).length;
    cells.push(`<button class="calendarCell ${list.length?'hasSignals':''} ${today?'today':''} ${sel?'selected':''}" data-day="${k}" type="button"><span class="dayNum">${d}</span><span class="dayMeta"><span class="count">${list.length?`${list.length} SIGNAL${list.length===1?'':'S'}`:''}</span><span class="outcomes">${checked?`${s.wins}W • ${s.losses}L • ${s.break_even}BE`:''}</span></span></button>`);
  }
  $('#calendarGrid').innerHTML=cells.join('');
  document.querySelectorAll('[data-day]').forEach(b=>b.addEventListener('click',()=>{selectedDate=b.dataset.day;renderCalendar();renderDay()}));
}

function statusClass(s){
  if(s==='TP2 HIT')return'tp';if(s==='SL HIT')return'sl';if(s==='BREAK EVEN')return'be';if(s==='AMBIGUOUS')return'amb';if(s==='OPEN'||s==='TP1 ACTIVE')return'open';return'wait';
}

function renderDay(){
  if(!selectedDate)selectedDate=todayKey();
  const list=records.filter(x=>x.local_date===selectedDate).sort((a,b)=>b.created_at-a.created_at),s=subsetSummary(list);
  const date=new Date(`${selectedDate}T00:00:00`);
  $('#selectedDayTitle').textContent=date.toLocaleDateString([],{weekday:'long',day:'2-digit',month:'long',year:'numeric'}).toUpperCase();
  $('#dayAccuracy').innerHTML=`${Number(s.accuracy||0).toFixed(1)}%<small>DAY ACCURACY</small>`;
  $('#dayStats').innerHTML=[
    `<div class="dayStat"><small>SIGNALS</small><b>${s.total_signals}</b></div>`,
    `<div class="dayStat"><small>TRADES</small><b>${s.total_trades}</b></div>`,
    `<div class="dayStat win"><small>WINS</small><b>${s.wins}</b></div>`,
    `<div class="dayStat loss"><small>LOSSES</small><b>${s.losses}</b></div>`,
    `<div class="dayStat be"><small>BREAK EVEN</small><b>${s.break_even}</b></div>`,
    `<div class="dayStat"><small>PENDING</small><b>${s.pending}</b></div>`
  ].join('');
  const tfs=['1m','5m','15m','30m','1h'];
  $('#timeframeBreakdown').innerHTML=tfs.map(tf=>`<div class="tfBox"><b>${list.filter(x=>x.timeframe===tf).length}</b><span>${tf.toUpperCase()}</span></div>`).join('');
  $('#tradeListTitle').textContent=`${date.toLocaleDateString([],{day:'2-digit',month:'short',year:'numeric'})} • SIGNALS`;
  $('#tradeCountPill').textContent=`${list.length} SIGNAL${list.length===1?'':'S'}`;
  const tbody=$('#tradeRows');
  tbody.innerHTML=list.map(x=>`<tr title="${esc(x.note||'')}"><td>${esc(x.local_time||timeLabel(x.created_at))}</td><td>${esc(x.symbol)}</td><td>${esc(x.timeframe)}</td><td class="${x.direction==='BUY'?'sigBuy':'sigSell'}">${esc(x.direction)}</td><td>${fmtNum(x.entry)}</td><td>${fmtNum(x.sl)}</td><td>${fmtNum(x.tp1)}</td><td>${fmtNum(x.tp2)}</td><td>${Math.round(Number(x.score)||0)}/100</td><td><span class="resultPill ${statusClass(x.status)}">${esc(x.status||'NOT CHECKED')}</span></td><td>${x.last_checked_at?timeLabel(x.last_checked_at):'—'}</td></tr>`).join('');
  $('#emptyDay').classList.toggle('show',!list.length);
}

function chooseInitialDay(){
  if(records.some(x=>x.local_date===todayKey())){selectedDate=todayKey();return}
  if(records.length){selectedDate=records[0].local_date;const d=new Date(`${selectedDate}T00:00:00`);monthCursor=new Date(d.getFullYear(),d.getMonth(),1);return}
  selectedDate=todayKey();
}

async function loadRecords(preserve=true){
  try{
    const r=await fetch('/api/records',{cache:'no-store'});if(!r.ok)throw new Error(`Records ${r.status}`);
    const j=await r.json();records=Array.isArray(j.records)?j.records:[];summary=j.summary||{};
    if(!preserve||!selectedDate)chooseInitialDay();
    renderOverall();renderCalendar();renderDay();
    $('#lastRefresh').textContent=`Records refreshed ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;
  }catch(e){$('#checkState').className='checkState bad';$('#checkState').textContent=`Records unavailable: ${e.message}`}
}

async function runAccuracy(){
  const b=$('#accuracyBtn'),state=$('#checkState');b.disabled=true;b.textContent='CHECKING 1M HISTORY…';state.className='checkState';state.textContent='Checking all unresolved saved signals. No per-signal API calls are made.';
  try{
    const r=await fetch('/api/records/accuracy',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const j=await r.json();if(!r.ok)throw new Error(j.error||`Accuracy ${r.status}`);
    records=Array.isArray(j.records)?j.records:records;summary=j.summary||summary;renderOverall();renderCalendar();renderDay();
    const warnings=Array.isArray(j.warnings)?j.warnings:[];
    if(warnings.length){state.className='checkState warn';state.textContent=`Checked with ${j.api_calls_used||0} market call(s). ${warnings.join(' • ')}`}
    else{state.className='checkState good';state.textContent=`Accuracy updated • ${j.api_calls_used||0} market call(s) • ${(j.checked_symbols||[]).join(', ')||'no unresolved symbols'}.`}
  }catch(e){state.className='checkState bad';state.textContent=e.message}
  finally{b.disabled=false;b.textContent='◎ ACCURACY CHECK'}
}

$('#accuracyBtn').addEventListener('click',runAccuracy);
$('#prevMonth').addEventListener('click',()=>{monthCursor=new Date(monthCursor.getFullYear(),monthCursor.getMonth()-1,1);renderCalendar()});
$('#nextMonth').addEventListener('click',()=>{monthCursor=new Date(monthCursor.getFullYear(),monthCursor.getMonth()+1,1);renderCalendar()});
$('#todayMonth').addEventListener('click',()=>{const n=new Date();monthCursor=new Date(n.getFullYear(),n.getMonth(),1);selectedDate=todayKey();renderCalendar();renderDay()});
loadRecords(false);
setInterval(()=>loadRecords(true),15000);
})();
