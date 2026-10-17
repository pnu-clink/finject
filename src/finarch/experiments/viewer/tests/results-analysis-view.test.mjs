import test from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { aggregate, filterRows, resultsAnalysisForTab, summarizePairAnswers } from '../../../../../viewer/experiments/model.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { Repository, artifactPaths } from '../repository.mjs';

const responses = [
  { response_id: 'before-a', variant: 'ORIGINAL', original_result: 'MISMATCH', answer_scale: 'million' },
  { response_id: 'after-a', variant: 'ORIGINAL', original_result: 'MATCH', answer_scale: 'million' },
  { response_id: 'before-b', variant: 'ORIGINAL', original_result: 'MATCH', answer_scale: 'unit' },
  { response_id: 'after-b', variant: 'ORIGINAL', original_result: 'UNEVALUATED', answer_scale: null },
];
const pair = (before, after, left, right) => ({ format_comparable: true,
  left: { response_id: before, choice: left === null ? 'NULL' : 'A', answer: left },
  right: { response_id: after, choice: right === null ? 'NULL' : 'A', answer: right } });
const pairs = [pair('before-a', 'after-a', 10, 12), pair('before-b', 'after-b', 7, null)];
const analysis = { method: 'results-focused-v1', stages: [{ status: 'COLLECTED' }, {}, {}], responses,
  comparisons: { overall: { planned: 4, response_ids: responses.map(row => row.response_id) },
    matrix: [{ variant: 'ORIGINAL', response_ids: responses.map(row => row.response_id) }],
    paired_groups: [{ axis: 'PROMPT', variant: 'ORIGINAL', comparable_pairs: 2, pairs }] },
  interpretations: [{ id: 'i1', excerpts: [{ response_id: 'after-a' }] }], findings: { findings: [], discussion: [] } };

test('analysis screens omit unrelated large records and preserve exact paired deltas', () => {
  const collection = resultsAnalysisForTab(analysis, 'analysis');
  assert.equal(collection.responses.length, 2);
  assert.equal(collection.comparisons.overall.response_ids, undefined);
  assert.equal(collection.comparisons.matrix[0].response_ids, undefined);

  const relationships = resultsAnalysisForTab(analysis, 'conditions');
  const group = relationships.comparisons.paired_groups[0];
  assert.equal(group.pairs, undefined);
  assert.equal(group.viewer_pair_index, 0);
  assert.deepEqual(group.viewer_delta, { comparable: 2, numeric_before: 2, numeric_after: 1,
    null_before: 0, null_after: 1, up: 1, down: 0, same: 0, different_scale: 0, invalid: 0 });
  assert.deepEqual(group.viewer_answer_changes, { comparable: 2, numeric_same: 0, numeric_different: 1,
    numeric_to_null: 1, null_to_numeric: 0, null_same: 0, scale_unmatched: 0, other: 0 });

  const research = resultsAnalysisForTab(analysis, 'reports');
  assert.deepEqual(research.responses.map(row => row.response_id), ['after-a']);
  assert.equal(research.comparisons, undefined);
  assert.equal(resultsAnalysisForTab(analysis, 'overview').responses, undefined);
});

test('paired answer summary keeps null changes distinct and withholds comparisons across scales', () => {
  const values = [
    pair('same-left', 'same-right', 10, 10), pair('different-left', 'different-right', 10, 12),
    pair('to-null-left', 'to-null-right', 10, null), pair('from-null-left', 'from-null-right', null, 12),
    pair('null-left', 'null-right', null, null), pair('scale-left', 'scale-right', 10, 12),
  ];
  values.push({ ...pair('ignored-left', 'ignored-right', 10, 12), format_comparable: false });
  const scale = new Map(values.flatMap(({ left, right }) => [left, right].map(side => [side.response_id, { answer_scale: side.response_id === 'scale-right' ? 'unit' : 'million' }])));
  assert.deepEqual(summarizePairAnswers({ pairs: values }, scale), { comparable: 6, numeric_same: 1,
    numeric_different: 1, numeric_to_null: 1, null_to_numeric: 1, null_same: 1, scale_unmatched: 1, other: 0 });
});

