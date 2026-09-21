from pathlib import Path

MARK='MH_V001_RESET_FUTURE_UPDATE'

# Run after V.02/V.03 patches: reset public release version to V.01 while retaining
# all updater, clean-title, privacy and replacement fixes.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('const mhPublicVersionV001 = "V.03"','const mhPublicVersionV001 = "V.01"',1)
if 'const mhPublicVersionV001 = "V.01"' not in s:
    raise SystemExit('public version reset failed')
p.write_text(s,encoding='utf-8')

p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('id="mhUpdateVersionV001">V.03</div>','id="mhUpdateVersionV001">V.01</div>',1)
s=s.replace('V.03 AUTO CYCLE (HAMMAD & SOMI)','V.01 AUTO CYCLE (HAMMAD & SOMI)',1)
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8')
s=s.replace("j.current||'V.03'","j.current||'V.01'")
# Make startup verification fail-closed and retry automatically. The gate must not
# disappear until the server has positively verified that current >= required.
if MARK not in s:
    s='// '+MARK+'\n'+s
    # Any network/JSON/status error stays locked; add periodic retry if the existing
    # catch path only exposes Retry manually.
    marker="console.error"
    # Do not depend on exact minified formatting; append an independent watchdog.
    s += r'''

// MH_V001_RESET_FUTURE_UPDATE startup watchdog.
// Native host starts locked. This repeatedly requests authoritative status until
// verification succeeds. It never unlocks the app itself; only backend/native
// verified status is allowed to do that.
(function mhV001VerifiedStartupWatchdog(){
  let busy=false;
  async function verify(){
    if(busy)return; busy=true;
    try{
      const r=await fetch('/api/update/status?startup=1&t='+Date.now(),{cache:'no-store'});
      if(!r.ok) throw new Error('version status '+r.status);
      const j=await r.json();
      if(!j || j.verified!==true) throw new Error('version not verified');
      // Existing update UI owns rendering and backend/native owns lock state.
      if(typeof check==='function') setTimeout(()=>check(),0);
      if(j.required===true) return; // remain locked until update completes
    }catch(e){
      // fail closed: native lock remains active
    }finally{busy=false}
  }
  verify();
  setInterval(verify,5000);
})();
'''
p.write_text(s,encoding='utf-8')
print(MARK+': release reset to V.01; future version checks fail closed')
