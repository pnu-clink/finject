// Log accounting must not invent completed calls, count nested spans twice, or mix reused runs.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
const script=html.split('<script>')[1].split('</script>')[0];
new vm.Script(script);
const ctx={};vm.createContext(ctx);
vm.runInContext(script.slice(script.indexOf('// [VL02]'),script.indexOf('function download')),ctx);
async function main(){
 const a={phase:'START',call_id:'outer',timestamp:'2026-01-01T00:00:00Z',stage:'02-calculation'},
  b={phase:'START',call_id:'inner',parent_call_id:'outer',timestamp:'2026-01-01T00:00:01Z',stage:'02-calculation'},
  end={phase:'END',call_id:'inner',parent_call_id:'outer',timestamp:'2026-01-01T00:00:02Z',status:'FAIL',elapsed_seconds:1};
 const run={path:'/runs/current/case',artifacts:{'events.jsonl':[a,b,end].map(JSON.stringify).join('\n')+'\nBROKEN\n'}};
 const read=ctx.readLogEvents(run);assert.equal(read.damaged.length,1);assert.equal(read.damaged[0],4);
 const spans=ctx.logSpans(read.events);assert.equal(spans.length,2);assert.equal(spans[0].status,'INCOMPLETE');assert.equal(spans[0].elapsed,undefined);assert.equal(spans[1].status,'FAIL');
 console.log('PASS partial/corrupt logs retain failure and missing completion');
 run.artifacts={
  '05-text/A/audit/01-input/cli-start.json':{role:'dtt.audit'},
  '05-text/A/audit/02-raw-response/cli-execution.json':{state:'EXITED',exit_code:0,elapsed_seconds:2},
  '05-text/A/T03-intent-audit/03-result.json':{status:'PASS'},
  '05-text/B/03-result/metadata.json':{realization_call_ref:'05-text/A/audit'},
  '05-text/C/audit/01-input/cli-start.json':{role:'dtt.audit'},
  '05-text/D/audit/01-input.json':{role:'dtt.audit'}
 };
 const calls=ctx.logCalls(run),summary=ctx.logSummary(calls);assert.equal(calls.length,2);assert.equal(summary.seconds,2);assert.equal(summary.timed,1);assert.equal(ctx.logProcessState(calls[1]),'\uc885\ub8cc \uae30\ub85d \uc5c6\uc74c');
 assert.equal(ctx.logDuration(null),'\uae30\ub85d \uc5c6\uc74c');assert.equal(ctx.logDuration(-1),'\uae30\ub85d \uc5c6\uc74c');
 console.log('PASS one CLI directory per call; missing times and unsent requests are not fabricated');
 assert.equal(ctx.logScope({stage:'03-graph',step:'DG03'},2),true);assert.equal(ctx.logScope({stage:'03-graph',step:'DG03'},3),false);
 assert.equal(ctx.logScope({stage:'03-graph',step:'EA01'},3),true);assert.equal(ctx.logScope({stage:'review',step:'EA15'},5),false);
 assert.equal(ctx.logScope({stage:'viewer',role:'human-interface-check',step:'EA15-UI'},5),false);
 assert.equal(ctx.logScope({stage:'viewer',role:'human-interface-check',step:'EA15-UI'},7),true);
 assert.equal(ctx.logScope({stage:'02-calculation',phase:'ARTIFACT',path:'00-data-preparation/input.json'},0),true);
 console.log('PASS graph build, perturbation, preparation, human log scopes stay distinct');
 const ordering=[{elapsed_seconds:10,sequence:1},{elapsed_seconds:null,sequence:2},{elapsed_seconds:2,sequence:3},{sequence:4}];
 assert.equal(ctx.sortedLogEvents(ordering,'elapsed_seconds',true).map(x=>x.sequence).join(','),'3,1,2,4');
 assert.equal(ctx.sortedLogEvents(ordering,'elapsed_seconds',false).map(x=>x.sequence).join(','),'1,3,2,4');
 assert.equal(ctx.logTime('2026-09-08T14:47:04.997Z'),'2026-09-08 23:47:04.997');
 console.log('PASS numeric sorting keeps absent durations last and UTC is displayed as Korean time');
 assert.equal(ctx.logLlmBoundary({function:'finarch.providers.cli.run_process',phase:'START'}),'LLM \uc2e4\ud589 \uc2dc\uc791');
 assert.equal(ctx.logLlmBoundary({function:'finarch.providers.cli.run_process',phase:'END',status:'FAIL'}),'LLM \uc2e4\ud589 \uc885\ub8cc');
 assert.equal(ctx.logLlmBoundary({phase:'ARTIFACT',path:'05-text/A/audit/02-raw-response.json'}),'LLM \uc6d0\uc751\ub2f5 \uc800\uc7a5');
 assert.equal(ctx.logLlmBoundary({phase:'START',function:'dtt.audit',kind:'llm'}),null);
 assert.equal(ctx.logLlmBoundary({phase:'ARTIFACT',path:'05-text/A/audit/02-raw-response/cli-execution.json'}),null);
 assert.equal(ctx.logProcessor({function:'finarch.providers.cli.run_process',phase:'START',kind:'python'}),'LLM');
 assert.equal(ctx.logProcessor({function:'dag.build',phase:'END',kind:'python'}),'Python');
 assert.equal(ctx.logProcessor({phase:'ARTIFACT',path:'03-graph/input.json'}),null);
 console.log('PASS LLM boundaries identify actual process and raw-response records, not wrapper events');
 const first={path:'/runs/current/case',artifacts:{'replay-source.json':{source_case:'/runs/old/case',model_calls:0}}};
 const old={path:'/runs/old/case',artifacts:{'02-calculation/01-generate-code/03-LLM-call/02-start.json':{role:'pot.author'}}};
 let fetches=0;const history=await ctx.loadPotLogHistory(first,async name=>{assert.equal(name,'old');fetches++;return {runs:[old]};});
 assert.equal(fetches,1);assert.equal(history.length,1);assert.equal(ctx.logCalls(first).length,0);assert.equal(ctx.logCalls(history[0].run).length,1);
 console.log('PASS inherited POT call is separate from current execution count');
 old.artifacts['replay-source.json']={source_case:'/runs/current/case'};
 await assert.rejects(ctx.loadPotLogHistory(first,async()=>({runs:[old]})),/\uc21c\ud658/);
 first.artifacts['replay-source.json'].source_case='/elsewhere/old/case';
 await assert.rejects(ctx.loadPotLogHistory(first,async()=>{throw Error('must not fetch');}),/\uac19\uc740 \ubb38\ud56d/);
 first.artifacts['replay-source.json'].source_case='/runs/old/case';
 await assert.rejects(ctx.loadPotLogHistory(first,async()=>({runs:[]})),/\ucc3e\uc9c0 \ubabb/);
 console.log('PASS invalid, cyclic, and missing history links report a limitation');
 const novel={path:'/runs/current/case',artifacts:{'events.jsonl':[
  {sequence:1,stage:'03-graph',step:'D01-compile',role:'new.graph.role',phase:'ARTIFACT',path:'03-graph/new/01-input/cli-start.json'},
  {sequence:2,stage:'new-stage',role:'unregistered-display-role',kind:'python',phase:'START'},
 ].map(JSON.stringify).join('\n'),'03-graph/new/01-input/cli-start.json':{role:'new.graph.role'}}};
 const inventory=ctx.logInventory(novel);assert.equal(inventory.events.length,2);assert.equal(inventory.calls.length,1);
 assert.equal(inventory.calls[0].step,'D01-compile');assert.equal(ctx.logScope(inventory.calls[0],2),true);
 assert.equal(inventory.groups.reduce((n,g)=>n+g.events,0),2);assert.equal(inventory.unscoped.length,1);
 assert.equal(ctx.logScope(inventory.unscoped[0],7),true);
 console.log('PASS original stage metadata drives call attribution and unknown records remain in all events');
 console.log('8 checks passed; no LLM calls');
}
module.exports=ctx;
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
