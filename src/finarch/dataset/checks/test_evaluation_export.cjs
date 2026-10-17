// Isolated evaluator state tests; no browser or production decision writes.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('viewer/dataset/evaluation.js','utf8');
const callbacks=[],controls=new Map(),storage=new Map();
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.style={};this.value='';this.textContent='';}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 querySelector(selector){return selector==='.viewer-language'?this.children.find(x=>x.className==='viewer-language')||null:null;}
 setAttribute(){} focus(){} click(){this.onclick?.();} get options(){return this.children;}
 getBoundingClientRect(){return {height:62};}
}
const el=(tag,cls='',text='')=>Object.assign(new Element(tag),{textContent:text});
const $=id=>{if(!controls.has(id))controls.set(id,new Element());return controls.get(id);};
const context=vm.createContext({console,Blob,Response,DecompressionStream,Uint8Array,atob,URL,setTimeout,Event,
 document:{documentElement:{style:{setProperty(){}}},body:{classList:{add(){},toggle(){}}},addEventListener:(event,fn)=>callbacks.push(fn),querySelector:selector=>selector==='header'?$('header'):null,querySelectorAll:()=>[],title:''},
 el,$,button:(title,fn)=>Object.assign(el('button','',title),{onclick:fn}),window:{addEventListener(){}},requestAnimationFrame:fn=>fn(),selections:{},rows:[],selected:null,
 render(){},initFilters(){},evaluationMountWorkspace(){},loadRows(){context.rows=context.DATA.runs.map(r=>({id:r.path+':ANSWER',sample:r.artifacts['01-source/01-receive-input/01-input.json']||r.artifacts['00-data-preparation/01-select-input/01-input.json']}));},
 localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k),key:i=>[...storage.keys()][i],get length(){return storage.size;}},
 stageFailureEntries:()=>[],jsonBox(){},DATA:{live:false}});
for(const path of ['evaluation/graph.js','evaluation/review.js','evaluation/workspace.js'])vm.runInContext(fs.readFileSync('viewer/dataset/'+path,'utf8'),context);
context.evaluationMountWorkspace=()=>{};
vm.runInContext(source,context);
// Dataset evidence determines eligibility, including named merged runs.
context.showSchemaDialog=()=>({dialog:{},body:$('export-body')});
context.DATA.batch={name:'20261003-concat-001'};
for(const [name,eligible] of [['20260917-002',true],['20261003-concat-001',true],['20261003-001-CodeTAT-QA-0917-002',true],['20261003-results-only',false]]){
 const option=el('option','',name);option.value=name;option.dataset.evaluationExportable=String(eligible);$('batch-select').append(option);
}
context.showEvaluationExport();
const exportLines=$('export-body').children.filter(x=>x.tagName==='label');
assert.deepEqual(exportLines.map(x=>x.children[1].textContent.split(' · ')[0]),['20260917-002','20261003-concat-001','20261003-001-CodeTAT-QA-0917-002']);
assert.equal(exportLines[1].children[0].checked,true);
assert.equal(context.evaluationFilename('\ud3c9\uac00\uc790','20260917-002',false,new Date(2026,8,18)),'\ud3c9\uac00\uc790-20260917-002-0918.json');
context.FinarchI18n={language:'en',translate:label=>label==='\uc784\uc2dc'?'Draft':label};
assert.equal(context.evaluationFilename('QA','20260917-002',true,new Date(2026,8,18)),'Draft-QA-20260917-002-0918.json');
delete context.FinarchI18n;
const html=fs.readFileSync(process.argv[2]||'outputs/evaluation-export-20260930/evaluation-sample.html','utf8');
const payload=JSON.parse(html.match(/<script id="data"[^>]*>([\s\S]*?)<\/script>/)[1]);
for(const match of html.matchAll(/<script type="application\/octet-stream" id="([^"]+)">([^<]+)<\/script>/g))$(match[1]).textContent=match[2];
context.DATA=payload;
const pkg=payload.evaluation,run=pkg.batches[0].batch.name,caseName=pkg.batches[0].cases[0].case;
const record={case:caseName,variant:'ANSWER',decision:'APPROVED',comment:'round-trip \uc8fc\uc11d',confirmed:true,checklist:{'05-verification':true}};
const imported={format:'finarch-evaluation-results-v1',package_id:pkg.id,run,reviewer:'QA',evaluations:[record]};
context.validateEvaluationImport(imported,pkg);
for(const bad of [{...imported,package_id:'wrong'},{...imported,evaluations:[record,record]},{...imported,evaluations:[{...record,case:'test-9999'}]},{...imported,evaluations:[{...record,decision:null}]}])assert.throws(()=>context.validateEvaluationImport(bad,pkg));
context.validateEvaluationImport({...imported,evaluations:[{...record,decision:'REJECTED',comment:''}]},pkg);
(async()=>{
 let request;
 context.filtered=()=>{throw Error('Evaluator export must not use production screen filters');};
 context.fetch=async(url,options)=>{request=JSON.parse(options.body);return {ok:true,text:async()=>'<html>sample</html>'};};
 context.evaluationDownload=()=>{};
 await $('export-body').children.find(x=>x.textContent==='HTML \ub2e4\uc6b4\ub85c\ub4dc').onclick();
 assert.equal(request.runs[0].name,'20261003-concat-001');assert(!('cases' in request.runs[0]));
 const toolbar=Object.assign(el('div'),{className:'viewer-language'});$('header').append(toolbar);
 callbacks[0]();assert($('header').children.includes(toolbar));context.applyEvaluationImport(imported);
 assert.equal(context.evaluationDocument(run,true).evaluations[0].comment,record.comment);
 assert.equal(context.evaluationDocument(run,true).evaluations[0].checklist['05-verification'],true);
 await context.evaluationLoadCase(caseName);
 assert.equal(context.DATA.runs.filter(r=>!r.summary_only).length,1);
 for(const batch of pkg.batches){context.evaluationSwitch(batch.batch.name);for(const entry of batch.cases){await context.evaluationLoadCase(entry.case);assert.equal(context.DATA.runs.filter(r=>!r.summary_only).length,1);}}
 context.evaluationSwitch(run);assert.equal(context.evaluationDocument(run,false).evaluations[0].decision,'APPROVED');
 const panel=el('div'),row={sample:{id:caseName},run:{artifacts:{},generation_origins:{}}};context.evaluationRenderOriginalReview(panel,row,null);
 const all=n=>[n,...n.children.flatMap(all)];
 assert(!all(panel).some(n=>n.tagName==='textarea'||n.tagName==='input'));assert(all(panel).some(n=>n.textContent===record.comment));
 assert.equal(context.evaluationDocument(run,false).evaluations[0].confirmed,true);
 assert(storage.size>0);
 console.log('PASS: filenames, strict imports, draft/final round-trip, run isolation, lazy per-case decoding, read-only original view preserves annotation');
})().catch(error=>{console.error(error);process.exitCode=1;});
