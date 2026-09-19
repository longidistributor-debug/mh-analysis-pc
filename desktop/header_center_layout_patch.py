from pathlib import Path

css_path = Path('web/runtime-fixes.css')
css = css_path.read_text(encoding='utf-8')
start = '/* MH_HEADER_CENTER_V796_START */'
end = '/* MH_HEADER_CENTER_V796_END */'
block = r'''/* MH_HEADER_CENTER_V796_START */
/* Keep branding compact while pinning Bismillah to the exact geometric header centre. */
.appHeader{
  position:relative!important;
  display:flex!important;
  grid-template-columns:none!important;
  align-items:center!important;
  justify-content:space-between!important;
  padding:0 8px!important;
}
.brandArea,.headerStatus{
  position:relative!important;
  z-index:2!important;
  min-width:0!important;
  flex:1 1 0!important;
}
.brandArea{
  gap:8px!important;
  flex-wrap:nowrap!important;
  white-space:nowrap!important;
}
.brandArea>div{
  flex:0 0 auto!important;
  min-width:max-content!important;
}
.version{
  white-space:nowrap!important;
  overflow:visible!important;
  text-overflow:clip!important;
  font-size:8px!important;
  line-height:1.1!important;
  letter-spacing:0!important;
  margin-top:2px!important;
}
.bismillahArea{
  position:absolute!important;
  left:50%!important;
  top:50%!important;
  transform:translate(-50%,-50%)!important;
  width:max-content!important;
  max-width:46vw!important;
  margin:0!important;
  justify-content:center!important;
  z-index:1!important;
  pointer-events:none!important;
}
.headerStatus{
  justify-content:flex-end!important;
  flex-wrap:nowrap!important;
  white-space:nowrap!important;
}
@media(max-width:1200px){
  .version{font-size:7.5px!important}
  .bismillahArea{max-width:52vw!important}
}
/* MH_HEADER_CENTER_V796_END */'''

if start in css and end in css:
    a = css.index(start)
    b = css.index(end, a) + len(end)
    css = css[:a] + block + css[b:]
else:
    css = css.rstrip() + '\n\n' + block + '\n'

css_path.write_text(css, encoding='utf-8')

html_path = Path('web/index.html')
html = html_path.read_text(encoding='utf-8')
expected = 'v79.6 AUTO CYCLE (HAMMAD & SOMI)'
if expected not in html:
    raise SystemExit('Expected branded version text missing')
# Do not alter the supplied Arabic wording.
arabic = 'بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ'
if arabic not in html:
    raise SystemExit('Bismillah Arabic wording changed or missing')
html_path.write_text(html, encoding='utf-8')
print('PASS exact-centre Bismillah + one-line Hammad & Somi header layout applied')
