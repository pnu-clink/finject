import test from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';
import { RQ_VARIANTS, RQ_CONDITIONS, RQ_BASELINE_CATEGORIES, rqAnswerOverview, rqAnswerPage,
  resultsAnalysisForTab } from '../../../../../viewer/experiments/model.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { Repository } from '../repository.mjs';

const make = (caseId, variant, answer, options = {}) => ({
  response_id: `${caseId}-${variant}`, case: caseId, variant, model: 'luna-api',
  prompt_condition: 'guided', reasoning: 'on', status: options.status ?? 'VALID',
  original_result: options.original_result ?? 'UNEVALUATED',
  answer, answer_scale: options.scale ?? 'million',
  answer_negative: options.negative ?? false,
  classification: options.classification ?? 'ANSWERABLE'
});

const synthetic = {
  responses: [
    make('same', 'ORIGINAL', '20'), make('same', 'EA_01', 20),
    make('different', 'ORIGINAL', 20), make('different', 'EA_01', 21),
    make('to-null', 'ORIGINAL', 20), make('to-null', 'EA_01', null),
    make('from-null', 'ORIGINAL', null), make('from-null', 'EA_01', 21),
    make('null-same', 'ORIGINAL', null), make('null-same', 'EA_01', null),
    make('invalid', 'ORIGINAL', 20), make('invalid', 'EA_01', 21, { status: 'INVALID_RESPONSE' }),
    make('scale', 'ORIGINAL', 20), make('scale', 'EA_01', 20, { scale: 'unit' }),
    make('missing', 'ORIGINAL', 20),
    make('negative', 'ORIGINAL', '20', { negative: true }),
    make('negative', 'EA_01', '-20', { negative: true })
  ],
  comparisons: { matrix: [{ model: 'luna-api', variant: 'EA_01',
    prompt_condition: 'guided', reasoning: 'on', planned: 10 }] }
};

test('RQ grid keeps seven changes and four official conditions in the requested order', () => {
  assert.deepEqual(RQ_VARIANTS.map(row => row.key), [
    'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
    'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02'
  ]);
  assert.deepEqual(RQ_CONDITIONS.map(row => [row.prompt, row.reasoning]), [
    ['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']
  ]);
  const summary = rqAnswerOverview(synthetic);
  assert.equal(summary.cells.length, 28);
  const cell = summary.cells.find(row => row.variant === 'EA_01'
    && row.prompt === 'guided' && row.reasoning === 'on');
  assert.equal(cell.planned, 10);
  assert.deepEqual(cell.counts, {
    numeric_same: 2, numeric_different: 1, numeric_to_null: 1,
    null_to_numeric: 1, null_same: 1, unavailable: 4
  });
  assert.equal(Object.values(cell.counts).reduce((sum, value) => sum + value, 0), cell.planned);
});

test('RQ details link only saved pairs and retain why a pair cannot be compared', () => {
  const different = rqAnswerPage(synthetic, { model: 'luna-api', variant: 'EA_01',
    prompt: 'guided', reasoning: 'on', category: 'numeric_different' });
  assert.equal(different.category_total, 1);
  assert.deepEqual(different.pairs.map(row => row.case), ['different']);
  assert.deepEqual([different.pairs[0].original.answer, different.pairs[0].changed.answer], [20, 21]);
  const unavailable = rqAnswerPage(synthetic, { model: 'luna-api', variant: 'EA_01',
    prompt: 'guided', reasoning: 'on', category: 'unavailable' });
  assert.equal(unavailable.category_total, 4);
  assert.equal(unavailable.unrecorded, 1);
  assert.deepEqual(unavailable.pairs.map(row => row.reason),
    ['형식 실패·미완료', '응답 미기록', 'scale 다름']);
  assert.throws(() => rqAnswerPage(synthetic, { model: 'luna-api', variant: '../EA_01',
    prompt: 'guided', reasoning: 'on' }), /선택값/);
});

test('RQ source subset changes the graph denominator and keeps pair links in that subset', () => {
  const all = rqAnswerOverview(synthetic);
  const subset = rqAnswerOverview(synthetic, { caseIds: ['same', 'different'] });
  const find = data => data.cells.find(row => row.model === 'luna-api' && row.variant === 'EA_01'
    && row.prompt === 'guided' && row.reasoning === 'on');
  assert.equal(find(all).planned, 10);
  assert.equal(find(subset).planned, 2);
  assert.equal(find(subset).counts.numeric_same, 1);
  assert.equal(find(subset).counts.numeric_different, 1);
  const page = rqAnswerPage(synthetic, { model: 'luna-api', variant: 'EA_01', prompt: 'guided',
    reasoning: 'on', category: 'numeric_different', caseIds: ['same', 'different'] });
  assert.deepEqual(page.pairs.map(pair => pair.case), ['different']);
  assert.equal(page.planned, 2);
});

