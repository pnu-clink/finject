// Exercise the real live controller with document-only bundles and dataset navigation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {test}=require('node:test');
const shell=fs.readFileSync('viewer/dataset/shell.html','utf8');
const controller=shell.slice(shell.lastIndexOf('if(DATA.live){'),shell.lastIndexOf('\n}\n</script>'));
const documentationSource=fs.readFileSync('viewer/dataset/reports/documentation.js','utf8');
const docRun='document-only',docPath='docs/02-experiments/review.md';
const documentPayload=()=>({revision:'doc-v1',runs:[],batch:{name:docRun,rounds:[],round:null,documentation:{
  documents:[{path:docPath,content:'# Saved design'}],catalog:[{path:docPath}],aliases:{},entry_document:docPath
}}});
const datasetPayload=name=>({revision:name,runs:[],batch:{name,rounds:[],round:null}});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function node(){return {value:'',textContent:'',hidden:false,disabled:false,style:{},dataset:{},options:[],
  replaceChildren(){this.options=[];this.textContent='';},append(...children){this.options.push(...children);},after(){}};}
async function fixture({query='?run='+docRun+'&doc='+encodeURIComponent(docPath),names=['latest-dataset'],payload=documentPayload(),hold=false}={}){
  const nodes=new Map(),requests=[],get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  let timer,release;
  const location={href:'http://localhost/'+query,search:query};
  const context={DATA:{live:true,runs:[]},rows:[],selected:null,tab:0,location,URL,URLSearchParams,Map,Set,Date,JSON,Error,
    $:get,el:(tag,cls,text)=>({...node(),textContent:text}),window:{},filterSpecs:[],selections:{},
    history:{replaceState(state,title,url){location.href=String(url);location.search=new URL(url).search;}},
    loadRows(){context.rows=[];},initFilters(){},render(){get('detail').textContent=context.DATA.batch?.name||'';},jsonBox(){},isDatasetSurvey:()=>false,
    document:{hidden:false,querySelectorAll:()=>[],querySelector:()=>node(),addEventListener(){}},
    setTimeout(fn){timer=fn;return 1;},clearTimeout(){},
    async fetch(url){
      requests.push(url);const target=new URL(url,'http://localhost');let value;
      if(target.pathname==='/api/runs')value=names.map(name=>({name,evaluation_exportable:true}));
      else if(target.searchParams.get('name')===docRun){if(hold)await new Promise(resolve=>{release=()=>{hold=false;resolve();};});value=payload;}
      else if(names.includes(target.searchParams.get('name')))value=datasetPayload(target.searchParams.get('name'));
      return {ok:Boolean(value),status:value?200:404,headers:{get:()=>null},json:async()=>structuredClone(value)};
    }};
  vm.createContext(context);vm.runInContext(documentationSource,context);vm.runInContext(controller,context);await tick();
  return {context,get,requests,poll:()=>timer(),release:()=>release()};
}
test('explicit document run opens even when excluded from the dataset selector, including refresh',async()=>{
  const f=await fixture();assert.equal(f.context.DATA.batch.name,docRun);assert.equal(f.get('detail').textContent,docRun);
  assert.deepEqual(f.get('batch-select').options.map(o=>o.value),['','latest-dataset']);
  assert.equal(f.get('batch-select').options[0].disabled,true);assert.equal(f.get('batch-select').options[0].dataset.evaluationExportable,'false');
  await f.poll();assert.equal(f.context.DATA.batch.name,docRun);
  assert(!f.requests.some(url=>url.includes('name=latest-dataset')));
});
test('explicit documentation remains readable when there are no dataset runs',async()=>{
  const f=await fixture({names:[]});assert.equal(f.get('detail').textContent,docRun);
  assert.deepEqual(f.get('batch-select').options.map(o=>o.value),['']);
});
test('switching to a dataset clears the document route and restores ordinary selection',async()=>{
  const f=await fixture();f.get('batch-select').value='latest-dataset';f.get('batch-select').onchange();await tick();
  assert.equal(f.context.DATA.batch.name,'latest-dataset');assert.equal(f.get('detail').textContent,'latest-dataset');
  const query=new URLSearchParams(f.context.location.search);assert.equal(query.has('doc'),false);assert.equal(query.get('run'),'latest-dataset');
  assert.deepEqual(f.get('batch-select').options.map(o=>o.value),['latest-dataset']);
  assert.equal(vm.runInContext('pipelineDocumentPath',f.context),'');
  assert.equal(f.get('batch-select').options[0].dataset.evaluationExportable,'true');
});
test('missing document runs display an error without loading another dataset',async()=>{
  const f=await fixture({payload:null});assert.equal(f.context.DATA.batch,undefined);
  assert.match(f.get('notice').textContent,/문서 링크를 열지 못했습니다/);
  assert(!f.requests.some(url=>url.includes('name=latest-dataset')));
});
test('unlisted or empty document paths cannot silently display the entry document',async()=>{
  for(const path of ['docs/missing.md','']){
    const f=await fixture({query:'?run='+docRun+'&doc='+encodeURIComponent(path)});
    assert.equal(f.context.DATA.batch,undefined);assert.match(f.get('notice').textContent,/문서 목록에 없습니다/);
  }
});
test('a document parameter pointing at a dataset cannot display dataset results',async()=>{
  const f=await fixture({payload:datasetPayload(docRun)});assert.equal(f.context.DATA.batch,undefined);
  assert.match(f.get('notice').textContent,/파이프라인 문서 기록이 없습니다/);
});
test('a late document response cannot replace a dataset selected by the user',async()=>{
  const f=await fixture({hold:true});f.get('batch-select').value='latest-dataset';f.get('batch-select').onchange();
  f.release();await tick();await f.poll();assert.equal(f.context.DATA.batch.name,'latest-dataset');
});
test('ordinary invalid run links retain the existing latest-dataset fallback',async()=>{
  const f=await fixture({query:'?run=removed-dataset'});assert.equal(f.context.DATA.batch.name,'latest-dataset');
  assert.deepEqual(f.get('batch-select').options.map(o=>o.value),['latest-dataset']);
});
