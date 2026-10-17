import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Repository, aggregate, filterRows, safePath } from '../repository.mjs';
import { createServer } from '../server.mjs';

const run = '20260920-exp-999';
async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-viewer-exp-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const folder = path.join(root, run);
  const write = async (name, value, lines = false) => { const file = path.join(folder, name); await fs.mkdir(path.dirname(file), { recursive: true }); await fs.writeFile(file, lines ? value.map(v => JSON.stringify(v)).join('\n') + '\n' : JSON.stringify(value)); };
  const row = { trial_id: 'trial-a', item_id: 'item-a', case: 'test-0001', experiment: 1, variant: 'ORIGINAL', prompt_condition: 'P0', reasoning: 'off', status: 'INVALID_RESPONSE', result_path: 'model/calls/test-0001/00-Original/_records/trial-a/attempt-001/result.json', call_path: 'model/calls/test-0001/00-Original/test-0001-P0-R-off.json' };
  const response = { answer: 42, explanation: '<script>bad()</script>', evidence: ['Sales 42'] };
  const request = { ...row, input: { question: 'What are sales?', context: 'Sales 42' }, response_schema: { title: 'V2', type: 'object' }, prompt: 'Answer.' };
  await write('config.json', { models: [{ key: 'model', model: 'Model' }] });
  await write('state.json', { status: 'FINISHED' });
  await write('summary.json', { status: 'FINISHED', originals: 1, variants: 0, models: [{ model: 'model' }] });
  await write('plan.json', { models: [{ key: 'model', requests: 1 }] });
  await write('01-input/public.jsonl', [{ item_id: 'item-a', question: 'What are sales?', context: 'Sales 42' }], true);
  await write('01-input/private.jsonl', [{ item_id: 'item-a', case: 'test-0001', variant: 'ORIGINAL', reference: { reference_answer: '42' }, source: '/not/allowed/secret.json' }], true);
  await write('model/03-results/results.jsonl', [row], true);
  await write('model/03-results/summary.json', { model: 'model', planned: 1, statuses: { INVALID_RESPONSE: 1 }, billed_cost_usd: null });
  await write('model/01-requests/manifest.jsonl', [request], true);
  await write(row.result_path, { status: 'INVALID_RESPONSE', response, schema_errors: [{ message: 'Expected string.' }] });
  await write(row.call_path, { request, response, response_text: JSON.stringify(response), records: { attempts: [] } });
  return { root, folder, write, row, response, repository: new Repository(root) };
}

test('counts preserve unassessed originals and exclude variants from numeric denominator', () => {
  const rows = [
    { case: 'a', experiment: 1, status: 'VALID', checks: { numeric_comparison: { matches: true } } },
    { case: 'b', experiment: 1, status: 'INVALID_RESPONSE' },
    { case: 'a', experiment: 2, status: 'VALID', checks: { declared_abstention: true } },
    { case: 'b', experiment: 2, status: 'NOT_RUN' }
  ];
  const a = aggregate(rows);
  assert.deepEqual([a.total, a.cases, a.numeric_eligible, a.numeric_compared, a.numeric_matches, a.numeric_unevaluated, a.collected], [4, 2, 2, 1, 1, 1, 3]);
});

test('duplicate diagnostic tags do not duplicate requests; all/any filters differ', () => {
  const rows = [{ tags: ['A', 'B'], status: 'INVALID_RESPONSE' }, { tags: ['A'], status: 'OUTPUT_TRUNCATED' }, { tags: ['B'], status: 'VALID' }];
  assert.equal(filterRows(rows, { tags: 'A,B', tag_mode: 'all' }).length, 1);
  assert.equal(filterRows(rows, { tags: 'A,B', tag_mode: 'any', status: 'FORMAT_FAILED' }).length, 2);
});

