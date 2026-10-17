import test from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { savedGroundingOutcome, validateGroundingPairs, readGroundingPairs } from '../grounding-reader.mjs';
import { groundingSummary, groundingPage } from '../../../../../viewer/experiments/grounding-model.mjs';
import { groundingSelection, groundingShare, groundingDrilldown } from '../../../../../viewer/experiments/grounding-view.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const fail = (message, status) => Object.assign(Error(message), { status });
const judgment = (a, d, review_status = 'COMPLETED', adaptation_success = null) => ({ review_status, adaptation_success,
  abstention_reason_validity: { verdict: a }, decision_grounding: { verdict: d } });
function fixture() {
  const privateItems = new Map(), rows = [], responseIdsByTrial = new Map(), analysisResponsesByTrial = new Map(), byResponse = new Map(), pairs = [];
  const examples = [
    ['numeric-supported', true, 'SUPPORTED', 'NOT_APPLICABLE', 'COMPLETED', true, 1, 'VALID', '12'],
    ['null-supported', false, 'SUPPORTED', 'SUPPORTED', 'COMPLETED', true, 2, 'VALID', null],
    ['null-unsupported-undetermined', false, 'UNDETERMINED', 'UNSUPPORTED', 'COMPLETED', false, 3, 'VALID', null],
    ['test-0008', true, 'UNSUPPORTED', 'UNSUPPORTED', 'COMPLETED', false, 4, 'VALID', null],
    ['numeric-unsupported', true, 'UNSUPPORTED', 'NOT_APPLICABLE', 'COMPLETED', false, 4, 'VALID', '0'],
    ['null-undetermined', true, 'UNDETERMINED', 'UNDETERMINED', 'COMPLETED', null, null, 'VALID', null],
    ['source-missing', true, null, null, 'SOURCE_MISSING', null, null, 'VALID', '12'],
    ['not-reviewable', true, null, null, 'NOT_REVIEWABLE', null, null, 'INVALID_RESPONSE', null],
    ['review-failed', true, null, null, 'REVIEW_FAILED', null, null, 'VALID', null],
    ['not-reviewed', true, null, null, 'NOT_REVIEWED', null, null, 'VALID', '12'],
    ['original-unassessed', null, 'SUPPORTED', 'NOT_APPLICABLE', 'COMPLETED', true, null, 'VALID', '12']
  ];
  for (const [id, x, d, a, status, y, q, variantStatus, answer] of examples) {
    const originalItem = `${id}:original`, item = `${id}:EA_02`, originalTrial = `${id}:original:off`, trial = `${id}:variant:off`;
    privateItems.set(originalItem, { generated_metadata: { provenance: { dataset: 'FinQA' } } }); privateItems.set(item, { original_item_id: originalItem });
    rows.push({ model:'luna', trial_id:originalTrial, item_id:originalItem, case:id, variant:'ORIGINAL', prompt_condition:'unguided', reasoning:'off', status:'VALID',
      checks: x === null ? {} : { numeric_comparison: { matches:x } } });
    rows.push({ model:'luna', trial_id:trial, item_id:item, case:id, variant:'EA_02', prompt_condition:'unguided', reasoning:'off', status:variantStatus });
    responseIdsByTrial.set(`luna:${trial}`, `luna:${trial}`); responseIdsByTrial.set(`luna:${originalTrial}`, `luna:${originalTrial}`);
    analysisResponsesByTrial.set(`luna:${trial}`, { response:{answer, classification:null} });
    const review = status === 'NOT_REVIEWED' ? null : { ...judgment(a,d,status,y), assessment_id:`review-${id}` };
    if (review) byResponse.set(`luna:${trial}`, review);
    pairs.push({ pair_id:id, model:'luna', source_type:'FinQA', case:id, variant:'EA_02', prompt_condition:'unguided', reasoning:'off', answerability:'NOT_ESTABLISHED',
      original_item_id:originalItem, variant_item_id:item, original_trial_id:originalTrial, variant_trial_id:trial, original_status:'VALID', variant_status:variantStatus,
      original_correctness:x, variant_appropriateness:y, quadrant:q, assessment_id:review?.assessment_id ?? null, assessment_review_status:review?.review_status ?? null,
      variant_answer_shape:variantStatus !== 'VALID' ? 'UNAVAILABLE' : answer === null ? 'NULL' : 'NUMERIC', original_result_path:`original/${id}.json`, variant_result_path:`variant/${id}.json` });
  }
  const type = { model:'luna', source_type:'FinQA', variant:'EA_02', prompt_condition:'unguided', reasoning:'off', answerability:'NOT_ESTABLISHED',
    planned_pairs:11, placed_pairs:5, unplaced_pairs:6, quadrants:{1:{count:1},2:{count:1},3:{count:1},4:{count:2}} };
  const summary = { schema_version:'RQ1PairOutcomeV2', run_id:'20261003-exp-999', types:[type], overall:{planned_pairs:11,placed_pairs:5,unplaced_pairs:6},
    original_axis_scope:'RECORDED_SIGNED_NUMERIC_MATCH_UNITS_NOT_SEPARATELY_SCORED' };
  const snap = { id:summary.run_id, rows, privateItems, responseIdsByTrial, analysisResponsesByTrial, responseAssessments:{byResponse,coverage:{review_status:{COMPLETED:7}}} };
  return {summary,pairs,snap,read:()=>validateGroundingPairs(summary,pairs,snap,fail)};
}

