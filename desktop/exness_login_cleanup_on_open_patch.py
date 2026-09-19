from pathlib import Path

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
old='if which == 4 { go func(){ _ = chEnsureExnessBrowser() }() } // MH_EXNESS_LOGIN_FIX_V796'
new='if which == 4 { go func(){ if chEnsureExnessBrowser()==nil { time.Sleep(900*time.Millisecond); exnessApplyLoginCleanup() } }() } // MH_EXNESS_LOGIN_FIX_V796'
if new in s:
    print('PASS Exness login cleanup already runs on tab open')
elif old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')
    print('PASS Exness login cleanup now runs on tab open')
else:
    raise SystemExit('Exness lazy-switch anchor missing')
