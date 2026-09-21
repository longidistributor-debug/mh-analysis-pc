// MH_MANDATORY_UPDATE_V001
(() => {
  const gate=document.getElementById('mhMandatoryUpdateV001');
  if(!gate)return;
  const title=document.getElementById('mhUpdateTitleV001');
  const sub=document.getElementById('mhUpdateSubV001');
  const btn=document.getElementById('mhUpdateNowV001');
  const retry=document.getElementById('mhUpdateRetryV001');
  const wrap=document.getElementById('mhUpdateProgressWrapV001');
  const fill=document.getElementById('mhUpdateFillV001');
  const pct=document.getElementById('mhUpdatePercentV001');
  const state=document.getElementById('mhUpdateStateV001');
  let verifiedOnce=false, required=false, progressTimer=0, checking=false;

  function showGate(){document.body.classList.remove('mhUpdateCheckingV001');document.body.classList.add('mhUpdateRequiredV001');gate.classList.remove('mhUpdateHiddenV001')}
  function hideGate(){document.body.classList.remove('mhUpdateRequiredV001');gate.classList.add('mhUpdateHiddenV001')}
  function percent(v){const n=Math.max(0,Math.min(100,Number(v)||0));fill.style.width=n+'%';pct.textContent=Math.round(n)+'%'}
  function checkError(msg){required=false;hideGate();document.body.classList.remove('mhUpdateCheckingV001');state.textContent='';setTimeout(()=>checkVersion(false),15000)}

  async function checkVersion(initial=false){
    if(checking)return;checking=true;
    if(initial){document.body.classList.add('mhUpdateCheckingV001');hideGate();title.textContent='Checking required version…';sub.textContent='Please wait.';btn.style.display='none';retry.classList.remove('show');state.textContent=''}
    try{
      const r=await fetch('/api/update/status',{cache:'no-store'});
      const j=await r.json();
      if(!j.verified){if(!verifiedOnce)checkError(j.error);return}
      verifiedOnce=true;
      if(j.required){
        required=true;showGate();
        title.textContent='Update Required';
        sub.textContent=`${j.latest||'New version'} is required before MH Analysis can continue.`;
        btn.style.display='inline-block';btn.disabled=false;btn.textContent='Update Now - To Access';
        retry.classList.remove('show');state.textContent='Your login, Records, WhatsApp settings and saved data will remain unchanged.';
      }else if(!required){
        hideGate();document.body.classList.remove('mhUpdateCheckingV001');
      }
    }catch(e){if(!verifiedOnce)checkError('Could not reach the update service. Check internet and retry.')}
    finally{checking=false}
  }

  async function pollProgress(){
    try{
      const r=await fetch('/api/update/progress',{cache:'no-store'});const j=await r.json();
      if(j.phase==='downloading'){
        title.textContent='Downloading Update';wrap.classList.add('show');percent(j.percent);state.textContent=j.total>0?'Downloading securely…':'Downloading update…';
      }else if(j.phase==='verifying'){
        title.textContent='Verifying Update';wrap.classList.add('show');percent(99);state.textContent='Checking update integrity…';
      }else if(j.phase==='installing'){
        title.textContent='Installing Update';wrap.classList.add('show');percent(100);state.textContent='MH Analysis will restart automatically with the new version.';
      }else if(j.phase==='error'){
        clearInterval(progressTimer);progressTimer=0;title.textContent='Update Failed';sub.textContent=j.error||'Please retry.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';retry.classList.add('show');state.textContent='No saved MH Analysis data was removed.';
      }
    }catch(_){/* keep current progress surface; process may be restarting */}
  }

  async function startUpdate(){
    showGate();btn.disabled=true;btn.textContent='Starting…';retry.classList.remove('show');wrap.classList.add('show');percent(0);title.textContent='Preparing Update';sub.textContent='Keep MH Analysis open while the update downloads.';state.textContent='';
    try{
      const r=await fetch('/api/update/start',{method:'POST',cache:'no-store'});
      if(!r.ok)throw new Error((await r.text())||'Update could not start.');
      btn.style.display='none';
      if(!progressTimer){progressTimer=setInterval(pollProgress,250)}
      pollProgress();
    }catch(e){title.textContent='Update Failed';sub.textContent=e?.message||'Update could not start.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';retry.classList.add('show')}
  }

  btn.addEventListener('click',startUpdate);
  retry.addEventListener('click',()=>checkVersion(true));
  checkVersion(true);
  setInterval(()=>checkVersion(false),60000);
})();
