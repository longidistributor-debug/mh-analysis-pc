(()=>{
'use strict';
let busy=false,timer=0;
function ensureNotice(){let n=document.getElementById('mhLoginNavNotice');if(n)return n;n=document.createElement('div');n.id='mhLoginNavNotice';n.className='mhLoginNavNotice';const card=document.querySelector('.mhLicenseCard');if(card)card.appendChild(n);return n}
async function poll(){if(busy)return;const overlay=document.getElementById('mhLicenseOverlay');if(!overlay||!overlay.classList.contains('show'))return;busy=true;try{const r=await fetch('/api/license/nav-notice',{cache:'no-store'});if(!r.ok)return;const j=await r.json();if(j.notice&&j.message){const n=ensureNotice();n.textContent=j.message+' Please enter your username and password.';n.classList.add('show');clearTimeout(timer);timer=setTimeout(()=>n.classList.remove('show'),1800)}}catch{}finally{busy=false}}
setInterval(poll,350);
})();
