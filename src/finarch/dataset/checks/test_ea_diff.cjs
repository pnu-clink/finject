const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const ctx=vm.createContext({});vm.runInContext(html.slice(html.indexOf('function eaSentenceDiff('),html.indexOf('// [TP03]')),ctx);
const cases=[['The fee is [EA_DELETE].','The fee is reported.'],['same','same'],['','new'],['old',''],['\uac00😀 80,000\uc785\ub2c8\ub2e4.','\uac00😀 \uae08\uc561\uc785\ub2c8\ub2e4.'],['A x B y C','A z B w C'],['a  b\n c','a b\r\n c'],['abc '.repeat(600),'xyz '.repeat(600)],['<script>alert(1)</script>','<img>']];
for(const [a,b] of cases){const blocks=ctx.eaSentenceDiff(a,b);assert.equal(blocks.map(x=>x.kind==='equal'?x.text:x.before).join(''),a);assert.equal(blocks.map(x=>x.kind==='equal'?x.text:x.after).join(''),b);}
const changes=ctx.eaSentenceDiff('A x B y C','A z B w C');assert.equal(changes.filter(x=>x.kind==='change').length,2);assert.ok(changes.some(x=>x.kind==='equal'&&x.text===' B '));
console.log('EA diff: 9 round-trip cases + separated edits PASS');
