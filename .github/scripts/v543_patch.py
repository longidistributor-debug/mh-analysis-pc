from pathlib import Path
import re
import textwrap

# Reapply the exact proven V54.2 runtime patch from the previous workflow.
base_wf = Path('.github/workflows/publish-v54-2-whatsapp-confirmed-send.yml').read_text(encoding='utf-8')
m = re.search(r"(?s)@'\r?\n(.*?)\r?\n\s*'@ \| Set-Content -Encoding utf8 \.v542_patch\.py", base_wf)
if not m:
    raise SystemExit('Could not extract proven V54.2 patch')
base_py = textwrap.dedent(m.group(1))
exec(compile(base_py, '.v542_patch.py', 'exec'), {})

# ---------- WhatsApp host: fast path + short retries ----------
p = Path('webview2_host.go')
s = p.read_text(encoding='utf-8')

if 'wv2WAActiveTarget' not in s:
    s = s.replace(
        'wv2WALastAckStatus     string\n)',
        'wv2WALastAckStatus     string\n\twv2WAActiveTarget      string\n\twv2WAResolvedTarget    string\n)',
        1,
    )

s = s.replace(
    '\twv2WAActiveMessage = t.message\n\twv2WAActiveGroup = isGroup\n\ttoken := wv2WAActiveToken',
    '\twv2WAActiveMessage = t.message\n\twv2WAActiveGroup = isGroup\n\twv2WAActiveTarget = target\n\ttoken := wv2WAActiveToken',
    1,
)

old = '''\t// Navigate the exact saved link in the already-created persistent WhatsApp WebView.
\t// This function is called from WndProc, so Navigate stays on the WebView UI thread.
\twv2Whatsapp.Navigate(target)

\tfor _, delay := range []time.Duration{800*time.Millisecond, 1500*time.Millisecond, 2500*time.Millisecond, 4*time.Second, 6*time.Second, 9*time.Second, 13*time.Second, 18*time.Second, 24*time.Second, 31*time.Second, 39*time.Second} {
\t\td := delay
\t\ttime.AfterFunc(d, func() { postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
\t}
\ttime.AfterFunc(43*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })'''
new = '''\t// Fast path: if this exact Signal Link already resolved to the current hidden group chat,
\t// do not navigate/reload WhatsApp again. This keeps MH Analysis responsive.
\tif wv2WAResolvedTarget == target {
\t\tpostMessage(hostHWND, wmWhatsAppEvalV54, token, 0)
\t} else {
\t\twv2Whatsapp.Navigate(target)
\t}

\t// NavigationCompleted also triggers immediately; these are short non-blocking fallbacks only.
\tfor _, delay := range []time.Duration{200*time.Millisecond, 500*time.Millisecond, 900*time.Millisecond, 1400*time.Millisecond, 2*time.Second, 3*time.Second} {
\t\td := delay
\t\ttime.AfterFunc(d, func() { postMessage(hostHWND, wmWhatsAppEvalV54, token, 0) })
\t}
\ttime.AfterFunc(4*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, token, 0) })'''
if old not in s:
    raise SystemExit('V54.2 WhatsApp timer block not found')
s = s.replace(old, new, 1)

s = s.replace(
    'if wv2WALastAckStatus == "sent" {\n\t\twv2FinishWhatsAppV54(token)',
    'if wv2WALastAckStatus == "sent" {\n\t\twv2WAResolvedTarget = wv2WAActiveTarget\n\t\twv2FinishWhatsAppV54(token)',
    1,
)

s = s.replace(
    '\twv2WAActiveMessage = ""\n\twv2WAActiveGroup = false',
    '\twv2WAActiveMessage = ""\n\twv2WAActiveGroup = false\n\twv2WAActiveTarget = ""',
    1,
)

# If the user manually opens WhatsApp, invalidate fast-chat cache to avoid a wrong-chat send.
s = s.replace(
    'case 2:\n\t\tif wv2Whatsapp != nil { chShowWindow.Call(wv2WhatsappContainer, chSWShow); _ = wv2Whatsapp.Show(); wv2Whatsapp.Focus() }',
    'case 2:\n\t\twv2WAResolvedTarget = ""\n\t\tif wv2Whatsapp != nil { chShowWindow.Call(wv2WhatsappContainer, chSWShow); _ = wv2Whatsapp.Show(); wv2Whatsapp.Focus() }',
    1,
)

s = s.replace(
    'time.AfterFunc(5*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, wp, 0) })',
    'time.AfterFunc(2*time.Second, func() { postMessage(hostHWND, wmWhatsAppNextV54, wp, 0) })',
    1,
)
p.write_text(s, encoding='utf-8', newline='\n')

