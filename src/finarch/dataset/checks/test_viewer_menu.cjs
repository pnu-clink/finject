// Read-only regressions against saved CLI/API runs and isolated missing-file cases.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root='viewer/dataset/',html=fs.readFileSync('viewer/dataset/index.html','utf8');
for(const match of html.matchAll(/<script(?: [^>]*)?>([\s\S]*?)<\/script>/g))if(!match[1].includes('__FINARCH_DATA__'))new vm.Script(match[1]);
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.style={};this.attributes={};this.classList={add:()=>{}};this._text='';}
 append(...items){this.children.push(...items);}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(item=>item.textContent).join('');}
 setAttribute(key,value){this.attributes[key]=value;}
}
const el=(tag,cls,value)=>{const n=new Element(tag);n.className=cls;if(value!==undefined)n.textContent=value;return n;};
let opened;
const ctx=vm.createContext({console,viewerDisclosure:(key,title,content)=>content,DATA:{batch:{name:'20260910-018',round:'03-round'}},el,document:{createTextNode:text=>el('#text','',text)},
 button:(label,fn)=>{const n=el('button','',label);n.onclick=fn;return n;},filePathLabel:path=>el('span','',path),jsonViewer:(data)=>el('pre','',JSON.stringify(data)),
 showSchemaDialog:()=>{opened=el('div');return {body:opened};}});
