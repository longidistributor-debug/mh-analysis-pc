(()=>{
'use strict';
// Block ordinary copy/cut/context-menu/zoom shortcuts while preserving login/settings typing.
const editable=e=>!!e.target.closest('input,textarea,[contenteditable="true"]');
for(const ev of ['copy','cut','contextmenu','dragstart']) document.addEventListener(ev,e=>{if(!editable(e))e.preventDefault()},true);
document.addEventListener('selectstart',e=>{if(!editable(e))e.preventDefault()},true);
document.addEventListener('keydown',e=>{
  if(e.key==='PrintScreen'){e.preventDefault();return;}
  if(!editable(e) && e.ctrlKey && ['c','x','a','+','-','=','0'].includes(e.key.toLowerCase())){e.preventDefault();e.stopPropagation();}
},true);
document.addEventListener('wheel',e=>{if(e.ctrlKey)e.preventDefault()},{passive:false,capture:true});
// Support button is explicitly external. Internal top navigation WhatsApp is untouched.
const support=document.getElementById('openWhatsappTab');
if(support){
  const clone=support.cloneNode(true); support.replaceWith(clone);
  clone.addEventListener('click',async e=>{e.preventDefault();try{await fetch('/api/open-support-external',{method:'POST'})}catch(_){}});
}
// V56.1 maintenance: keep the Bismillah text exact and remove decorative glyphs
// that can render as odd characters on some Windows font setups.
const bismillah=document.querySelector('.bismillah');
if(bismillah){bismillah.textContent='بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ';bismillah.setAttribute('dir','rtl');}
document.querySelectorAll('.bismillahArea .ornament').forEach(el=>{el.textContent='';});
// V56.0 isolated UI/mode guard. Loaded separately so the proven baseline app.js
// remains untouched.
const guard=document.createElement('script');
guard.src='/v560-mode-guard.js';
guard.defer=true;
document.head.appendChild(guard);
})();
