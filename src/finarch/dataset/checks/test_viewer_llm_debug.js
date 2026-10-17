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
 await check('\uc2e4\uc81c \uc131\uacf5: provider+P01 \ud55c \ubb36\uc74c, \ud504\ub86c\ud504\ud2b8/\uc785\ub825/\uc6d0\uc751\ub2f5/\ud574\uc2dc',()=>{
  const calls=ctx.llmCallRecords(success,'pot.author');assert.equal(calls.length,1);const call=calls[0];
  assert.equal(call.cli.model,'gpt-5.3-codex-spark');assert.ok(call.cli.prompt.includes(call.model.input.question));assert.equal(call.model.prompt,undefined);assert.equal(typeof call.raw.text,'string');assert.ok(call.result.data.code);
  assert.equal(ctx.schemaEvidence(call.cli.response_schema,call.definition,call.check).kind,'match');assert.equal(ctx.schemaEvidence(call.stageSchema,call.stageSchema,call.stageCheck).kind,'match');
  assert.equal(ctx.callLogEvents(success,call)[0].attempt,1);
  const root=new Element('div');ctx.stageProcessing(root,success,1);assert.equal(klass(root,'llm-call').length,1);assert.equal(klass(root,'llm-group').length,2);
  mountDetails(root);assert.ok(root.textContent.includes(call.cli.prompt));assert.ok(root.textContent.includes('\uc2e4\uc81c \ubaa8\ub378 \uc6d0\uc751\ub2f5'));assert.ok(root.textContent.includes('\ub3d9\uc77c \uc815\uc758 \ud655\uc778'));
 });
 await check('\uc2e4\uc81c CLI \uc2e4\ud328: \uc6d0\uc751\ub2f5 \uc5c6\uc74c\uacfc \ud574\uc2dc \ud655\uc778 \ubd88\uac00',()=>{
  const calls=ctx.llmCallRecords(failure,'pot.author');assert.equal(calls.length,1);const call=calls[0];assert.equal(call.raw,undefined);assert.equal(call.check.reason,'CLI_PROCESS_FAILED');
  assert.match(ctx.llmCallState(call),/^\ud638\ucd9c \uc2e4\ud328/);assert.equal(ctx.schemaEvidence(call.cli.response_schema,call.definition,call.check).kind,'unknown');
  const root=new Element('div');ctx.stageProcessing(root,failure,1);assert.match(root.textContent,/CLI_PROCESS_FAILED/);assert.doesNotMatch(root.textContent,/SHA-256\uc774 \ub2e4\ub985\ub2c8\ub2e4|\uc751\ub2f5 \ud615\uc2dd \ubd88\uc77c\uce58/);
  assert.equal(ctx.sameJson(call.definition.schema,ctx.llmCallRecords(success,'pot.author')[0].definition.schema),false);
 });
 await check('\uc7ac\uc2e4\ud589: P01 \ud638\ucd9c \ubbf8\uc2e4\ud589, \ub2e4\ub978 \uc2e4\ud589 \uae30\ub85d \ud63c\ud569 \uc5c6\uc74c',()=>{
  assert.equal(ctx.llmCallRecords(replay,'pot.author').length,0);const root=new Element('div');ctx.stageProcessing(root,replay,1);assert.equal(klass(root,'llm-call').length,0);assert.match(root.textContent,/\uc0c8 \ubaa8\ub378 \ud638\ucd9c 0\ud68c/);
  const variant={...replay,label:'IC_SOURCE_A_ONLY',axis:'IC_SOURCE'},dtt=new Element('div');ctx.stageProcessing(dtt,variant,4);assert.equal(klass(dtt,'llm-call').length,0);assert.match(dtt.textContent,/\uc2e4\uc81c LLM \uc0dd\uc131 \uc544\ub2d8/);
 });
 await check('\ud569\uc131 \uacbd\uacc4 \uc0ac\ub840: \uae30\ub85d \ub204\ub77d/\uc0ac\uc804 \uc911\ub2e8/\ud615\uc2dd \uac80\uc0ac \uc2e4\ud328/\ud574\uc2dc \ucc28\uc774',()=>{
  const schema={type:'object'},definition={schema,sha256:'a'};
  assert.equal(ctx.schemaEvidence(schema,definition,{status:'PASS'}).kind,'unknown');
  assert.equal(ctx.schemaEvidence(schema,definition,{schema_sha256:'b'}).kind,'mismatch');
  assert.equal(ctx.schemaEvidence({type:'array'},definition,{schema_sha256:'a'}).kind,'mismatch');
  assert.equal(ctx.schemaEvidence(schema,definition,{status:'FAIL',reason:'RESPONSE_SCHEMA_INVALID'}).kind,'unknown');
  assert.match(ctx.llmCallState({check:{phase:'before_call',transport_invoked:false}}),/^\ubbf8\uc2e4\ud589/);
  assert.match(ctx.llmCallState({raw:{text:'{}'},check:{status:'FAIL',reason:'RESPONSE_SCHEMA_INVALID'}}),/\uc218\uc2e0 \uac80\uc0ac \uc2e4\ud328/);
  assert.match(ctx.llmCallState({raw:{read_error:'broken JSON'}}),/\uc6d0\ubb38 \uc77d\uae30 \ud655\uc778 \ubd88\uac00/);
  assert.equal(ctx.sameJson({a:1,b:2},{b:2,a:1}),true);
 });
 await check('\ud569\uc131 \uc2dc\ub3c4/\ud6c4\ubcf4 \uacbd\ub85c \ubd84\ub9ac\uc640 \uc694\uccad \ud30c\uc77c \uc5c6\ub294 \ubc18\ud658 \uae30\ub85d',()=>{
  const artifacts={};for(const n of [1,2]){const base=`02-calculation/attempt-${n}/`;artifacts[base+'P01-author/02-raw-response.json']={status:'PASS',data:{n}};artifacts[base+'author/01-input.json']={role:'pot.author',attempt:n};}
  const calls=ctx.llmCallRecords({run:{artifacts}},'pot.author');assert.equal(calls.length,2);assert.equal(calls[0].cli.attempt,1);assert.equal(calls[1].result.data.n,2);
  artifacts['05-text/OTHER/T01-realize/01-input.json']={};assert.equal(ctx.llmCallRecords({label:'SELECTED',run:{artifacts}},'dtt.realize').length,0);
 });
 const raw=' {"\ud55c\uad6d\uc5b4":"<img src=x onerror=alert(1)> & 😀 \\uAC00", "n":90071992547409931234, "e":1e+04, "b":true,"z":null,"a":[false,{"x":"line\\nnext"}],"dup":1,"dup":2} \n';
 await check('JSON \ud1a0\ud070 \uc6d0\ubb38 \ubcf4\uc874: \ud070 \uc815\uc218/\uc9c0\uc218/\uc911\ubcf5 \ud0a4/Unicode/\uc774\uc2a4\ucf00\uc774\ud504',()=>{
  const tree=ctx.parseJsonTree(raw);assert.equal(tree.children.length,8);assert.equal(raw.slice(tree.children[1].start,tree.children[1].end),'90071992547409931234');assert.equal(raw.slice(tree.children[2].start,tree.children[2].end),'1e+04');
  const root=ctx.jsonViewer(raw,'\uc6d0\uc751\ub2f5');btn(root,'\uc804\uccb4 \ud3bc\uce58\uae30').click();for(const name of ['key','string','number','boolean','null'])assert.ok(klass(root,'json-'+name).length);
  assert.equal(all(root,n=>n.tagName==='img').length,0);assert.ok(root.textContent.includes('\\uAC00'));assert.ok(root.textContent.includes('line\\nnext'));
 });
 await check('\uc811\uae30/\ud3bc\uce58\uae30, \uc804\uccb4 \uc81c\uc5b4, \ub300\uc6a9\ub7c9 \ucd5c\ub300 200\uc904, \ub2e4\uc74c \ud398\uc774\uc9c0',()=>{
  const root=ctx.jsonViewer({items:Array.from({length:6000},(_,i)=>({i,ok:true}))});btn(root,'\uc804\uccb4 \ud3bc\uce58\uae30').click();assert.equal(klass(root,'json-line').length,200);btn(root,'\ub2e4\uc74c 200\uc904').click();assert.equal(klass(root,'json-line').length,200);assert.match(root.textContent,/201–400\uc904/);
  btn(root,'\uc804\uccb4 \uc811\uae30').click();assert.equal(klass(root,'json-line').length,1);const toggle=klass(root,'json-toggle')[0];assert.equal(toggle.attributes['aria-expanded'],'false');toggle.click();assert.equal(klass(root,'json-toggle')[0].attributes['aria-expanded'],'true');assert.equal(document.activeElement.attributes['aria-expanded'],'true');
  const deep='['.repeat(3000)+'0'+']'.repeat(3000);assert.equal([...ctx.jsonRows(ctx.parseJsonTree(deep),()=>true)].length,6001);
 });
 await check('\ub2eb\ud78c JSON \uc9c0\uc5f0 \ub80c\ub354\uc640 \uc6d0\ubb38 \ubcf5\uc0ac/\ubcf5\uc0ac \uc2e4\ud328 \ub300\uccb4 \uacbd\ub85c',async()=>{
  const parent=new Element('div'),d=ctx.jsonBox(parent,'\uc9c0\uc5f0 \ubcf4\uae30',{a:1});assert.equal(klass(parent,'json-viewer').length,0);d.open=true;d.emit('toggle');assert.equal(klass(parent,'json-viewer').length,1);d.emit('toggle');assert.equal(klass(parent,'json-viewer').length,1);
  const root=ctx.jsonViewer(raw);await btn(root,'\uc6d0\ubcf8 JSON \ubcf5\uc0ac').click();assert.equal(copied,raw);
  const invalid='```json\n{"bad":\n';const text=ctx.jsonViewer(invalid);assert.equal(klass(text,'json-raw')[0].textContent,invalid);await btn(text,'\uc6d0\ubb38 \ubcf5\uc0ac').click();assert.equal(copied,invalid);
  const saved=navigator.clipboard;navigator.clipboard={writeText:async()=>{throw Error('denied');}};await ctx.copyJsonText(raw+'\r\n',parent);assert.equal(copied,raw+'\r\n');navigator.clipboard=saved;assert.equal(document.events.copy.length,0);
  assert.equal(klass(ctx.jsonViewer(null),'json-null')[0].textContent,'null');
 });
 await check('\ud31d\uc5c5 \ub2eb\uae30/ESC/\ubc30\uacbd \uc774\ubca4\ud2b8, \ub0b4\ubd80 \ud074\ub9ad \uc720\uc9c0\uc640 \ucd08\uc810 \ubcf5\uadc0',()=>{
  const opener=new Element('button');opener.focus();let {dialog}=ctx.showSchemaDialog('\uc800\uc7a5 \uc2a4\ud0a4\ub9c8','\uc124\uba85');btn(dialog,'\ub2eb\uae30').click();assert.equal(dialog.isConnected,false);assert.equal(document.activeElement,opener);
  ({dialog}=ctx.showSchemaDialog('\uc800\uc7a5 \uc2a4\ud0a4\ub9c8','\uc124\uba85'));let prevented=false;dialog.emit('cancel',{preventDefault:()=>{prevented=true;}});assert.equal(prevented,true);assert.equal(dialog.isConnected,false);
  ({dialog}=ctx.showSchemaDialog('\uc800\uc7a5 \uc2a4\ud0a4\ub9c8','\uc124\uba85'));const inside={target:dialog,clientX:50,clientY:50};dialog.emit('pointerdown',inside);dialog.emit('click',inside);assert.equal(dialog.open,true);
  const outside={target:dialog,clientX:0,clientY:0};dialog.emit('pointerdown',outside);dialog.emit('click',outside);assert.equal(dialog.isConnected,false);
 });
 await check('\uc800\uc7a5 \ud31d\uc5c5\uc740 \ub124\ud2b8\uc6cc\ud06c \uc5c6\uc74c, \ud604\uc7ac \uc815\uc758 \uc870\ud68c\ub9cc \ub85c\uceec API',async()=>{
  const root=new Element('div');ctx.savedSchemaBox(root,'\uc800\uc7a5 \uc2a4\ud0a4\ub9c8',{schema:{type:'string'},sha256:'a'});btn(root,'\uc800\uc7a5 \uc2a4\ud0a4\ub9c8 · \ud31d\uc5c5').click();assert.equal(fetches.length,0);
  await ctx.showSchemaModal('pot.author.response');assert.deepEqual(fetches,['/api/schema?name=pot.author.response']);assert.match(document.body.textContent,/\ud604\uc7ac \ucf54\ub4dc\uc758 \uc815\uc758/);
 });
 await check('\uc2e4\uc81c \ud638\ucd9c: \uc804\uc1a1/\uc218\uc2e0/\ub2e8\uacc4/\ud604\uc7ac \uc2a4\ud0a4\ub9c8 \ud31d\uc5c5\uc5d0 \uac19\uc740 \ud504\ub86c\ud504\ud2b8 \ud45c\uc2dc',async()=>{
  const call=ctx.llmCallRecords(success,'pot.author')[0],root=new Element('div');ctx.stageProcessing(root,success,1);
  for(const title of ['\uc694\uccad\uc5d0 \ub2f4\uae34 \uc751\ub2f5 \uc2a4\ud0a4\ub9c8','\uc800\uc7a5\ub41c \uc751\ub2f5 \uc815\uc758·\ubc84\uc804·\ud574\uc2dc','\ub2e8\uacc4 handler\uc5d0 \uc804\ub2ec\ud560 \uc751\ub2f5 \uc815\uc758','\uc218\uc2e0 \uac80\uc99d\uc5d0 \uc5f0\uacb0\ub41c \uc751\ub2f5 \uc2a4\ud0a4\ub9c8 · \uc800\uc7a5 \uc815\uc758']){
   btn(root,title+' · \ud31d\uc5c5').click();const dialog=document.body.children.at(-1);assert.equal(klass(dialog,'schema-pair').length,1);
   const pane=klass(dialog,'schema-prompt-pane')[0];assert.match(pane.textContent,/\uac19\uc740 \uc751\ub2f5 \uc815\uc758\ub97c \uc0ac\uc6a9\ud55c \uc800\uc7a5 \ud504\ub86c\ud504\ud2b8/);assert.equal(klass(pane,'json-raw')[0].textContent,call.cli.prompt);
   await btn(pane,'\uc6d0\ubb38 \ubcf5\uc0ac').click();assert.equal(copied,call.cli.prompt);dialog.close();
  }
  const original=ctx.fetch;ctx.fetch=async()=>({ok:true,json:async()=>call.definition});
  try{await btn(root,'\ud604\uc7ac \uc751\ub2f5 \uc2a4\ud0a4\ub9c8 \ubcf4\uae30').click();const dialog=document.body.children.at(-1);assert.equal(klass(dialog,'schema-prompt-pane')[0].textContent.includes(call.cli.prompt),true);assert.match(dialog.textContent,/\ud604\uc7ac \uc751\ub2f5 \uc2a4\ud0a4\ub9c8/);dialog.close();}finally{ctx.fetch=original;}
 });
 await check('\ud604\uc7ac\uc640 \ub2e4\ub978 \ub2f9\uc2dc \uc815\uc758 / \uc0c8 \ud638\ucd9c \uc5c6\uc74c / \uc900\ube44 \uc785\ub825\uc740 \ud504\ub86c\ud504\ud2b8\uc640 \uad6c\ubcc4',()=>{
  const current=ctx.llmCallRecords(success,'pot.author')[0].definition,old=ctx.llmCallRecords(failure,'pot.author')[0],root=new Element('div');
  ctx.renderSchemaPair(root,current,{row:failure,role:'pot.author',current:true});assert.match(root.textContent,/\ub2e4\ub978 \uc751\ub2f5 \uc815\uc758\ub97c \uc0ac\uc6a9\ud55c \uc800\uc7a5 \ud504\ub86c\ud504\ud2b8/);assert.ok(root.textContent.includes(old.cli.prompt));assert.match(root.textContent,/\ud638\ucd9c \uc2e4\ud328/);
  ctx.renderSchemaPair(root,current,{row:replay,role:'pot.author',current:true});assert.match(root.textContent,/\uc800\uc7a5\ub41c \uc2e4\uc81c \ud504\ub86c\ud504\ud2b8\uac00 \uc5c6\uc2b5\ub2c8\ub2e4/);assert.match(root.textContent,/\ud604\uc7ac \ucf54\ub4dc\uc758 \ud504\ub86c\ud504\ud2b8 \ud15c\ud50c\ub9bf\uc740 \uc774 \uc870\ud68c\uc5d0 \ud3ec\ud568\ub418\uc5b4 \uc788\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4/);assert.equal(klass(root,'json-raw').length,0);
  const base='04-perturbation/02-plan-ic-source/02-attribute-original-claim/',variant={...replay,label:'IC_SOURCE_A_ONLY'};
  ctx.renderSchemaPair(root,replay.run.artifacts[base+'realization-response-schema.json'],{row:variant,role:'dtt.realize',preparedInput:replay.run.artifacts[base+'realization-input.json']});assert.match(root.textContent,/\ubbf8\uc804\uc1a1 \uc790\ub8cc\uc774\uba70 \ud504\ub86c\ud504\ud2b8\ub098 LLM \uc0dd\uc131 \uacb0\uacfc\uac00 \uc544\ub2d9\ub2c8\ub2e4/);assert.equal(klass(root,'json-raw').length,0);
  ctx.renderSchemaPair(root,current,{call:{role:'pot.author',model:{input:{context:'input only'}}}});assert.match(root.textContent,/\ud504\ub86c\ud504\ud2b8 \uae30\ub85d \uc5c6\uc74c/);assert.equal(klass(root,'json-raw').length,0);
 });
 await check('\uc5ec\ub7ec \uae30\ub85d \uc120\ud0dd\uacfc \ud504\ub86c\ud504\ud2b8\ub97c \uc2e4\uc81c \ubcf4\uad00\ud55c \uc694\uccad\uc758 \uc2a4\ud0a4\ub9c8\ub85c\ub9cc \uc5f0\uacb0',()=>{
  const schema={type:'object'},other={type:'array'},calls=[{role:'pot.author',dir:'1/',cli:{prompt:'old',response_schema:other}},{role:'pot.author',dir:'2/',cli:{prompt:'right',response_schema:schema}}];
  assert.deepEqual(Array.from(ctx.schemaPromptEntries(schema,calls),entry=>entry.match),[false,true]);
  const mixed={cli:{response_schema:schema},model:{prompt:'model-only',response_schema:other}};assert.equal(ctx.schemaPromptEntries(schema,[mixed])[0].match,false);
  const row={label:'ANSWER',run:{path:'synthetic',artifacts:{'02-calculation/attempt-1/author/01-input.json':calls[0].cli,'02-calculation/attempt-2/author/01-input.json':calls[1].cli}}};
  row.run.artifacts['02-calculation/attempt-1/author/01-input.json'].role='pot.author';row.run.artifacts['02-calculation/attempt-2/author/01-input.json'].role='pot.author';
  const root=new Element('div');ctx.renderSchemaPair(root,schema,{row,role:'pot.author'});const selector=all(root,n=>n.tagName==='select')[0];assert.equal(selector.value,'1');assert.equal(klass(root,'json-raw')[0].textContent,'right');selector.value='0';selector.onchange();assert.equal(klass(root,'json-raw')[0].textContent,'old');assert.match(root.textContent,/\ub2e4\ub978 \uc751\ub2f5 \uc815\uc758/);
 });
 await check('\ud604\uc7ac \uc2a4\ud0a4\ub9c8 \uc870\ud68c \uc624\ub958 \ubc0f \ud31d\uc5c5\uc744 \ub2eb\uc740 \ud6c4 \ub2a6\uc740 \uc751\ub2f5 \ubb34\uc2dc',async()=>{
  const original=ctx.fetch;try{
   ctx.fetch=async()=>({ok:false});await ctx.showSchemaModal('pot.author.response',success);let dialog=document.body.children.at(-1);assert.match(dialog.textContent,/\uc2a4\ud0a4\ub9c8\ub97c \uc77d\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4/);dialog.close();
   let resolve;ctx.fetch=()=>new Promise(done=>{resolve=done;});const pending=ctx.showSchemaModal('pot.author.response',success);dialog=document.body.children.at(-1);dialog.close();resolve({ok:true,json:async()=>({schema:{type:'object'}})});await pending;assert.equal(dialog.isConnected,false);assert.equal(klass(dialog,'schema-pair').length,0);
  }finally{ctx.fetch=original;}
 });
 await check('\ud604\uc7ac \uc720\ud615 \uc9c0\uce68 \ud31d\uc5c5\uc740 \uc800\uc7a5 \ud638\ucd9c\uacfc \uad6c\ubd84\ud558\uba70 \ud55c \uc720\ud615\ub9cc \uc870\ud68c',async()=>{
  const original=ctx.fetch;try{
   ctx.fetch=async url=>{assert.equal(url,'/api/realization-prompt?axis=EA');return {ok:true,json:async()=>({id:'dtt.realize.ea',version:1,parts:[{file:'common.md',text:'Common output rules'},{file:'ea.md',text:'EA instructions'}]})};};
   const open=ctx.currentRealizationPromptButton({axis:'EA'});await open.click();const dialog=document.body.children.at(-1);
   assert.match(dialog.textContent,/\uacfc\uac70 \ud504\ub86c\ud504\ud2b8\uac00 \uc544\ub2c8\uba70/);assert.match(dialog.textContent,/EA instructions/);assert.doesNotMatch(dialog.textContent,/OBJECTIVE: IC/);dialog.close();
  }finally{ctx.fetch=original;}
 });
 await check('\ud604\uc7ac \uc758\ubbf8 \uac80\uc0ac \uc9c0\uce68\uc740 ANSWER\ub97c \ud3ec\ud568\ud558\uace0 \uacfc\uac70 \ud310\uc815\uacfc \uad6c\ubd84',async()=>{
  const original=ctx.fetch;try{
   for(const axis of ['ANSWER','EA']){
    ctx.fetch=async url=>{assert.equal(url,'/api/audit-prompt?axis='+axis);return {ok:true,json:async()=>({id:'dtt.audit.'+axis.toLowerCase(),version:1,parts:[{file:'common.md',text:'Three judgments'},{file:axis+'.md',text:axis+' criteria'}]})};};
    const open=ctx.currentAuditPromptButton({axis});assert.equal(open.disabled,false);await open.click();const dialog=document.body.children.at(-1);
    assert.match(dialog.textContent,/\uacfc\uac70 \ud504\ub86c\ud504\ud2b8\uac00 \uc544\ub2c8\uba70/);assert.ok(dialog.textContent.includes(axis+' criteria'));dialog.close();
   }
  }finally{ctx.fetch=original;}
 });
 console.log(JSON.stringify({status:'PASS',checks:results.length,results,model_calls:0,network:'stub only',browser_ui:'NOT_RUN — user verification pending'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
