from pathlib import Path

MARK='MH_RECORDS_MT5_LOCAL_V797'

def rep(s, old, new, label):
    if new in s:
        return s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return s.replace(old,new,1)

# Register local MT5 lifecycle records routes beside the legacy Records route.
p=Path('main.go')
s=p.read_text(encoding='utf-8')
if 'registerRecordsV2Routes(mux)' not in s:
    s=rep(s,
        '\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n',
        '\tregisterRecordsRoutes(mux) // MH_RECORDS_V796_PATCH\n\tregisterRecordsV2Routes(mux) // '+MARK+'\n',
        'register Records v2 routes')
p.write_text(s,encoding='utf-8')

# Use one stable signal ID for both the saved Record and the EA signal handoff.
p=Path('web/app.js')
s=p.read_text(encoding='utf-8')
if 'function ensureMHSignalIdV796' not in s:
    s=rep(s,
        'async function captureSignalRecordV796(d,state=\'NEW\'){',
        '''function ensureMHSignalIdV796(d){
  if(!d)return `MH${Date.now()}_${String(symbol||'SYM').replace(/[^A-Za-z0-9_.-]/g,'')}_${String(timeframe||'TF').replace(/[^A-Za-z0-9_.-]/g,'')}`;
  if(!d._mhSignalId){
    const nonce=Math.random().toString(36).slice(2,8);
    d._mhSignalId=`MH${Date.now()}_${String(symbol||'SYM').replace(/[^A-Za-z0-9_.-]/g,'')}_${String(timeframe||'TF').replace(/[^A-Za-z0-9_.-]/g,'')}_${nonce}`;
  }
  return d._mhSignalId;
}
async function captureSignalRecordV796(d,state='NEW'){''',
        'stable signal id function')

s=s.replace("await fetch('/api/records/capture'","await fetch('/api/records-v2/capture'",1)
if 'signal_id:ensureMHSignalIdV796(d),symbol,timeframe' not in s:
    s=rep(s,
        '      symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,\n',
        '      signal_id:ensureMHSignalIdV796(d),symbol,timeframe,direction:sig.direction,entry:sig.entry,sl:sig.sl,tp1:sig.tp1,tp2:sig.tp2,\n',
        'capture signal id')

old="  const signalId=`MH${Date.now()}_${symbol}_${timeframe}`;"
new="  const signalId=ensureMHSignalIdV796(d);"
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('EA signal id anchor not found')

p.write_text(s,encoding='utf-8')
print('PASS MT5 local Records patch: stable signal ID + v2 capture + local lifecycle routes')
