const fs=require('fs');
function read(p){return fs.readFileSync(p,'utf8').replace(/\r\n/g,'\n')}
function write(p,s){fs.writeFileSync(p,s,'utf8')}
function must(s,n,l){if(!s.includes(n))throw new Error(l+' marker not found')}

// V56.11: accept every FCS history shape we can safely recognize without
// issuing any extra provider request. In particular, support positional chart
// arrays and JSON-encoded nested payloads inside multi_url responses.
{
  const p='main.go';let s=read(p);
  const old=`\t\tcase []any:\n\t\t\tfor _, y := range x {\n\t\t\t\twalk(y, nil)\n\t\t\t}\n\t\t}\n`;
  must(s,old,'extractCandles array branch');
  const neu=`\t\tcase []any:\n\t\t\t// FCS chart-style candles can arrive as [t,o,h,l,c,v].\n\t\t\tif len(x) >= 5 {\n\t\t\t\tt, tOK := fint64(x[0])\n\t\t\t\to, oOK := fnum(x[1])\n\t\t\t\th, hOK := fnum(x[2])\n\t\t\t\tl, lOK := fnum(x[3])\n\t\t\t\tcl, cOK := fnum(x[4])\n\t\t\t\tif tOK && oOK && hOK && lOK && cOK {\n\t\t\t\t\tvv := 0.0\n\t\t\t\t\tif len(x) > 5 { vv, _ = fnum(x[5]) }\n\t\t\t\t\tif !seen[t] { seen[t] = true; out = append(out, candle{T:t,O:o,H:h,L:l,C:cl,V:vv}) }\n\t\t\t\t\treturn\n\t\t\t\t}\n\t\t\t}\n\t\t\tfor _, y := range x {\n\t\t\t\twalk(y, nil)\n\t\t\t}\n\t\tcase string:\n\t\t\t// Some multi_url plans/providers serialize an individual response as JSON text.\n\t\t\ttxt := strings.TrimSpace(x)\n\t\t\tif txt != "" && (strings.HasPrefix(txt, "{") || strings.HasPrefix(txt, "[")) {\n\t\t\t\tvar decoded any\n\t\t\t\tif json.Unmarshal([]byte(txt), &decoded) == nil { walk(decoded, key) }\n\t\t\t}\n\t\t}\n`;
  s=s.replace(old,neu);
  write(p,s);
}

