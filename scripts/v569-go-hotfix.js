const fs=require('fs');
const p='analysis_context_v569.go';
let s=fs.readFileSync(p,'utf8');
const old='\tu, _ := url.Parse("https://api-v4.fcsapi.com/forex/multi_url")';
const neu='\tmultiEndpoint := "https://api-v4.fcsapi.com/forex/multi_url"\n\tif strings.EqualFold(strings.TrimSpace(q.Symbol), "BTCUSDT") {\n\t\tmultiEndpoint = "https://api-v4.fcsapi.com/crypto/multi_url"\n\t}\n\tu, _ := url.Parse(multiEndpoint)';
if(!s.includes(old))throw new Error('V56.9 multi_url endpoint marker not found');
s=s.replace(old,neu);
fs.writeFileSync(p,s,'utf8');
console.log('V56.9 Go precision hotfix applied');
