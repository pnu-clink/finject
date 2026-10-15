import test from 'node:test';
import assert from 'node:assert/strict';
import { VARIANTS, caseHeatmap, caseHeatmapCategory, heatmapNumericAnswer } from '../../../../../viewer/experiments/model.mjs';

const variant = { variant: 'EA_02', status: 'VALID' };
const original = matches => ({ variant: 'ORIGINAL', status: 'VALID', checks: { numeric_comparison: { matches } } });

function numericCell(answer, gold = '20', responseFields = {}, status = 'VALID') {
  const row = { ...variant, case: 'c1', model: 'a', trial_id: 'one', prompt_condition: 'P0', reasoning: 'on', status, response: { answer, ...responseFields } };
  const selection = { caseId: 'c1', rows: [{ model: 'a' }], items: [{ variant: 'ORIGINAL', reference: { reference_answer: gold } }] };
  return caseHeatmap({ rows: [row] }, selection).models[0].conditions[1].cells[7];
}

test('actual numbers compare against the private original reference without changing variant verdicts', () => {
  const different = numericCell(21);
  assert.equal(different.answer_text, '21');
  assert.equal(different.reference_matches, false);
  assert.equal(different.category, 'numeric');
  assert.equal(different.numeric_comparison, null);
  assert.equal(numericCell(20).reference_matches, true);
  assert.equal(numericCell(21, 'not recorded').reference_matches, null);
  assert.equal(numericCell(21, null).reference_matches, null);
  assert.equal(numericCell(null).answer_text, null);
  assert.equal(numericCell(null).reference_matches, null);
  assert.equal(numericCell(0, '1').answer_text, '0');
  assert.equal(numericCell(0, '1').reference_matches, false);
  assert.equal(numericCell(21, '20', {}, 'INVALID_RESPONSE').answer_text, null);
  assert.equal(numericCell(21, '20', {}, 'OUTPUT_TRUNCATED').reference_matches, null);
});

test('reference equality preserves decimals, zero and large numeric strings without coercion', () => {
  for (const [answer, gold] of [['20.00', '2e1'], ['0.10', '.1'], ['-0.000', '0'], ['1e-100', '10e-101']]) {
    assert.equal(numericCell(answer, gold).reference_matches, true);
  }
  assert.equal(numericCell('9007199254740993', '9007199254740992').reference_matches, false);
  assert.equal(numericCell('0.10000000000000001', '0.1').reference_matches, false);
  assert.equal(numericCell('20 or 21').reference_matches, null);
});

test('legacy magnitudes use their sign while numeric answers keep their own sign and scale is not multiplied', () => {
  const legacy = { status: 'answered', answer_meta: { negative: true, scale: 'million' } };
  assert.equal(numericCell('20', '-20', legacy).answer_text, '-20');
  assert.equal(numericCell('20', '-20', legacy).reference_matches, true);
  assert.equal(numericCell(-20, '-20', { answer_meta: { negative: true, scale: 'million' } }).reference_matches, true);
  assert.equal(numericCell(20, '20', { answer_meta: { negative: false, scale: 'million' } }).reference_matches, true);
  assert.equal(heatmapNumericAnswer({ answer: null }), null);
});

test('only assessed, valid originals use correctness colors; variants never inherit gold or semantic judgments', () => {
  assert.equal(caseHeatmapCategory(original(true)), 'match');
  assert.equal(caseHeatmapCategory(original(false)), 'mismatch');
  assert.equal(caseHeatmapCategory(original(undefined)), 'unassessed');
  assert.equal(caseHeatmapCategory({ ...original(true), status: 'INVALID_RESPONSE' }), 'invalid');
  assert.equal(caseHeatmapCategory({ ...original(false), status: 'OUTPUT_TRUNCATED' }), 'truncated');
  for (const matches of [true, false]) {
    assert.equal(caseHeatmapCategory({ ...original(matches), ...variant, response: { answer: 0 }, semantic: { appropriate: matches } }), 'numeric');
  }
});

test('null, zero, missing response, absent answer and mixed text remain distinct', () => {
  const classify = response => caseHeatmapCategory(variant, { response });
  assert.equal(classify({ answer: null }), 'null');
  for (const answer of [0, -2, '0', '-1.2', '+.5', '2e3']) assert.equal(classify({ answer }), 'numeric');
  for (const answer of ['12 or 13', 'No answer', '', false, [1, 2], { value: 1 }]) assert.equal(classify({ answer }), 'other');
  assert.equal(classify({ explanation: 'No answer field.' }), 'other');
  assert.equal(classify(null), 'missing');
  assert.equal(caseHeatmapCategory({ ...variant, status: 'OUTPUT_TRUNCATED' }, { response: null }), 'truncated');
  assert.equal(caseHeatmapCategory({ ...variant, status: 'NOT_RUN' }), 'pending');
  assert.equal(caseHeatmapCategory(variant, { read_error: true }), 'read_error');
  assert.equal(caseHeatmapCategory(undefined), 'not_planned');
});

test('every model has four condition rows and all eight columns regardless of detail filters', () => {
  const rows = [
    { ...original(true), case: 'c1', model: 'a', trial_id: 'a0', prompt_condition: 'P0', reasoning: 'off' },
    { ...variant, case: 'c1', model: 'a', trial_id: 'a7', prompt_condition: 'P1', reasoning: 'on' },
    { ...variant, case: 'c1', model: 'b', trial_id: 'b7', prompt_condition: 'P1', reasoning: 'on' },
    { ...variant, case: 'other', model: 'a', trial_id: 'foreign', prompt_condition: 'P0', reasoning: 'off', response: { answer: 1 } }
  ];
  const selection = { caseId: 'c1', variant: 'EA_02', prompt: 'P1', reasoning: 'on', rows: [{ model: 'a' }, { model: 'b' }] };
  const records = { 'a:a7': { response: { answer: null } }, 'b:b7': { response: { answer: 0 } } };
  const heatmap = caseHeatmap({ rows }, selection, records);
  assert.deepEqual(heatmap.variants, VARIANTS);
  for (const model of heatmap.models) {
    assert.deepEqual(model.conditions.map(c => [c.prompt, c.reasoning]), [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']]);
    assert.ok(model.conditions.every(c => c.cells.length === 8));
    for (const condition of model.conditions.slice(2)) {
      assert.equal(condition.cells[0].category, 'not_planned');
      assert.equal(condition.cells[0].selectable, false);
    }
  }
  assert.equal(heatmap.models[0].conditions[0].cells[0].category, 'match');
  assert.equal(heatmap.models[0].conditions[0].cells[7].category, 'not_planned');
  assert.equal(heatmap.models[0].conditions[3].cells[7].category, 'null');
  assert.equal(heatmap.models[1].conditions[3].cells[7].category, 'numeric');
  assert.deepEqual(caseHeatmap({ rows }, { ...selection, rows: [{ model: 'b' }] }, records).models, [heatmap.models[1]]);
});
