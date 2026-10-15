import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { validateRQ1Materials, readRQ1Materials, RQ1_FILES } from '../rq1-reader.mjs';
import { rq1Selection, rq1Share } from '../../../../../viewer/experiments/rq1-materials.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';

const fail = message => Error(message);
function fixture() {
  const privateItems = new Map(), requests = new Map(), records = [];
  const row = (id, metric, x, y, quadrant, classification, reason = 'PLACED', status = 'VALID', condition = 'guided') => {
    const variant = metric === 'OV' ? 'IC_VALUE_01_BEFORE' : 'IC_SOURCE_A_ONLY';
    const item = `${id}:${variant}`, trial = `${id}:${variant}:${condition}`;
    const value = { metric, model: 'luna', source: 'dataset-1', prompt_condition: condition, reasoning: 'off', variant,
      item_id: item, original_item_id: id, case: id, trial_id: trial, original_trial_id: `${id}:original:${condition}`,
      response_id: `luna:${trial}`, x, y, quadrant, classification, placement_status: reason,
      response_status: status, observation_status: y === null ? reason : 'OBSERVED' };
    requests.set(value.response_id, { ...value });
    requests.set(`luna:${value.original_trial_id}`, { item_id: id, case: id, variant: 'ORIGINAL', prompt_condition: condition, reasoning: 'off' });
    privateItems.set(id, { source: 'dataset-1' }); privateItems.set(item, { matched_value_parent_ids: [`${id}:IC_VALUE_01_BEFORE`] });
    records.push(value); return value;
  };
  const v1 = row('case-1', 'OV', true, true, 1, 'CONFLICT');
  const v2 = row('case-2', 'OV', false, true, 2, 'CONFLICT');
  const v3 = row('case-3', 'OV', true, null, null, null, 'RESPONSE_UNAVAILABLE', 'INVALID_RESPONSE');
  const v4 = row('case-4', 'OV', null, true, null, 'CONFLICT', 'ORIGINAL_UNASSESSED');
  const vu = row('case-5', 'OV', true, null, null, null, 'CLASSIFICATION_NOT_REQUESTED', 'VALID', 'unguided');
  const s1 = row('case-1', 'OVS_all', true, false, 4, 'ANSWERABLE');
  const s2 = row('case-2', 'OVS_all', false, true, 2, 'CONFLICT');
  const s4 = row('case-4', 'OVS_all', null, true, null, 'CONFLICT', 'ORIGINAL_UNASSESSED');
  const su = row('case-5', 'OVS_all', true, null, null, null, 'CLASSIFICATION_NOT_REQUESTED', 'VALID', 'unguided');
  records.push({ ...s1, metric: 'OVS', value_parent_item_id: v1.item_id });
  const selection = [[s1, true, v1], [s2, false, v2], [s4, null, v4], [su, null, vu]].map(([source, eligible, parent]) =>
    ({ ...source, metric: undefined, eligible, parent_item_id: parent.item_id }));
  const group = (metric, ids, q, unplaced, numerator, classes, reasons = {}, cohort, condition = 'guided') => {
    const N = ids.length;
    return { metric, model: 'luna', source: 'dataset-1', prompt_condition: condition, reasoning: 'off',
      variant: metric === 'OV' ? 'IC_VALUE_01_BEFORE' : 'IC_SOURCE_A_ONLY', N, denominator: N, numerator,
      fraction: `${numerator}/${N}`, rate: N ? numerator/N : null, denominator_symbol: metric === 'OVS' ? 'm' : 'N',
      quadrants: Object.fromEntries(q.map((count, index) => [String(index + 1), { count, denominator: N, fraction: `${count}/${N}`, ratio_of_planned: N ? count/N : null }])),
      unplaced, unplaced_reasons: reasons, classifications: classes, answerable_count: classes.ANSWERABLE || 0,
      answerable_rate: N ? (classes.ANSWERABLE || 0)/N : null, response_ids: ids.map(row => row.response_id), ...(cohort ? { cohort } : {}) };
  };
  const groups = [
    group('OV', [v1,v2,v3,v4], [1,1,0,0], 2, 1, {CONFLICT:3}, {RESPONSE_UNAVAILABLE:1, ORIGINAL_UNASSESSED:1}),
    group('OV', [vu], [0,0,0,0], 1, 0, {}, {CLASSIFICATION_NOT_REQUESTED:1}, undefined, 'unguided'),
    group('OVS_all', [s1,s2,s4], [0,1,0,1], 1, 2, {ANSWERABLE:1, CONFLICT:2}, {ORIGINAL_UNASSESSED:1}),
    group('OVS_all', [su], [0,0,0,0], 1, 0, {}, {CLASSIFICATION_NOT_REQUESTED:1}, undefined, 'unguided'),
    group('OVS', [s1], [0,0,0,1], 0, 0, {ANSWERABLE:1}, {}, {planned_source_responses:3, eligible:1, excluded:1, undetermined:1}),
    group('OVS', [], [0,0,0,0], 0, 0, {}, {}, {planned_source_responses:1, eligible:0, excluded:0, undetermined:1}, 'unguided')
  ];
  const summary = { schema_version:'RQ1MaterialsV1', status:'AVAILABLE', groups,
    basis:'SUBMITTED_CLASSIFICATION_NOT_SEMANTIC_SUCCESS', original_axis:'SAVED_NUMERIC_MATCH', inverse_reconstruction:{status:'TBD',result:null} };
  const read = () => validateRQ1Materials(summary, records, selection, requests, privateItems, fail);
  return { summary, records, selection, requests, privateItems, read };
}

