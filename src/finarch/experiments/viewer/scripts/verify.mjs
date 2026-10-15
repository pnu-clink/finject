import { projectDirectory, assetDirectory } from '../paths.mjs';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { Repository, aggregate } from '../repository.mjs';
import { defaultRoot } from '../server.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const project = projectDirectory;
const logDir = path.join(project, 'log/viewer-experiments-v1');
await fs.mkdir(logDir, { recursive: true });
const tests = spawnSync(process.execPath, ['--test', path.join(directory, '../tests/repository.test.mjs')], { encoding: 'utf8' });
await fs.writeFile(path.join(logDir, 'tests.log'), tests.stdout + tests.stderr);
assert.equal(tests.status, 0, 'Viewer boundary tests must pass');
const repo = new Repository(defaultRoot);
const verification = { at: new Date().toISOString(), status: 'PASS', model_calls_added: 0, result_files_written: 0, local_test_exit_code: tests.status, runs: [] };
const hash = async file => createHash('sha256').update(await fs.readFile(file)).digest('hex');
for (const run of await repo.runs()) {
  const start = performance.now(), snap = await repo.snapshot(run.id), overview = repo.overview(snap, {});
  const files = ['01-input/public.jsonl', '01-input/private.jsonl', ...snap.config.models.flatMap(m => [`${m.key}/03-results/results.jsonl`, `${m.key}/01-requests/manifest.jsonl`])];
  const hashes = Object.fromEntries(await Promise.all(files.map(async f => [f, await hash(path.join(snap.root, f))])));
  for (const model of snap.summaries) {
    const totals = aggregate(snap.rows.filter(r => r.model === model.key));
    assert.equal(totals.total, model.planned);
    assert.deepEqual(totals.statuses, model.statuses);
  }
  const samples = [];
  for (const status of ['VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'NOT_RUN', 'AUTH_BLOCKED']) {
    const row = snap.rows.find(r => r.status === status); if (!row) continue;
    const detail = await repo.detail(snap, row.case, { variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning });
    const response = detail.responses.find(r => r.model === row.model);
    assert.equal(response.status, status); assert.ok(response.request, 'An exact request must be available');
    assert.equal(response.request.trial_id, row.trial_id);
    if (status === 'VALID') assert.ok(response.response);
    for (const file of response.artifacts) await repo.file(snap, file.id);
    samples.push({ model: row.model, case: row.case, status, has_response: !!response.response, artifacts_opened: response.artifacts.length });
  }
  const docs = await repo.documents(snap);
  for (const doc of docs) await repo.file(snap, doc.id);
  for (const [file, digest] of Object.entries(hashes)) assert.equal(await hash(path.join(snap.root, file)), digest, 'Source files must remain unchanged');
  verification.runs.push({ id: run.id, state: overview.status, totals: overview.view.aggregate, warnings: overview.warnings, documents_read: docs.length, samples, source_sha256: hashes, elapsed_ms: Math.round(performance.now() - start) });
}
await fs.writeFile(path.join(logDir, 'verification.json'), JSON.stringify(verification, null, 2) + '\n');
console.log(JSON.stringify({ status: verification.status, runs: verification.runs.map(r => ({ id: r.id, total: r.totals.total, documents: r.documents_read })), log: path.relative(project, logDir), model_calls_added: 0 }));
