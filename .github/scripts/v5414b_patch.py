from pathlib import Path
import re, runpy

src = Path('.github/scripts/v5414_patch.py').read_text(encoding='utf-8')
pat = r"# When user opens WhatsApp manually, force a full repaint.*?s = s\.replace\(needle, needle \+ '; chRedrawWindowV5414\.Call\(wv2WhatsappContainer,0,0,0x0001\|0x0080\|0x0100\); chUpdateWindow\.Call\(wv2WhatsappContainer\)', 1\)\n"
repl = '''# When user opens WhatsApp manually, force a full repaint of the same session so
# the view never stays as a blank theme-colour surface after a background send.
show_fn = s.index('func wv2ShowLocal(which int)')
case2 = s.index('\\tcase 2:', show_fn)
case3 = s.index('\\n\\tcase 3:', case2)
seg = s[case2:case3]
focus = 'wv2Whatsapp.Focus()'
if focus not in seg:
    raise SystemExit('V54.14 manual WhatsApp Focus anchor missing')
seg = seg.replace(focus, focus + '; chRedrawWindowV5414.Call(wv2WhatsappContainer,0,0,0x0001|0x0080|0x0100); chUpdateWindow.Call(wv2WhatsappContainer)', 1)
s = s[:case2] + seg + s[case3:]
'''
patched, n = re.subn(pat, repl, src, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not make V54.14 repaint patch resilient')
tmp = Path('.github/scripts/.v5414_runtime.py')
tmp.write_text(patched, encoding='utf-8', newline='\n')
runpy.run_path(str(tmp), run_name='__main__')