test('failed responses absent in summary rows remain visible from original attempt', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run);
  const detail = await f.repository.detail(snap, 'test-0001', {});
  assert.deepEqual(detail.responses[0].response, f.response);
  assert.equal(detail.responses[0].schema_errors.length, 1);
  assert.equal(detail.responses[0].request.input.context, 'Sales 42');
  assert.equal(detail.original_metadata.reference.reference_answer, '42');
  assert.equal('reference' in detail.responses[0].request.input, false);
});

test('path escapes, absolute paths and symlinks are rejected', async t => {
  const f = await fixture(t);
  await assert.rejects(safePath(f.folder, '../secret'));
  await assert.rejects(safePath(f.folder, '/etc/passwd'));
  await fs.symlink(os.tmpdir(), path.join(f.folder, 'outside'));
  await assert.rejects(safePath(f.folder, 'outside/something'), /\uc2ec\ubcfc\ub9ad/);
  await assert.rejects(f.repository.snapshot('../other'));
});

test('model version dots are listed and resolved without permitting path escapes', async t => {
  const f = await fixture(t);
  const versioned = '20260929-exp-003-a100-financereasoning-qwen3.8-27b';
  await fs.rename(f.folder, path.join(f.root, versioned));
  assert.equal((await f.repository.runs())[0].id, versioned);
  const actual = await fs.realpath(path.join(f.root, versioned));
  assert.equal(await f.repository.runPath(versioned), actual);
  assert.equal(await f.repository.runPath('20260929-exp-003'), actual);
  for (const suffix of ['qwen..27b', 'qwen.27b/other', 'qwen.']) {
    await assert.rejects(f.repository.runPath('20260929-exp-003-' + suffix));
  }
});

test('dated Fin-o1 runs use the standard viewer layout and reject unsafe names', async t => {
  const f = await fixture(t);
  for (const key of ['8b', '14b']) {
    const id = '20261002-fin-o1-' + key;
    await fs.cp(f.folder, path.join(f.root, id), { recursive: true });
    assert.equal(await f.repository.runPath(id), await fs.realpath(path.join(f.root, id)));
    const snap = await f.repository.snapshot(id);
    assert.equal(snap.id, id);
  }
  const listed = (await f.repository.runs()).map(row => row.id);
  assert.ok(listed.includes('20261002-fin-o1-8b'));
  assert.ok(listed.includes('20261002-fin-o1-14b'));
  for (const bad of ['20261002-fin-o1-8b/other', '20261002-fin-o1-..', '20261002-fino1-recovery']) {
    await assert.rejects(f.repository.runPath(bad));
  }
});

test('other-condition time reads preserve zero and isolate a partially written result', async t => {
  const f = await fixture(t), other = { ...f.row, trial_id: 'trial-b', reasoning: 'on', result_path: 'model/other-result.json', call_path: null };
  await f.write('model/03-results/results.jsonl', [f.row, other], true);
  await f.write(f.row.result_path, { response: f.response, elapsed_seconds: 0 });
  await f.write(other.result_path, { elapsed_seconds: 2.75 });
  const snap = await f.repository.snapshot(run);
  const detail = await f.repository.detail(snap, 'test-0001', { reasoning: 'off' });
  assert.equal(detail.conditions[0].models[0].elapsed_seconds, 0);
  assert.equal(detail.conditions[1].models[0].elapsed_seconds, 2.75);
  assert.equal(detail.conditions[2].available, false);
  await fs.writeFile(path.join(f.folder, other.result_path), '{"elapsed_seconds":');
  const partial = await f.repository.detail(snap, 'test-0001', { reasoning: 'off' });
  assert.deepEqual(partial.responses[0].response, f.response);
  assert.equal(partial.conditions[1].models[0].elapsed_seconds, null);
  assert.equal(partial.conditions[1].models[0].timing_error, true);
  assert.equal(partial.heatmap.models[0].conditions[1].cells[0].category, 'read_error');
});

