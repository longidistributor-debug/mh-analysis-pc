from pathlib import Path

MARK='MH_MT5_SYSTEM_V796'
MT5_URL='https://www.exness.com/webterminal/'

# Convert the existing fourth embedded browser tab from the Exness custom
# terminal to Exness MetaTrader WebTerminal while preserving the proven native
# embedding, focus, profile persistence and signal bridge plumbing.
p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    if 'chWstr("Exness")' not in s:
        raise SystemExit('MT5 button anchor missing')
    s=s.replace('chWstr("Exness")','chWstr("MT5 System")',1)
    if '"ExnessProfile"' not in s:
        raise SystemExit('Exness profile anchor missing')
    s=s.replace('"ExnessProfile"','"MT5SystemProfile"')
    if '"https://my.exness.global/webtrading/"' not in s:
        raise SystemExit('Exness terminal URL anchor missing')
    s=s.replace('"https://my.exness.global/webtrading/"',f'"{MT5_URL}"')
    s=s.replace('func chEnsureExnessBrowser() error {','// '+MARK+'\nfunc chEnsureExnessBrowser() error {',1)
p.write_text(s,encoding='utf-8')

# Keep the local /api/exness/* bridge route names for backward compatibility
# with web/app.js, but make all user-facing state MT5-specific and prefer the
# MetaTrader 5 tab on the Exness WebTerminal landing page.
p=Path('exness_bridge.go')
s=p.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('QUEUED FOR EXNESS PREFILL','QUEUED FOR MT5 PREFILL')
    s=s.replace('Exness browser page is not ready','MT5 System browser page is not ready')
    s=s.replace('Exness terminal returned no prefill status','MT5 WebTerminal returned no prefill status')
    s=s.replace('automatic Exness symbol switch','automatic MT5 symbol switch')

    anchor="""hide();
if(!window.__mhExnessLoginCleanup){window.__mhExnessLoginCleanup=true;new MutationObserver(hide).observe(document.documentElement,{childList:true,subtree:true,characterData:true});}
"""
    replacement="""hide();
// Prefer MT5 on the Exness MetaTrader WebTerminal landing page. Do not press
// Continue/Connect and never submit an order here.
try{
 if(location.hostname.toLowerCase().includes('exness')&&location.pathname.toLowerCase().includes('webterminal')){
  const nodes=[...document.querySelectorAll('button,[role=\"tab\"],a,div,span')];
  const mt5=nodes.find(e=>String(e.innerText||e.textContent||'').replace(/\\s+/g,' ').trim().toLowerCase()==='metatrader 5');
  if(mt5&&mt5.getAttribute('aria-selected')!=='true'&&!String(mt5.className||'').toLowerCase().includes('active'))mt5.click();
 }
}catch(_){ }
if(!window.__mhExnessLoginCleanup){window.__mhExnessLoginCleanup=true;new MutationObserver(hide).observe(document.documentElement,{childList:true,subtree:true,characterData:true});}
"""
    if anchor not in s:
        raise SystemExit('login cleanup MT5 preference anchor missing')
    s=s.replace(anchor,replacement,1)

    # Add common MetaTrader WebTerminal order wording without adding any final
    # submit action. Existing bridge still stops at READY FOR USER CONFIRMATION.
    s=s.replace("clickText(['New order','Trade']);","clickText(['New Order','New order','Order','Trade']);",1)
    s=s.replace("clickText(['Pending order','Pending']);","clickText(['Pending Order','Pending order','Pending']);",1)
    s=s.replace('// MH_SYMBOL_SYNC_CHART_RESET_V796\ntype exnessOrderPrep struct {','// MH_SYMBOL_SYNC_CHART_RESET_V796\n// '+MARK+'\ntype exnessOrderPrep struct {',1)
p.write_text(s,encoding='utf-8')

print('PASS MT5 System: embedded Exness MetaTrader WebTerminal + persistent MT5 profile + existing signal prefill bridge retained')
