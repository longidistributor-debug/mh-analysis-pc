from pathlib import Path
import re

def rd(p): return Path(p).read_text(encoding='utf-8-sig')
def wr(p,s): Path(p).write_text(s,encoding='utf-8',newline='\n')
def need(c,m):
    if not c: raise SystemExit(m)

# Register the existing, proven MT5 EA Common-Files bridge.
p='main.go'; s=rd(p)
if 'registerEASignalBridgeRoutes(mux)' not in s:
    anchor='\tregisterRecordsRoutes(mux)    // MH_RECORDS_V796_PATCH\n'
    need(anchor in s,'V30 EA route anchor missing')
    s=s.replace(anchor,anchor+'\tregisterEASignalBridgeRoutes(mux) // V30 automatic unique-signal pending bridge\n',1)
wr(p,s)

# app.js: explicit unique-signal EA handoff. This is the single automatic pending-order path.
p='web/app.js'; s=rd(p)
if 'sendUniqueSignalToEAV30' not in s:
    anchor='async function prepareMT5SignalV796(d,state=\'NEW\'){'
    need(anchor in s,'V30 EA JS insertion anchor missing')
    fn=r'''async function sendUniqueSignalToEAV30(d){
  const sig=d?.signal;if(!sig||d?._sameActiveSignal)return null;
  const market=Number((candleCache.get(keyFor())||[]).at(-1)?.c)||Number(sig.entry);
  const pending=derivePendingTypeV30(sig.direction,Number(sig.entry),market);
  const signalId=`MH${Date.now()}_${symbol}_${timeframe}`;
  try{
    const r=await fetch('/api/mt5/ea/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_id:signalId,symbol,type:pending,entry:Number(sig.entry),sl:Number(sig.sl),tp:Number(sig.tp1),lot:0.02,expiry:0})});
    let j={};try{j=await r.json()}catch(_){ }
    if(!r.ok)throw new Error(j.error||`EA bridge HTTP ${r.status}`);
    setAutoStatus(`MT5 pending sent to EA • ${pending}`,'good');
    return j;
  }catch(e){
    console.warn('MT5 EA pending bridge failed',e);
    setAutoStatus(`MT5 pending failed • ${e.message||e}`,'bad');
    return null;
  }
}
function derivePendingTypeV30(direction,entry,market){
  direction=String(direction||'').toUpperCase();
  if(direction==='BUY')return entry<=market?'BUY_LIMIT':'BUY_STOP';
  return entry>=market?'SELL_LIMIT':'SELL_STOP';
}

'''
    s=s.replace(anchor,fn+anchor,1)

old="if(d.signal&&!d._sameActiveSignal){void captureSignalRecordV30(d);void prepareMT5SignalV796(d,'NEW');} // V30 unique signal fan-out"
new="if(d.signal&&!d._sameActiveSignal){void captureSignalRecordV30(d);void sendUniqueSignalToEAV30(d);void prepareMT5SignalV796(d,'NEW');} // V30 unique signal fan-out"
need(old in s,'V30 unique fanout post anchor missing'); s=s.replace(old,new,1)

old="$('#analysisStatusHeading').textContent=mode==='REEVAL'?'RE-EVALUATE SIGNAL':'NEW ANALYSIS';"
new="$('#analysisStatusHeading').textContent=mode==='REEVAL'?'RE-EVALUATE SIGNAL':(d?._sameActiveSignal?'SAME SIGNAL STILL ACTIVE — NO NEW SIGNAL':'NEW ANALYSIS');"
need(old in s,'V30 duplicate heading anchor missing'); s=s.replace(old,new,1)

old="""        }else setAutoStatus('Manual analysis ready • WhatsApp number not saved','warn');
"""
new="""        }else if(d._sameActiveSignal)setAutoStatus('Same signal still active • no new WhatsApp / Record / MT5 pending','warn');
        else setAutoStatus('Manual analysis ready • WhatsApp Signal Link not saved','warn');
"""
need(old in s,'V30 manual duplicate status anchor missing'); s=s.replace(old,new,1)
wr(p,s)

# Native MT5 prefill remains visual/support only. EA bridge above owns final order placement,
# preventing two pending orders from the same unique signal.
p='mt5_prefill.go'; s=rd(p)
pattern=re.compile(r'''\$place=\$null\n\$buttons=All \$dialog \(\[System\.Windows\.Automation\.ControlType\]::Button\).*?Out-Result \$true 'PENDING ORDER SUBMITTED' \(\\"\$\(\$p\.pending_type\).*?\\"\)''',re.S)
replacement="Out-Result $true 'READY - EA HANDLES AUTO PENDING' (\"$($p.pending_type) • Entry $($p.entry) • SL $($p.sl) • TP1 $($p.tp1)\")"
s,n=pattern.subn(replacement,s,count=1)
if n==0:
    a=s.find("$place=$null")
    b=s.find("\n`\n",a)
    if a>=0 and b>a:
        s=s[:a]+replacement+s[b:]
s=s.replace("[pscustomobject]@{ok=$ok;status=$status;detail=$detail;submitted=($status -eq 'PENDING ORDER SUBMITTED')} | ConvertTo-Json -Compress","[pscustomobject]@{ok=$ok;status=$status;detail=$detail;submitted=$false} | ConvertTo-Json -Compress")
s=s.replace('res.Status = "PENDING ORDER SUBMITTED"','res.Status = "READY - EA HANDLES AUTO PENDING"')
wr(p,s)

# Final visible-text Unicode sanitation. Old source mixes cp1252 punctuation with raw C1
# byte code-points, so reconstruct the original byte stream one character at a time.
def mixed_legacy_bytes(x):
    out=bytearray()
    for ch in x:
        try:
            b=ch.encode('cp1252')
            if len(b)==1:
                out.extend(b); continue
        except Exception:
            pass
        o=ord(ch)
        if o<=255:
            out.append(o); continue
        raise UnicodeError('not legacy-byte text')
    return bytes(out)

def recover_visible_html(path):
    src=rd(path)
    def fix_node(m):
        x=m.group(1)
        if not any(k in x for k in ('Ã','Â','â','ð','Ø','Ù','�')):
            return '>'+x+'<'
        y=x
        for _ in range(3):
            try:
                z=mixed_legacy_bytes(y).decode('utf-8')
                if z==y: break
                y=z
            except Exception:
                break
        # No replacement glyph or legacy mojibake marker is allowed in visible text.
        y=y.replace('\ufffd','')
        if any(k in y for k in ('Ã','Â','â','ð','Ø','Ù')):
            parts=[]
            for token in re.split(r'(\s+)',y):
                if any(k in token for k in ('Ã','Â','â','ð','Ø','Ù')):
                    try: token=mixed_legacy_bytes(token).decode('utf-8')
                    except Exception: token='•'
                parts.append(token)
            y=''.join(parts).replace('\ufffd','')
        return '>'+y+'<'
    src=re.sub(r'>([^<>]+)<',fix_node,src)
    src=re.sub(r'<div class="bismillah">.*?</div>','<div class="bismillah">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>',src,count=1)
    src=src.replace('\ufffd','')
    wr(path,src)

recover_visible_html('web/index.html')
recover_visible_html('web/records.html')

print('V30 post patch applied: EA auto-pending is single final-placement path; mixed-byte Unicode sanitized')
