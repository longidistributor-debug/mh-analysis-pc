from pathlib import Path

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')

old='if which == 4 { go func(){ _ = chEnsureExnessBrowser() }() } // MH_EXNESS_LOGIN_FIX_V796'
new='if which == 4 { go func(){ if chEnsureExnessBrowser()==nil { time.Sleep(900*time.Millisecond); exnessApplyLoginCleanup() } }() } // MH_EXNESS_LOGIN_FIX_V796'
if new in s:
    print('PASS Exness login cleanup already runs on tab open')
elif old in s:
    s=s.replace(old,new,1)
    print('PASS Exness login cleanup now runs on tab open')
else:
    raise SystemExit('Exness lazy-switch anchor missing')

# Preserve the original Signal Link command ID (1003) and keep Exness at 1004.
# Records is the new control, so move only Records to an unused command ID.
old_id='\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n'
new_id='\tidRecords       = 1005 // MH_RECORDS_V796_PATCH\n'
if new_id in s:
    print('PASS native IDs already separated: Signal Link 1003, Exness 1004, Records 1005')
elif old_id in s:
    s=s.replace(old_id,new_id,1)
    print('PASS native IDs separated: Signal Link 1003, Exness 1004, Records 1005')
else:
    raise SystemExit('Records native ID anchor missing')

p.write_text(s,encoding='utf-8')