test('planned denominator includes format failures and unassessed originals; submissions are not semantic judgments', () => {
  const data = fixture().read(), ov = data.groups.find(g => g.metric === 'OV' && g.prompt_condition === 'guided');
  assert.equal(ov.fraction, '1/4'); assert.equal(ov.unplaced, 2);
  assert.deepEqual(ov.unplaced_response_statuses, {INVALID_RESPONSE:1, VALID:1});
  const all = data.groups.find(g => g.metric === 'OVS_all' && g.prompt_condition === 'guided');
  assert.equal(all.fraction, '2/3'); assert.equal(all.quadrants['1'].count, 0);
  assert.equal(all.answerable_count, 1);
});
test('Unguided classification null remains unknown; empty OVS retains undetermined cohort and null rate', () => {
  const data = fixture().read(), unguided = data.groups.find(g => g.metric === 'OV' && g.prompt_condition === 'unguided');
  assert.equal(unguided.unplaced_observations.CLASSIFICATION_NOT_REQUESTED, 1);
  const empty = data.groups.find(g => g.metric === 'OVS' && g.prompt_condition === 'unguided');
  assert.equal(empty.denominator, 0); assert.equal(empty.rate, null); assert.equal(empty.cohort.undetermined, 1);
  assert.equal(rq1Share(0, 0, null), '0/0 · 계산 불가');
});
test('OVS follows its saved parent, never a neighboring value variant or pooled before/after cohort', () => {
  const f = fixture(); f.selection[0].parent_item_id = 'case-2:IC_VALUE_01_BEFORE';
  assert.throws(f.read, /부모 연결/);
});
test('missing planned responses and shrinking the denominator are rejected', () => {
  const f = fixture(); f.records.splice(2, 1); assert.throws(f.read, /계획 요청/);
  const changed = fixture(); changed.summary.groups[0].denominator = 2; assert.throws(changed.read, /전체 분모/);
});
test('wrong rates, missing cohorts and semantic-success substitution are rejected', () => {
  const rate = fixture(); rate.summary.groups[0].quadrants['1'].ratio_of_planned = 0.5; assert.throws(rate.read, /사분면 분모/);
  const cohort = fixture(); cohort.summary.groups[4].cohort.undetermined = 0; assert.throws(cohort.read, /OVS의 m/);
  const basis = fixture(); basis.summary.basis = 'ADAPTATION_SUCCESS'; assert.throws(basis.read, /집계 계약/);
});
test('RQ1 selection keeps source/model/variant cohorts separate and preserves TBD', () => {
  const data = fixture().read();
  assert.equal(rq1Selection(data,{rq1_metric:'OVS'}).groups.length, 2);
  assert.equal(rq1Selection(data,{rq1_metric:'inverse'}).metric, 'inverse');
  assert.equal(rq1Share(1,4), '1/4 · 25.0%');
});
test('live reader rejects a source changed after Python aggregation', async t => {
  const root = await mkdtemp(path.join(os.tmpdir(),'finarch-rq1-hash-')); t.after(()=>rm(root,{recursive:true,force:true}));
  const model = 'luna', source = '00_input/public.jsonl';
  const expected = createHash('sha256').update('old').digest('hex'); await writeFile(path.join(root,'source.txt'),'new');
  const summary = {run_id:'run',records_path:RQ1_FILES[1],selection_path:RQ1_FILES[2],source_hashes:Object.fromEntries(
    [source,'00_input/private.jsonl','01_evaluation/04_validation/numeric-comparisons.jsonl','manifest.jsonl'].map(name=>[name,expected]))};
  await assert.rejects(readRQ1Materials({root,id:'run',config:{models:[{key:model}]}},{
    readJSON:async()=>summary, readText:async()=>'', safePath:async(_,relative)=>{
      if(relative === 'results/results.jsonl'){const e=Error();e.code='ENOENT';throw e;} return path.join(root,'source.txt');
    }, artifactPaths:()=>({input:'00_input',request:()=> 'manifest.jsonl', results:()=> 'results'}),fail
  }), /원자료가 집계 후 갱신/);
});
test('offline route preserves every saved RQ1 count, cohort and unjudged state', async () => {
  const rq1Materials = fixture().read(), data = {id:'run',rq1Materials};
  const bundle = {version:1,run:{id:'run'},chunks:{index:gzipSync(JSON.stringify(data)).toString('base64')}};
  assert.deepEqual(await createOfflineStore(bundle).request('/api/runs/run/rq1-materials'),rq1Materials);
});