test('a planned results-focused run keeps A01/A02/A03 pending before files exist', () => {
  const paths = artifactPaths({ layout_version: 2, analysis: { enabled: true, backends: { codex: { model: 'gpt-6-sol' } } } });
  assert.equal(paths.resultsFocused, true);
  assert.equal(paths.diagnosticsFile, '02_analysis/01_results/responses.jsonl');
  const pending = resultsAnalysisForTab({ method: 'results-focused-v1', stages: [{}, {}, {}], responses: [],
    comparisons: null, interpretations: null, findings: null }, 'analysis');
  assert.equal(pending.comparisons, null);
  assert.deepEqual(pending.responses, []);
  assert.equal(pending.timing, null);
});

test('analysis tabs preserve timing without fabricating missing historical measurements', () => {
  const timing = { status: 'RUNNING', steps: [{ step: 'comparison_models', running: 1, occupied_wall_seconds: 12 }],
    bottleneck: { provisional: true, share_of_measured_analysis_steps: .8 } };
  for (const tab of ['analysis', 'conditions', 'reports']) {
    assert.deepEqual(resultsAnalysisForTab({ ...analysis, timing }, tab).timing, timing);
  }
});

test('analysis tabs preserve the observed scheduler without inventing CPU usage', () => {
  const scheduler = { current_limit: 22, active_calls: 22, last_cpu_sample: { cpu_percent: 36.1 } };
  for (const tab of ['analysis', 'conditions', 'reports']) {
    assert.deepEqual(resultsAnalysisForTab({ ...analysis, scheduler }, tab).scheduler, scheduler);
    assert.equal(resultsAnalysisForTab(analysis, tab).scheduler, null);
  }
});

test('uncollected originals are separated from stored numeric unevaluated responses', () => {
  const rows = [
    { case: 'a', experiment: 1, status: 'BATCH_PENDING', checks: {} },
    { case: 'b', experiment: 1, status: 'VALID', checks: { numeric_comparison: { matches: true } } },
    { case: 'c', experiment: 1, status: 'VALID', checks: {} },
    { case: 'd', experiment: 2, status: 'BATCH_PENDING', checks: {} },
  ];
  const totals = aggregate(rows);
  assert.deepEqual([totals.numeric_eligible, totals.numeric_matches, totals.numeric_mismatches,
    totals.numeric_unevaluated, totals.numeric_pending], [3, 1, 0, 1, 1]);
  assert.deepEqual(filterRows(rows, { metric: 'numeric_pending' }).map(row => row.case), ['a']);
  assert.deepEqual(filterRows(rows, { metric: 'numeric_unevaluated' }).map(row => row.case), ['c']);
});

