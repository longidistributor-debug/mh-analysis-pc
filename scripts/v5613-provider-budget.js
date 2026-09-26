const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

// V56.13: the provider limit is 3 ACTUAL FCS requests per rolling minute.
// V56.12 uses exactly 3 direct FCS requests per analysis action, therefore one
// NEW ANALYZE / RE-EVALUATE must reserve all 3 slots atomically. This prevents
// the old action-level limiter from accidentally allowing 6-9 provider calls.
{
  const p='main.go'; let s=read(p);
  const a=s.indexOf('func allowCall() bool {');
  const b=s.indexOf('\nfunc historyHandler(',a);
  if(a<0||b<0)throw new Error('allowCall block not found');
  const repl=`func reserveProviderCalls(n int) (bool, time.Duration) {\n\trateMu.Lock()\n\tdefer rateMu.Unlock()\n\tif n < 1 { n = 1 }\n\tnow := time.Now()\n\twindow := 61 * time.Second\n\tcut := now.Add(-window)\n\tj := 0\n\tfor _, t := range calls {\n\t\tif t.After(cut) {\n\t\t\tcalls[j] = t\n\t\t\tj++\n\t\t}\n\t}\n\tcalls = calls[:j]\n\tif len(calls)+n > providerMaxRequestsPerMinute {\n\t\twait := time.Second\n\t\tif len(calls) > 0 {\n\t\t\twait = calls[0].Add(window).Sub(now)\n\t\t\tif wait < time.Second { wait = time.Second }\n\t\t}\n\t\treturn false, wait\n\t}\n\tfor i := 0; i < n; i++ { calls = append(calls, now) }\n\treturn true, 0\n}\n\nfunc allowCall() bool {\n\tok, _ := reserveProviderCalls(1)\n\treturn ok\n}\n`;
  s=s.slice(0,a)+repl+s.slice(b);
  write(p,s);
}

{
  const p='analysis_context_v569.go'; let s=read(p);
  const start=s.indexOf('func v569AnalysisSnapshotHandler(w http.ResponseWriter, r *http.Request) {');
  const end=s.indexOf('\nfunc v569Outcome(',start);
  if(start<0||end<0)throw new Error('snapshot handler not found');
  let block=s.slice(start,end);
  const old=`\tif !allowCall() {\n\t\tw.WriteHeader(http.StatusTooManyRequests)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": "Too many fresh market requests. Please wait about a minute."})\n\t\treturn\n\t}\n`;
  must(block,old,'snapshot limiter');
  const neu=`\t// Reserve the full provider budget before starting the 3 direct requests.\n\t// Provider plan: max 3 requests / rolling minute; this action uses exactly 3.\n\tif ok, wait := reserveProviderCalls(3); !ok {\n\t\tsecs := int(math.Ceil(wait.Seconds()))\n\t\tif secs < 1 { secs = 1 }\n\t\tw.WriteHeader(http.StatusTooManyRequests)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": fmt.Sprintf("FCS 3-call minute budget is still cooling down. Please wait %d seconds.", secs), "retry_after_seconds": secs})\n\t\treturn\n\t}\n`;
  block=block.replace(old,neu);
  s=s.slice(0,start)+block+s.slice(end);
  write(p,s);
}

console.log('V56.13 provider 3-calls-per-minute budget fix applied');
