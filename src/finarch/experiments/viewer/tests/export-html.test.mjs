import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { Repository } from '../repository.mjs';
import { buildBundle, renderHTML } from '../export-html.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { createServer } from '../server.mjs';
import { verifyInputEdits } from '../../../../../viewer/experiments/input-edits.mjs';

const run = '20260920-exp-999';
const hostile = '</script><script>globalThis.injected = true</script>&\u2028$&';
const roundTrip = value => JSON.parse(JSON.stringify(value));
async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-export-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const folder = path.join(root, run);
  async function write(name, value, lines = false) {
    const target = path.join(folder, name); await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, lines ? value.map(v => JSON.stringify(v)).join('\n') : typeof value === 'string' ? value : JSON.stringify(value));
  }
  await write('config.json', { models: [{ key: 'a', model: 'Model A' }, { key: 'b', model: 'Model B' }] });
  await write('state.json', { status: 'INCOMPLETE' });
  await write('summary.json', { status: 'INCOMPLETE', originals: 2, variants: 2 });
  await write('plan.json', { models: [{ key: 'a', requests: 4 }, { key: 'b', requests: 4 }] });
  const variants = ['ORIGINAL', 'EA_01', 'ORIGINAL', 'EA_01'];
  const rows = variants.map((variant, i) => ({ trial_id: `trial-${i}`, item_id: `item-${i}`, case: i < 2 ? 'case-1' : 'case-2', variant,
    experiment: variant === 'ORIGINAL' ? 1 : 2, prompt_condition: 'P0', reasoning: 'off',
    status: ['VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'NOT_RUN'][i],
    checks: i === 0 ? { numeric_comparison: { matches: true } } : {}, response: i === 0 ? { answer: '42', evidence: [hostile] } : undefined }));
  await write('01-input/public.jsonl', rows.map(r => ({ item_id: r.item_id, question: 'Sales?', context: hostile })), true);
  await write('01-input/private.jsonl', rows.map(r => ({ item_id: r.item_id, case: r.case, variant: r.variant, reference: { reference_answer: '42' }, source: '/outside/secret' })), true);
  const diagnostics = [];
  for (const model of ['a', 'b']) {
    const requests = rows.map(r => ({ trial_id: r.trial_id, item_id: r.item_id, case: r.case, experiment: r.experiment, variant: r.variant,
      input: { question: 'Sales?', context: hostile }, prompt: 'Read only.', response_schema: { title: r.variant === 'ORIGINAL' ? 'V2' : 'V4', type: 'object' } }));
    const results = rows.map((r, i) => ({ ...r, checks: i === 0 ? { numeric_comparison: { matches: model === 'a' } } : {},
      ...(i < 3 ? { call_path: `${model}/calls/${r.trial_id}/call.json`, result_path: `${model}/calls/${r.trial_id}/result.json` } : {}) }));
    for (const [i, row] of results.entries()) {
      diagnostics.push({ model, trial_id: row.trial_id, tags: i === 1 ? ['A', 'B'] : ['B'] });
      if (i === 3) continue;
      const response = i === 0 ? row.response : i === 1 ? { answer: 42, answer_meta: { status: 'abstained', negative: false, scale: 'raw' }, evidence: [hostile] } : null;
      await write(row.call_path, { request: requests[i], response, response_text: i === 2 ? '{"answer":' : JSON.stringify(response), records: { raw_response_path: `${model}/calls/${row.trial_id}/raw-response.json`, attempts: [{ attempt: 'attempt-001', status: row.status, result_path: row.result_path }] } });
      await write(row.result_path, { response, schema_errors: i ? [{ message: hostile }] : [], usage: { output_tokens: 5 }, elapsed_seconds: i + (model === 'a' ? 0.125 : 0.875) });
      await write(`${model}/calls/${row.trial_id}/raw-response.json`, { text: hostile });
    }
    await write(`${model}/01-requests/manifest.jsonl`, requests, true);
    await write(`${model}/03-results/results.jsonl`, results, true);
    await write(`${model}/03-results/summary.json`, { planned: 4, statuses: { VALID: 1, INVALID_RESPONSE: 1, OUTPUT_TRUNCATED: 1, NOT_RUN: 1 } });
  }
  await write('analysis/response-diagnostics.jsonl', diagnostics, true);
  await write('REPORT.md', `# Report\n[History](analysis/previous.md) [Raw](a/calls/trial-1/raw-response.json) [Outside](../secret)\n${hostile}`);
  await write('analysis/previous.md', '[Back](../REPORT.md) [Data](notes.json)');
  await write('analysis/notes.json', { text: hostile });
  await write('events.jsonl', [{ event: 'FINISHED' }], true);
  const repo = new Repository(root), snap = await repo.snapshot(run);
  return { root, folder, write, repo, snap };
}