for(const file of ['common/stage-guide.js','common/saved-calls.js','prepare/answer/stages.js','prepare/generation/common/menu.js'])vm.runInContext(fs.readFileSync(root+file,'utf8'),ctx);
function fn(name){let start=html.indexOf('function '+name+'('),end=start;assert(start>=0);for(;;){end=html.indexOf('\n',end)+1;assert(end);const source=html.slice(start,end);try{new vm.Script(source);return source;}catch{}}}
vm.runInContext(fn('llmCallState'),ctx);
const sources=[];
function artifacts(dir){const a={};for(const entry of fs.readdirSync(dir,{recursive:true,withFileTypes:true})){if(!entry.isFile()||!entry.name.endsWith('.json'))continue;const path=(entry.parentPath||entry.path)+'/'+entry.name,bytes=fs.readFileSync(path);a[path.slice(dir.length+1)]=JSON.parse(bytes);sources.push({path,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});}return a;}
const prepPath='reports/run/20260910-018/01-preparation/test-0001',prep={sample:{id:'test-0001'},run:{path:prepPath,artifacts:artifacts(prepPath)}};
const failurePath='reports/run/20260915-003/01-preparation/test-0004',failure={run:{path:failurePath,artifacts:artifacts(failurePath)}};
const genPath='reports/run/20260910-018/02-generation/01-round/test-0001';prep.run.generation=artifacts(genPath);
const results=[];function check(name,fn){fn();results.push(name);}
const descendants=node=>[node,...node.children.flatMap(descendants)];
check('Saved CLI prompt, input, response, schema and result refer to one call',()=>{
 const calls=ctx.savedMenuCalls(prep,'03-calculation/','pot.author');assert.equal(calls.length,1);const c=calls[0];assert(c.cli.prompt.includes(c.model.input.question));assert.equal(typeof c.raw.text,'string');assert.equal(c.check.status,'PASS');assert(c.responsePath.includes('03-LLM-call/02-raw-response.json'));
});
check('Failed API response remains inspectable with its actual role name',()=>{
 const c=ctx.savedMenuCalls(failure,'03-calculation/','pot.author');assert.equal(c.length,1);assert.equal(c[0].cli.role,'01-preparation.03-calculation.pot');assert.equal(c[0].check.reason,'RESPONSE_SCHEMA_INVALID');assert.equal(typeof c[0].raw.text,'string');assert(ctx.llmCallState(c[0]).includes('수신 검사 실패'));
});
check('No cross-stage call leakage or fabricated missing response',()=>{
 assert.equal(ctx.savedMenuCalls(failure,'04-graph/','pot.author').length,0);
 const row={run:{artifacts:{'x/01-input.json':{role:'pot.author',prompt:'saved'},'other/02-raw-response.json':{text:'foreign'}}}};
 const call=ctx.savedMenuCalls(row,'x/','pot.author')[0];assert.equal(call.raw,undefined);assert.equal(ctx.savedMenuCalls(row,'x/','dtt.audit').length,0);
});
check('All 5 preparation and all 28 generation menus have explicit steps',()=>{
 for(const stage of ['01-source','02-review-and-correct','03-calculation','04-graph','05-verification','06-exception-handler','07-human-review']){const panel=el('div');ctx.renderMenuGuide(panel,prep,null,stage);assert(panel.textContent.length>80);}
 for(const variant of ['01-ic-value-before','02-ic-value-after','03-ic-source-type-1','04-ic-source-type-2','05-ic-relation','06-ea-earlier-input','07-ea-later-input'])for(const stage of ['01-perturbation','02-generate-text','03-validation','04-human-review']){
  const panel=el('div');ctx.renderMenuGuide(panel,prep,variant,stage);assert(panel.textContent.length>80);assert(!panel.textContent.includes('undefined'));
 }
});
check('Preview buttons open exactly their saved files; absence is explicit',()=>{
 const panel=el('div');ctx.renderMenuGuide(panel,prep,null,'03-calculation');const buttons=descendants(panel).filter(n=>n.tagName==='button'&&n.dataset.previewPaths);assert(buttons.length>=4);
 for(const button of buttons){const paths=JSON.parse(button.dataset.previewPaths);button.onclick();assert(opened.textContent);for(const path of paths){assert(Object.hasOwn(prep.run.artifacts,path));assert(opened.textContent.includes(JSON.stringify(prep.run.artifacts[path])));}}
 const empty=el('div');ctx.renderMenuGuide(empty,{run:{artifacts:{}}},null,'03-calculation');assert(empty.textContent.includes(' 저장 기록 없음'));assert.equal(descendants(empty).filter(n=>n.tagName==='button'&&n.dataset.previewPaths).length,0);
});
check('Generation preview keeps its producing round and variant path',()=>{
 const variant='01-ic-value-before',path=variant+'/02-generate-text/04-observation.json',resolved=ctx.stageFilePath(prep,variant,path);assert(resolved.includes('/01-round/test-0001/'+variant+'/'));assert(!resolved.includes('/03-round/'));
 const r=ctx.generationRow(prep,variant);assert.equal(ctx.savedMenuCalls(r,'02-generate-text/').length,1);assert.equal(ctx.savedMenuCalls(r,'03-validation/').length,1);
});
check('Paired sentence links only to its recorded producing call',()=>{
 const source=ctx.generationCallSource(prep,'02-ic-value-after');assert(source.run.path.endsWith('/01-ic-value-before'));
 assert.equal(ctx.savedMenuCalls(source,'02-generate-text/').length,1);
 const run={...prep.run,generation:{...prep.run.generation,'02-ic-value-after/02-generate-text/02-place-paired-sentence.json':{source:'different-run/01-ic-value-before',new_model_calls:0}}};
 assert.equal(ctx.savedMenuCalls(ctx.generationCallSource({...prep,run},'02-ic-value-after'),'02-generate-text/').length,0);
});
check('View source order is explanation, comparison, result tree',()=>{
 const menu=fs.readFileSync(root+'menu.js','utf8');assert(menu.indexOf('renderMenuGuide(')<menu.indexOf('renderPreparationContent('));assert(menu.indexOf('renderGenerationContent(')<menu.indexOf('renderStageFiles('));
 for(const axis of ['IC-value','IC-source','IC-relation','EA'])assert(fs.existsSync(root+'prepare/generation/'+axis+'/01-perturbation/view.js'));
});
check('Saved source files were not changed by inspection',()=>{for(const {path,sha256} of sources)assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex'),sha256);});
console.log(JSON.stringify({status:'PASS',checks:results.length,results,source_files_read:sources.length,model_calls:0},null,2));
