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
})();
