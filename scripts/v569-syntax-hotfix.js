const fs=require('fs');
const p='web/app.js';
let s=fs.readFileSync(p,'utf8');
s=s.split("quality:rollover?.35:.58").join("quality:rollover ? .35 : .58");
fs.writeFileSync(p,s,'utf8');
console.log('V56.9 syntax hotfix applied');