# ---------- Frontend: requested message format + fire-and-forget queue handoff ----------
p = Path('web/app.js')
s = p.read_text(encoding='utf-8')
pattern = r"function decisionWhatsAppMessage\(d,action='NEW ANALYSIS',status=''\)\{.*?\n\}\nasync function sendDecisionWhatsApp\(d,action,status=''\)\{.*?\n\}"
replacement = '''function decisionWhatsAppMessage(d,action='NEW ANALYSIS',status=''){
  const sig=d?.signal||(action==='RE-EVALUATE'?d?.originalSignal:null),isSell=sig?.direction==='SELL',dot=sig?(isSell?'🔴':'🟢'):'⚪';
  const statusText=status||(sig?'Signal generated':'No clear edge');
  const lines=[`*MH ANALYSIS SIGNAL*`,`🤝 *Status:* ${statusText}`,'',`*Pair:* ${symbol}`,`*Timeframe:* ${String(timeframe).toUpperCase()}`,`*Time:* ${new Date().toLocaleString()}`,''];
  if(sig){lines.push(`*Signal:* ${dot} ${sig.direction}`,`*Entry:* ${dot} ${fmt(sig.entry)}`,`*SL:* ${fmt(sig.sl)}`,`*TP1:* ${fmt(sig.tp1)}`,`*TP2:* ${fmt(sig.tp2)}`,`*Score:* ${sig.score}/100`,`*Setup:* ${d.bestFamily||sig.setupReason||'Best current setup'}`)}
  else{lines.push(`*Signal:* ⚪ NO CLEAR EDGE`,`*BUY Score:* ${d?.buyScore??'—'}`,`*SELL Score:* ${d?.sellScore??'—'}`,`*Reason:* ${d?.explanation||'No statistically clear directional edge on the fresh analysis.'}`)}
  return lines.join('\\n');
}
function sendDecisionWhatsApp(d,action,status=''){
  const message=decisionWhatsAppMessage(d,action,status);
  setTimeout(()=>{(async()=>{
    try{
      await refreshBackendSettings();
      if(!backendSettings.has_whatsapp)throw new Error('WhatsApp Signal Link is not saved. Open the WhatsApp tab and set Signal Link.');
      const r=await fetch('/api/send-whatsapp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
      let j={};try{j=await r.json()}catch(_){ }
      if(!r.ok)throw new Error(j.error||'WhatsApp queue failed');
    }catch(e){console.warn('Background WhatsApp send failed',e)}
  })()},0);
  return Promise.resolve({ok:true,queued:true,background:true});
}'''
ns, n = re.subn(pattern, lambda _m: replacement, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'WhatsApp formatter/background sender replacement failed: {n}')
p.write_text(ns, encoding='utf-8', newline='\n')

# ---------- V54.3 stamps ----------
for path, pat, repl in [
    ('updater.go', r'const mhPublicVersionV001 = "[^"]+"', 'const mhPublicVersionV001 = "V.54.3"'),
    ('license_auth.go', r'const licAppVersion = "[^"]+"', 'const licAppVersion = "V.54.3"'),
]:
    q = Path(path)
    z = q.read_text(encoding='utf-8')
    z, n = re.subn(pat, repl, z, count=1)
    if n != 1:
        raise SystemExit(f'version stamp failed {path}')
    q.write_text(z, encoding='utf-8', newline='\n')

Path('VERSION').write_text('V.54.3\n', encoding='ascii')
q = Path('web/index.html')
z = q.read_text(encoding='utf-8')
z = re.sub(r'<div class="version">[^<]*</div>', '<div class="version">V.54.3 AUTO CYCLE (HAMMAD & SOMI)</div>', z, count=1)
z = re.sub(r'<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">[^<]*</div>', '<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.54.3</div>', z, count=1)
q.write_text(z, encoding='utf-8', newline='\n')

# Guards.
wa = Path('webview2_host.go').read_text(encoding='utf-8')
a = Path('web/app.js').read_text(encoding='utf-8')
checks = [
    ('fast resolved-group path', 'wv2WAResolvedTarget == target' in wa),
    ('short retries', '200*time.Millisecond' in wa),
    ('legacy 43-second wait removed', '43*time.Second' not in wa),
    ('confirmed target cache', 'wv2WAResolvedTarget = wv2WAActiveTarget' in wa),
    ('requested Status format', '🤝 *Status:*' in a),
    ('legacy Action line removed', '*Action:*' not in a),
    ('non-blocking handoff', 'background:true' in a),
]
for name, ok in checks:
    if not ok:
        raise SystemExit(f'Guard failed: {name}')
