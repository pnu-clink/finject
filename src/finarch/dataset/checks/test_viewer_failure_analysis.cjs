// Offline UI contract tests. All HTTP requests are intercepted; no backend or LLM calls.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../../../../viewer/dataset');
function assemble(file){return fs.readFileSync(path.join(root,file),'utf8').replace(/\/\* @include ([\w./-]+) \*\//g,(_,name)=>assemble(name));}
const html=assemble('shell.html');
for(const script of html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
const all=node=>[node,...node.children.flatMap(all)];
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.style={};this.events={};this._text='';this.className='';this.disabled=false;
  this.classList={add:(...names)=>{this.className=[...new Set([...this.className.split(' '),...names])].join(' ').trim();},remove:(...names)=>{this.className=this.className.split(' ').filter(name=>!names.includes(name)).join(' ');}};
 }
 set textContent(value){this._text=String(value);this.replaceChildren();}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 get isConnected(){return this.tagName==='body'||!!this.parent?.isConnected;}
 append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node);}}
 replaceChildren(...nodes){for(const child of this.children)child.parent=null;this.children=[];this.append(...nodes);}
 setAttribute(key,value){this.attributes[key]=String(value);}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
 emit(name,event={}){for(const fn of this.events[name]||[])fn(event);}
 querySelectorAll(selector){return all(this).slice(1).filter(node=>selector.startsWith('.')?node.className.split(' ').includes(selector.slice(1)):node.tagName===selector);}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 click(){if(!this.disabled){this.emit('click');return this.onclick?.();}}
 focus(){this.owner.activeElement=this;}
 showModal(){this.open=true;}
 close(){this.open=false;this.emit('close');}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}
}
const variant='01-ic-value-before',otherVariant='02-ic-value-after';
function result(overrides={}){return {case:'test-0001',variant:null,round:'01-round',status:'COMPLETED',analysis:{rejection_summary:'Saved rejection',observations:[{statement:'Recorded fact',evidence_ids:['E1','MISSING'],kind:'FACT'}],assessment:'REVIEW',rationale:'Source differs',recommended_action:'Inspect input',target_step:'03-calculation',limitations:'No rerun'},display_ko:null,error:null,stale:false,artifacts:[{id:'E1',path:'reports/run/run A/01-preparation/test-0001/01-round/03-calculation/03-result.json',sha256:'abc123'}],...overrides};}
function job(overrides={}){return {id:'analysis-002',phase:'preparation',status:'COMPLETED',planned:1,completed:1,results:[result()],...overrides};}
function data(){return {live:true,batch:{name:'run A',round:'01-round',failure_analysis:{jobs:[],busy:false,preparation:2,generation:3},rechecks:{preparation:2,generation:3,busy:false}}};}
function env(){
 const document={body:new Element('body'),activeElement:null,addEventListener(){},querySelector(selector){return this.body.querySelector(selector);},querySelectorAll(selector){return this.body.querySelectorAll(selector);}};
 const el=(tag,cls,value)=>{const node=new Element(tag);node.owner=document;node.className=cls||'';if(value!==undefined)node.textContent=value;return node;};
 const requests=[],storage=new Map();let handler=async()=>{throw Error('Unexpected HTTP request');};
 const ctx=vm.createContext({console,DATA:data(),window:{addEventListener(){},removeEventListener(){}},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{search:''},URLSearchParams,document,el,localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
  button:(label,fn,cls)=>{const node=el('button',cls,label);node.onclick=fn;return node;},filePathLabel:p=>el('span','source-file-path',p),
  fetch:async(url,options={})=>{requests.push({url,options});return handler(url,options);},
  finalGenerationCounts:()=>{},pipelineRoundSummary:()=>{},externalKnowledgeModel:()=>({tags:[]}),appendFeedbackBadge:()=>{},stageFeedbackState:()=>null,
  renderMenuGuide:parent=>parent.append(el('section','guide','\uc774 \ub2e8\uacc4\uc5d0\uc11c \ud558\ub294 \uc77c')),
  renderPreparationContent:parent=>parent.append(el('div','content','Preparation actual verdict')),
  renderGenerationContent:parent=>parent.append(el('div','content','Generation actual verdict')),decorateExternalKnowledge:()=>{},
  renderStageFiles:parent=>parent.append(el('div','files','\uacb0\uacfc \ud30c\uc77c'))});
 for(const file of ['common/disclosure.js','common/failure-analysis.js','menu.js'])vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),ctx);
 return {ctx,document,el,requests,storage,handle(fn){handler=fn;},mount(fn){const node=el('div');document.body.append(node);fn(node);return node;}};
}
const find=(node,cls)=>node.querySelectorAll('.'+cls),buttons=node=>node.querySelectorAll('button'),named=(node,text)=>buttons(node).find(b=>b.textContent===text);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=(body,ok=true)=>({ok,json:async()=>body});
const preview=(overrides={})=>({preview_id:'snapshot 123',phase:'preparation',planned:2,model:'gpt-6-luna',effort:'max',calls:4,estimated_cost_usd:null,estimate_note:'Token volume unavailable',...overrides});
const analysisOnly=process.argv.includes('--analysis-only');
const menuChecks=new Set(['Generation labels stay short; only variants without artifacts are disabled','Early failed Preparation and Generation show matched analysis immediately after the guide']);
const checks=[];async function check(name,fn){if(analysisOnly&&menuChecks.has(name))return;await fn();checks.push(name);console.log('PASS '+name);}
(async()=>{
 await check('Shared shell assembles with the new module and valid JavaScript',()=>{assert(html.includes('function failureAnalysisButton('));assert(!html.includes('/* @include '));});
 await check('Generation labels stay short; only variants without artifacts are disabled',()=>{
  const e=env(),row={sample:{id:'test-0001'},status:'FAIL',run:{artifacts:{'run.json':{status:'FAIL'}},generation:{[variant+'/run.json']:{status:'FAIL'},[otherVariant+'/02-generate-text/02-raw-response.json']:{text:'error'},'05-ic-relation/run.json':{status:'ERROR'}}}};
  const node=e.mount(n=>e.ctx.renderPreparationDetail(n,row)),gen=find(node,'phase-generation')[0];
  for(const label of ['IC-VALUE \uc55e','IC-VALUE \ub4a4','IC-RELATION'])assert.equal(named(gen,label).disabled,false);
  for(const label of ['IC-SOURCE Type 1','IC-SOURCE Type 2','EA 01','EA 02'])assert.equal(named(gen,label).disabled,true);
  assert(buttons(gen).every(b=>!b.textContent.includes('\ubbf8\uc2e4\ud589')));
  for(const phase of ['preparation','generation']){const group=find(node,'phase-'+phase)[0],items=buttons(group),i=items.findIndex(b=>b.textContent.startsWith('\uc2e4\ud328\uac74 \uc7ac\uac80\ud1a0'));assert(items[i-1].className.includes('failure-analysis-button'));}
  assert(node.children.indexOf(find(node,'preparation-overview')[0])<node.children.indexOf(find(node,'failure-analysis-overview')[0]));
  assert(node.children.indexOf(find(node,'failure-analysis-overview')[0])<node.children.indexOf(find(node,'problem-selection')[0]));
  assert.equal(e.requests.length,0);
 });
 await check('Latest jobs stay phase scoped, older snapshots persist, and reads do not mutate DATA',()=>{
  const e=env();e.ctx.DATA.batch.failure_analysis.jobs=[job({id:'analysis-2'}),job({id:'analysis-10',status:'RUNNING',planned:3,completed:1,results:[result({stale:true})]}),job({id:'analysis-9',phase:'generation',status:'ERROR',error:'worker stopped',results:[result({variant,error:'schema invalid',analysis:null})]})];
  const before=JSON.stringify(e.ctx.DATA),node=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n)),prep=find(node,'failure-analysis-preparation')[0];
  assert(prep.textContent.indexOf('analysis-10')<prep.textContent.indexOf('analysis-2'));assert.match(prep.textContent,/1\/3\uac74/);assert.match(prep.textContent,/\ubd80\ubd84 \uacb0\uacfc/);assert.match(node.textContent,/worker stopped/);assert.match(node.textContent,/schema invalid/);assert.match(node.textContent,/\uc774\uc804 \uc790\ub8cc \uae30\uc900/);
  assert.equal(find(node,'failure-analysis-overview')[0].children[0].open,false);
  assert(node.querySelectorAll('details').some(d=>d.children[0].textContent==='\uc774\uc804 \ud574\uc11d \uae30\ub85d 1\uac1c'&&!d.open));
  assert.equal(JSON.stringify(e.ctx.DATA),before);assert.equal(e.requests.length,0);
 });
 await check('Translated fields, original fallback, evidence IDs and safe stage links are displayed',()=>{
  const e=env(),r=result({display_ko:{rejection_summary:'\uc800\uc7a5 \uac70\uc808 \uc0ac\uc720',observations:[{statement:'\ud655\uc778\ub41c \ub0b4\uc6a9',evidence_ids:['E1','MISSING'],kind:'FACT'}],assessment:'\uac80\ud1a0 \ud544\uc694',rationale:'\uadfc\uac70 \ucc28\uc774',recommended_action:'\uc785\ub825 \ud655\uc778',target_step:'\uacc4\uc0b0',limitations:'\uc7ac\uc2e4\ud589 \uc548 \ud568'}});
  const node=e.mount(n=>e.ctx.renderFailureAnalysisTable(n,job({results:[r]})));assert.match(node.textContent,/\uc800\uc7a5 \uac70\uc808 \uc0ac\uc720/);assert.match(node.textContent,/\ud655\uc778\ub41c \ub0b4\uc6a9/);assert.match(node.textContent,/\uc5f0\uacb0 \uadfc\uac70 \uc5c6\uc74c/);assert.match(node.textContent,/abc123/);assert.doesNotMatch(node.textContent,/Saved rejection/);
  const evidence=node.querySelectorAll('a').find(a=>a.textContent==='E1'),files=node.querySelector('details');assert.equal(!!files.open,false);evidence.click();assert.equal(files.open,true);assert(all(node).some(n=>'#'+n.id===evidence.href));
  const link=node.querySelectorAll('a').find(a=>a.textContent.includes('\ub2e8\uacc4·\ud30c\uc77c \ubaa9\ub85d')),query=new URLSearchParams(link.href.slice(1));assert.equal(query.get('run'),'run A');assert.equal(query.get('stage'),'03-calculation');assert.equal(query.get('round'),'01-round');
  assert.equal(e.ctx.failureAnalysisArtifactLink(r,'preparation',{path:'javascript:alert(1)'}),null);
  assert.equal(e.ctx.failureAnalysisArtifactLink(r,'preparation',{path:'reports/run/other/01-preparation/test-0001/03-calculation/file.json'}),null);
  assert(e.ctx.failureAnalysisArtifactLink(r,'preparation',{path:'01-preparation/test-0001/03-calculation/file.json'}));
  const prepEvidence=e.ctx.failureAnalysisArtifactLink({...r,variant},'generation',{path:'01-preparation/test-0001/03-calculation/file.json'});assert.equal(new URLSearchParams(prepEvidence.href.slice(1)).get('variant'),null);
  const raw=e.mount(n=>e.ctx.renderFailureAnalysisTable(n,job()));assert.match(raw.textContent,/\ud55c\uad6d\uc5b4 \ud45c\uc2dc \uc5c6\uc74c/);assert.match(raw.textContent,/Recorded fact/);
 });
 await check('Analysis text is inert; evidence identities are unique across duplicated displays',()=>{
  const e=env(),r=result();r.analysis.rejection_summary='<img src=x onerror=alert(1)>';
  const a=e.mount(n=>e.ctx.renderFailureAnalysisTable(n,job({results:[r]}))),b=e.mount(n=>e.ctx.renderFailureAnalysisTable(n,job({results:[r]})));
  assert.match(a.textContent,/<img/);assert.equal(a.querySelectorAll('img').length,0);assert.notEqual(find(a,'failure-analysis-artifact')[0].id,find(b,'failure-analysis-artifact')[0].id);
 });
 await check('Early failed Preparation and Generation show matched analysis immediately after the guide',()=>{
  for(const selectedVariant of [null,variant]){
   const e=env(),phase=selectedVariant?'generation':'preparation',stage=selectedVariant?'05-human-review':'07-human-review';
   e.ctx.window.preparationVariant=selectedVariant;e.ctx.window[selectedVariant?'generationStage':'preparationStage']=stage;
   e.ctx.DATA.batch.failure_analysis.jobs=[job({phase,results:[result({variant:selectedVariant}),result({case:'foreign-case',variant:selectedVariant,analysis:{rejection_summary:'FOREIGN CASE'}}),result({variant:'foreign-variant',analysis:{rejection_summary:'FOREIGN VARIANT'}})]})];
   const row={sample:{id:'test-0001'},status:'FAIL',run:{artifacts:{'run.json':{status:'FAIL',stopped_at:'02-review'}},generation:{[variant+'/run.json']:{status:'FAIL',stopped_at:'01-perturbation'}}}};
   const node=e.mount(n=>e.ctx.renderPreparationDetail(n,row)),analysis=find(node,'failure-analysis-selected')[0];assert(analysis);const children=analysis.parent.children,i=children.indexOf(analysis);assert.equal(children[i-1].className,'guide');assert.equal(children[i+1].className,'stage-content');assert.doesNotMatch(analysis.textContent,/FOREIGN/);
   assert.equal(e.ctx.reviewDefaultDecision(row,null),'REJECTED');assert.equal(row.run.artifacts['run.json'].status,'FAIL');
   const other=e.mount(n=>e.ctx.renderSelectedFailureAnalysis(n,row,selectedVariant,'03-calculation'));assert.equal(other.children.length,0);
  }
 });
 await check('Older per-case results are explicitly snapshots when newest phase job has no match',()=>{
  const e=env();e.ctx.DATA.batch.failure_analysis.jobs=[job({id:'2',status:'RUNNING',results:[]}),job({id:'1'})];
  const node=e.mount(n=>e.ctx.renderSelectedFailureAnalysis(n,{sample:{id:'test-0001'}},null,'07-human-review'));assert.match(node.textContent,/\uc774\uc804 \uc791\uc5c5\uc758 \ud574\uc11d/);
  const overview=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n));assert.match(overview.textContent,/\uc800\uc7a5\ub41c \ud574\uc11d \uacb0\uacfc\ub97c \uae30\ub2e4\ub9ac\uace0/);
 });
 await check('No, Escape and native close each cancel without POST; unknown cost is explicit',async()=>{
  for(const action of ['no','escape','close']){
   const e=env();e.handle(async()=>response(preview()));const b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);const task=b.click();await tick();
   const dialog=e.document.body.querySelector('dialog');assert(dialog.open);assert.match(dialog.textContent,/gpt-6-luna/);assert.match(dialog.textContent,/max/);assert.match(dialog.textContent,/\ucd5c\ub300 \ud638\ucd9c: 4\ud68c/);assert.match(dialog.textContent,/\ubb34\ub8cc\ub97c \ub73b\ud558\uc9c0/);assert.match(dialog.textContent,/\ud574\uc11d 1\ud68c \+ \ud55c\uad6d\uc5b4 \ud45c\uc2dc \ubc88\uc5ed 1\ud68c/);assert.match(dialog.textContent,/Token volume unavailable/);assert.match(dialog.textContent,/\uc2e4\uc81c \uccad\uad6c\uc561\uc774 \uc544\ub2d9\ub2c8\ub2e4/);assert.equal(e.document.activeElement.textContent,'No · \ucde8\uc18c');
   if(action==='no')named(dialog,'No · \ucde8\uc18c').click();else if(action==='escape')dialog.emit('cancel',{preventDefault(){}});else dialog.close();await task;
   assert.equal(e.requests.length,1);assert(e.requests[0].url.startsWith('/api/failure-analysis/preview?'));assert.equal(b.disabled,false);assert.equal(dialog.isConnected,false);
  }
 });
 await check('Yes alone sends the exact preview snapshot, entire-phase scope and no verdict mutation',async()=>{
  const e=env(),before=JSON.stringify(e.ctx.DATA);e.handle(async(url,options)=>response(options.method==='POST'?{ok:true}:preview({phase:'generation',estimated_cost_usd:0.012345})));
  const b=e.ctx.failureAnalysisButton('generation');e.document.body.append(b);const task=b.click();await tick();const dialog=e.document.body.querySelector('dialog');assert.match(dialog.textContent,/US\$ 0.012345/);assert.match(dialog.textContent,/Generation \uc804\uccb4/);named(dialog,'Yes · \uc2e4\ud328 \ud574\uc11d \uc2dc\uc791').click();await task;
  assert.equal(e.requests.length,2);assert.equal(e.requests[0].url,'/api/failure-analysis/preview?name=run%20A&phase=generation');
  assert.equal(e.requests[1].url,'/api/failure-analysis');assert.deepEqual(JSON.parse(e.requests[1].options.body),{run:'run A',phase:'generation',preview_id:'snapshot 123'});assert.equal(JSON.stringify(e.ctx.DATA),before);assert.equal(b.disabled,true);
  e.ctx.DATA.batch.failure_analysis.jobs=[job({id:'fresh'})];e.ctx.failureAnalysisSync();assert.equal(b.disabled,false);
 });
 await check('Budget shows analysis and translation separately with the combined token limit',async()=>{
  const e=env();e.handle(async()=>response(preview({planned:8,calls:16,analysis_calls:8,translation_calls:8,estimated_cost_usd:1.164288,
   cost_breakdown:{input_token_budget:167232,output_token_budget:32768,total_token_budget:200000,input_per_million:0.2,output_per_million:1.2,per_call_usd:0.072768,analysis_usd:0.582144,translation_usd:0.582144}})));
  const b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);const task=b.click();await tick();
  const dialog=e.document.body.querySelector('dialog');assert.match(dialog.textContent,/167,232 \+ \ucd9c\ub825 32,768 = \ucd1d 200,000/);assert.match(dialog.textContent,/\uc2e4\ud328 \ubd84\uc11d: US\$ 0.072768 × 8\uac74 = US\$ 0.582144/);assert.match(dialog.textContent,/\ud55c\uad6d\uc5b4 \ubc88\uc5ed \ubcc4\ub3c4: US\$ 0.072768 × 8\uac74 = US\$ 0.582144/);
  named(dialog,'No · \ucde8\uc18c').click();await task;assert.equal(e.requests.length,1);
 });
 await check('Concurrent rerendered buttons cannot duplicate preview or accepted start requests',async()=>{
  const e=env();let release;e.handle(()=>new Promise(resolve=>{release=resolve;}));const first=e.ctx.failureAnalysisButton('preparation');e.document.body.append(first);const task=first.click();
  const second=e.ctx.failureAnalysisButton('generation');e.document.body.append(second);assert.equal(second.disabled,true);second.click();assert.equal(e.requests.length,1);
  release(response(preview()));await tick();const replacement=e.ctx.failureAnalysisButton('preparation');assert.equal(replacement.disabled,true);named(e.document.body.querySelector('dialog'),'No · \ucde8\uc18c').click();await task;
 });
 await check('Returning an existing completed job clears pending state without waiting for a new job',async()=>{
  const e=env(),completed=job({preview_id:'snapshot 123'});e.ctx.DATA.batch.failure_analysis.jobs=[completed];const before=JSON.stringify(e.ctx.DATA);
  e.handle(async(url,options)=>response(options.method==='POST'?completed:preview()));const node=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n)),b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);
  const task=b.click();await tick();named(e.document.body.querySelector('dialog'),'Yes · \uc2e4\ud328 \ud574\uc11d \uc2dc\uc791').click();await task;
  assert.equal(e.requests.length,2);assert.equal(b.disabled,false);assert.equal(e.ctx.failureAnalysisButton('preparation').disabled,false);assert.match(node.textContent,/\ucd94\uac00 \uc720\ub8cc \ud638\ucd9c\uc740 \uc5c6\uc2b5\ub2c8\ub2e4/);assert.equal(JSON.stringify(e.ctx.DATA),before);
 });
 await check('Translation-only failures keep the interpretation and completed usage totals separate',()=>{
  const e=env(),r=result({status:'PARTIAL',translation_error:'Translation schema invalid'}),j=job({status:'PARTIAL',results:[r],usage:{calls:2,token_totals_known:{total_tokens:1234},estimated_cost_usd_known:0.023,missing_usage_calls:1,missing_cost_calls:1}});
  const before=JSON.stringify(j),node=e.mount(n=>e.ctx.renderFailureAnalysisJob(n,j));assert.match(node.textContent,/Saved rejection/);assert.match(node.textContent,/Recorded fact/);assert.match(node.textContent,/\ud55c\uad6d\uc5b4 \ud45c\uc2dc \ubc88\uc5ed \uc624\ub958: Translation schema invalid/);assert.match(node.textContent,/\ucd1d \ud1a0\ud070 1234/);assert.match(node.textContent,/US\$ 0.023/);assert.match(node.textContent,/\uc2e4\uc81c \uccad\uad6c\uc561 \uc544\ub2d8/);assert.match(node.textContent,/\ube44\uc6a9 \uc0b0\uc815 \ub204\ub77d 1\ud68c/);assert.equal(JSON.stringify(j),before);
 });
 await check('Run changes invalidate both pending preview and confirmed launch',async()=>{
  for(const point of ['preview','confirm']){
   const e=env();let release;e.handle(()=>point==='preview'?new Promise(resolve=>{release=resolve;}):Promise.resolve(response(preview())));
   const b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);const task=b.click();if(point==='confirm')await tick();e.ctx.DATA.batch.name='different';
   if(point==='preview')release(response(preview()));else named(e.document.body.querySelector('dialog'),'Yes · \uc2e4\ud328 \ud574\uc11d \uc2dc\uc791').click();await task;assert.equal(e.requests.length,1);assert.equal(e.document.body.querySelector('dialog'),null);
  }
 });
 await check('Preview errors, invalid contract and zero targets never reach a start call',async()=>{
  for(const fixture of [response({error:'Preview unavailable'},false),response(preview({model:'other'})),response(preview({phase:'generation'})),response(preview({planned:0})),response(preview({calls:null}))]){
   const e=env();e.handle(async()=>fixture);const node=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n)),b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);await b.click();assert.equal(e.requests.length,1);assert.equal(e.document.body.querySelector('dialog'),null);assert.equal(b.disabled,false);assert(find(node,'failure-analysis-notice')[0].textContent.length>0);assert.equal(find(node,'failure-analysis-overview')[0].children[0].open,true);
  }
 });
 await check('Stale preview POST errors preserve saved jobs and require a new explicit request',async()=>{
  const e=env();e.ctx.DATA.batch.failure_analysis.jobs=[job()];const before=JSON.stringify(e.ctx.DATA);e.handle(async(url,options)=>response(options.method==='POST'?{error:'PREVIEW_STALE'}:preview(),options.method!=='POST'));
  const node=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n)),b=e.ctx.failureAnalysisButton('preparation');e.document.body.append(b);const task=b.click();await tick();named(e.document.body.querySelector('dialog'),'Yes · \uc2e4\ud328 \ud574\uc11d \uc2dc\uc791').click();await task;assert.equal(e.requests.length,2);assert.match(node.textContent,/PREVIEW_STALE/);assert.equal(b.disabled,false);assert.equal(JSON.stringify(e.ctx.DATA),before);
 });
 await check('Empty data, zero targets and server busy disable execution without affecting saved views',()=>{
  const e=env();delete e.ctx.DATA.batch.failure_analysis;assert.equal(e.ctx.failureAnalysisButton('preparation').disabled,true);const empty=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n));assert.equal(empty.children.length,0);
  e.ctx.DATA.batch.failure_analysis={jobs:[job()],busy:true,preparation:1,generation:0};assert.equal(e.ctx.failureAnalysisButton('preparation').disabled,true);assert.equal(e.ctx.failureAnalysisButton('generation').disabled,true);
  const node=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n));assert.match(node.textContent,/Saved rejection/);assert.match(node.textContent,/\uc9c4\ud589 \uc911/);
 });
 await check('Collapse state is kept per run across refreshes',()=>{
  const e=env(),first=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n)),d=find(first,'failure-analysis-overview')[0].children[0];d.open=true;d.emit('toggle');
  const again=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n));assert.equal(find(again,'failure-analysis-overview')[0].children[0].open,true);
  e.ctx.DATA.batch.name='other';const other=e.mount(n=>e.ctx.renderFailureAnalysisOverview(n));assert.equal(find(other,'failure-analysis-overview')[0].children[0].open,false);
 });
 console.log(JSON.stringify({status:'PASS',checks:checks.length,model_calls:0,network_calls:0,scope:'viewer UI and mocked HTTP only'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
