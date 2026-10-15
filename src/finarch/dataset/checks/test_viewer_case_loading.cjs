// Run the actual live controller against delayed case and overview responses.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('viewer/dataset/shell.html','utf8');
const controller=source.slice(source.lastIndexOf('if(DATA.live){'),source.lastIndexOf('\n}\n</script>'));
function node(){return {value:'',textContent:'',hidden:false,style:{},dataset:{},options:[],replaceChildren(){this.options=[];},append(...children){this.options.push(...children);},after(){}};}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
const summary=id=>({path:'/run/'+id+'/01-round',case_path:'/run/'+id,summary_only:true,artifacts:{'run.json':{status:'PASS'},'00-data-preparation/01-select-input/01-input.json':{id}}});
const detail=id=>({...summary(id),summary_only:false,list_entry:summary(id),generation:{private_detail:id}});
const batch={name:'example',round:'03-round',rounds:['01-round','03-round'],layout:'preparation-generation-v1'};
const full=()=>({revision:'overview',batch,runs:[detail('test-0001'),summary('test-0002'),summary('test-0003')]});
const partial=id=>({revision:id,detail_only:true,batch:{name:'example',round:'03-round'},runs:[detail(id)]});
let timer,holdOverview=false,releaseOverview,slowCase='',releaseCase,requests=[];
const context={DATA:{live:true,runs:[]},rows:[],selected:null,tab:0,
 location:{search:'?run=example&round=03-round&case=test-0001'},URLSearchParams,Map,Set,Date,JSON,Error,
 $:get,el:()=>node(),window:{},filterSpecs:[],selections:{},
 loadRows(){context.rows=context.DATA.runs.map(r=>({run:r,id:r.path,sample:r.artifacts['00-data-preparation/01-select-input/01-input.json']}));},initFilters(){},render(){},jsonBox(){},
 document:{hidden:false,querySelectorAll:()=>[],querySelector:()=>node(),addEventListener(){}},
 setTimeout(fn){timer=fn;return 1;},clearTimeout(){},
 async fetch(url){
  requests.push(url);const query=new URL(url,'http://localhost').searchParams;
  let value;
  if(url==='/api/runs')value=[{name:'example'}];
  else if(query.get('detail_only')){
   const id=query.get('case');if(id===slowCase)await new Promise(resolve=>releaseCase=resolve);
   value=partial(id);
  }else{if(holdOverview)await new Promise(resolve=>releaseOverview=resolve);value=full();}
  return {ok:true,status:200,headers:{get:()=>null},json:async()=>structuredClone(value)};
 }
};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 vm.runInNewContext(controller,context);await tick();
 assert.equal(context.DATA.runs.length,3);
 // A background full refresh cannot block foreground navigation.
 holdOverview=true;const refresh=timer();await tick();
 assert.equal(typeof releaseOverview,'function');
 await context.window.loadDetailCase('test-0002');
 assert.equal(context.DATA.runs.length,3);
 assert.equal(context.DATA.runs.filter(r=>!r.summary_only).length,1);
 assert.equal(context.DATA.runs.find(r=>!r.summary_only).case_path,'/run/test-0002');
 assert.equal(context.DATA.runs[0].generation,undefined);
 assert.equal(context.DATA.batch.layout,batch.layout);
 releaseOverview();await refresh;
 assert.equal(context.DATA.runs.find(r=>!r.summary_only).case_path,'/run/test-0002');
 // A slow older case response cannot replace a newer user selection.
 slowCase='test-0003';const older=context.window.loadDetailCase('test-0003');await tick();
 await context.window.loadDetailCase('test-0001');releaseCase();await older;
 assert.equal(context.DATA.runs.find(r=>!r.summary_only).case_path,'/run/test-0001');
 assert(requests.filter(u=>u.includes('detail_only=1')).length===3);
 assert.equal(requests.filter(u=>u==='/api/runs').length,2);
 console.log('PASS: one current detail, cached list, navigation during refresh, stale response guard');
})().catch(error=>{console.error(error);process.exitCode=1;});
