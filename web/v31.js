// MH Analysis V.31 client hardening
(()=>{
  const editable=e=>e&&/^(INPUT|TEXTAREA)$/i.test(e.tagName);
  document.addEventListener('copy',e=>e.preventDefault(),true);
  document.addEventListener('cut',e=>e.preventDefault(),true);
  document.addEventListener('contextmenu',e=>e.preventDefault(),true);
  document.addEventListener('dragstart',e=>e.preventDefault(),true);
  document.addEventListener('selectstart',e=>{if(!editable(e.target))e.preventDefault()},true);
  document.addEventListener('keydown',e=>{
    const k=String(e.key||'').toLowerCase();
    if(k==='printscreen'){e.preventDefault();return false}
    if((e.ctrlKey||e.metaKey)&&['c','x','p','s','u'].includes(k)){e.preventDefault();return false}
    if((e.ctrlKey||e.metaKey)&&['+','-','=','0'].includes(k)){e.preventDefault();return false}
    if((e.ctrlKey||e.metaKey)&&k==='a'&&!editable(e.target)){e.preventDefault();return false}
  },true);
  document.addEventListener('wheel',e=>{if(e.ctrlKey){e.preventDefault()}},{capture:true,passive:false});

  function wireExternalSupport(){
    const a=document.querySelector('.mhLicenseWhatsapp');
    if(!a||a.dataset.v31External==='1')return;
    a.dataset.v31External='1';
    a.removeAttribute('target');
    a.addEventListener('click',async e=>{
      e.preventDefault();e.stopPropagation();
      try{await fetch('/api/open-external-support',{method:'POST',cache:'no-store'})}catch(_){ }
    },true);
  }
  const mo=new MutationObserver(wireExternalSupport);
  mo.observe(document.documentElement,{childList:true,subtree:true});
  wireExternalSupport();
})();
