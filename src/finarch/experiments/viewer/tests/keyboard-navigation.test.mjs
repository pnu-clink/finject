import test from 'node:test';
import assert from 'node:assert/strict';
import { query } from '../../../../../viewer/experiments/model.mjs';

const cases = Array.from({ length: 52 }, (_, i) => `test-${String(i + 1).padStart(4, '0')}`);
const snap = {
  config: { models: [{ key: 'a' }, { key: 'b' }] },
  rows: cases.flatMap((id, i) => ['a', 'b'].map(model => ({
    case: id, model, variant: 'ORIGINAL', experiment: 1, prompt_condition: 'P0', reasoning: 'off',
    status: i % 3 === 0 ? 'OUTPUT_TRUNCATED' : 'VALID', question: i % 2 === 0 ? 'Even group' : 'Odd group', tags: [],
  }))),
};

test('case shortcuts traverse the full list and ignore legacy page offsets without duplicate model rows', () => {
  const firstPage = query(snap, { case: cases[24] });
  assert.equal(firstPage.case_total, 52);
  assert.equal(firstPage.cases.length, 52);
  assert.deepEqual(firstPage.cases.map(c => c.id), cases);
  assert.deepEqual(firstPage.case_navigation.next, { id: cases[25], case_offset: 0 });
  const secondPage = query(snap, { case: cases[25], case_offset: '25' });
  assert.deepEqual(secondPage.case_navigation.previous, { id: cases[24], case_offset: 0 });
  const lastPage = query(snap, { case: cases[50], case_offset: '50' });
  assert.deepEqual(lastPage.case_navigation.previous, { id: cases[49], case_offset: 0 });
  assert.deepEqual(lastPage.case_navigation.next, { id: cases[51], case_offset: 0 });
  assert.deepEqual(lastPage.cases, firstPage.cases);
});

test('neighbors obey status and search filters rather than the unfiltered run', () => {
  const data = query(snap, { case: cases[6], status: 'FORMAT_FAILED', q: 'Even', model: 'a' });
  assert.deepEqual(data.cases.map(item => item.id), cases.filter((_, i) => i % 6 === 0));
  assert.deepEqual(data.case_navigation.previous, { id: cases[0], case_offset: 0 });
  assert.deepEqual(data.case_navigation.next, { id: cases[12], case_offset: 0 });
  assert.equal(data.case_navigation.total, 9);
});

test('first, last, empty and off-filter cases never wrap or invent a neighbor', () => {
  assert.equal(query(snap, { case: cases[0] }).case_navigation.previous, null);
  assert.equal(query(snap, { case: cases.at(-1) }).case_navigation.next, null);
  assert.deepEqual(query(snap, { case: cases[0], q: 'absent' }).case_navigation, { index: -1, total: 0, previous: null, next: null });
  const outside = query(snap, { case: cases[1], status: 'FORMAT_FAILED' }).case_navigation;
  assert.equal(outside.index, -1); assert.equal(outside.previous, null);
  assert.deepEqual(outside.next, { id: cases[0], case_offset: 0 });
});

test('a case opened from a legacy page link without explicit selection starts at the first filtered case', () => {
  const data = query(snap, { case_offset: '25' });
  assert.equal(data.case_navigation.index, 0);
  assert.equal(data.cases.length, 52);
  assert.deepEqual(data.case_navigation.next, { id: data.cases[1].id, case_offset: 0 });
  assert.equal(data.case_navigation.previous, null);
});

test('sidebar counts each filtered classification, format and numeric state without choosing a representative', () => {
  const base = { case: 'c1', model: 'a', variant: 'ORIGINAL', experiment: 1, prompt_condition: 'guided', reasoning: 'on', status: 'VALID', tags: [], question: 'Searchable full question' };
  const rows = [
    { ...base, response: { answer: null, classification: 'UNRESOLVED' }, checks: {} },
    { ...base, reasoning: 'off', response: { answer: 74, classification: 'ANSWERABLE' }, checks: { numeric_comparison: { matches: true } } },
    { ...base, model: 'b', response: { answer: 73, classification: 'ANSWERABLE' }, checks: { numeric_comparison: { matches: false } } },
    { ...base, variant: 'EA_01', experiment: 2, response: { answer: null, classification: 'INSUFFICIENT_EVIDENCE' } },
    { ...base, status: 'OUTPUT_TRUNCATED' },
    { ...base, prompt_condition: 'unguided', response: { answer: 74, classification: null }, checks: { numeric_comparison: { matches: true } } }
  ];
  const local = { config: snap.config, rows };
  const all = query(local).cases[0];
  assert.equal(all.total, 6);
  assert.deepEqual(all.statuses, { VALID: 5, OUTPUT_TRUNCATED: 1 });
  assert.deepEqual(Object.fromEntries(all.classifications.map(c => [c.value, c.count])), { ANSWERABLE: 2, INSUFFICIENT_EVIDENCE: 1, SUMMARY_NOT_RECORDED: 1, UNRESOLVED: 1, '분류 미요구': 1 });
  assert.deepEqual([all.numeric_matches, all.numeric_mismatches, all.numeric_unevaluated, all.total - all.numeric_eligible], [2, 1, 2, 1]);
  const narrowed = query(local, { variant: 'ORIGINAL', prompt: 'guided', reasoning: 'on', status: 'VALID', model: 'a', metric: 'numeric_unevaluated', q: 'full question' }).cases[0];
  assert.equal(narrowed.total, 1);
  assert.deepEqual(narrowed.classifications, [{ value: 'UNRESOLVED', label: '의미 모호', count: 1 }]);
  assert.equal(narrowed.numeric_unevaluated, 1);
});

test('stored summary classification fallback remains distinct from missing and explicitly null fields', () => {
  const base = { case: 'c1', model: 'a', experiment: 1, variant: 'ORIGINAL', prompt_condition: 'guided', reasoning: 'on', status: 'VALID', tags: [] };
  const result = query({ config: snap.config, rows: [
    { ...base, checks: { reported_classification: 'CONFLICT' } },
    { ...base, response: { classification: null }, checks: { reported_classification: 'ANSWERABLE' } },
    { ...base, checks: { reported_classification: null } },
    { ...base, response: { explanation: 'Classification: UNRESOLVED; Response: ABSTAIN. Stored declaration.' } }
  ] }).cases[0];
  assert.deepEqual(Object.fromEntries(result.classifications.map(c => [c.value, c.count])), { CONFLICT: 1, SUMMARY_NOT_RECORDED: 1, UNRESOLVED: 1, '미기록': 1 });
});
