import { projectDirectory, assetDirectory } from '../paths.mjs';
import assert from 'node:assert/strict';
import { promises as fs, createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { Repository } from '../repository.mjs';
import { exportHTML } from '../export-html.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { defaultRoot } from '../server.mjs';

// [EV09.1] Compare real saved runs without experiments or model calls.
const directory = path.dirname(fileURLToPath(import.meta.url)), project = projectDirectory;
const logDir = path.join(project, 'log/viewer-experiments-html-export'), outputDir = path.join(project, 'outputs/experiment-exports');
await fs.mkdir(logDir, { recursive: true }); await fs.mkdir(outputDir, { recursive: true });
const tests = spawnSync(process.execPath, ['--test', path.join(directory, '../tests/repository.test.mjs'), path.join(directory, '../tests/export-html.test.mjs')], { encoding: 'utf8' });
await fs.writeFile(path.join(logDir, 'tests.log'), tests.stdout + tests.stderr);
assert.equal(tests.status, 0);
const roundTrip = value => JSON.parse(JSON.stringify(value));
async function hash(file) { const digest = createHash('sha256'); for await (const data of createReadStream(file)) digest.update(data); return digest.digest('hex'); }
const runs = process.argv.slice(2);
if (!runs.length) throw Error('Specify the saved experiment run IDs to verify.');
const verification = { at: new Date().toISOString(), status: 'RUNNING', tests: Number(tests.stdout.match(/tests (\d+)/)?.[1]), model_calls_added: 0, source_files_written: 0, runs: [] };
const repository = new Repository(defaultRoot);
for (const run of runs) {
  const started = performance.now(), snap = await repository.snapshot(run);
  const sources = ['01-input/public.jsonl', '01-input/private.jsonl', ...snap.config.models.flatMap(m => [`${m.key}/03-results/results.jsonl`, `${m.key}/01-requests/manifest.jsonl`])];
  const before = Object.fromEntries(await Promise.all(sources.map(async p => [p, await hash(path.join(snap.root, p))])));
  const result = await exportHTML(repository, snap, { initialView: { tab: 'conditions' }, progress(info) { if (info.completed % 25 === 0 || info.completed === info.total) console.log(JSON.stringify(info)); } });
  const reader = createOfflineStore(result.bundle), base = `/api/runs/${run}`;
  const filterChecks = [{}, { status: 'FORMAT_FAILED' }, { status: 'NOT_RUN' }, { metric: 'numeric_mismatches' }, { metric: 'numeric_unevaluated' }, { variant: 'EA_01', prompt: 'P1', reasoning: 'on' }, { paired: 'true' }, { offset: '30', case_offset: '25' }];
  for (const filters of filterChecks) assert.deepEqual(roundTrip(await reader.request(`${base}/overview?${new URLSearchParams(filters)}`)), roundTrip(repository.overview(snap, filters)));
  const samples = [];
  for (const model of snap.config.models) for (const status of [...new Set(snap.rows.filter(r => r.model === model.key).map(r => r.status))]) {
    const row = snap.rows.find(r => r.model === model.key && r.status === status);
    const filters = { case: row.case, variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning };
    const detail = await reader.request(`${base}/case?${new URLSearchParams(filters)}`);
    assert.deepEqual(roundTrip(detail), roundTrip(await repository.detail(snap, row.case, filters)));
    for (const response of detail.responses) for (const file of response.artifacts ?? []) assert.deepEqual(await reader.request(`${base}/file?id=${file.id}`), await repository.file(snap, file.id));
    samples.push({ model: model.key, case: row.case, variant: row.variant, status });
  }
  for (const document of await repository.documents(snap)) assert.deepEqual(await reader.request(`${base}/file?id=${document.id}`), await repository.file(snap, document.id));
  assert.deepEqual(await reader.request(`${base}/activity`), await repository.activity(snap));
  for (const [name, digest] of Object.entries(before)) assert.equal(await hash(path.join(snap.root, name)), digest);
  const output = path.join(outputDir, result.filename);
  await fs.writeFile(output, result.html);
  const entry = { id: run, status: result.bundle.run.status, ...result.bundle.stats, html_bytes: Buffer.byteLength(result.html), html_sha256: await hash(output), output: path.relative(project, output), filter_checks: filterChecks.length, samples, source_sha256: before, elapsed_ms: Math.round(performance.now() - started) };
  verification.runs.push(entry);
  await fs.writeFile(path.join(logDir, 'verification.json'), JSON.stringify(verification, null, 2) + '\n');
  console.log(JSON.stringify({ event: 'RUN_EXPORT_VERIFIED', ...entry, source_sha256: undefined }));
}
verification.status = 'PASS';
await fs.writeFile(path.join(logDir, 'verification.json'), JSON.stringify(verification, null, 2) + '\n');
