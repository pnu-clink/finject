/* VS02: saved files + an in-memory DOM double. No browser, model, network or writes.
   Run from the project root: node src/finarch/dataset/checks/test_viewer_llm_debug.js */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
class Element {
 constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.style={};this.events={};this._text='';this.isConnected=true;}
 set textContent(v){this._text=String(v);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 prepend(...nodes){for(const n of nodes)n.parent=this;this.children.unshift(...nodes);}
 replaceChildren(...nodes){this._text='';this.children=[];this.append(...nodes);}
 setAttribute(k,v){this.attributes[k]=String(v);}
 addEventListener(k,fn){(this.events[k]??=[]).push(fn);}
 emit(k,event={}){for(const fn of this.events[k]||[])fn(event);}
 click(){if(!this.disabled)return this.onclick?.();}
 focus(){document.activeElement=this;}
 select(){copied=this.value;}
 showModal(){this.open=true;}
 close(){this.open=false;this.emit('close');}
 remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 getBoundingClientRect(){return {left:20,right:400,top:20,bottom:500};}
}
let copied,fetches=[];
const document={createElement:tag=>new Element(tag),body:new Element('body'),activeElement:null,events:{},addEventListener:Element.prototype.addEventListener,removeEventListener(k,fn){this.events[k]=this.events[k].filter(f=>f!==fn);},execCommand(){for(const fn of this.events.copy||[])fn({clipboardData:{setData:(type,value)=>{copied=value;}},preventDefault(){}});return true;}};
const navigator={clipboard:{writeText:async text=>{copied=text;}}};
const ctx=vm.createContext({document,navigator,DATA:{live:true},console,fetch:async url=>{fetches.push(url);return {ok:true,json:async()=>({schema:{type:'object'}})};}});
vm.runInContext(html.slice(html.indexOf('const text='),html.indexOf('function box(')),ctx);
vm.runInContext('function eventOf(row,key){return row.run.artifacts[key];}',ctx);
vm.runInContext(html.match(/function realizationStage\(r\)\{[^\n]+/)[0],ctx);
vm.runInContext(html.slice(html.indexOf('function showSchemaDialog('),html.indexOf('function renderDetail(')),ctx);
const all=(root,fn)=>[root,...root.children.flatMap(n=>all(n,()=>true))].filter(fn);
const btn=(root,label)=>all(root,n=>n.tagName==='button'&&n.textContent===label)[0];
const klass=(root,name)=>all(root,n=>(n.className||'').split(' ').includes(name));
const mountDetails=root=>{for(const d of all(root,n=>n.tagName==='details')){d.open=true;d.emit('toggle');}};
function loadRun(name){const path='reports/run/'+name+'/test-0001',artifacts={};
 for(const entry of fs.readdirSync(path,{recursive:true,withFileTypes:true})){if(!entry.isFile()||!['.json','.jsonl'].some(ext=>entry.name.endsWith(ext)))continue;
  const full=(entry.parentPath||entry.path)+'/'+entry.name,relative=full.slice(path.length+1),raw=fs.readFileSync(full,'utf8');artifacts[relative]=entry.name.endsWith('.json')?JSON.parse(raw):raw;
 }
 return {label:'ANSWER',axis:'ANSWER',run:{path,artifacts}};
}
const results=[];
async function check(name,fn){await fn();results.push(name);}
(async()=>{
 const success=loadRun('first-10-pot-stepwise-v1'),failure=loadRun('first-10-pot'),replay=loadRun('first-10-pot-validated-v3');
 // This fixture models preparation before DTT; later production calls must not change that scenario.
 replay.run.artifacts=Object.fromEntries(Object.entries(replay.run.artifacts).filter(([path])=>!path.startsWith('05-text/')));
 await check('실제 성공: provider+P01 한 묶음, 프롬프트/입력/원응답/해시',()=>{
  const calls=ctx.llmCallRecords(success,'pot.author');assert.equal(calls.length,1);const call=calls[0];
  assert.equal(call.cli.model,'gpt-5.3-codex-spark');assert.ok(call.cli.prompt.includes(call.model.input.question));assert.equal(call.model.prompt,undefined);assert.equal(typeof call.raw.text,'string');assert.ok(call.result.data.code);
  assert.equal(ctx.schemaEvidence(call.cli.response_schema,call.definition,call.check).kind,'match');assert.equal(ctx.schemaEvidence(call.stageSchema,call.stageSchema,call.stageCheck).kind,'match');
  assert.equal(ctx.callLogEvents(success,call)[0].attempt,1);
  const root=new Element('div');ctx.stageProcessing(root,success,1);assert.equal(klass(root,'llm-call').length,1);assert.equal(klass(root,'llm-group').length,2);
  mountDetails(root);assert.ok(root.textContent.includes(call.cli.prompt));assert.ok(root.textContent.includes('실제 모델 원응답'));assert.ok(root.textContent.includes('동일 정의 확인'));
 });
 await check('실제 CLI 실패: 원응답 없음과 해시 확인 불가',()=>{
  const calls=ctx.llmCallRecords(failure,'pot.author');assert.equal(calls.length,1);const call=calls[0];assert.equal(call.raw,undefined);assert.equal(call.check.reason,'CLI_PROCESS_FAILED');
  assert.match(ctx.llmCallState(call),/^호출 실패/);assert.equal(ctx.schemaEvidence(call.cli.response_schema,call.definition,call.check).kind,'unknown');
  const root=new Element('div');ctx.stageProcessing(root,failure,1);assert.match(root.textContent,/CLI_PROCESS_FAILED/);assert.doesNotMatch(root.textContent,/SHA-256이 다릅니다|응답 형식 불일치/);
  assert.equal(ctx.sameJson(call.definition.schema,ctx.llmCallRecords(success,'pot.author')[0].definition.schema),false);
 });
 await check('재실행: P01 호출 미실행, 다른 실행 기록 혼합 없음',()=>{
  assert.equal(ctx.llmCallRecords(replay,'pot.author').length,0);const root=new Element('div');ctx.stageProcessing(root,replay,1);assert.equal(klass(root,'llm-call').length,0);assert.match(root.textContent,/새 모델 호출 0회/);
  const variant={...replay,label:'IC_SOURCE_A_ONLY',axis:'IC_SOURCE'},dtt=new Element('div');ctx.stageProcessing(dtt,variant,4);assert.equal(klass(dtt,'llm-call').length,0);assert.match(dtt.textContent,/실제 LLM 생성 아님/);
 });
 await check('합성 경계 사례: 기록 누락/사전 중단/형식 검사 실패/해시 차이',()=>{
  const schema={type:'object'},definition={schema,sha256:'a'};
  assert.equal(ctx.schemaEvidence(schema,definition,{status:'PASS'}).kind,'unknown');
  assert.equal(ctx.schemaEvidence(schema,definition,{schema_sha256:'b'}).kind,'mismatch');
  assert.equal(ctx.schemaEvidence({type:'array'},definition,{schema_sha256:'a'}).kind,'mismatch');
  assert.equal(ctx.schemaEvidence(schema,definition,{status:'FAIL',reason:'RESPONSE_SCHEMA_INVALID'}).kind,'unknown');
  assert.match(ctx.llmCallState({check:{phase:'before_call',transport_invoked:false}}),/^미실행/);
  assert.match(ctx.llmCallState({raw:{text:'{}'},check:{status:'FAIL',reason:'RESPONSE_SCHEMA_INVALID'}}),/수신 검사 실패/);
  assert.match(ctx.llmCallState({raw:{read_error:'broken JSON'}}),/원문 읽기 확인 불가/);
  assert.equal(ctx.sameJson({a:1,b:2},{b:2,a:1}),true);
 });
 await check('합성 시도/후보 경로 분리와 요청 파일 없는 반환 기록',()=>{
  const artifacts={};for(const n of [1,2]){const base=`02-calculation/attempt-${n}/`;artifacts[base+'P01-author/02-raw-response.json']={status:'PASS',data:{n}};artifacts[base+'author/01-input.json']={role:'pot.author',attempt:n};}
  const calls=ctx.llmCallRecords({run:{artifacts}},'pot.author');assert.equal(calls.length,2);assert.equal(calls[0].cli.attempt,1);assert.equal(calls[1].result.data.n,2);
  artifacts['05-text/OTHER/T01-realize/01-input.json']={};assert.equal(ctx.llmCallRecords({label:'SELECTED',run:{artifacts}},'dtt.realize').length,0);
 });
 const raw=' {"한국어":"<img src=x onerror=alert(1)> & 😀 \\uAC00", "n":90071992547409931234, "e":1e+04, "b":true,"z":null,"a":[false,{"x":"line\\nnext"}],"dup":1,"dup":2} \n';
 await check('JSON 토큰 원문 보존: 큰 정수/지수/중복 키/Unicode/이스케이프',()=>{
  const tree=ctx.parseJsonTree(raw);assert.equal(tree.children.length,8);assert.equal(raw.slice(tree.children[1].start,tree.children[1].end),'90071992547409931234');assert.equal(raw.slice(tree.children[2].start,tree.children[2].end),'1e+04');
  const root=ctx.jsonViewer(raw,'원응답');btn(root,'전체 펼치기').click();for(const name of ['key','string','number','boolean','null'])assert.ok(klass(root,'json-'+name).length);
  assert.equal(all(root,n=>n.tagName==='img').length,0);assert.ok(root.textContent.includes('\\uAC00'));assert.ok(root.textContent.includes('line\\nnext'));
 });
 await check('접기/펼치기, 전체 제어, 대용량 최대 200줄, 다음 페이지',()=>{
  const root=ctx.jsonViewer({items:Array.from({length:6000},(_,i)=>({i,ok:true}))});btn(root,'전체 펼치기').click();assert.equal(klass(root,'json-line').length,200);btn(root,'다음 200줄').click();assert.equal(klass(root,'json-line').length,200);assert.match(root.textContent,/201–400줄/);
  btn(root,'전체 접기').click();assert.equal(klass(root,'json-line').length,1);const toggle=klass(root,'json-toggle')[0];assert.equal(toggle.attributes['aria-expanded'],'false');toggle.click();assert.equal(klass(root,'json-toggle')[0].attributes['aria-expanded'],'true');assert.equal(document.activeElement.attributes['aria-expanded'],'true');
  const deep='['.repeat(3000)+'0'+']'.repeat(3000);assert.equal([...ctx.jsonRows(ctx.parseJsonTree(deep),()=>true)].length,6001);
 });
 await check('닫힌 JSON 지연 렌더와 원문 복사/복사 실패 대체 경로',async()=>{
  const parent=new Element('div'),d=ctx.jsonBox(parent,'지연 보기',{a:1});assert.equal(klass(parent,'json-viewer').length,0);d.open=true;d.emit('toggle');assert.equal(klass(parent,'json-viewer').length,1);d.emit('toggle');assert.equal(klass(parent,'json-viewer').length,1);
  const root=ctx.jsonViewer(raw);await btn(root,'원본 JSON 복사').click();assert.equal(copied,raw);
  const invalid='```json\n{"bad":\n';const text=ctx.jsonViewer(invalid);assert.equal(klass(text,'json-raw')[0].textContent,invalid);await btn(text,'원문 복사').click();assert.equal(copied,invalid);
  const saved=navigator.clipboard;navigator.clipboard={writeText:async()=>{throw Error('denied');}};await ctx.copyJsonText(raw+'\r\n',parent);assert.equal(copied,raw+'\r\n');navigator.clipboard=saved;assert.equal(document.events.copy.length,0);
  assert.equal(klass(ctx.jsonViewer(null),'json-null')[0].textContent,'null');
 });
 await check('팝업 닫기/ESC/배경 이벤트, 내부 클릭 유지와 초점 복귀',()=>{
  const opener=new Element('button');opener.focus();let {dialog}=ctx.showSchemaDialog('저장 스키마','설명');btn(dialog,'닫기').click();assert.equal(dialog.isConnected,false);assert.equal(document.activeElement,opener);
  ({dialog}=ctx.showSchemaDialog('저장 스키마','설명'));let prevented=false;dialog.emit('cancel',{preventDefault:()=>{prevented=true;}});assert.equal(prevented,true);assert.equal(dialog.isConnected,false);
  ({dialog}=ctx.showSchemaDialog('저장 스키마','설명'));const inside={target:dialog,clientX:50,clientY:50};dialog.emit('pointerdown',inside);dialog.emit('click',inside);assert.equal(dialog.open,true);
  const outside={target:dialog,clientX:0,clientY:0};dialog.emit('pointerdown',outside);dialog.emit('click',outside);assert.equal(dialog.isConnected,false);
 });
 await check('저장 팝업은 네트워크 없음, 현재 정의 조회만 로컬 API',async()=>{
  const root=new Element('div');ctx.savedSchemaBox(root,'저장 스키마',{schema:{type:'string'},sha256:'a'});btn(root,'저장 스키마 · 팝업').click();assert.equal(fetches.length,0);
  await ctx.showSchemaModal('pot.author.response');assert.deepEqual(fetches,['/api/schema?name=pot.author.response']);assert.match(document.body.textContent,/현재 코드의 정의/);
 });
 await check('실제 호출: 전송/수신/단계/현재 스키마 팝업에 같은 프롬프트 표시',async()=>{
  const call=ctx.llmCallRecords(success,'pot.author')[0],root=new Element('div');ctx.stageProcessing(root,success,1);
  for(const title of ['요청에 담긴 응답 스키마','저장된 응답 정의·버전·해시','단계 handler에 전달할 응답 정의','수신 검증에 연결된 응답 스키마 · 저장 정의']){
   btn(root,title+' · 팝업').click();const dialog=document.body.children.at(-1);assert.equal(klass(dialog,'schema-pair').length,1);
   const pane=klass(dialog,'schema-prompt-pane')[0];assert.match(pane.textContent,/같은 응답 정의를 사용한 저장 프롬프트/);assert.equal(klass(pane,'json-raw')[0].textContent,call.cli.prompt);
   await btn(pane,'원문 복사').click();assert.equal(copied,call.cli.prompt);dialog.close();
  }
  const original=ctx.fetch;ctx.fetch=async()=>({ok:true,json:async()=>call.definition});
  try{await btn(root,'현재 응답 스키마 보기').click();const dialog=document.body.children.at(-1);assert.equal(klass(dialog,'schema-prompt-pane')[0].textContent.includes(call.cli.prompt),true);assert.match(dialog.textContent,/현재 응답 스키마/);dialog.close();}finally{ctx.fetch=original;}
 });
 await check('현재와 다른 당시 정의 / 새 호출 없음 / 준비 입력은 프롬프트와 구별',()=>{
  const current=ctx.llmCallRecords(success,'pot.author')[0].definition,old=ctx.llmCallRecords(failure,'pot.author')[0],root=new Element('div');
  ctx.renderSchemaPair(root,current,{row:failure,role:'pot.author',current:true});assert.match(root.textContent,/다른 응답 정의를 사용한 저장 프롬프트/);assert.ok(root.textContent.includes(old.cli.prompt));assert.match(root.textContent,/호출 실패/);
  ctx.renderSchemaPair(root,current,{row:replay,role:'pot.author',current:true});assert.match(root.textContent,/저장된 실제 프롬프트가 없습니다/);assert.match(root.textContent,/현재 코드의 프롬프트 템플릿은 이 조회에 포함되어 있지 않습니다/);assert.equal(klass(root,'json-raw').length,0);
  const base='04-perturbation/02-plan-ic-source/02-attribute-original-claim/',variant={...replay,label:'IC_SOURCE_A_ONLY'};
  ctx.renderSchemaPair(root,replay.run.artifacts[base+'realization-response-schema.json'],{row:variant,role:'dtt.realize',preparedInput:replay.run.artifacts[base+'realization-input.json']});assert.match(root.textContent,/미전송 자료이며 프롬프트나 LLM 생성 결과가 아닙니다/);assert.equal(klass(root,'json-raw').length,0);
  ctx.renderSchemaPair(root,current,{call:{role:'pot.author',model:{input:{context:'input only'}}}});assert.match(root.textContent,/프롬프트 기록 없음/);assert.equal(klass(root,'json-raw').length,0);
 });
 await check('여러 기록 선택과 프롬프트를 실제 보관한 요청의 스키마로만 연결',()=>{
  const schema={type:'object'},other={type:'array'},calls=[{role:'pot.author',dir:'1/',cli:{prompt:'old',response_schema:other}},{role:'pot.author',dir:'2/',cli:{prompt:'right',response_schema:schema}}];
  assert.deepEqual(Array.from(ctx.schemaPromptEntries(schema,calls),entry=>entry.match),[false,true]);
  const mixed={cli:{response_schema:schema},model:{prompt:'model-only',response_schema:other}};assert.equal(ctx.schemaPromptEntries(schema,[mixed])[0].match,false);
  const row={label:'ANSWER',run:{path:'synthetic',artifacts:{'02-calculation/attempt-1/author/01-input.json':calls[0].cli,'02-calculation/attempt-2/author/01-input.json':calls[1].cli}}};
  row.run.artifacts['02-calculation/attempt-1/author/01-input.json'].role='pot.author';row.run.artifacts['02-calculation/attempt-2/author/01-input.json'].role='pot.author';
  const root=new Element('div');ctx.renderSchemaPair(root,schema,{row,role:'pot.author'});const selector=all(root,n=>n.tagName==='select')[0];assert.equal(selector.value,'1');assert.equal(klass(root,'json-raw')[0].textContent,'right');selector.value='0';selector.onchange();assert.equal(klass(root,'json-raw')[0].textContent,'old');assert.match(root.textContent,/다른 응답 정의/);
 });
 await check('현재 스키마 조회 오류 및 팝업을 닫은 후 늦은 응답 무시',async()=>{
  const original=ctx.fetch;try{
   ctx.fetch=async()=>({ok:false});await ctx.showSchemaModal('pot.author.response',success);let dialog=document.body.children.at(-1);assert.match(dialog.textContent,/스키마를 읽지 못했습니다/);dialog.close();
   let resolve;ctx.fetch=()=>new Promise(done=>{resolve=done;});const pending=ctx.showSchemaModal('pot.author.response',success);dialog=document.body.children.at(-1);dialog.close();resolve({ok:true,json:async()=>({schema:{type:'object'}})});await pending;assert.equal(dialog.isConnected,false);assert.equal(klass(dialog,'schema-pair').length,0);
  }finally{ctx.fetch=original;}
 });
 await check('현재 유형 지침 팝업은 저장 호출과 구분하며 한 유형만 조회',async()=>{
  const original=ctx.fetch;try{
   ctx.fetch=async url=>{assert.equal(url,'/api/realization-prompt?axis=EA');return {ok:true,json:async()=>({id:'dtt.realize.ea',version:1,parts:[{file:'common.md',text:'Common output rules'},{file:'ea.md',text:'EA instructions'}]})};};
   const open=ctx.currentRealizationPromptButton({axis:'EA'});await open.click();const dialog=document.body.children.at(-1);
   assert.match(dialog.textContent,/과거 프롬프트가 아니며/);assert.match(dialog.textContent,/EA instructions/);assert.doesNotMatch(dialog.textContent,/OBJECTIVE: IC/);dialog.close();
  }finally{ctx.fetch=original;}
 });
 await check('현재 의미 검사 지침은 ANSWER를 포함하고 과거 판정과 구분',async()=>{
  const original=ctx.fetch;try{
   for(const axis of ['ANSWER','EA']){
    ctx.fetch=async url=>{assert.equal(url,'/api/audit-prompt?axis='+axis);return {ok:true,json:async()=>({id:'dtt.audit.'+axis.toLowerCase(),version:1,parts:[{file:'common.md',text:'Three judgments'},{file:axis+'.md',text:axis+' criteria'}]})};};
    const open=ctx.currentAuditPromptButton({axis});assert.equal(open.disabled,false);await open.click();const dialog=document.body.children.at(-1);
    assert.match(dialog.textContent,/과거 프롬프트가 아니며/);assert.ok(dialog.textContent.includes(axis+' criteria'));dialog.close();
   }
  }finally{ctx.fetch=original;}
 });
 console.log(JSON.stringify({status:'PASS',checks:results.length,results,model_calls:0,network:'stub only',browser_ui:'NOT_RUN — user verification pending'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
