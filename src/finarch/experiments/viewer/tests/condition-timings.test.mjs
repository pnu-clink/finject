import test from 'node:test';
import assert from 'node:assert/strict';
import { caseConditionRows, conditionTimings, recordedElapsed } from '../../../../../viewer/experiments/model.mjs';

test('all four pairs keep their own per-model times regardless of the selected pair', () => {
  const rows = [], records = {};
  for (const model of ['a', 'b']) for (const prompt of ['P0', 'P1']) for (const reasoning of ['off', 'on']) {
    const trial_id = `${model}-${prompt}-${reasoning}`;
    rows.push({ case: 'case-1', variant: 'EA_02', model, prompt_condition: prompt, reasoning, trial_id, status: 'VALID' });
    records[`${model}:${trial_id}`] = { elapsed_seconds: rows.length / 10 };
  }
  const selection = { caseId: 'case-1', variant: 'EA_02', prompt: 'P1', reasoning: 'on', rows: [{ model: 'a' }, { model: 'b' }] };
  const choices = conditionTimings(caseConditionRows({ rows }, selection), records);
  assert.deepEqual(choices.map(c => [c.prompt, c.reasoning]), [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']]);
  assert.deepEqual(choices.map(c => c.models.map(m => m.elapsed_seconds)), [[0.1, 0.5], [0.2, 0.6], [0.3, 0.7], [0.4, 0.8]]);
  const oneModel = conditionTimings(caseConditionRows({ rows }, { ...selection, rows: [{ model: 'b' }] }), records);
  assert.ok(oneModel.every(c => c.models.length === 1 && c.models[0].model === 'b'));
});

test('unplanned original P1 and missing times stay distinct from zero seconds', () => {
  const row = { case: 'case-1', variant: 'ORIGINAL', prompt_condition: 'P0', reasoning: 'off', model: 'a', trial_id: 'one', status: 'VALID' };
  const selection = { caseId: 'case-1', variant: 'ORIGINAL', rows: [{ model: 'a', row }] };
  const choices = conditionTimings(caseConditionRows({ rows: [row] }, selection), { 'a:one': { elapsed_seconds: 0 } });
  assert.equal(choices[0].models[0].elapsed_seconds, 0);
  assert.equal(choices[1].available, false); assert.equal(choices[1].models[0].elapsed_seconds, null);
  assert.equal(choices[1].models[0].status, 'NOT_PLANNED');
  assert.equal(choices[2].available, false); assert.equal(choices[3].available, false);
  assert.equal(conditionTimings(caseConditionRows({ rows: [row] }, selection), { 'a:one': { timing_error: true } })[0].models[0].timing_error, true);
});

test('duration uses the saved result, with a call-record fallback but no invented or coerced time', () => {
  assert.equal(recordedElapsed({ elapsed_seconds: 2.5 }, { result: { elapsed_seconds: 8 } }), 2.5);
  assert.equal(recordedElapsed(null, { result: { elapsed_seconds: 8 } }), 8);
  assert.equal(recordedElapsed({ elapsed_seconds: 0 }), 0);
  for (const value of [-1, NaN, Infinity, '2.5', false, undefined]) assert.equal(recordedElapsed({ elapsed_seconds: value }), null);
});
