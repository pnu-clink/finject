import test from 'node:test';
import assert from 'node:assert/strict';
import {finalizationStatus} from '../finalization.mjs';
import {buildProgress} from '../progress.mjs';
const summary={status:'CLASSIFIED',schema_version:'ResponseOutcomeV1',scopes:{variants:{total:7},all:{total:8}}};
const root={analysis:{status:'COMPLETE',stage:'PYTHON_OUTCOMES',a04_status:'SKIPPED_BY_USER',semantic_response_outcomes:{path:'02_analysis/05_outcomes/summary.json',schema_version:'ResponseOutcomeV1',counts:{total:7}}},full_pipeline:{status:'COMPLETE'}};
const research={status:'COLLECTED',requests:2,valid:2};
const policy={skip_a04:true};
test('completion requires policy, collected A03, actual postprocessing and verified output',()=>{
 assert.equal(finalizationStatus(null,root,research,summary,null,true),null);
 assert.equal(finalizationStatus(policy,root,research,summary,null,true).status,'COMPLETE');
 for(const [r,a,v] of [[{},research,true],[root,null,true],[root,{...research,valid:1},true],[root,research,false]]) assert.notEqual(finalizationStatus(policy,r,a,summary,null,v).status,'COMPLETE');
 const waiting={analysis:{status:'HOLD_SEMANTIC_SCOPE',updated_at:'2026-10-05'},full_pipeline:{status:'HOLD_SEMANTIC_SCOPE'}};
 assert.equal(finalizationStatus(policy,waiting,null,summary,{status:'WAIT_EVALUATION_AND_TRANSFER',updated_at:'2026-10-06'},true).status,'WAIT_EVALUATION_AND_TRANSFER');
});
test('skipped A04 retains historical errors without remaining work, no-policy remains failed',()=>{
 const args={id:'test',config:{},rootState:{full_pipeline:{status:'FAILED',stage:'A04',error:'old'}},stages:{'04_quadrant':{status:'FAILED',requests:2,completed:1,valid:0,error:'old'}},selectedStage:'04_quadrant'};
 const f=finalizationStatus(policy,root,research,summary,null,true);
 const result=buildProgress({...args,finalization:f});
 assert.equal(result.status,'SKIPPED_BY_USER');assert.equal(result.counts.remaining,null);assert.ok(result.issues.every(x=>x.historical));assert.equal(result.records.failed,1);
 assert.equal(buildProgress(args).status,'PROCESSING_FAILED');
 assert.equal(buildProgress({...args,selectedStage:undefined,finalization:f}).stage,'05_outcomes');
});
