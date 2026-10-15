import test from 'node:test';
import assert from 'node:assert/strict';
import { responseClassification, caseHeatmap, RESPONSE_CLASSIFICATIONS, semanticSummary } from '../../../../../viewer/experiments/model.mjs';

test('JSON classification takes precedence and null never implies abstention', () => {
  const prefix = 'Classification: CONFLICT; Response: ABSTAIN. Conflicting sources.';
  const explicit = responseClassification({ classification: 'ABSTAIN', explanation: prefix }, 'P1', 'EA_02', 'VALID');
  assert.equal(explicit.value, 'ABSTAIN'); assert.equal(explicit.source, 'JSON_FIELD');
  assert.equal(responseClassification({ classification: null, explanation: prefix }, 'P0').label, '분류 미요구');
  assert.equal(responseClassification({ classification: null, explanation: prefix }, 'P1').label, '미기록');
  assert.equal(responseClassification({ answer: null }, 'P0').label, '미기록');
  assert.equal(responseClassification({ answer: null, status: 'abstained' }, 'P1').known, false);
  assert.equal(responseClassification({ explanation: 'Response: ABSTAIN.' }, 'P1').known, false);
  assert.equal(responseClassification({ classification: 'UNKNOWN', explanation: prefix }, 'P1').label, 'UNKNOWN');
  assert.equal(responseClassification({ classification: { value: 'CONFLICT' } }, 'P1').label, '분류 형식 오류');
});

test('only the explicit legacy prefix supplies historical input classifications', () => {
  for (const value of ['ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED']) {
    const declared = responseClassification({ explanation: `Classification: ${value}; Response: ABSTAIN. Evidence.` }, 'P1');
    assert.equal(declared.value, value); assert.equal(declared.source, 'LEGACY_EXPLANATION_PREFIX');
  }
  assert.equal(responseClassification({ explanation: 'The example says Classification: CONFLICT; Response: ABSTAIN.' }, 'P1').known, false);
});

test('ANSWERABLE colors require an appropriate saved original evaluation, never a variant gold shortcut', () => {
  for (const matches of [true, false]) {
    const checks = { numeric_comparison: { matches } };
    const original = responseClassification({ classification: 'ANSWERABLE', answer: 20 }, 'P1', 'ORIGINAL', 'VALID', checks);
    assert.equal(original.color, matches ? 'class-answerable-match' : 'class-answerable-mismatch');
    const variant = responseClassification({ classification: 'ANSWERABLE', answer: 21 }, 'P1', 'IC_SOURCE_B_ONLY', 'VALID', checks);
    assert.equal(variant.color, 'class-answerable'); assert.equal(variant.assessment, '정답 미평가');
    assert.equal(responseClassification({ classification: 'ANSWERABLE' }, 'P1', 'ORIGINAL', 'INVALID_RESPONSE', checks).assessment, '정답 미평가');
  }
  for (const value of Object.keys(RESPONSE_CLASSIFICATIONS).filter(value => value !== 'ANSWERABLE')) {
    assert.equal(responseClassification({ classification: value, answer: null }, 'P1').assessment, null);
  }
});

test('heatmap shares declared colors while preserving actual values, reference differences, and failure states', () => {
  const row = { case: 'c', model: 'a', variant: 'EA_02', prompt_condition: 'P1', reasoning: 'on', trial_id: 'one', status: 'VALID' };
  const selection = { caseId: 'c', items: [{ variant: 'ORIGINAL', reference: { reference_answer: '20' } }], rows: [{ model: 'a' }] };
  for (const value of Object.keys(RESPONSE_CLASSIFICATIONS)) {
    const records = { 'a:one': { response: { classification: value, answer: value === 'ANSWERABLE' ? 21 : null } } };
    const map = caseHeatmap({ rows: [row] }, selection, records), cell = map.models[0].conditions[3].cells[7];
    assert.equal(cell.classification.value, value); assert.equal(cell.color, RESPONSE_CLASSIFICATIONS[value].color);
    assert.ok(map.legend.some(entry => entry.key === cell.color));
    if (value === 'ANSWERABLE') { assert.equal(cell.answer_text, '21'); assert.equal(cell.reference_matches, false); assert.equal(cell.classification.assessment, '정답 미평가'); }
    const invalid = caseHeatmap({ rows: [{ ...row, status: 'INVALID_RESPONSE' }] }, selection, records).models[0].conditions[3].cells[7];
    assert.equal(invalid.color, 'invalid'); assert.equal(invalid.classification.value, value);
  }
});


test('new guided summary counters take priority while historical counters remain readable', () => {
  const old = { matrix: [{ p1_planned: 5, p1_stated_classifications: { ANSWERABLE: 2 } }] };
  assert.equal(semanticSummary(old).matrix[0].guided_planned, 5);
  assert.deepEqual(semanticSummary(old).matrix[0].guided_stated_classifications, { ANSWERABLE: 2 });
  assert.equal(Object.hasOwn(old.matrix[0], 'guided_planned'), false);
  const mixed = { matrix: [{ p1_planned: 5, guided_planned: 4, p1_labels_present: 5, guided_labels_present: null }] };
  assert.equal(semanticSummary(mixed).matrix[0].guided_planned, 4);
  assert.equal(semanticSummary(mixed).matrix[0].guided_labels_present, null);
});
