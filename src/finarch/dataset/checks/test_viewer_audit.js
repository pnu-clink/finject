// Current text binding is consequential: an old PASS must not approve new text.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
new Function(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const ctx=vm.createContext({eventOf:(r,k)=>r.run.artifacts[k],sameJson:(a,b)=>JSON.stringify(a)===JSON.stringify(b),names:{},realizationStage:r=>r.stage});
vm.runInContext(html.slice(html.indexOf('function auditRecord('),html.indexOf('function realizedStatus(')),ctx);
const stage='05-text/EA_01/01-generate-text/v3',audit='05-text/EA_01/03-audit-meaning/v1';
const r={axis:'EA',label:'EA_01',stage,sample:{context:'original',question:'Q'},run:{artifacts:{}}},a=r.run.artifacts;
a['05-text/EA_01/latest-audit.json']={stage:audit};a[audit+'/03-result.json']={status:'PASS',stage16_ref:stage,plan_sha256:'same'};
a[audit+'/01-input.json']={original_context:'original',context:'changed',question:'Q'};
a[stage+'/04-final-observation.json']={context:'changed',question:'Q'};a[stage+'/03-result/metadata.json']={plan_sha256:'same'};
assert.equal(ctx.auditRecord(r).stale,false);assert.match(ctx.auditStatus(r),/이번 범위 통과/);
a[stage+'/04-final-observation.json'].context='new text';assert.equal(ctx.auditRecord(r).stale,true);assert.match(ctx.auditStatus(r),/재검사 필요/);
a[stage+'/04-final-observation.json'].context='changed';a[stage+'/03-result/metadata.json'].plan_sha256='new plan';assert.equal(ctx.auditRecord(r).stale,true);
a[stage+'/03-result/metadata.json'].plan_sha256='same';r.variant={plan:{target:'A'}};
a[audit+'/plan-binding.json']={plan_snapshot:{target:'A'}};assert.equal(ctx.auditRecord(r).stale,false);
r.variant.plan.target='B';assert.equal(ctx.auditRecord(r).stale,true);
a['05-text/EA_01/latest-audit.json'].stage='05-text/OTHER/03-audit-meaning/v1';assert.equal(ctx.auditRecord(r),null);
console.log('viewer audit: current text, stale text, stale plan and foreign pointer checks PASS');

// Render both response generations: no undefined state/quote UI for v3.
class Node {
 constructor(tag,cls='',value=''){this.tag=tag;this.className=cls;this.value=value;this.children=[];}
 append(...nodes){this.children.push(...nodes);}
 get textContent(){return this.value+this.children.map(n=>n.textContent??String(n)).join('');}
}
ctx.el=(tag,cls,value)=>new Node(tag,cls,value);
ctx.box=(title,value)=>new Node('div','',title+': '+value);
ctx.jsonBox=()=>{};
ctx.currentAuditPromptButton=()=>new Node('button','','현재 유형 검증 지침 보기 · 미호출');
ctx.llmCallRecords=()=>[];
ctx.auditFailureItems=()=>[];ctx.appendFailureEvidence=()=>{};
a['05-text/EA_01/latest-audit.json'].stage=audit;
r.variant.plan.target='A';
const report=a[audit+'/03-result.json'];
Object.assign(report,{audit_version:3,model:'gpt-5.6-luna',effort:'none',findings:[
 {criterion:'planned_change',judgment:'PASS',reason:''},
 {criterion:'unintended_change',judgment:'PASS',reason:''},
 {criterion:'readability',judgment:'UNKNOWN',reason:'지칭 대상 불확실'}],status:'NOT_EVALUATED'});
let panel=new Node('div');ctx.semanticAuditPanel(panel,r);
assert.match(panel.textContent,/세 가지 의미 판단/);assert.match(panel.textContent,/추론: none/);
assert.match(panel.textContent,/허용하지 않은 의미 변화 없음/);assert.match(panel.textContent,/지칭 대상 불확실/);
assert.doesNotMatch(panel.textContent,/관찰 설명|실제 문장에서 관찰한 상태|undefined/);
delete report.audit_version;report.observed_state='CONFLICT';report.state_reason='historical';
panel=new Node('div');ctx.semanticAuditPanel(panel,r);
assert.match(panel.textContent,/이전 8항목/);assert.match(panel.textContent,/historical/);
assert.ok(panel.children[0].children.some(n=>n.tag==='details'));
console.log('viewer audit: compact/legacy rendering, none model, no synthetic state PASS');