test('numeric NOT_APPLICABLE is neutral; null responses require both verdicts and any UNSUPPORTED is decisive', () => {
  assert.equal(savedGroundingOutcome(judgment('NOT_APPLICABLE','SUPPORTED'), {answer:'0',classification:null}), true);
  assert.equal(savedGroundingOutcome(judgment('NOT_APPLICABLE','UNSUPPORTED'), {answer:'0'}), false);
  assert.equal(savedGroundingOutcome(judgment('SUPPORTED','SUPPORTED'), {answer:null,classification:null}), true);
  assert.equal(savedGroundingOutcome(judgment('UNSUPPORTED','UNDETERMINED'), {answer:null}), false);
  assert.equal(savedGroundingOutcome(judgment('UNDETERMINED','UNSUPPORTED'), {answer:null}), false);
  assert.equal(savedGroundingOutcome(judgment('SUPPORTED','UNDETERMINED'), {answer:null}), null);
  assert.equal(savedGroundingOutcome(judgment('SUPPORTED','SUPPORTED','REVIEW_FAILED'), {answer:null}), null);
});
test('Unguided null classification is placed; real assessment failures and missing originals stay separate', () => {
  const data = fixture().read(), sample = data.pairs.find(row=>row.case==='test-0008');
  assert.equal(sample.quadrant,4); assert.equal(sample.adaptation_success,false); assert.equal(sample.review_status,'COMPLETED');
  const summary = groundingSummary(data).groups[0];
  assert.equal(summary.planned_pairs,11); assert.equal(summary.placed_pairs,5); assert.equal(summary.unplaced_pairs,6);
  assert.deepEqual(summary.unplaced_reasons, {UNDETERMINED:1,SOURCE_MISSING:1,VARIANT_UNAVAILABLE:1,REVIEW_FAILED:1,NOT_REVIEWED:1,ORIGINAL_NUMERIC_UNASSESSED:1});
  assert.equal(summary.review_status.NOT_REVIEWABLE,1);
  assert.equal(data.pairs.find(row=>row.case==='not-reviewable').abstention_reason_validity,'UNREVIEWED');
  assert.equal(data.pairs.some(row=>row.decision_grounding==='UNRESOLVED'),false);
});
test('NOT_APPLICABLE remains visible and filters keep the planned denominator and both base placement counts', () => {
  const data=fixture().read(), group=groundingSummary(data,{abstention:'NOT_APPLICABLE'}).groups[0];
  assert.equal(group.filtered_pairs,3); assert.equal(group.planned_pairs,11); assert.equal(group.placed_pairs,5); assert.equal(group.filtered_unplaced,1);
  assert.deepEqual(group.quadrants[1],{count:1,denominator:11,rate:1/11});
  assert.equal(group.abstention_reason_validity.NOT_APPLICABLE,3);
  assert.equal(groundingShare(0,0),'0/0 · 계산 불가');
  const empty=groundingSummary({metadata:{},pairs:[]}); assert.deepEqual(empty.groups,[]);
});
test('wrong original, prompt, source, saved combined result or shrinking N is rejected', () => {
  let f=fixture(); f.snap.privateItems.get(f.pairs[0].variant_item_id).original_item_id='another-parent'; assert.throws(f.read,/\uc2e4\uc81c \ubd80\ubaa8/);
  f=fixture(); f.snap.rows[0].prompt_condition='guided'; assert.throws(f.read,/\ub2e4\ub978 \uc6d0\ubcf8 \ub610\ub294 \uc870\uac74/);
  f=fixture(); f.pairs[0].source_type='TAT-QA'; assert.throws(f.read,/\ub370\uc774\ud130 \ucd9c\ucc98/);
  f=fixture(); f.snap.responseAssessments.byResponse.get('luna:test-0008:variant:off').adaptation_success=true; assert.throws(f.read,/\uacb0\ud569 \uaddc\uce59/);
  f=fixture(); f.summary.types[0].planned_pairs=5; assert.throws(f.read,/\uc804\uccb4 \ubd84\ubaa8/);
  f=fixture(); f.pairs.pop(); assert.throws(f.read,/\ube60\uc9c4 \uc694\uccad/);
  f=fixture(); f.pairs[3].quadrant=1; assert.throws(f.read,/\ud604\uc7ac A02 \ud310\uc815/);
});
test('list filters and pagination retain exact response IDs and a fixed denominator', () => {
  const data=fixture().read(); data.pairs=Array.from({length:45},(_,i)=>({...data.pairs[3],case:`test-${i}`,pair_id:String(i)}));
  const page=groundingPage(data,{quadrant:'4',offset:'20'}); assert.equal(page.pairs.length,20); assert.equal(page.total,45); assert.equal(page.planned_pairs,45);
  assert.equal(groundingPage(data,{case:'test-8'}).pairs[0].variant_trial_id,'test-0008:variant:off');
  assert.equal(groundingPage(data,{case:'test-8'}).planned_pairs,45);
  const end=groundingPage(data,{offset:'99'}); assert.equal(end.offset,45); assert.deepEqual(end.pairs,[]);
  for (const filters of [{quadrant:'0'},{decision:'UNRESOLVED'},{review:'VALID'},{offset:'-1'}]) assert.throws(()=>groundingPage(data,filters));
  assert.throws(()=>groundingSummary(data,{abstention:'UNRESOLVED'}),/\ud544\ud130/);
});
test('source and variant selection keep the seven types and the four condition groups separate', () => {
  const data=groundingSummary(fixture().read());
  data.groups.push({...data.groups[0],source_type:'TAT-QA',variant:'IC_SOURCE_B_ONLY',prompt_condition:'guided',reasoning:'on'});
  const selected=groundingSelection(data,{ground_model:'luna',ground_source:'TAT-QA',ground_variant:'IC_SOURCE_B_ONLY'});
  assert.equal(selected.groups.length,1); assert.equal(selected.groups[0].reasoning,'on'); assert.equal(selected.groups[0].source_type,'TAT-QA');
});
test('offline and live share every quadrant, missing status, verdict filter and paged response link', async () => {
  const data=fixture().read(), pack=value=>gzipSync(JSON.stringify(value)).toString('base64');
  const store=createOfflineStore({version:1,run:{id:data.metadata.run_id},initial_view:{tab:'grounding',ground_variant:'EA_02'},chunks:{index:pack({id:data.metadata.run_id}), 'grounding-pairs':pack(data)}});
  assert.equal(store.initialView.tab,'grounding');
  for (const filters of [{},{original:'correct'},{original:'incorrect'},{mode:'pairs',original:'correct'},{decision:'UNSUPPORTED'},{abstention:'NOT_APPLICABLE'},{review:'SOURCE_MISSING'},{mode:'pairs',quadrant:'4'},{mode:'pairs',quadrant:'unplaced'},{mode:'pairs',case:'test-0008'}]) {
    const offline=await store.request(`/api/runs/${data.metadata.run_id}/grounding-pairs?${new URLSearchParams(filters)}`);
    assert.deepEqual(offline,filters.mode==='pairs'?groundingPage(data,filters):groundingSummary(data,filters));
  }
});
test('a missing pair artifact is explicit; changed input bytes cannot silently reuse an old grounding aggregation', async t => {
  const folder=await mkdtemp(path.join(os.tmpdir(),'finarch-grounding-')); t.after(()=>rm(folder,{recursive:true,force:true}));
  const snap={id:'run',root:folder,responseAssessments:{}};
  const missing=await readGroundingPairs(snap,{readJSON:async()=>null}); assert.equal(missing.metadata.status,'NOT_PREPARED'); assert.equal(missing.metadata.assessments_available,true);
  await writeFile(path.join(folder,'input.json'),'changed');
  await assert.rejects(()=>readGroundingPairs(snap,{readJSON:async()=>({source_hashes:{'input.json':createHash('sha256').update('original').digest('hex')}}), safePath:async(root,file)=>path.join(root,file),fail}),/\uc6d0\uc790\ub8cc\uac00 pair \uc9d1\uacc4 \ud6c4 \ubc14\ub00c/);
});

