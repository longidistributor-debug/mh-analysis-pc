const fs=require('fs');
const p='web/app.js';
let s=fs.readFileSync(p,'utf8');
const fixes=[
  ["(m.equalHigh&&Math.abs(m.equalHigh-highTarget)<=tol?.35:0)","(m.equalHigh&&Math.abs(m.equalHigh-highTarget)<=tol ? .35 : 0)"],
  ["(m.equalLow&&Math.abs(m.equalLow-lowTarget)<=tol?.35:0)","(m.equalLow&&Math.abs(m.equalLow-lowTarget)<=tol ? .35 : 0)"],
  ["(failed?.1:0)","(failed ? .1 : 0)"],
  ["(lowSweep?.42:0)","(lowSweep ? .42 : 0)"],
  ["(last.c>mid?.2:0)","(last.c>mid ? .2 : 0)"],
  ["(highSweep?.42:0)","(highSweep ? .42 : 0)"],
  ["(last.c<mid?.2:0)","(last.c<mid ? .2 : 0)"]
];
for(const [a,b] of fixes)s=s.split(a).join(b);
fs.writeFileSync(p,s,'utf8');
console.log('V56.8 syntax hotfix applied');
