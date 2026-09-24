(()=>{
'use strict';
const ids=['mhSlAdjustment','mhProgressiveV1','mhFastScalping'];
function send(){
  try{
    const els=ids.map(id=>document.getElementById(id));
    if(els.some(x=>!x))return false;
    els.forEach(x=>{x.style.display='none';x.setAttribute('aria-hidden','true');});
    const labels=els.map(x=>(x.textContent||'').trim().replace(/\s+/g,' '));
    if(window.chrome&&window.chrome.webview&&window.chrome.webview.postMessage){
      window.chrome.webview.postMessage('MHCTRL|'+labels.join('|'));
    }
    return true;
  }catch(_){return false;}
}
let tries=0;
const t=setInterval(()=>{if(send()||++tries>100)clearInterval(t)},100);
new MutationObserver(()=>send()).observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','disabled']});
})();
