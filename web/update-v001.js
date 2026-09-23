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
  let progressTimer=0, checking=false, starting=false;

  function showGate(){document.body.classList.remove('mhUpdateCheckingV001');document.body.classList.add('mhUpdateRequiredV001');gate.classList.remove('mhUpdateHiddenV001')}
  function hideGate(){document.body.classList.remove('mhUpdateRequiredV001');gate.classList.add('mhUpdateHiddenV001')}
  function percent(v){const n=Math.max(0,Math.min(100,Number(v)||0));fill.style.width=n+'%';pct.textContent=Math.round(n)+'%'}
  function noInternet(){
    showGate();
    title.textContent='No Internet Connection';
    sub.textContent='';
    state.textContent='';
    btn.style.display='none';
    retry.classList.add('show');retry.textContent='Retry Check';
    wrap.classList.remove('show');
  }

  async function pollProgress(){
    try{
      const r=await fetch('/api/update/progress',{cache:'no-store'});const j=await r.json();
      if(j.phase==='downloading'){
        title.textContent='Downloading Update';wrap.classList.add('show');percent(j.percent);state.textContent='Downloading securely…';
      }else if(j.phase==='verifying'){
        title.textContent='Verifying Update';wrap.classList.add('show');percent(99);state.textContent='Checking update integrity…';
      }else if(j.phase==='installing'){
        title.textContent='Installing Update';wrap.classList.add('show');percent(100);state.textContent='MH Analysis will restart automatically with the new version.';
      }else if(j.phase==='error'){
        clearInterval(progressTimer);progressTimer=0;starting=false;title.textContent='Update Failed';sub.textContent='Please retry.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';state.textContent='Your saved MH Analysis data remains unchanged.';
      }
    }catch(_){/* updater may be replacing/restarting the application */}
  }

  async function startUpdate(){
    if(starting)return;starting=true;showGate();retry.classList.remove('show');btn.style.display='none';wrap.classList.add('show');percent(0);title.textContent='Preparing Update';sub.textContent='A newer MH Analysis version was found.';state.textContent='Starting automatic download and installation…';
    try{
      const r=await fetch('/api/update/start',{method:'POST',cache:'no-store'});
      if(!r.ok)throw new Error('Update could not start.');
      if(!progressTimer)progressTimer=setInterval(pollProgress,250);pollProgress();
    }catch(e){starting=false;title.textContent='Update Failed';sub.textContent='Update could not start.';btn.style.display='inline-block';btn.disabled=false;btn.textContent='Retry Update';state.textContent='Your saved MH Analysis data remains unchanged.';}
  }

  async function checkVersion(){
    if(checking||starting)return;checking=true;
    document.body.classList.add('mhUpdateCheckingV001');showGate();title.textContent='Checking for Updates';sub.textContent='Please wait…';btn.style.display='none';retry.classList.remove('show');wrap.classList.remove('show');state.textContent='Checking the MH Analysis update manifest before login…';
    try{
      const r=await fetch('/api/update/status',{cache:'no-store'});
      if(!r.ok)throw new Error('offline');
      const j=await r.json();
      if(!j.verified){noInternet();return}
      if(j.required){
        showGate();title.textContent='Update Available';sub.textContent=`${j.latest||'A newer version'} is available. Updating MH Analysis now…`;state.textContent='Your login, Records, WhatsApp settings and saved data will remain unchanged.';
        checking=false;await startUpdate();return;
      }
      hideGate();document.body.classList.remove('mhUpdateCheckingV001');
    }catch(_){noInternet()}
    finally{checking=false}
  }

  btn.addEventListener('click',startUpdate);
  retry.addEventListener('click',checkVersion);
  checkVersion();
})();