test('unfinished writes preserve the last complete snapshot and show stale warning', async t => {
  const f = await fixture(t), before = await f.repository.snapshot(run);
  await fs.writeFile(path.join(f.folder, 'model/03-results/results.jsonl'), '{"incomplete":');
  const during = await f.repository.snapshot(run);
  assert.equal(during.stale, true); assert.equal(during.rows.length, before.rows.length);
  assert.ok(during.warnings.some(w => w.includes('마지막 정상 자료')));
  await f.write('model/03-results/results.jsonl', [{ ...f.row, status: 'NOT_RUN' }], true);
  const after = await f.repository.snapshot(run);
  assert.equal(after.rows[0].status, 'NOT_RUN'); assert.ok(!after.stale);
});

test('an initial malformed file fails visibly and does not fabricate an empty run', async t => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.folder, '01-input/public.jsonl'), '{');
  await assert.rejects(f.repository.snapshot(run), /\uc644\uc131\ub418\uc9c0/);
});

test('duplicate result IDs fail instead of inflating denominators', async t => {
  const f = await fixture(t);
  await f.write('model/03-results/results.jsonl', [f.row, f.row], true);
  await assert.rejects(f.repository.snapshot(run), /\uc911\ubcf5 \uc694\uccad/);
});

test('model manifests supply unique item totals and logs supply exclusion history', async t => {
  const f = await fixture(t);
  const request = { ...f.row, input: { question: 'What are sales?', context: 'Sales 42' } };
  const requests = [request, { ...request, trial_id: 'trial-on', reasoning: 'on' }];
  await f.write('config.json', { models: [{ key: 'model' }, { key: 'second' }] });
  await f.write('model/01-requests/manifest.jsonl', requests, true);
  await f.write('second/01-requests/manifest.jsonl', requests, true);
  await f.write('summary.json', { originals: 999, variants: 999 });
  await f.write('input-selection.json', { originals: 888, variants: 888 });
  await f.write('events.jsonl', [{ event: 'INPUT_SELECTION', exclusions: [{ case: 'excluded', reason: 'EXPLICIT_EXCLUSION' }] }], true);
  const snap = await f.repository.snapshot(run), overview = f.repository.overview(snap);
  assert.deepEqual([overview.originals, overview.variants, overview.selection.exclusions], [1, 0, 1]);
  assert.equal(overview.selection.source, 'MODEL_REQUEST_MANIFESTS');
  assert.equal(overview.selection.manifest_files.length, 2);
  assert.ok(overview.warnings.some(value => value.includes('고유 문항 수')));
  await fs.unlink(path.join(f.folder, 'input-selection.json'));
  await fs.unlink(path.join(f.folder, 'events.jsonl'));
  const after = f.repository.overview(await f.repository.snapshot(run));
  assert.equal(after.originals, 1);
  assert.equal(after.selection.exclusions, null);
});

test('contradictory manifest identities fail rather than guessing from private data', async t => {
  const f = await fixture(t);
  await f.write('model/01-requests/manifest.jsonl', [f.row, { ...f.row, trial_id: 'other', case: 'different-case' }], true);
  await assert.rejects(f.repository.snapshot(run), /\ubb38\ud56d \uc5f0\uacb0 \uc815\ubcf4\uac00 \uc11c\ub85c/);
});

test('semantic judgments join exact trial identities and preserve audit uncertainty', async t => {
  const f = await fixture(t);
  const semantic = { ...f.row, model: 'model', semantic_assessed: false, appropriate: null,
    audit_disagreement: true, review: { outcome: 'SUPPORTED_ANSWER', reasoning: 'Provisional.' } };
  await f.write('02_analysis/02_comparison/rows.jsonl', [semantic], true);
  await f.write('02_analysis/02_comparison/summary.json', { overall: { planned: 1, assessed: 0, unassessed: 1 } });
  await f.write('02_analysis/01_response_review/01-LLM-input/state.json', { status: 'COLLECTED', requests: 2, statuses: { VALID: 1 }, token_cost_estimate_usd: 0.25 });
  await f.write('02_analysis/01_response_review/01-LLM-input/retry-001/state.json', { status: 'COLLECTED', requests: 1, statuses: { VALID: 1 }, token_cost_estimate_usd: 0.1 });
  const snap = await f.repository.snapshot(run), overview = f.repository.overview(snap);
  assert.equal(overview.semantic.overall.assessed, 0);
  assert.equal(overview.semantic_cases[0].appropriate, null);
  assert.equal(overview.review_stages[0].token_cost_estimate_usd, 0.35);
  assert.equal((await f.repository.detail(snap, 'test-0001', {})).responses[0].semantic.audit_disagreement, true);
});

