// Read saved journals only; verify that the viewer accounts for every CLI execution.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const viewer=require('./test_viewer_logs.cjs');
function load(root){
 const artifacts={};
 function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
  const file=path.join(dir,entry.name);
  if(entry.isSymbolicLink())continue;
  if(entry.isDirectory())walk(file);
  else if(entry.name==='events.jsonl'||/^(cli-start|cli-result|cli-request|cli-usage|replay-source)\.json$/.test(entry.name)){
   const text=fs.readFileSync(file,'utf8');artifacts[path.relative(root,file)]=entry.name.endsWith('jsonl')?text:JSON.parse(text);
  }
 }}walk(root);return {path:root,artifacts};
}
const parent=path.resolve(process.argv[2]||'reports/run/first-10-pot-validated-v3'),rows=[];
const cases=fs.readdirSync(parent).filter(name=>/^test-\d+$/.test(name));
for(const name of cases){let run=load(path.join(parent,name));const seen=new Set();
 while(run){assert(!seen.has(run.path),'cyclic source reference');seen.add(run.path);
  const inventory=viewer.logInventory(run),starts=inventory.events.filter(e=>viewer.logLlmBoundary(e)==='LLM 실행 시작');
  assert.equal(starts.length,inventory.calls.length,'process events and CLI files differ');
  assert.equal(inventory.damaged.length,0,'damaged journal');
  for(const call of inventory.calls)assert.equal(Array.from({length:7},(_,n)=>n).filter(n=>viewer.logScope(call,n)).length,1,'unmapped or double-mapped call');
  assert.equal(inventory.groups.reduce((n,g)=>n+g.events,0),inventory.events.length,'unaccounted event');
  rows.push({case:name,run:path.basename(path.dirname(run.path)),events:inventory.events.length,cli:inventory.calls.length,
   process_starts:starts.length,mapped_once:true,stages:inventory.groups,
   roles:Object.fromEntries([...new Set(inventory.calls.map(c=>c.role))].map(role=>[role,inventory.calls.filter(c=>c.role===role).length]))});
  const source=run.artifacts['replay-source.json']?.source_case;
  if(source){assert.equal(path.basename(source),name);assert.equal(path.dirname(path.dirname(source)),path.dirname(parent));}
  run=source?load(source):null;
 }
}
console.log(JSON.stringify({case_count:cases.length,run_cases:rows.length,total_cli:rows.reduce((n,r)=>n+r.cli,0),unmapped_cli:0,model_calls:0,rows},null,2));
