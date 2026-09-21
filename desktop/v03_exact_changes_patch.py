from pathlib import Path

# Apply ONLY requested V.03 changes after existing Records/MT5 restore patches.

p=Path('chrome_host.go'); s=p.read_text(encoding='utf-8')
s=s.replace('chSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")', 'chSetForegroundWindow   = chUser32.NewProc("SetForegroundWindow")\n\tchSetFocus              = chUser32.NewProc("SetFocus")')
s=s.replace('chEXAppWindow   = 0x00040000', 'chEXAppWindow   = 0x00040000\n\tchEXToolWindow  = 0x00000080')
s=s.replace('exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow', 'exStyle &^= chEXDlgModal | chEXWindowEdge | chEXClientEdge | chEXStaticEdge | chEXAppWindow\n\texStyle |= chEXToolWindow')
s=s.replace('chSetParent.Call(hwnd, hostHWND)', 'chSetParent.Call(hwnd, hostHWND)\n\tchSetFocus.Call(hwnd)', 1)
needle='''\t\tid := int(wParam & 0xffff)\n\t\tswitch id {'''
replacement='''\t\tid := int(wParam & 0xffff)\n\t\tif !licAuthorized {\n\t\t\tsection := "MH Analysis"\n\t\t\tswitch id {\n\t\t\tcase idWhatsapp: section = "WhatsApp"\n\t\t\tcase idRecords: section = "Records"\n\t\t\tcase idMT5: section = "MT5 System"\n\t\t\tcase chIDSignalLink: section = "Signal Link"\n\t\t\t}\n\t\t\tif id == idAnalysis || id == idWhatsapp || id == idRecords || id == idMT5 || id == chIDSignalLink {\n\t\t\t\tlicSetNavNotice(section)\n\t\t\t\tchSwitchView(1)\n\t\t\t\treturn 0\n\t\t\t}\n\t\t}\n\t\tswitch id {'''
if needle not in s: raise SystemExit('native command anchor missing')
s=s.replace(needle,replacement,1)
s=s.replace('chShowWindowAsync.Call(chAnalysisWnd, chSWShow)', 'chShowWindowAsync.Call(chAnalysisWnd, chSWShow)\n\t\tchSetFocus.Call(chAnalysisWnd)', 1)
p.write_text(s,encoding='utf-8')

# Records: custom themed centered Clear/Cancel confirmation and exact footer.
p=Path('web/records.js'); s=p.read_text(encoding='utf-8')
old="""  if(!confirm(`Delete saved Records for ${label}?\\n\\nThis resets MH Analysis records only. It does not delete MT5 account history.`))return;"""
new="""  if(!(await mhRecordsConfirm(`Delete saved Records for ${label}?`, 'This resets MH Analysis records only. It does not delete MT5 account history.')))return;"""
if old not in s: raise SystemExit('records confirm anchor missing')
s=s.replace(old,new,1)
insert="""
function mhRecordsConfirm(title,detail){
  return new Promise(resolve=>{
    const old=document.getElementById('mhRecordsConfirm');if(old)old.remove();
    const wrap=document.createElement('div');wrap.id='mhRecordsConfirm';wrap.className='mhRecordsConfirm';
    wrap.innerHTML=`<div class="mhRecordsConfirmCard" role="dialog" aria-modal="true"><div class="mhRecordsConfirmTag">MH ANALYSIS • RECORDS</div><h3>${esc(title)}</h3><p>${esc(detail)}</p><div class="mhRecordsConfirmActions"><button class="clear" type="button">CLEAR</button><button class="cancel" type="button">CANCEL</button></div></div>`;
    document.body.appendChild(wrap);
    const done=v=>{wrap.remove();resolve(v)};
    wrap.querySelector('.clear').onclick=()=>done(true);wrap.querySelector('.cancel').onclick=()=>done(false);
  });
}
"""
s=s.replace('async function resetSelectedRecords(){',insert+'\nasync function resetSelectedRecords(){',1)
p.write_text(s,encoding='utf-8')

p=Path('web/records.html'); s=p.read_text(encoding='utf-8')
s=s.replace('<span>Outcomes come from your attached MT5 EA trade_events.jsonl • no FCS history is used for Records verification.</span>', '<span>MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved.</span>')
s=s.replace('<link rel="stylesheet" href="/records-layout-fix.css" />','<link rel="stylesheet" href="/records-layout-fix.css" />\n<link rel="stylesheet" href="/v03.css" />')
p.write_text(s,encoding='utf-8')

# Main footer exact copyright and V.03 stylesheet.
p=Path('web/index.html'); s=p.read_text(encoding='utf-8')
s=s.replace('<link rel="stylesheet" href="/update-v001.css" />','<link rel="stylesheet" href="/update-v001.css" />\n<link rel="stylesheet" href="/v03.css" />')
s=s.replace('<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.02</div>','<div class="mhUpdateVersionV001" id="mhUpdateVersionV001">V.03</div>')
footer='<footer class="mhMainCopyright">MH ANALYSIS by Muhammad Hammad Shaukat — © 2026. All Rights Reserved.</footer>'
if footer not in s: s=s.replace('</div>\n<script src="/lightweight-charts.standalone.production.js"></script>', '</div>\n'+footer+'\n<script src="/lightweight-charts.standalone.production.js"></script>',1)
p.write_text(s,encoding='utf-8')
print('PASS V.03 exact requested UI/native changes')
