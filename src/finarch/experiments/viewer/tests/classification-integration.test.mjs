import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { Repository } from '../repository.mjs';
import { buildBundle, renderHTML } from '../export-html.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { classificationFixture } from './fixtures/classification.mjs';

test('V7 and legacy declarations, original conditions and gold pairs agree in live and exported views', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-classification-test-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const { run } = await classificationFixture(root), repo = new Repository(root), snap = await repo.snapshot(run);
  const bundle = await buildBundle(repo, snap), offline = createOfflineStore(bundle);
  assert.equal(bundle.stats.requests, 62);
  const roundTrip = value => JSON.parse(JSON.stringify(value));
  for (const filters of [{ variant: 'ORIGINAL', prompt: 'guided', reasoning: 'on' }, { variant: 'EA_02', prompt: 'unguided', reasoning: 'on' }, { variant: 'ORIGINAL', prompt: 'P1', reasoning: 'on' }, { variant: 'EA_01', prompt: 'P1', reasoning: 'off' }, { variant: 'IC_VALUE_01_AFTER', prompt: 'P1', reasoning: 'on' }, { variant: 'EA_02', prompt: 'P0', reasoning: 'off' }]) {
    const live = await repo.detail(snap, 'fixture-0001', filters);
    const exported = await offline.request(`/api/runs/${run}/case?${new URLSearchParams({ case: 'fixture-0001', ...filters })}`);
    assert.deepEqual(roundTrip(exported), roundTrip(live));
  }
  const original = await repo.detail(snap, 'fixture-0001', { variant: 'ORIGINAL', prompt: 'P1', reasoning: 'on' });
  assert.equal(original.prompt, 'guided');
  assert.equal(original.responses[0].response.answer, 21);
  assert.equal(original.responses[0].request.prompt_condition, 'guided');
  assert.equal(original.responses[0].classification.color, 'class-answerable-mismatch');
  assert.equal(original.responses[1].status, 'NOT_PLANNED');
  assert.equal(original.responses[1].classification.label, '미기록');
  assert.ok(original.conditions.every(condition => condition.available));
  assert.equal(original.heatmap.models[0].conditions[3].cells[0].selectable, true);
  assert.equal(original.heatmap.models[1].conditions[3].cells[0].selectable, false);
  const old = await repo.detail(snap, 'fixture-0001', { model: 'fixture-legacy', variant: 'ORIGINAL', prompt: 'P1', reasoning: 'on' });
  assert.equal(old.conditions[3].available, false);
  assert.equal(old.responses[0].status, 'NOT_PLANNED');
  const v7Null = await repo.detail(snap, 'fixture-0001', { variant: 'EA_02', prompt: 'P0', reasoning: 'off' });
  assert.equal(v7Null.responses[0].classification.label, '분류 미요구');
  assert.equal(v7Null.responses[1].classification.label, '미기록');
  const profile = repo.overview(snap, {}).content_analysis;
  const guided = profile.models.find(group => group.key === 'fixture-v7' && group.prompt === 'guided');
  assert.equal(guided.baseline.off_only.count, 1);
  const oldGuided = profile.models.find(group => group.key === 'fixture-legacy' && group.prompt === 'guided');
  assert.equal(oldGuided.baseline.unevaluated.count, 1);
  assert.equal(oldGuided.variants[0].cells[0].cases[0].original, null);
  const html = await renderHTML(bundle);
  new vm.Script(html.match(/<script type="module">([\s\S]*?)<\/script>/)[1]);
});
