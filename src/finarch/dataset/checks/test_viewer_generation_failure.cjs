// Failed generation without a successful pointer must remain visible.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('viewer/dataset/index.html','utf8');
new Function(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const ctx=vm.createContext({eventOf:(r,k)=>r.run.artifacts[k],realizationStage:r=>`05-text/${r.label}`});
vm.runInContext(html.slice(html.indexOf('function plainFailure('),html.indexOf('// [VF03]')),ctx);
let r={label:'EA_02',run:{artifacts:{
 '05-text/EA_02/01-generate-text/typed-v1/03-result/failure.json':{reason:'CLI_PROCESS_FAILED'},
 '05-text/EA_02/01-generate-text/typed-v1/realize/02-raw-response/cli-execution.json':{stdout:"You've hit your usage limit",ended_at:'2026-09-09'}
}}};
assert.match(ctx.realizationFailure(r).reason,/\uc0ac\uc6a9\ub7c9 \ud55c\ub3c4/);
r.run.artifacts['05-text/EA_02/04-final-observation.json']={context:'success'};
r.run.artifacts['05-text/EA_02/03-result/validation.json']={status:'PASS'};
assert.equal(ctx.realizationFailure(r),null);
r={label:'IC_VALUE_01_AFTER',run:{artifacts:{
 '05-text/IC_VALUE_01_AFTER/01-generate-text/typed-v1/03-result/failure.json':{reason:'PAIR_SOURCE_GENERATION_FAILED'},
 '05-text/OTHER/01-generate-text/later/03-result/failure.json':{reason:'wrong variant'}
}}};
assert.match(ctx.realizationFailure(r).reason,/\uba3c\uc800 \uc0dd\uc131/);
console.log('Generation revision, quota, dependency, foreign variant and later success checks PASS');
