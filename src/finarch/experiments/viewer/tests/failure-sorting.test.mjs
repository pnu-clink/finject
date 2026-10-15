import test from 'node:test';
import assert from 'node:assert/strict';
import { query, sortResponses, VARIANTS } from '../../../../../viewer/experiments/model.mjs';

const row = (id, extra = {}) => ({ case: `test-${id}`, trial_id: `trial-${id}`, question: 'Question', model: 'a', variant: 'ORIGINAL', experiment: 1, prompt_condition: 'P0', reasoning: 'off', status: 'VALID', tags: [], ...extra });
const snapshot = rows => ({ config: { models: [{ key: 'a' }, { key: 'b' }] }, rows });

test('natural case order applies before pagination and never mutates the saved rows', () => {
  const rows = Array.from({ length: 65 }, (_, i) => row(65 - i));
  const original = structuredClone(rows), snap = snapshot(rows);
  assert.deepEqual(query(snap).rows.map(r => r.case), Array.from({ length: 30 }, (_, i) => `test-${i + 1}`));
  assert.equal(query(snap, { offset: '30' }).rows[0].case, 'test-31');
  assert.equal(query(snap, { sort: 'case_desc' }).rows[0].case, 'test-65');
  assert.equal(query(snap, { sort: 'case_desc', offset: '30' }).rows[0].case, 'test-35');
  assert.deepEqual(rows, original);
});

test('ties keep canonical variant, model and P0/P1-reasoning order after source shuffling', () => {
  const rows = VARIANTS.flatMap(variant => ['b', 'a'].flatMap(model => ['P1', 'P0'].flatMap(prompt_condition => ['on', 'off'].map(reasoning => row(2, { variant, model, prompt_condition, reasoning }))))).reverse();
  const sorted = sortResponses(rows).rows;
  assert.deepEqual(sorted.slice(0, 4).map(r => [r.variant, r.model, r.prompt_condition, r.reasoning]), [
    ['ORIGINAL', 'a', 'P0', 'off'], ['ORIGINAL', 'a', 'P0', 'on'], ['ORIGINAL', 'a', 'P1', 'off'], ['ORIGINAL', 'a', 'P1', 'on'],
  ]);
  assert.deepEqual([...new Set(sorted.map(r => r.variant))], VARIANTS);
  assert.deepEqual(sortResponses([...rows].reverse()).rows, sorted);
});

test('column sorting is global, directional and deterministic, including distinct reason counts', () => {
  const rows = [row(3, { status: 'VALID', tags: ['A', 'A'] }), row(2, { status: 'NEW_STATUS', tags: ['B', 'A'] }), row(10, { status: 'OUTPUT_TRUNCATED' }), row(1, { status: 'INVALID_RESPONSE' })];
  assert.deepEqual(sortResponses(rows, 'status_asc').rows.map(r => r.status), ['OUTPUT_TRUNCATED', 'INVALID_RESPONSE', 'NEW_STATUS', 'VALID']);
  assert.equal(sortResponses(rows, 'status_desc').rows[0].status, 'VALID');
  assert.deepEqual(sortResponses(rows, 'diagnostics_desc').rows.map(r => r.case), ['test-2', 'test-3', 'test-1', 'test-10']);
  for (const invalid of ['bad_desc', 'case_asc_extra', '', null]) assert.equal(sortResponses(rows, invalid).sort, 'case_asc');
});

test('reason counts ignore selected reasons, deduplicate tags and retain the base and paired scope', () => {
  const compared = { numeric_comparison: { matches: false } };
  const snap = snapshot([
    row(1, { model: 'a', tags: ['A', 'B', 'B'], checks: compared }),
    row(1, { model: 'b', tags: ['A'], checks: compared }),
    row(2, { model: 'a', tags: ['B'], checks: compared }),
    row(2, { model: 'b', tags: ['B'], checks: compared }),
    row(3, { model: 'a', tags: ['C'], status: 'NOT_RUN' }),
  ]);
  const selected = query(snap, { status: 'VALID', tags: 'B', paired: 'true', metric: 'numeric_mismatches' });
  assert.equal(selected.aggregate.total, 2);
  assert.deepEqual(selected.tags, { B: 2 });
  assert.equal(selected.tag_scope_total, 4);
  assert.deepEqual(selected.tag_counts, { A: 2, B: 3 });
  const scoped = query(snap, { model: 'a', q: 'test-1', tags: 'A' });
  assert.equal(scoped.tag_scope_total, 1);
  assert.deepEqual(scoped.tag_counts, { A: 1, B: 1 });
});

test('stale page offsets stop at the last result page or zero for an empty result', () => {
  const snap = snapshot(Array.from({ length: 35 }, (_, i) => row(i + 1)));
  const last = query(snap, { offset: '900' });
  assert.equal(last.offset, 30); assert.equal(last.rows.length, 5);
  const empty = query(snap, { offset: '900', tags: 'absent' });
  assert.equal(empty.offset, 0); assert.deepEqual(empty.rows, []);
});
