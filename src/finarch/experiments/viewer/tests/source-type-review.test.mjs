import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Repository } from '../repository.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
const run = '20260928-exp-001-luna';
const folder = path.join(root, 'reports/experiments-run', run);

test('saved source partitions cover the completed Luna run and are available in viewer', async () => {
  const repository = new Repository(path.join(root, 'reports/experiments-run'));
  const snap = { root: folder, id: run, files: new Map() };
  const files = await repository.documents(snap);
  const indexFile = files.find(file => file.path === '02_analysis/source-types/source-type-index.json');
  assert.ok(indexFile);
  const index = JSON.parse((await repository.file(snap, indexFile.id)).content);
  assert.deepEqual(index.types.map(item => item.source_type), ['FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning']);
  assert.equal(index.types.reduce((sum, item) => sum + item.case_count, 0), 1080);
  assert.equal(index.types.reduce((sum, item) => sum + item.response_count, 0), 34560);
  assert.equal(index.types.reduce((sum, item) => sum + item.observation_count, 0), 7965);
  for (const item of index.types) {
    const report = files.find(file => file.path === item.review_path);
    assert.ok(report, item.review_path);
    const content = (await repository.file(snap, report.id)).content;
    assert.match(content, /원천 유형별 검토/);
    const summary = JSON.parse(await readFile(path.join(folder, item.folder, 'summary.json')));
    assert.equal(summary.case_count, item.case_count);
    assert.equal(summary.response_count, item.response_count);
    assert.equal(summary.case_ids.length, item.case_count);
    for (const group of Object.values(summary.conditions)) {
      for (const condition of Object.values(group)) {
        assert.equal(condition.planned, item.case_count);
        assert.equal(condition.numeric_case_ids.length, condition.numeric_answer);
        assert.equal(condition.null_case_ids.length, condition.null_answer);
        assert.equal(condition.numeric_answer + condition.null_answer + condition.format_failed_case_ids.length, condition.planned);
      }
    }
  }
});

test('RQ1 viewer graphs partition the saved paired-answer counts by source type', async () => {
  const repository = new Repository(path.join(root, 'reports/experiments-run'));
  const snap = await repository.snapshot(run);
  const source = await repository.rqSourceSummaries(snap);
  assert.equal(source.types.length, 4);
  assert.equal(source.types.reduce((sum, item) => sum + item.case_count, 0), 1080);
  for (const group of source.types) {
    assert.equal(group.rq_answers.cells.length, 28);
    for (const cell of group.rq_answers.cells) {
      assert.equal(cell.planned, group.case_count);
      assert.equal(Object.values(cell.counts).reduce((sum, value) => sum + value, 0), group.case_count);
    }
    for (const cell of group.rq_answers.baselines) {
      assert.equal(cell.planned, group.case_count);
      assert.equal(cell.counts.match + cell.counts.mismatch + cell.counts.unevaluated
        + cell.counts.failed + cell.counts.missing, group.case_count);
    }
  }
  const selected = await repository.rqPairs(snap, { source_type: 'FinQA', model: 'luna-api',
    variant: 'EA_01', prompt: 'guided', reasoning: 'on', category: 'numeric_different' });
  assert.equal(selected.planned, 404);
  const finqa = new Set(JSON.parse(await readFile(path.join(folder,
    '02_analysis/source-types/exp-001-luna-FinQA/summary.json'))).case_ids);
  assert.ok(selected.pairs.every(pair => finqa.has(pair.case)));
});