test('seed-suffixed run is selectable and an old unsuffixed link resolves to its unique successor', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'finarch-viewer-runs-'));
  try {
    const renamed = path.join(root, '20260927-exp-007-20260920');
    await mkdir(renamed);
    const repository = new Repository(root);
    assert.equal(await repository.runPath('20260927-exp-007-20260920'), await realpath(renamed));
    assert.equal(await repository.runPath('20260927-exp-007'), await realpath(renamed));
    const listed = await repository.runs();
    assert.equal(listed.some(run => run.id === '20260927-exp-007-20260920'), true);
    await assert.rejects(repository.runPath('../20260927-exp-007'), /\uc62c\ubc14\ub974\uc9c0/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('E04 numeric comparisons appear before A01 Analysis is collected', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'finarch-viewer-e04-'));
  const run = '20260927-exp-999-20260920';
  const folder = path.join(root, run);
  const write = async (relative, value, lines = false) => {
    const target = path.join(folder, relative);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, lines ? value.map(row => JSON.stringify(row)).join('\n') + '\n' : JSON.stringify(value));
  };
  try {
    const row = { trial_id: 'trial-a', item_id: 'item-a', case: 'test-0001', experiment: 1,
      variant: 'ORIGINAL', prompt_condition: 'unguided', reasoning: 'off', status: 'VALID' };
    await write('config.json', { layout_version: 2, evaluation: { models: [{ key: 'luna-api' }] },
      analysis: { enabled: true, backends: { codex: { model: 'gpt-6-sol' } } } });
    await write('state.json', { status: 'FINISHED', analysis: { status: 'PAUSED_BY_USER', new_model_calls: 0 } });
    await write('01_evaluation/04_validation/summary.json', { status: 'FINISHED', originals: 1, variants: 0,
      models: [{ model: 'luna-api' }] });
    await write('01_evaluation/02_request/plan.json', { models: [{ key: 'luna-api', requests: 1 }] });
    await write('00_input/public.jsonl', [{ item_id: 'item-a', question: 'What are sales?' }], true);
    await write('00_input/private.jsonl', [{ item_id: 'item-a', case: 'test-0001', variant: 'ORIGINAL', reference: {} }], true);
    await write('01_evaluation/02_request/luna-api/manifest.jsonl', [{ ...row, input: { question: 'What are sales?' } }], true);
    await write('01_evaluation/04_validation/luna-api/results.jsonl', [{ ...row, checks: {}, response: { answer: 42 } }], true);
    await write('01_evaluation/04_validation/luna-api/summary.json', { planned: 1, statuses: { VALID: 1 } });
    const comparisonFile = '01_evaluation/04_validation/numeric-comparisons.jsonl';
    await write(comparisonFile, [{ ...row, model: 'luna-api', checks: { numeric_comparison: { matches: true } }, tags: ['NUMERIC_MATCH'] }], true);
    const repository = new Repository(root);
    const first = await repository.snapshot(run);
    assert.deepEqual([first.rows[0].checks.numeric_comparison.matches, first.resultsAnalysis.responses.length,
      first.diagnosticsAvailable, aggregate(first.rows).numeric_matches], [true, 0, true, 1]);
    await write('02_analysis/config.json', { analysis: { enabled: true, backend: 'api',
      backends: { api: { model: 'analysis-model' } } } });
    const configured = await repository.snapshot(run);
    assert.equal(configured.config.analysis.backend, 'api');
    assert.equal(configured.config.analysis.backends.api.model, 'analysis-model');
    assert.notEqual(configured.signature, first.signature);
    await write('02_analysis/scheduler.json', { current_limit: 22, active_calls: 20 });
    const scheduled = await repository.snapshot(run);
    assert.equal(scheduled.resultsAnalysis.scheduler.current_limit, 22);
    assert.notEqual(scheduled.signature, configured.signature);
    await write('02_analysis/scheduler.json', { current_limit: 22, active_calls: 20, updated_at: 'later' });
    assert.equal((await repository.snapshot(run)).signature, scheduled.signature);
    await write(comparisonFile, [{ ...row, model: 'luna-api', checks: { numeric_comparison: { matches: false } }, tags: ['NUMERIC_MISMATCH'] }], true);
    const updated = await repository.snapshot(run);
    assert.deepEqual([updated.rows[0].checks.numeric_comparison.matches, aggregate(updated.rows).numeric_mismatches], [false, 1]);
    await write(comparisonFile, [], true);
    const incomplete = await repository.snapshot(run);
    assert.equal(incomplete.stale, true);
    assert.equal(incomplete.rows[0].checks.numeric_comparison.matches, false);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('saved response pairs are paged from the same group without changing source records', () => {
  const many = { ...analysis, comparisons: { ...analysis.comparisons,
    paired_groups: [{ ...analysis.comparisons.paired_groups[0], pairs: Array.from({ length: 55 }, (_, index) => ({ ...pairs[0], case: `test-${index}` })) }] } };
  const repository = new Repository('/unused');
  const snap = { resultsAnalysis: many };
  const first = repository.analysisPairs(snap, { group: '0', offset: '0' });
  const last = repository.analysisPairs(snap, { group: '0', offset: '50' });
  assert.deepEqual([first.total, first.pairs.length, last.pairs.length, last.pairs[0].case], [55, 50, 5, 'test-50']);
  assert.equal(many.comparisons.paired_groups[0].pairs.length, 55);
  assert.throws(() => repository.analysisPairs(snap, { group: '../0' }), /\uc62c\ubc14\ub974\uc9c0/);
});

test('a single-file export pages the same saved comparison pairs offline', async () => {
  const index = { id: '20260927-exp-999', resultsAnalysis: analysis };
  const bundle = { version: 1, run: { id: index.id }, chunks: { index: gzipSync(JSON.stringify(index)).toString('base64') } };
  const offline = createOfflineStore(bundle);
  const page = await offline.request(`/api/runs/${index.id}/analysis-pairs?group=0&offset=1`);
  assert.deepEqual([page.total, page.offset, page.pairs.length, page.pairs[0].left.response_id], [2, 1, 1, 'before-b']);
});
