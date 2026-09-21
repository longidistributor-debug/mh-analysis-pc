from pathlib import Path
import re

MARK = "MH_PUBLIC_VERSION_V01"
VERSION = Path("VERSION").read_text(encoding="utf-8").strip()
if VERSION != "V.01":
    raise SystemExit(f"Expected VERSION V.01, got {VERSION!r}")
PUBLIC = f"{VERSION} (CH Shaukat Ali)"

# Main visible version.
p = Path("web/index.html")
s = p.read_text(encoding="utf-8")
s2, n = re.subn(r'<div class="version">.*?</div>', f'<div class="version">{PUBLIC}</div>', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit("main version anchor missing")
p.write_text(s2, encoding="utf-8")

# Records visible version.
p = Path("web/records.html")
s = p.read_text(encoding="utf-8")
s2, n = re.subn(r'<div class="recordsVersion">.*?</div>', f'<div class="recordsVersion">{PUBLIC}</div>', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit("records version anchor missing")
p.write_text(s2, encoding="utf-8")

# Normal copy/select/drag protection for displayed wording. Inputs remain usable.
copy_css = r'''

/* MH_PUBLIC_VERSION_V01 — displayed wording copy/select guard */
html,body,body *:not(input):not(textarea):not(select):not(option):not([contenteditable="true"]){
  -webkit-user-select:none!important;user-select:none!important;
}
img{-webkit-user-drag:none!important;user-drag:none!important}
'''
for name in ("web/styles.css", "web/records.css", "web/auth.css"):
    p = Path(name)
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    if "MH_PUBLIC_VERSION_V01 — displayed wording copy/select guard" not in s:
        s += copy_css
    p.write_text(s, encoding="utf-8")

copy_js = r'''

// MH_PUBLIC_VERSION_V01 — block ordinary copying/selection of displayed app wording.
(function mhCopyGuardV01(){
  if(window.__mhCopyGuardV01)return; window.__mhCopyGuardV01=true;
  const editable=t=>!!(t && (t.closest?.('input,textarea,select,[contenteditable="true"]')));
  ['copy','cut','contextmenu','dragstart','selectstart'].forEach(type=>{
    document.addEventListener(type,e=>{if(!editable(e.target))e.preventDefault()},true);
  });
  document.addEventListener('keydown',e=>{
    if(editable(e.target))return;
    const k=String(e.key||'').toLowerCase();
    if((e.ctrlKey||e.metaKey) && ['c','a','s','u','p'].includes(k)){e.preventDefault();e.stopPropagation();}
    if(e.key==='F12' || ((e.ctrlKey||e.metaKey)&&e.shiftKey&&['i','j','c'].includes(k))){e.preventDefault();e.stopPropagation();}
  },true);
})();
'''
for name in ("web/app.js", "web/records.js", "web/auth.js"):
    p = Path(name)
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    if "function mhCopyGuardV01" not in s:
        s += copy_js
    p.write_text(s, encoding="utf-8")

print(f"{MARK}: main + Records version = {PUBLIC}; ordinary displayed-text copy/select blocked")