{
  const p='analysis_context_v569.go';let s=read(p);
  const a=s.indexOf('func v569MultiPart(root map[string]any, n int) any {');
  const b=s.indexOf('\nfunc v569FindQuote(',a);
  if(a<0||b<0)throw new Error('v569MultiPart block not found');
  const replacement=`func v569DecodeJSONValue(v any) any {\n\ts, ok := v.(string)\n\tif !ok { return v }\n\tt := strings.TrimSpace(s)\n\tif t == "" || (!strings.HasPrefix(t, "{") && !strings.HasPrefix(t, "[")) { return v }\n\tvar out any\n\tif json.Unmarshal([]byte(t), &out) == nil { return out }\n\treturn v\n}\n\nfunc v569UnwrapMulti(v any) any {\n\tfor i := 0; i < 8; i++ {\n\t\tv = v569DecodeJSONValue(v)\n\t\tswitch z := v.(type) {\n\t\tcase []any:\n\t\t\tif len(z) == 1 { v = z[0]; continue }\n\t\t\treturn z\n\t\tcase map[string]any:\n\t\t\tif st, ok := z["status"].(bool); ok && !st { return z }\n\t\t\tfor _, key := range []string{"response","data","result"} {\n\t\t\t\tif x, ok := z[key]; ok { v = x; goto next }\n\t\t\t}\n\t\t\treturn z\n\t\tdefault:\n\t\t\treturn v\n\t\t}\n\tnext:\n\t}\n\treturn v\n}\n\n// V56.11 multi_url response-shape compatibility: locate urlN whether FCS\n// returns it at the root or under a response/data/result wrapper.\nfunc v569MultiPart(root map[string]any, n int) any {\n\tkeys := []string{fmt.Sprintf("url%d", n), fmt.Sprintf("%d", n), fmt.Sprintf("url[%d]", n)}\n\tvar find func(any, int) any\n\tfind = func(v any, depth int) any {\n\t\tif v == nil || depth > 7 { return nil }\n\t\tv = v569DecodeJSONValue(v)\n\t\tswitch z := v.(type) {\n\t\tcase map[string]any:\n\t\t\tfor _, k := range keys {\n\t\t\t\tif x, ok := z[k]; ok { return v569UnwrapMulti(x) }\n\t\t\t}\n\t\t\tfor _, k := range []string{"response","data","result"} {\n\t\t\t\tif x, ok := z[k]; ok { if got := find(x, depth+1); got != nil { return got } }\n\t\t\t}\n\t\tcase []any:\n\t\t\tfor _, x := range z { if got := find(x, depth+1); got != nil { return got } }\n\t\t}\n\t\treturn nil\n\t}\n\treturn find(root, 0)\n}\n\nfunc v569DeepError(v any, def string) string {\n\tseen := 0\n\tvar walk func(any) string\n\twalk = func(x any) string {\n\t\tif seen > 200 || x == nil { return "" }; seen++\n\t\tx = v569DecodeJSONValue(x)\n\t\tswitch z := x.(type) {\n\t\tcase map[string]any:\n\t\t\tfor _, k := range []string{"msg","message","details"} {\n\t\t\t\tif s, ok := z[k].(string); ok && strings.TrimSpace(s) != "" { return strings.TrimSpace(s) }\n\t\t\t}\n\t\t\tif e, ok := z["error"]; ok { if s := walk(e); s != "" { return s } }\n\t\t\tfor _, k := range []string{"response","data","result"} { if y, ok := z[k]; ok { if s := walk(y); s != "" { return s } } }\n\t\tcase []any:\n\t\t\tfor _, y := range z { if s := walk(y); s != "" { return s } }\n\t\tcase string:\n\t\t\tif strings.TrimSpace(z) != "" { return strings.TrimSpace(z) }\n\t\t}\n\t\treturn ""\n\t}\n\tif s := walk(v); s != "" { return s }\n\treturn def\n}\n`;
  s=s.slice(0,a)+replacement+s.slice(b);

  const oldParse=`\tprimary := extractCandles(v569MultiPart(root, 1))\n\thtf := extractCandles(v569MultiPart(root, 2))\n`;
  must(s,oldParse,'primary parser');
  const newParse=`\tprimaryPart := v569MultiPart(root, 1)\n\thtfPart := v569MultiPart(root, 2)\n\tquotePart := v569MultiPart(root, 3)\n\tprimary := extractCandles(primaryPart)\n\thtf := extractCandles(htfPart)\n`;
  s=s.replace(oldParse,newParse);

  const oldErr=`\t\tw.WriteHeader(status)\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": extractError(root, "No usable primary candles returned")})\n\t\treturn\n`;
  must(s,oldErr,'primary error response');
  const newErr=`\t\tw.WriteHeader(status)\n\t\tmsg := v569DeepError(primaryPart, "")\n\t\tif msg == "" { msg = v569DeepError(root, "No usable primary candles returned") }\n\t\t_ = json.NewEncoder(w).Encode(map[string]any{"error": msg, "primary_shape": fmt.Sprintf("%T", primaryPart)})\n\t\treturn\n`;
  s=s.replace(oldErr,newErr);

  s=s.replace('ask, bid, closePrice, quoteOK := v569FindQuote(v569MultiPart(root, 3))','ask, bid, closePrice, quoteOK := v569FindQuote(quotePart)');
  write(p,s);
}

console.log('V56.11 primary candle compatibility hotfix applied');