test('RQ1 original row separates correctness, unassessed, failed and absent records', () => {
  const source = {
    responses: [
      make('a', 'ORIGINAL', 10, { original_result: 'MATCH' }),
      make('b', 'ORIGINAL', 11, { original_result: 'MISMATCH' }),
      make('c', 'ORIGINAL', null),
      make('d', 'ORIGINAL', 12, { status: 'INVALID_RESPONSE' }),
      make('e', 'EA_01', 13)
    ],
    comparisons: { matrix: [{ model: 'luna-api', variant: 'ORIGINAL',
      prompt_condition: 'guided', reasoning: 'on', planned: 6 }] }
  };
  const summary = rqAnswerOverview(source);
  assert.deepEqual(RQ_BASELINE_CATEGORIES.map(item => item.key),
    ['match', 'mismatch', 'unevaluated', 'failed', 'missing']);
  const original = summary.baselines.find(row => row.prompt === 'guided' && row.reasoning === 'on');
  assert.equal(original.planned, 6);
  assert.deepEqual(original.counts, { match: 1, mismatch: 1, unevaluated: 1,
    failed: 1, missing: 2, null: 1 });
  assert.equal(RQ_BASELINE_CATEGORIES.reduce((sum, item) => sum + original.counts[item.key], 0), 6);
  const mismatch = rqAnswerPage(source, { model: 'luna-api', variant: 'ORIGINAL',
    prompt: 'guided', reasoning: 'on', category: 'mismatch' });
  assert.deepEqual([mismatch.category_total, mismatch.pairs[0].case,
    mismatch.pairs[0].original.answer, mismatch.pairs[0].changed], [1, 'b', 11, null]);
  const missing = rqAnswerPage(source, { model: 'luna-api', variant: 'ORIGINAL',
    prompt: 'guided', reasoning: 'on', category: 'missing' });
  assert.deepEqual([missing.category_total, missing.linked_total, missing.unrecorded], [2, 1, 1]);
  assert.throws(() => rqAnswerPage(source, { model: 'luna-api', variant: 'ORIGINAL',
    prompt: 'guided', reasoning: 'on', category: 'numeric_different' }), /선택값/);
});

test('RQ summary is available in A03 while full responses stay behind case detail', async () => {
  const research = resultsAnalysisForTab({ ...synthetic, interpretations: [], findings: { findings: [], discussion: [] } }, 'reports');
  assert.equal(research.rq_answers.cells.length, 28);
  assert.deepEqual(research.responses, []);
  assert.equal((await new Repository('.').rqPairs({ resultsAnalysis: synthetic }, {
    model: 'luna-api', variant: 'EA_01', prompt: 'guided', reasoning: 'on',
    category: 'numeric_same'
  })).linked_total, 2);
});

test('single-file HTML provides the same RQ pair page without a server', async () => {
  const id = '20260927-exp-999';
  const index = { id, resultsAnalysis: synthetic };
  const bundle = { version: 1, run: { id },
    chunks: { index: gzipSync(JSON.stringify(index)).toString('base64') } };
  const offline = createOfflineStore(bundle);
  const page = await offline.request(`/api/runs/${id}/rq-pairs?model=luna-api&variant=EA_01&prompt=guided&reasoning=on&category=numeric_different`);
  assert.deepEqual(page, rqAnswerPage(synthetic, { model: 'luna-api', variant: 'EA_01',
    prompt: 'guided', reasoning: 'on', category: 'numeric_different' }));
  const original = await offline.request(`/api/runs/${id}/rq-pairs?model=luna-api&variant=ORIGINAL&prompt=guided&reasoning=on&category=unevaluated`);
  assert.deepEqual(original, rqAnswerPage(synthetic, { model: 'luna-api', variant: 'ORIGINAL',
    prompt: 'guided', reasoning: 'on', category: 'unevaluated' }));
});

test('single-file HTML keeps source-type RQ summaries and linked pairs within the chosen cases', async () => {
  const id = '20260928-exp-001-luna';
  const folder = '02_analysis/source-types/exp-001-luna-FinQA';
  const sourceIndex = { run: id, types: [{ source_type: 'FinQA', case_count: 2, folder }] };
  const summary = { source_type: 'FinQA', case_ids: ['same', 'different'] };
  const fileIndex = { id: 'source-index', path: '02_analysis/source-types/source-type-index.json' };
  const fileSummary = { id: 'source-summary', path: `${folder}/summary.json` };
  const packed = value => gzipSync(JSON.stringify(value)).toString('base64');
  const bundle = { version: 1, run: { id }, documents: [fileIndex, fileSummary],
    files: { 'source-index': 'source-files', 'source-summary': 'source-files' },
    chunks: { index: packed({ id, resultsAnalysis: synthetic }), 'source-files': packed({ files: {
      'source-index': { content: JSON.stringify(sourceIndex) },
      'source-summary': { content: JSON.stringify(summary) }
    } }) } };
  const offline = createOfflineStore(bundle);
  const grouped = await offline.request(`/api/runs/${id}/rq-source-summaries`);
  assert.equal(grouped.types[0].rq_answers.cells.find(row => row.variant === 'EA_01'
    && row.prompt === 'guided' && row.reasoning === 'on').planned, 2);
  const page = await offline.request(`/api/runs/${id}/rq-pairs?source_type=FinQA&model=luna-api&variant=EA_01&prompt=guided&reasoning=on&category=numeric_different`);
  assert.deepEqual(page.pairs.map(row => row.case), ['different']);
});
