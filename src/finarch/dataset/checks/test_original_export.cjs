// Exercise embedded gzip loading, bounded memory and rapid navigation without a server.
const fs=require('node:fs'),vm=require('node:vm'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const summaries=[1,2,3].map(n=>({case_path:'/test-000'+n,path:'/test-000'+n,summary_only:true,sample:{id:'test-000'+n}}));
const details=summaries.map(row=>({...row,summary_only:false,artifacts:{code:'answer = 4\n'},generation:{graph:{nodes:[1,2]}}}));
const elements=new Map(details.map((row,i)=>['case-'+i,{textContent:zlib.gzipSync(JSON.stringify(row)).toString('base64')} ]));
elements.set('batch-status',{textContent:''});
let heldCase='',release,decompressions=0;
class EmbeddedResponse extends Response{
 async text(){decompressions++;const raw=await super.text();if(JSON.parse(raw).sample.id===heldCase)await new Promise(resolve=>release=resolve);return raw;}
}
const context={DATA:{batch:{name:'run'},runs:summaries,original:{cases:summaries.map((row,i)=>({case:row.sample.id,blob:'case-'+i,variants:[]}))}},
 rows:[],selected:null,window:{},document:{addEventListener(){}},$:id=>elements.get(id),summaries,
 Uint8Array,Blob,Response:EmbeddedResponse,DecompressionStream,atob,URL,Map,JSON,Error,
 fetch(){throw Error('Offline case selection must not fetch');},
 loadRows(){context.rows=context.DATA.runs.map(run=>({id:run.path,sample:run.sample}));},render(){}};
const exportMessages=[],downloads=[];
context.el=(tag,className,text)=>({textContent:text||''});
context.showSchemaDialog=()=>({body:{append(node){exportMessages.push(node);}}});
context.evaluationDownload=(...args)=>downloads.push(args);
const source=fs.readFileSync('viewer/dataset/original-export.js','utf8');
vm.runInNewContext(source+'\noriginalSummaries=summaries;',context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 for(const name of ['test-0001','test-0002','test-0003'])await context.originalLoadCase(name);
 assert.equal(vm.runInNewContext('originalCache.size',context),2);
 assert.equal(context.DATA.runs.filter(row=>!row.summary_only).length,1);
 assert.equal(context.selected,'/test-0003');
 assert.equal(decompressions,3);
 await context.originalLoadCase('test-0002');assert.equal(decompressions,3);
 heldCase='test-0001';const older=context.originalLoadCase(heldCase);
 while(!release)await tick();
 await context.originalLoadCase('test-0003');release();await older;
 assert.equal(context.selected,'/test-0003');
 assert.equal(context.DATA.runs.filter(row=>!row.summary_only).length,1);
 assert.equal(context.DATA.runs.find(row=>!row.summary_only).artifacts.code,'answer = 4\n');
 assert.equal(vm.runInNewContext('originalCache.has("test-0001")',context),false);
 context.fetch=async()=>({ok:false,status:403,headers:{get:()=> 'text/html'},text:async()=> '<!DOCTYPE HTML><p>Forbidden</p>'});
 await context.showOriginalExport();assert.match(exportMessages.at(-1).textContent,/HTTP 403/);assert.equal(downloads.length,0);
 context.fetch=async()=>({ok:false,status:400,headers:{get:()=> 'application/json'},text:async()=> '{"error":"UNKNOWN_RUN"}'});
 await context.showOriginalExport();assert.equal(exportMessages.at(-1).textContent,'UNKNOWN_RUN');
 context.fetch=async()=>({ok:true,status:200,headers:{get:()=> 'text/html; charset=utf-8'},text:async()=> '<head><script>window.FINARCH_ORIGINAL=true;</script></head>'});
 await context.showOriginalExport();assert.equal(downloads[0][0],'run-\uc6d0\ubcf8.html');
 console.log('PASS: offline gzip cases, two-case cache, one displayed detail, stale response guard, exact Python');
 console.log('PASS: HTML 403 / JSON error handling and original HTML download');
})().catch(error=>{console.error(error);process.exitCode=1;});