test('offline/live aggregates, filters, paired comparisons and pagination stay identical', async t => {
  const f = await fixture(t), bundle = await buildBundle(f.repo, f.snap), offline = createOfflineStore(bundle);
  for (const filters of [{}, { status: 'FORMAT_FAILED' }, { metric: 'numeric_mismatches' }, { metric: 'numeric_unevaluated' }, { variant: 'EA_01', tags: 'A,B' }, { tags: 'A,B', tag_mode: 'any' }, { model: 'b', q: 'case-2' }, { paired: 'true' }, { offset: '3', case_offset: '1' }, { sort: 'case_desc', tags: 'B', diagnostic_sort: 'name' }, { sort: 'status_asc' }, { sort: 'model_desc' }, { sort: 'diagnostics_desc' }]) {
    const data = await offline.request(`/api/runs/${run}/overview?${new URLSearchParams(filters)}`);
    assert.deepEqual(roundTrip(data), roundTrip(f.repo.overview(f.snap, filters)));
  }
  assert.equal(bundle.stats.requests, 8); assert.equal(bundle.stats.cases, 2);
  assert.deepEqual(await offline.request(`/api/runs/${run}/rq1-materials`), await f.repo.rq1Materials(f.snap));
  assert.deepEqual(await offline.request(`/api/runs/${run}/grounding-pairs`), await f.repo.groundingPairs(f.snap));
});

