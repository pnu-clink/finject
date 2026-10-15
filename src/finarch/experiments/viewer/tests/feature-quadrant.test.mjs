import test from 'node:test';
import assert from 'node:assert/strict';
import { buildFeatureQuadrant, quadrantDeltaBand } from '../../../../../viewer/experiments/feature-quadrant.mjs';

// Counts transcribed from the saved 20260927-exp-007-luna A02 IC-value-before matrix.
const saved = [
  ['unguided', 'off', { A: 447, B: 37, OTHER: 67, NULL: 5, FORMAT_OR_EXECUTION_FAILED: 1 }],
  ['unguided', 'on', { A: 440, B: 62, OTHER: 40, NULL: 15 }],
  ['guided', 'off', { A: 260, B: 33, OTHER: 49, NULL: 215 }],
  ['guided', 'on', { A: 18, B: 7, OTHER: 5, NULL: 527 }],
].map(([prompt_condition, reasoning, numeric_candidate_choices]) => ({
  model: 'luna-api', variant: 'IC_VALUE_01_BEFORE', prompt_condition, reasoning,
  planned: 557, collected: 557, numeric_candidate_choices,
}));

test('IC-value sample preserves every saved answer form and uses the same denominator', () => {
  const result = buildFeatureQuadrant(saved, 'luna-api');
  assert.equal(result.status, 'READY');
  assert.deepEqual(result.cells.map(cell => [cell.key, cell.planned]), [
    ['unguided/off', 557], ['unguided/on', 557], ['guided/off', 557], ['guided/on', 557],
  ]);
  for (const cell of result.cells) assert.equal(Object.values(cell.counts).reduce((a, b) => a + b), 557);
  assert.equal(result.largest.choice, 'NULL');
  assert.equal(result.largest.target, 'guided/on');
  assert.deepEqual([result.largest.before, result.largest.after, result.largest.band], [5, 527, 4]);
  assert.ok(Math.abs(result.largest.deltaPp - 522 / 557 * 100) < 1e-10);
  assert.deepEqual([result.largestSingle.choice, result.largestSingle.target, result.largestSingle.before, result.largestSingle.after],
    ['NULL', 'guided/off', 5, 215]);
  assert.equal(result.changes.find(change => change.choice === 'B' && change.target === 'unguided/on').deltaPp,
    25 / 557 * 100);
});

test('10, 25 and 50 percentage-point boundaries change arrow weight', () => {
  assert.deepEqual([0, 9.9, 10, 24.9, 25, 49.9, 50].map(quadrantDeltaBand), [1, 1, 2, 2, 3, 3, 4]);
});

test('incomplete or inconsistent condition data never shows a misleading quadrant', () => {
  assert.equal(buildFeatureQuadrant(saved.slice(1), 'luna-api').status, 'MISSING');
  assert.equal(buildFeatureQuadrant([{ ...saved[0], collected: 556 }, ...saved.slice(1)], 'luna-api').status, 'PENDING');
  assert.equal(buildFeatureQuadrant([{ ...saved[0], numeric_candidate_choices: { ...saved[0].numeric_candidate_choices, A: 448 } }, ...saved.slice(1)], 'luna-api').status, 'INCONSISTENT');
});

test('truncated completed requests stay in the planned denominator without blocking the chart', () => {
  const finished = saved.map(row => ({ ...row, collected: 556,
    statuses: { VALID: 556, OUTPUT_TRUNCATED: 1 },
    numeric_candidate_choices: { A: 556, FORMAT_OR_EXECUTION_FAILED: 1 } }));
  const result = buildFeatureQuadrant(finished, 'luna-api');
  assert.equal(result.status, 'READY');
  assert.equal(result.cells[0].planned, 557);
  assert.equal(result.cells[0].counts.FORMAT_OR_EXECUTION_FAILED, 1);
  for (const status of ['RUNNING', 'UNKNOWN_DELIVERY', 'NOT_RUN']) {
    assert.equal(buildFeatureQuadrant([{ ...finished[0], statuses: { VALID: 556, [status]: 1 } }, ...finished.slice(1)], 'luna-api').status, 'PENDING');
  }
  assert.equal(buildFeatureQuadrant([{ ...finished[0], statuses: { VALID: 555, OUTPUT_TRUNCATED: 1 } }, ...finished.slice(1)], 'luna-api').status, 'PENDING');
});
