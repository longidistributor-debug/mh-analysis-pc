(()=>{
'use strict';

const $=s=>document.querySelector(s);
let allowSignalPass=false;

function setBranding(){
  const version=$('.version');
  if(version)version.textContent='Hammad & Somi V8.0.3';
  document.querySelectorAll('img.logo').forEach(img=>{img.src='/mh-logo.png?v=hs803';img.alt='MH Analysis';});
}

function modalRoot(){
  let root=$('#mhUiModal');
  if(root)return root;
  root=document.createElement('div');
  root.id='mhUiModal';
  root.className='mhUiModal mhHidden';
  root.innerHTML=`
    <div class="mhUiCard" role="dialog" aria-modal="true" aria-labelledby="mhUiTitle">
      <div class="mhUiHead">
        <img src="/mh-logo.png?v=hs803" alt="MH" />
        <div class="mhUiHeadText"><div class="mhUiTitle" id="mhUiTitle">MH Analysis</div><div class="mhUiSub">Hammad & Somi V8.0.3</div></div>
        <button class="mhUiClose" type="button" aria-label="Close">×</button>
      </div>
      <div class="mhUiDesc" id="mhUiDesc"></div>
      <div class="mhUiStatus" id="mhUiStatus"></div>
      <form id="mhUiForm"><div id="mhUiFields"></div><div class="mhUiError" id="mhUiError"></div><div class="mhUiActions" id="mhUiActions"></div></form>
    </div>`;
  document.body.appendChild(root);
  return root;
}

function showForm(opts={}){
  const root=modalRoot(),title=root.querySelector('#mhUiTitle'),desc=root.querySelector('#mhUiDesc'),status=root.querySelector('#mhUiStatus'),fieldsWrap=root.querySelector('#mhUiFields'),error=root.querySelector('#mhUiError'),actions=root.querySelector('#mhUiActions'),form=root.querySelector('#mhUiForm'),close=root.querySelector('.mhUiClose');
  title.textContent=opts.title||'MH Analysis';
  desc.textContent=opts.description||'';
  status.textContent=opts.status||'';
  error.textContent='';
  fieldsWrap.innerHTML='';
  actions.innerHTML='';

  const inputs={};
  (opts.fields||[]).forEach(f=>{
    const row=document.createElement('div');row.className='mhUiField';
    const label=document.createElement('label');label.textContent=f.label||f.name;label.htmlFor='mhField_'+f.name;
    const input=document.createElement('input');input.id='mhField_'+f.name;input.name=f.name;input.type=f.type||'text';input.placeholder=f.placeholder||'';input.value=f.value||'';input.autocomplete='off';input.spellcheck=false;
    if(f.maxLength)input.maxLength=f.maxLength;
    row.append(label,input);fieldsWrap.appendChild(row);inputs[f.name]=input;
  });

  const cancel=document.createElement('button');cancel.type='button';cancel.className='mhUiBtn';cancel.textContent='CANCEL';
  actions.appendChild(cancel);
  let clear=null;
  if(opts.allowClear){clear=document.createElement('button');clear.type='button';clear.className='mhUiBtn danger';clear.textContent=opts.clearLabel||'CLEAR';actions.appendChild(clear);}
  const save=document.createElement('button');save.type='submit';save.className='mhUiBtn primary';save.textContent=opts.saveLabel||'SAVE';actions.appendChild(save);

  root.classList.remove('mhHidden');document.body.classList.add('mhUiModalOpen');
  setTimeout(()=>Object.values(inputs)[0]?.focus(),20);

  return new Promise(resolve=>{
    let done=false;
    const finish=value=>{if(done)return;done=true;root.classList.add('mhHidden');document.body.classList.remove('mhUiModalOpen');document.removeEventListener('keydown',onKey,true);root.onclick=null;form.onsubmit=null;close.onclick=null;cancel.onclick=null;if(clear)clear.onclick=null;resolve(value)};
    const onKey=e=>{if(e.key==='Escape'){e.preventDefault();finish(null)}};
    document.addEventListener('keydown',onKey,true);
    close.onclick=()=>finish(null);cancel.onclick=()=>finish(null);
    root.onclick=e=>{if(e.target===root)finish(null)};
    if(clear)clear.onclick=()=>finish({action:'clear',values:{}});
    form.onsubmit=e=>{
      e.preventDefault();error.textContent='';
      const values={};for(const [name,input] of Object.entries(inputs))values[name]=String(input.value||'').trim();
      for(const f of (opts.fields||[])){if(f.required&&!values[f.name]){error.textContent=f.requiredMessage||`${f.label||f.name} is required.`;inputs[f.name]?.focus();return}}
      finish({action:'save',values});
    };
  });
}

async function getSettings(){
  const r=await fetch('/api/settings',{cache:'no-store'});if(!r.ok)throw new Error('Could not read settings.');return r.json();
}
async function saveSettings(payload){
  const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw new Error('Could not save settings.');return r.json();
}
function updateKeyUi(saved){
  const state=$('#restState'),detail=$('#restDetail');
  if(state){state.className='statusPill neutralDot';state.textContent=`MH Analysis By MHammadS • Data • ${saved?'Key saved':'Access key not saved'}`;}
  if(detail){detail.className=saved?'good':'warn';detail.textContent=saved?'Key saved':'Access key not saved';}
}
async function themedKeyDialog(){
  try{
    const s=await getSettings();
    const result=await showForm({title:'ACCESS KEY',description:'Save the market-data access key used by MH Analysis. The key stays in the app settings on this PC.',status:s.has_api_key?'Current status: KEY SAVED':'Current status: NO KEY SAVED',allowClear:true,saveLabel:'SAVE KEY',fields:[{name:'api_key',label:'Access Key',type:'password',placeholder:s.has_api_key?'Enter a new key to replace the saved key':'Paste your access key',required:true,requiredMessage:'Enter an access key, or choose CLEAR.'}]});
    if(!result)return;
    if(result.action==='clear'){await saveSettings({api_key:null});updateKeyUi(false);return;}
    await saveSettings({api_key:result.values.api_key});updateKeyUi(true);
  }catch(err){await showForm({title:'SETTINGS ERROR',description:String(err?.message||err),saveLabel:'CLOSE',fields:[]});}
}

async function themedSignalSetup(button,knownSettings=null){
  try{
    const s=knownSettings||await getSettings();
    const fields=[{
      name:'whatsapp_link',
      label:'WhatsApp Number / Profile Link',
      value:s.whatsapp_link||'',
      placeholder:'Example: https://wa.me/923434824609 or 923434824609',
      required:true,
      requiredMessage:'Enter the WhatsApp number or profile link where signals should be sent.'
    }];
    if(!s.has_api_key)fields.push({name:'api_key',label:'Access Key',type:'password',placeholder:'Paste your access key',required:true,requiredMessage:'Enter the access key.'});
    const result=await showForm({
      title:'WHATSAPP SIGNAL SETUP',
      description:'Save the WhatsApp number/profile link where automatic signals will be sent. Log in once from the WhatsApp tab; the app keeps that WhatsApp session in its persistent profile.',
      status:`WhatsApp destination: ${s.has_whatsapp?'SAVED':'MISSING'}  •  Access key: ${s.has_api_key?'SAVED':'MISSING'}`,
      allowClear:!!s.has_whatsapp,
      clearLabel:'CLEAR PROFILE',
      saveLabel:'SAVE & START',
      fields
    });
    if(!result)return true;
    if(result.action==='clear'){
      await saveSettings({whatsapp_link:null});
      return true;
    }
    const destination=String(result.values.whatsapp_link||'').trim();
    const digits=destination.replace(/\D/g,'');
    if(digits.length<8){
      await showForm({title:'WHATSAPP SETUP ERROR',description:'Enter a valid WhatsApp number or a profile link that contains the destination phone number.',saveLabel:'CLOSE',fields:[]});
      return true;
    }
    const payload={whatsapp_link:destination};
    if(result.values.api_key)payload.api_key=result.values.api_key;
    await saveSettings(payload);updateKeyUi(s.has_api_key||!!result.values.api_key);
    allowSignalPass=true;button.click();
    return true;
  }catch(err){await showForm({title:'GET SIGNAL ERROR',description:String(err?.message||err),saveLabel:'CLOSE',fields:[]});return true;}
}

function installHandlers(){
  const key=$('#openKey');
  if(key)key.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();themedKeyDialog();},true);

  const signal=$('#autoSignalToggle');
  if(signal)signal.addEventListener('click',async e=>{
    if(allowSignalPass){allowSignalPass=false;return;}
    const isOn=signal.classList.contains('on')||/^Get Signal:\s*ON/i.test(signal.textContent||'');
    if(isOn)return;
    e.preventDefault();e.stopImmediatePropagation();
    const settings=await getSettings().catch(()=>null);
    await themedSignalSetup(signal,settings);
  },true);

  const exit=$('#exitApp');
  if(exit)exit.addEventListener('click',e=>{
    e.preventDefault();e.stopImmediatePropagation();exit.disabled=true;exit.textContent='EXITING…';
    let nativeCalled=false;
    try{if(typeof window.mhExit==='function'){nativeCalled=true;Promise.resolve(window.mhExit()).catch(()=>{});}}catch(_){nativeCalled=false;}
    setTimeout(()=>{fetch('/api/shutdown',{method:'POST',keepalive:true}).catch(()=>{});},nativeCalled?100:0);
    setTimeout(()=>{try{window.close();}catch(_){}},350);
  },true);
}

function loadResponsiveRefresh(){
  let timer=0;
  const refresh=()=>{clearTimeout(timer);timer=setTimeout(()=>{window.dispatchEvent(new Event('resize'));},80)};
  window.addEventListener('resize',refresh,{passive:true});
  if(window.ResizeObserver){const ro=new ResizeObserver(refresh);const shell=$('.appShell');if(shell)ro.observe(shell);window.__mhUiResizeObserver=ro;}
}

function boot(){setBranding();installHandlers();loadResponsiveRefresh();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();