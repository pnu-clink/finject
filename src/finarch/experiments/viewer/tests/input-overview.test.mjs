import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Repository } from '../repository.mjs';
import { classificationFixture } from './fixtures/classification.mjs';
import { filterRows, query } from '../../../../../viewer/experiments/model.mjs';

for (const modern of [false, true]) test(`input flow resolves ${modern ? 'modern' : 'legacy'} stored files without opening upstream paths`, async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-input-flow-'));
  t.after(() => fs.rm(root, { force: true, recursive: true }));
  const { run, folder } = await classificationFixture(root);
  const definition = modern ? '01_evaluation/02_request' : '00-definition';
  const move = async (from, to) => { await fs.mkdir(path.dirname(path.join(folder, to)), { recursive: true }); await fs.rename(path.join(folder, from), path.join(folder, to)); };
  const config = JSON.parse(await fs.readFile(path.join(folder, 'config.json'), 'utf8'));
  config.dataset = { source_run: 'reports/run/recorded-source', input_path: 'data/recorded-input.json', require_collected_results: modern };
  if (modern) {
    await move('01-input', '00_input');
    for (const model of config.models) {
      await move(`${model.key}/01-requests/manifest.jsonl`, `${definition}/${model.key}/manifest.jsonl`);
      await move(`${model.key}/03-results/results.jsonl`, `01_evaluation/04_validation/${model.key}/results.jsonl`);
    }
    await move('summary.json', '01_evaluation/04_validation/summary.json'); await move('plan.json', `${definition}/plan.json`);
  }
  await fs.writeFile(path.join(folder, 'config.json'), JSON.stringify(modern ? { layout_version: 2, evaluation: config } : config));
  await fs.mkdir(path.join(folder, definition), { recursive: true });
  for (const file of ['common.md', 'response.schema.json', ...(modern ? ['prompt-unguided.md', 'prompt-guided.md'] : ['p0-standard.md', 'p1-abstention-aware.md'])]) await fs.writeFile(path.join(folder, definition, file), '{}');
  const priv = path.join(folder, modern ? '00_input' : '01-input', 'private.jsonl');
  const rows = (await fs.readFile(priv, 'utf8')).split('\n').map(JSON.parse);
  rows[0].source = '/outside/unavailable/private-source.json';
  await fs.writeFile(priv, rows.map(JSON.stringify).join('\n'));
  const repo = new Repository(root), snap = await repo.snapshot(run), input = await repo.input(snap);
  assert.equal(input.mode, modern ? 'COLLECTED_RESULTS' : 'SAVED_SOURCES');
  assert.equal(input.public.path, modern ? '00_input/public.jsonl' : '01-input/public.jsonl');
  assert.equal(input.public.absolute_path, path.join(await fs.realpath(folder), input.public.path));
  assert.ok(input.contracts.every(file => file.status === 'AVAILABLE'));
  assert.equal(input.contracts[1].path, `${definition}/${modern ? 'prompt-unguided.md' : 'p0-standard.md'}`);
  assert.equal(input.models[0].requests, 32);
  assert.deepEqual(input.models[0].input_fields, ['context', 'question']);
  assert.equal(input.sources[0].source.status, 'RECORDED');
  assert.equal(input.sources[0].source.absolute_path, rows[0].source);
  assert.equal(input.events.status, 'MISSING');
  assert.ok(!(await repo.file(snap, input.public.id)).content.includes('private-source'));
});

test('collected manifest provenance resolves eight input paths rather than presenting the manifest as problem data', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-input-collected-'));
  t.after(() => fs.rm(root, { force: true, recursive: true }));
  const { run, folder } = await classificationFixture(root);
  const priv = path.join(folder, '01-input/private.jsonl');
  const rows = (await fs.readFile(priv, 'utf8')).split('\n').map(JSON.parse);
  rows[0].source = '/outside/recorded-dataset/results/manifest.json';
  await fs.writeFile(priv, rows.map(JSON.stringify).join('\n'));
  const repo = new Repository(root), snap = await repo.snapshot(run), input = await repo.input(snap);
  assert.equal(input.mode, 'COLLECTED_RESULTS');
  assert.equal(input.delivery_manifest.absolute_path, rows[0].source);
  assert.equal(input.delivery_files.length, 8);
  assert.equal(input.delivery_files[0].absolute_path, '/outside/recorded-dataset/results/00-input.json');
  assert.equal(input.delivery_files.at(-1).absolute_path, '/outside/recorded-dataset/results/07-ea-later-input.json');
  assert.ok(input.delivery_files.every(file => file.status === 'CONTRACT_PATH' && !file.id));
  assert.equal(input.sources[0].source.label, 'private에 기록된 데이터셋 전달 목록');
  assert.equal(input.sources[0].input_file.path, input.delivery_files[0].path);
});

test('four original conditions count correctly and every drilldown uses exactly its original rows', () => {
  const rows = [];
  for (const prompt of ['unguided', 'guided']) for (const reasoning of ['off', 'on']) for (let n = 0; n < 10; n++) rows.push({
    model: 'a', case: `c${n}`, variant: 'ORIGINAL', experiment: 1, prompt_condition: prompt, reasoning, status: 'VALID', tags: [],
    checks: { numeric_comparison: { matches: !(prompt === 'guided' && reasoning === 'on' && n >= 8) } }
  });
  rows.push({ ...rows[0], variant: 'EA_01', experiment: 2, checks: { numeric_comparison: { matches: false } } });
  const snap = { rows, config: { models: [{ key: 'a' }] } }, data = query(snap), groups = data.original_conditions[0].conditions;
  assert.deepEqual(groups.map(c => c.numeric_matches), [10, 10, 10, 8]);
  for (const c of groups) for (const metric of ['numeric_matches', 'numeric_mismatches', 'numeric_unevaluated']) {
    const result = filterRows(rows, { prompt: c.prompt, reasoning: c.reasoning, metric });
    assert.equal(result.length, c[metric]); assert.ok(result.every(row => row.variant === 'ORIGINAL'));
  }
  assert.equal(filterRows(rows, { metric: 'numeric_mismatches' }).length, 2);
  const legacy = query({ ...snap, rows: rows.filter(row => row.prompt_condition === 'unguided') });
  assert.equal(legacy.original_conditions[0].conditions[2].numeric_eligible, 0);
  assert.equal(legacy.original_conditions[0].conditions[2].run_requests, 0);
  const filtered = query(snap, { prompt: 'unguided' }).original_conditions[0].conditions[2];
  assert.equal(filtered.numeric_eligible, 0);
  assert.equal(filtered.run_requests, 10);
  const missing = { ...rows[0], checks: {}, status: 'OUTPUT_TRUNCATED' };
  assert.deepEqual(filterRows([missing, rows[0]], { metric: 'numeric_unevaluated' }), [missing]);
});
