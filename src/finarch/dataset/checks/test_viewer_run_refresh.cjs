// Exercise the actual live controller with changing server responses.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('viewer/dataset/shell.html','utf8');
const controller=source.slice(source.lastIndexOf('if(DATA.live){'),source.lastIndexOf('\n}\n</script>'));
function node(){return {value:'',textContent:'stale',hidden:false,style:{},options:[],replaceChildren(){this.options=[];this.textContent='';},append(...children){this.options.push(...children);},after(){}};}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
let names=['old'],timer,requests=[];
const context={DATA:{live:true,batch:{name:'old'},runs:[{path:'old'}]},rows:[],selected:'old:ANSWER',tab:5,
 location:{search:'?run=old&round=03-round'},URLSearchParams,Map,Set,Date,JSON,Error,
 $:get,el:(tag,cls,text)=>({...node(),textContent:text}),window:{},filterSpecs:[],selections:{},
 loadRows(){context.rows=context.DATA.runs;},initFilters(){},render(){get('detail').textContent=context.DATA.batch?.name||'';},jsonBox(){},
 document:{querySelectorAll:()=>[],querySelector:()=>node()},
 setInterval(fn,ms){assert.equal(ms,3000);timer=fn;},
 async fetch(url){requests.push(url);return {ok:true,status:200,headers:{get:()=>null},json:async()=>url==='/api/runs'?names.map(name=>({name})):{revision:url,batch:{name:new URL(url,'http://localhost').searchParams.get('name'),rounds:[]},runs:[]}};}
};
(async()=>{
 vm.runInNewContext(controller,context);await new Promise(resolve=>setImmediate(resolve));
 assert.equal(get('batch-select').value,'old');
 // Remove the selected run while reviewing. Its round, detail and selector must go.
 names=['new'];requests=[];await timer();
 assert.deepEqual(get('batch-select').options.map(o=>o.value),['new']);
 assert.equal(get('batch-select').value,'new');assert.equal(get('detail').textContent,'new');
 assert(requests.some(url=>url.startsWith('/api/run?name=new')&&!url.includes('round=')));
 // Deleting the last run must remove stale data and review controls.
 names=[];requests=[];await timer();
 assert.equal(context.DATA.runs.length,0);assert.equal(context.DATA.batch,undefined);
 assert.equal(get('detail').textContent,'');assert.equal(get('batch-info').textContent,'');
 assert.equal(get('round-select').hidden,true);assert.equal(get('batch-select').options.length,0);
 assert(get('batch-status').textContent.includes('실행 기록이 아직 없습니다'));
 assert.deepEqual(requests,['/api/runs']);
 // A newly created directory appears on the very next poll, without a reload.
 names=['restored'];await timer();assert.equal(get('batch-select').value,'restored');
 assert.equal(get('detail').textContent,'restored');
 console.log('PASS: selected run removal, empty state, round reset, and new run discovery');
})().catch(error=>{console.error(error);process.exitCode=1;});