test('Original filter includes unknowns only in all and keeps A02 distributions and planned N explicit', () => {
  const data=fixture().read();
  const all=groundingSummary(data,{original:'all'}).groups[0];
  const yes=groundingSummary(data,{original:'correct'}).groups[0];
  const no=groundingSummary(data,{original:'incorrect'}).groups[0];
  assert.equal(all.original_pairs,11); assert.equal(all.original_unevaluated,1);
  assert.equal(yes.original_pairs,8); assert.equal(no.original_pairs,2);
  assert.equal(yes.planned_pairs,11); assert.equal(no.planned_pairs,11);
  assert.equal(yes.filtered_placed,3); assert.equal(yes.filtered_unplaced,5);
  assert.equal(yes.quadrants[2].count,0); assert.equal(no.quadrants[1].count,0);
  assert.equal(yes.decision_grounding.UNSUPPORTED,2); assert.equal(no.decision_grounding.SUPPORTED,1);
  const page=groundingPage(data,{original:'correct'});
  assert.equal(page.planned_pairs,11); assert.equal(page.total,8);
  assert.ok(page.pairs.every(row=>row.original_correctness===true));
  assert.throws(()=>groundingSummary(data,{original:'unknown'}),/\ud544\ud130/);
});

test('verdict drilldown selects the exact condition and clears unrelated verdict intersections', () => {
  const group={model:'luna',source_type:'TAT-QA',variant:'EA_01',prompt_condition:'unguided',reasoning:'off'};
  const patch=groundingDrilldown(group,'ground_abstention','SUPPORTED','correct');
  assert.equal(patch.ground_view,'list'); assert.equal(patch.ground_prompt,'unguided'); assert.equal(patch.ground_reasoning,'off');
  assert.equal(patch.ground_variant,'EA_01'); assert.equal(patch.ground_source,'TAT-QA');
  assert.equal(patch.ground_original,'correct'); assert.equal(patch.ground_abstention,'SUPPORTED');
  assert.equal(patch.ground_decision,''); assert.equal(patch.ground_review,'');
});
