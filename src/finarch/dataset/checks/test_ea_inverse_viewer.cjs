// Display only: original LLM judgment, safe quotation marks, and Q/C binding.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
class Node{
 constructor(tag,cls='',value=''){this.tag=tag;this.className=cls;this.value=value??'';this.children=[];}
 append(...n){this.children.push(...n);}
 get textContent(){return this.value+this.children.map(n=>n.textContent??String(n)).join('');}
}
const ctx=vm.createContext({el:(t,c,v)=>new Node(t,c,v),document:{createTextNode:t=>new Node('#text','',t)},jsonBox:()=>{},badge:v=>new Node('span','',v)});
vm.runInContext(fs.readFileSync('viewer/dataset/prepare/generation/common/03-validation/view.js','utf8'),ctx);
const variant='06-ea-earlier-input',base=variant+'/',stage='03-validation/07-ea-inverse-review/attempt-001';
const qc={question:'Recover A?',context:'😀 Total 100; B 40. <script>bad()</script>'};
const record={status:'COMPLETED',observation_sha256:'h',request_ref:stage+'/01-input/qc.json',evidence_display_check_ref:stage+'/03-result/evidence-display-check.json',inverse_review:{inverse_possible:true,missing_quantity:'A',reason:'Explicit total',formula:'A = 100 - 40 = 60'}};
const ref={path:stage+'/03-result/inverse-review.json',observation_sha256:'h'};
const row={run:{generation:{[base+'run.json']:{inverse_review_ref:ref,observation:qc},[base+ref.path]:record,[base+record.request_ref]:qc,[base+record.evidence_display_check_ref]:{status:'PASS',resolved_evidence:[{field:'context',start:8,end:11,quote:'100'},{field:'context',start:15,end:17,quote:'40'}]}}}};
let panel=new Node('div');ctx.renderEAInverseReview(panel,row,variant);
assert.match(panel.textContent,/역산 가능 · true/);assert.match(panel.textContent,/A = 100 - 40 = 60/);
const body=panel.children[0].children.find(n=>n.className==='prose ea-inverse-observation'&&n.textContent===qc.context);
assert.ok(body);assert.deepEqual(body.children.filter(n=>n.tag==='mark').map(n=>n.textContent),['100','40']);
assert.ok(body.children.every(n=>n.tag==='#text'||n.tag==='mark'));
record.inverse_review.inverse_possible=false;record.inverse_review.formula=null;
panel=new Node('div');ctx.renderEAInverseReview(panel,row,variant);assert.match(panel.textContent,/역산 불가 · false/);assert.doesNotMatch(panel.textContent,/A = 100/);
record.status='CALL_FAILED';record.inverse_review=null;
panel=new Node('div');ctx.renderEAInverseReview(panel,row,variant);assert.match(panel.textContent,/실패는 false가 아닙니다/);assert.doesNotMatch(panel.textContent,/역산 불가 · false/);
row.run.generation[base+'run.json'].observation={...qc,context:'Changed'};
panel=new Node('div');ctx.renderEAInverseReview(panel,row,variant);assert.match(panel.textContent,/현재 EA 문장이 달라/);
row.run.generation[base+'run.json'].inverse_review_ref={...ref,path:'../foreign.json'};
assert.equal(ctx.eaInverseRecord(row,variant).stale,true);
new Function(fs.readFileSync('viewer/dataset/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1]);
assert.match(fs.readFileSync('viewer/dataset/prepare/generation/common/05-human-review/view.js','utf8'),/renderEAInverseReview\(panel,row,variant\)/);
console.log('EA inverse viewer: true/false/failure, Unicode highlights, safe text, stale binding, G03/G05 and JS syntax PASS');
