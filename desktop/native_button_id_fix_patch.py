from pathlib import Path

p=Path('chrome_host.go')
s=p.read_text(encoding='utf-8')
old='\tidRecords       = 1003 // MH_RECORDS_V796_PATCH\n'
new='\tidRecords       = 1005 // MH_RECORDS_V796_PATCH\n'
if new in s:
    print('PASS native IDs already separated: Signal Link 1003, Exness 1004, Records 1005')
elif old in s:
    s=s.replace(old,new,1)
    p.write_text(s,encoding='utf-8')
    print('PASS native IDs separated: Signal Link 1003, Exness 1004, Records 1005')
else:
    raise SystemExit('Records native ID anchor missing')
