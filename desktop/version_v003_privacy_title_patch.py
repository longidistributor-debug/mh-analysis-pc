from pathlib import Path

MARK = "MH_V003_PRIVACY_TITLE"

# V.03: keep the native window title clean and strengthen capture exclusion.
p = Path("chrome_host.go")
s = p.read_text(encoding="utf-8")
if MARK not in s:
    s = s.replace("package main\n", "package main\n\n// "+MARK+"\n", 1)

    # Remove timestamp/build suffixes from the visible native title.
    # Cover the known generated-title forms without changing internal versioning.
    for old in [
        'fmt.Sprintf("MH%%20Analysis(%s)",',
        'fmt.Sprintf("MH Analysis(%s)",',
        'fmt.Sprintf("MH%20Analysis(%s)",',
    ]:
        if old in s:
            # handled below by line rewrite
            pass
    lines = s.splitlines()
    for i,line in enumerate(lines):
        if ('MH%20Analysis(' in line or 'MH%%20Analysis(' in line or 'MH Analysis(' in line) and 'Sprintf' in line:
            prefix = line[:len(line)-len(line.lstrip())]
            # Preserve assignment target when possible.
            if ':=' in line:
                lhs=line.split(':=',1)[0].strip()
                lines[i]=prefix+lhs+' := "MH Analysis" // '+MARK
            elif '=' in line:
                lhs=line.split('=',1)[0].strip()
                lines[i]=prefix+lhs+' = "MH Analysis" // '+MARK
    s='\n'.join(lines)+'\n'

    # The V81.6 protection loop already enumerates every top-level window owned by
    # this EXE every 250ms and applies WDA_EXCLUDEFROMCAPTURE. V.03 adds the older
    # WDA_MONITOR fallback for Windows builds where EXCLUDEFROMCAPTURE is rejected.
    old='\tchSetWindowDisplayAffinityV816.Call(hwnd, chWDAExcludeFromCaptureV816)\n'
    new='''\tr1, _, _ := chSetWindowDisplayAffinityV816.Call(hwnd, chWDAExcludeFromCaptureV816)\n\tif r1 == 0 {\n\t\t// WDA_MONITOR fallback: remote/capture paths receive protected content rather than the app.\n\t\tchSetWindowDisplayAffinityV816.Call(hwnd, 0x00000001)\n\t}\n'''
    if old in s:
        s=s.replace(old,new,1)
    elif 'WDA_MONITOR fallback' not in s:
        raise SystemExit('capture protection anchor missing')
    p.write_text(s,encoding='utf-8')

# Public version V.03 while keeping the same verified update channel.
p=Path('updater.go')
s=p.read_text(encoding='utf-8')
s=s.replace('const mhPublicVersionV001 = "V.02"','const mhPublicVersionV001 = "V.03"',1)
p.write_text(s,encoding='utf-8')

p=Path('web/index.html')
s=p.read_text(encoding='utf-8')
s=s.replace('id="mhUpdateVersionV001">V.02</div>','id="mhUpdateVersionV001">V.03</div>',1)
s=s.replace('V.02 AUTO CYCLE (HAMMAD & SOMI)','V.03 AUTO CYCLE (HAMMAD & SOMI)',1)
p.write_text(s,encoding='utf-8')

p=Path('web/update-v001.js')
s=p.read_text(encoding='utf-8').replace("j.current||'V.02'","j.current||'V.03'")
p.write_text(s,encoding='utf-8')

print(MARK+': clean title, V.03 version, and capture fallback applied')