test('offline case-list classification retains explicit Unguided null and historical explanation declarations', async t => {
  const f = await fixture(t);
  const file = 'a/03-results/results.jsonl';
  const rows = (await fs.readFile(path.join(f.folder, file), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  rows[0].response = { answer: '42', classification: null, explanation: 'A numeric answer.' };
  await f.write(file, rows, true);
  let snap = await f.repo.snapshot(run);
  let live = f.repo.overview(snap), offline = createOfflineStore(await buildBundle(f.repo, snap));
  assert.deepEqual(roundTrip(await offline.request(`/api/runs/${run}/overview`)), roundTrip(live));
  assert.ok(live.view.cases.some(item => item.classifications?.some(c => c.label === '분류 미요구')));

  rows[0].response = { answer: null, explanation: 'Classification: CONFLICT; Response: ABSTAIN. Contradictory figures.' };
  await f.write(file, rows, true);
  snap = await f.repo.snapshot(run);
  live = f.repo.overview(snap); offline = createOfflineStore(await buildBundle(f.repo, snap));
  assert.deepEqual(roundTrip(await offline.request(`/api/runs/${run}/overview`)), roundTrip(live));
  assert.ok(live.view.cases.some(item => item.classifications?.some(c => c.value === 'CONFLICT')));
});

test('all case conditions retain failed and truncated bodies, exact requests, missing conditions and analyst metadata', async t => {
  const f = await fixture(t), offline = createOfflineStore(await buildBundle(f.repo, f.snap));
  for (const row of f.snap.rows) {
    const filters = { case: row.case, variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning };
    assert.deepEqual(roundTrip(await offline.request(`/api/runs/${run}/case?${new URLSearchParams(filters)}`)), roundTrip(await f.repo.detail(f.snap, row.case, filters)));
  }
  const missing = await offline.request(`/api/runs/${run}/case?case=case-1&reasoning=on`);
  assert.ok(missing.responses.every(r => r.status === 'NOT_PLANNED'));
  await assert.rejects(offline.request(`/api/runs/${run}/case?case=unknown`), /없는 문항/);
});

test('case heatmap reads unselected saved responses and stays identical in exported HTML', async t => {
  const f = await fixture(t);
  const rows = (await fs.readFile(path.join(f.folder, 'a/03-results/results.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
  rows[1].status = 'VALID'; rows[1].response = { answer: 99 };
  await f.write('a/03-results/results.jsonl', rows, true);
  await f.write(rows[1].result_path, { response: { answer: null }, elapsed_seconds: 2 });
  const snap = await f.repo.snapshot(run);
  const live = await f.repo.detail(snap, 'case-1', { variant: 'ORIGINAL', reasoning: 'off', status: 'VALID' });
  const store = createOfflineStore(await buildBundle(f.repo, snap));
  const offline = await store.request(`/api/runs/${run}/case?case=case-1&variant=ORIGINAL&reasoning=off&status=VALID`);
  assert.deepEqual(offline.heatmap, live.heatmap);
  assert.equal(live.heatmap.models[0].conditions[0].cells[6].category, 'null');
  assert.equal(live.heatmap.models[1].conditions[0].cells[6].category, 'invalid');
  assert.equal(live.heatmap.models[0].conditions[0].cells[0].category, 'match');
  assert.equal(live.heatmap.models[0].conditions[0].cells[0].answer_text, '42');
  assert.equal(live.heatmap.models[0].conditions[0].cells[0].reference_matches, true);
  assert.equal(live.heatmap.models[1].conditions[0].cells[0].category, 'mismatch');
});

test('private edit provenance and request verification survive offline case loading', async t => {
  const f = await fixture(t), sha = text => createHash('sha256').update(text).digest('hex');
  const rows = [...f.snap.privateItems.values()].map(item => item.variant !== 'ORIGINAL' ? item : { ...item, edit_provenance: {
    schema_version: 1, status: 'VERIFIED', offset_unit: 'unicode_code_point',
    baseline: { case: item.case, variant: 'ORIGINAL', question_sha256: sha('Sales?'), context_sha256: sha(hostile) },
    final: { question_sha256: sha('Sales?'), context_sha256: sha(hostile) }, steps: []
  } });
  await f.write('01-input/private.jsonl', rows, true);
  const snap = await f.repo.snapshot(run), bundle = await buildBundle(f.repo, snap), offline = createOfflineStore(bundle);
  const data = await offline.request(`/api/runs/${run}/case?case=case-1&variant=ORIGINAL&reasoning=off`);
  assert.deepEqual(data.metadata.edit_provenance, rows[0].edit_provenance);
  const result = await verifyInputEdits({ caseId: data.case, variant: data.variant, original: data.original, item: data.item, request: data.responses[0].request.input, provenance: data.metadata.edit_provenance });
  assert.equal(result.status, 'UNCHANGED'); assert.equal(result.spans.map(s => s.text).join(''), hostile);
  const html = await renderHTML(bundle);
  assert.match(html, /async function verifyInputEdits/);
  assert.match(html, /function renderInputContext/);
  assert.doesNotMatch(html, /from ['"]\.\/input-edits\.mjs/);
});

test('raw files, attempts, recursive report links and activity open without server access', async t => {
  const f = await fixture(t), bundle = await buildBundle(f.repo, f.snap), offline = createOfflineStore(bundle);
  const docs = await f.repo.documents(f.snap);
  const report = await f.repo.file(f.snap, docs.find(d => d.path === 'REPORT.md').id);
  assert.equal(report.links['../secret'], undefined);
  const history = await f.repo.file(f.snap, report.links['analysis/previous.md'].id);
  await f.repo.file(f.snap, history.links['notes.json'].id);
  for (const row of f.snap.rows) await f.repo.detail(f.snap, row.case, { variant: row.variant });
  assert.deepEqual(await offline.request(`/api/runs/${run}/input-flow`), roundTrip(await f.repo.input(f.snap)));
  for (const id of Object.keys(bundle.files)) assert.deepEqual(await offline.request(`/api/runs/${run}/file?id=${id}`), await f.repo.file(f.snap, id));
  assert.deepEqual(await offline.request(`/api/runs/${run}/activity`), await f.repo.activity(f.snap));
  assert.match(await offline.request(`/api/runs/${run}/export?status=NOT_RUN`), /분모: 2 요청/);
  await assert.rejects(offline.request(`/api/runs/${run}/file?id=../../secret`));
  await assert.rejects(offline.request('/api/runs/20260920-exp-001/overview'), /선택한 회차/);
});

test('single HTML uses exact inline CSP hashes, inert data and no external assets', async t => {
  const f = await fixture(t), bundle = await buildBundle(f.repo, f.snap, { initialView: { lang: 'en', tab: 'conditions', display_metric: 'numeric_matches', status: 'VALID', sort: 'case_desc', diagnostic_sort: 'name', q: hostile, unknown: hostile } });
  const html = await renderHTML(bundle);
  assert.equal(html.includes(hostile), false);
  assert.equal((html.match(/<script\b/g) ?? []).length, 2);
  assert.ok(!/<script[^>]*src=|<link[^>]*href=|\bimport .*from /.test(html));
  const script = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1], css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  new vm.Script(script);
  assert.match(script, /function buildFeatureQuadrant\(/);
  assert.match(script, /function renderRQ1Materials\(/);
  assert.match(script, /global.FinarchI18n =/);
  assert.match(css, /viewer-language button/);
  for (const value of [script, css]) assert.ok(html.includes(`sha256-${createHash('sha256').update(value).digest('base64')}`));
  assert.match(html, /connect-src 'none'/);
  const restored = JSON.parse(html.match(/id="experiment-snapshot">([\s\S]*?)<\/script>/)[1]);
  assert.deepEqual(restored.initial_view, { lang: 'en', tab: 'conditions', display_metric: 'numeric_matches', status: 'VALID', sort: 'case_desc', diagnostic_sort: 'name', q: hostile });
  assert.equal((await createOfflineStore(restored).request(`/api/runs/${run}/case?case=case-1`)).item.context, hostile);
});

test('stale snapshots, changed raw artifacts and symlinks cannot yield a misleading successful export', async t => {
  const f = await fixture(t);
  await assert.rejects(buildBundle(f.repo, { ...f.snap, stale: true }), /정상 자료/);
  const altered = new Repository(f.root);
  const originalResponse = altered.response.bind(altered);
  altered.response = async (...args) => { const data = await originalResponse(...args); if (args[1].case === 'case-2') await fs.writeFile(path.join(f.folder, 'a/calls/trial-0/raw-response.json'), '{"changed":true}'); return data; };
  await assert.rejects(buildBundle(altered, f.snap), /갱신/);
  await fs.unlink(path.join(f.folder, 'a/calls/trial-0/raw-response.json'));
  await fs.symlink('/etc/hosts', path.join(f.folder, 'a/calls/trial-0/raw-response.json'));
  await assert.rejects(buildBundle(f.repo, f.snap), /심볼릭/);
});

test('missing requests stop export; oversized linked files disclose the existing viewer limit', async t => {
  const f = await fixture(t);
  await f.write('large.txt', 'x'.repeat(8 * 1024 * 1024 + 1));
  await f.write('REPORT.md', '[Large](large.txt)');
  const bundle = await buildBundle(f.repo, f.snap), reader = createOfflineStore(bundle);
  assert.equal(bundle.stats.unavailable_files.length, 1);
  const report = await reader.request(`/api/runs/${run}/file?id=${bundle.documents.find(d => d.path === 'REPORT.md').id}`);
  await assert.rejects(reader.request(`/api/runs/${run}/file?id=${report.links['large.txt'].id}`), /8MB/);
  await f.write('a/01-requests/manifest.jsonl', [] , true);
  const incomplete = await f.repo.snapshot(run);
  assert.equal(incomplete.stale, true);
  assert.ok(incomplete.warnings.some(value => value.includes('요청 목록이 비어')));
  await assert.rejects(buildBundle(f.repo, incomplete), /마지막 정상 자료/);
});

test('cancelled downloads stop work before reading and corrupt chunks fail explicitly', async t => {
  const f = await fixture(t), controller = new AbortController(); controller.abort();
  await assert.rejects(buildBundle(f.repo, f.snap, { signal: controller.signal }), { name: 'AbortError' });
  const bundle = await buildBundle(f.repo, f.snap); bundle.chunks.index = 'broken';
  await assert.rejects(createOfflineStore(bundle).request('/api/runs'));
});

test('HTTP exports an attachment with the full run even when an initial filter is supplied', async t => {
  const f = await fixture(t), server = createServer({ root: f.root });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const response = await fetch(`http://127.0.0.1:${server.address().port}/api/runs/${run}/export-html?status=VALID`);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('content-disposition'), `attachment; filename="${run}-experiments.html"`);
  const html = await response.text();
  const data = JSON.parse(html.match(/id="experiment-snapshot">([\s\S]*?)<\/script>/)[1]);
  assert.equal(data.stats.requests, 8);
  const reader = createOfflineStore(data);
  assert.equal((await reader.request(`/api/runs/${run}/overview?status=NOT_RUN`)).view.aggregate.total, 2);
});


test('ANSWERABLE export preserves every raw category and missing/null rows', async t => {
  const f = await fixture(t);
  const rows = [{semantic_answerability:'SUPPORTED_ANSWER'}, {semantic_answerability:'NEW_VALUE'}, {semantic_answerability:null}, {}];
  const payload = rows.map(r=>JSON.stringify(r)).join('\n');
  await f.write('02_analysis/05_outcomes/responses.jsonl', payload);
  await f.write('02_analysis/05_outcomes/summary.json', {schema_version:'ResponseOutcomeV1', run,
    categories:{}, scopes:{all:{total:4}}, source_hashes:{}, latest_attempts:{},
    output_hashes:{'responses.jsonl':createHash('sha256').update(payload).digest('hex')}});
  const bundle = await buildBundle(f.repo, await f.repo.snapshot(run), {initialView:{tab:'answerable'}});
  const data = await createOfflineStore(bundle).request(`/api/runs/${run}/semantic-outcomes?scope=all`);
  assert.equal(data.total, 4);
  assert.equal(Object.values(data.counts).reduce((a,b)=>a+b,0),4);
  assert.equal(data.counts['\0null'],1);
  assert.equal(data.counts['\0missing'],1);
  assert.equal(data.counts.NEW_VALUE,1);
  const html=await renderHTML(bundle);
  assert.match(html, /async function renderSemanticOutcomes/);
  assert.match(html, /function outcomePage/);
  assert.equal(bundle.initial_view.tab,'answerable');
});