test('foreign, duplicate, or mismatched semantic judgments fail closed', async t => {
  const f = await fixture(t), semantic = { ...f.row, model: 'model' };
  for (const [rows, message] of [
    [[semantic, semantic], /\uc911\ubcf5 \uc694\uccad/],
    [[{ ...semantic, trial_id: 'not-a-real-request' }], /\uc2e4\uc81c \uc694\uccad\uc5d0 \uc5c6\ub294/],
    [[{ ...semantic, case: 'wrong-case' }], /\uc5f0\uacb0\uc774 \ub2e4\ub985\ub2c8\ub2e4/]
  ]) {
    await f.write('02_analysis/02_comparison/rows.jsonl', rows, true);
    await assert.rejects(new Repository(f.root).snapshot(run), message);
  }
});

test('state overrides stale summary without relabeling prepared requests as completed', async t => {
  const f = await fixture(t);
  await f.write('state.json', { status: 'SUPERSEDED_NOT_RUN' });
  const snap = await f.repository.snapshot(run), overview = f.repository.overview(snap, {});
  assert.equal(overview.status, 'SUPERSEDED_NOT_RUN');
  assert.ok(overview.warnings.some(w => w.includes('실행 상태')));
  assert.equal(overview.models[0].billed_cost_usd, null);
});

test('Markdown links are registered only inside the selected run and kept inert', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run);
  await fs.writeFile(path.join(f.folder, 'REPORT.md'), '[Local](summary.json) [Escape](../../secret) <script>bad()</script>');
  const docs = await f.repository.documents(snap);
  const report = await f.repository.file(snap, docs.find(d => d.path === 'REPORT.md').id);
  assert.ok(report.links['summary.json']); assert.equal(report.links['../../secret'], undefined);
  assert.ok(report.content.includes('<script>'));
  await assert.rejects(f.repository.file(snap, '../../secret'));
});

test('paired export and displayed totals use the same model intersection', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run);
  const row = { ...f.row, status: 'VALID', tags: [], checks: { numeric_comparison: { matches: true } } };
  snap.config.models = [{ key: 'a' }, { key: 'b' }];
  snap.rows = [{ ...row, model: 'a', case: 'paired' }, { ...row, model: 'b', case: 'paired' }, { ...row, model: 'a', case: 'single' }];
  const filters = { paired: 'true' }, view = f.repository.query(snap, filters), exported = f.repository.export(snap, filters);
  assert.equal(view.aggregate.total, 2); assert.equal(view.aggregate.cases, 1);
  assert.ok(exported.includes('문항: paired')); assert.ok(!exported.includes('single'));
});

test('read-only HTTP denies mutations, foreign origins, unknown artifacts and arbitrary files', async t => {
  const f = await fixture(t), server = createServer({ root: f.root });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(`${url}/api/runs`)).status, 200);
  const jsonViewer = await fetch(`${url}/json-viewer.mjs`);
  assert.equal(jsonViewer.status, 200);
  assert.match(jsonViewer.headers.get('content-type'), /text\/javascript/);
  assert.match(await jsonViewer.text(), /export function valueView/);
  assert.equal((await fetch(`${url}/api/runs`, { method: 'POST' })).status, 405);
  assert.equal((await fetch(`${url}/api/runs`, { headers: { Origin: 'https://unrelated.example' } })).status, 403);
  assert.equal((await fetch(`${url}/.env`)).status, 404);
  assert.equal((await fetch(`${url}/api/runs/${run}/file?id=unknown`)).status, 404);
});
