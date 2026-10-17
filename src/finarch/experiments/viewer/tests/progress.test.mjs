import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { buildProgress } from '../progress.mjs';
import { createServer } from '../server.mjs';

const baseTime = Date.parse('2026-09-27T12:00:00Z');
const iso = seconds => new Date(baseTime + seconds * 1000).toISOString();
const start = (id, trial, seconds, extra = {}) => ({ span_id: id, trial_id: trial, stage: '02_comparison',
  step: 'model_call', pid: 10, event: 'START', started_at: iso(seconds), attempt: 1, ...extra });
const end = (row, seconds, result_status = 'VALID') => ({ ...row, event: 'END', ended_at: iso(seconds),
  elapsed_seconds: (Date.parse(iso(seconds)) - Date.parse(row.started_at)) / 1000, status: 'COMPLETED', result_status });
const options = () => ({ id: '20260927-exp-999', config: { analysis: { backend: 'codex' } },
  rootState: { status: 'FINISHED' }, stages: { '02_comparison': { requests: 10, completed: 3, valid: 2, status: 'RUNNING' } },
  scheduler: { pid: 10, stage: '02_comparison', status: 'RUNNING', current_limit: 20, policy: { concurrency: 20 } },
  timingEvents: [], events: [], now: baseTime + 900000, alive: pid => pid === 10 });

test('counts reconcile while failures stay in remaining and outside successful average', () => {
  const a = start('a', 'a', 0), b = start('b', 'b', 10), failure = start('f', 'f', 0), active = start('r', 'r', 800);
  const data = buildProgress({ ...options(), timingEvents: [a, b, failure, active, end(a, 120), end(b, 250), end(failure, 600, 'UNKNOWN_DELIVERY')] });
  assert.deepEqual(data.counts, { total: 10, completed: 2, running: 1, waiting: 6, errors: 1, remaining: 8, consistent: true });
  assert.equal(data.metrics.mean_seconds, 180);
  assert.equal(data.metrics.p95_seconds, 240);
  assert.equal(data.metrics.timed_failure_count, 1);
  assert.equal(data.charts.averages.at(-1).seconds, 180);
  assert.equal(data.charts.history.at(-1).running, 1);
});

test('a retry is one request and historical failed attempts are excluded from the mean', () => {
  const old = start('old', 'same', 0), next = start('next', 'same', 601, { attempt: 2 });
  const settings = options(); settings.stages['02_comparison'] = { requests: 1, completed: 1, valid: 1 };
  const data = buildProgress({ ...settings, timingEvents: [old, end(old, 600, 'UNKNOWN_DELIVERY'), next, end(next, 701)] });
  assert.equal(data.counts.completed, 1); assert.equal(data.counts.errors, 0);
  assert.equal(data.metrics.mean_seconds, 100); assert.equal(data.metrics.samples, 1);
});

test('an active retry is not simultaneously counted as a terminal failure', () => {
  const old = start('old', 'same', 0), next = start('next', 'same', 601, { attempt: 2 });
  const settings = options(); settings.stages['02_comparison'] = { requests: 2, completed: 1, valid: 0 };
  const data = buildProgress({ ...settings, timingEvents: [old, end(old, 600, 'INVALID_RESPONSE'), next] });
  assert.deepEqual([data.counts.running, data.counts.errors, data.counts.waiting], [1, 0, 1]);
});

test('dead owners do not leave fake running calls or fabricated durations', () => {
  const data = buildProgress({ ...options(), timingEvents: [start('dead', 'dead', 0)], alive: () => false });
  assert.equal(data.counts.running, 0); assert.equal(data.status, 'INTERRUPTED');
  assert.equal(data.metrics.mean_seconds, null); assert.deepEqual(data.charts.history, []);
});

test('missing plans and time records stay unknown, including for prepared runs', () => {
  const data = buildProgress({ ...options(), stages: {}, timingEvents: [], scheduler: null });
  assert.equal(data.counts.total, null); assert.equal(data.counts.completed, null);
  assert.equal(data.metrics.mean_seconds, null); assert.deepEqual(data.charts.calls, []);
});

test('API Batch status does not require a local Codex scheduler', () => {
  const settings = options(); settings.config.analysis.backend = 'api';
  const data = buildProgress({ ...settings, scheduler: null });
  assert.equal(data.status, 'RUNNING');
});

test('live Python preparation is visible before any model request is planned', () => {
  const row = { span_id: 'prepare', step: 'result_collection', event: 'START', pid: 10, started_at: iso(0) };
  const data = buildProgress({ ...options(), stages: {}, scheduler: null, timingEvents: [row] });
  assert.equal(data.status, 'PREPARING');
  assert.equal(data.activity.processor, 'PYTHON');
  assert.equal(data.activity.elapsed_seconds, 900);
  assert.equal(data.counts.total, null);
  assert.match(data.warnings.join(' '), /Codex \ud638\ucd9c\uc740 \uc544\uc9c1 \uc2dc\uc791\ud558\uc9c0/);
  assert.equal(buildProgress({ ...options(), stages: {}, scheduler: null, timingEvents: [row], alive: () => false }).status, 'NOT_STARTED');
  assert.equal(buildProgress({ ...options(), stages: {}, scheduler: null, timingEvents: [row, { ...row, event: 'END' }] }).status, 'NOT_STARTED');
});

test('provider probe explains the serial wait without counting the configured limit as active calls', () => {
  const settings = options(); settings.scheduler.status = 'PROVIDER_PROBE'; settings.scheduler.current_limit = 100;
  const data = buildProgress({ ...settings, timingEvents: [start('probe', 'probe', 600)] });
  assert.equal(data.status, 'PROVIDER_PROBE');
  assert.equal(data.counts.running, 1);
  assert.equal(data.scheduler.limit, 100);
  assert.equal(data.activity.elapsed_seconds, 300);
  assert.match(data.warnings.join(' '), /\uccab Codex \uc751\ub2f5/);
  assert.equal(buildProgress({ ...settings, timingEvents: [], alive: () => false }).status, 'INTERRUPTED');
});

test('A02 and A03 counts and timing samples cannot mix', () => {
  const a = start('a', 'a', 0), b = start('b', 'b', 0, { stage: '03_research' });
  const settings = options(); settings.stages['03_research'] = { requests: 2, completed: 1, valid: 1 };
  const data = buildProgress({ ...settings, selectedStage: '03_research', timingEvents: [end(a, 100), end(b, 300)] });
  assert.equal(data.counts.total, 2); assert.equal(data.metrics.mean_seconds, 300); assert.equal(data.charts.calls.length, 1);
  assert.equal(data.scheduler.last_cpu_sample, null);
});

test('A04 preparation failure wins over a completed A03 scheduler without inventing requests', () => {
  const settings = options();
  settings.rootState.analysis = { status: 'RUNNING', stage: 'A04', completed_at: iso(100) };
  settings.rootState.full_pipeline = { status: 'FAILED', stage: 'ANALYSIS', updated_at: iso(110),
    error: 'A04_GLOBAL_GROUPING_INPUT_BUDGET_EXCEEDED' };
  settings.scheduler = { ...settings.scheduler, stage: '03_research', status: 'COMPLETE' };
  settings.stages['03_research'] = { requests: 289, completed: 289, valid: 289, status: 'COLLECTED' };
  const data = buildProgress(settings);
  assert.equal(data.stage, '04_quadrant'); assert.equal(data.status, 'PREPARATION_FAILED');
  assert.equal(data.counts.total, null); assert.equal(data.counts.errors, null);
  assert.deepEqual(data.records, { planned: null, completed: null, valid: null, failed: null });
  assert.equal(data.issues[0].kind, 'PREPARATION'); assert.equal(data.issues[0].message, settings.rootState.full_pipeline.error);
  assert.equal(data.analysis.status, 'RUNNING'); assert.equal(data.analysis.pipeline_status, 'FAILED');
  assert.equal(data.phases.find(row => row.key === '03_research').status, 'COLLECTED');
  assert.equal(data.phases.find(row => row.key === '04_quadrant').status, 'PREPARATION_FAILED');
  assert.equal(data.metrics.stage_elapsed_seconds, null); assert.equal(data.scheduler.alive, false);
});

test('A04 counts, failure reasons, timing and CPU exclude other stages', () => {
  const settings = options(); settings.rootState.analysis = { status: 'RUNNING', stage: 'A04' };
  settings.stages['04_quadrant'] = { requests: 3, completed: 2, valid: 1, status: 'RUNNING' };
  settings.scheduler.stage = '04_quadrant';
  const valid = start('q1', 'q1', 0, { stage: '04_quadrant' }), failed = start('q2', 'q2', 20, { stage: '04_quadrant' });
  const active = start('q3', 'q3', 800, { stage: '04_quadrant' });
  const data = buildProgress({ ...settings, timingEvents: [end(start('old', 'old', 0), 40), valid, end(valid, 100),
    failed, end(failed, 320, 'UNKNOWN_DELIVERY'), active],
    stageArtifacts: { '04_quadrant': { failures: [{ trial_id: 'q2', message: 'Provider timeout', source: 'calls/q2/result.json' }] } } });
  assert.deepEqual([data.counts.total, data.counts.completed, data.counts.errors, data.counts.running], [3, 1, 1, 1]);
  assert.deepEqual(data.records, { planned: 3, completed: 2, valid: 1, failed: 1 });
  assert.equal(data.metrics.mean_seconds, 100); assert.equal(data.metrics.stage_elapsed_seconds, 900);
  assert.equal(data.charts.calls.length, 2); assert.equal(data.issues[0].kind, 'MODEL_CALL');
  assert.equal(data.issues[0].message, 'Provider timeout'); assert.equal(data.activity.processor, 'LLM');
});

test('live A04 Python preparation is distinct from calls and does not reuse A03 preparation', () => {
  const settings = { ...options(), stages: {}, scheduler: null, selectedStage: '04_quadrant' };
  const row = { span_id: 'prepare', step: 'finding_request_preparation', stage: 'A04', event: 'START', pid: 10, started_at: iso(0) };
  const data = buildProgress({ ...settings, timingEvents: [row] });
  assert.equal(data.status, 'PREPARING'); assert.equal(data.activity.processor, 'PYTHON');
  assert.equal(data.activity.elapsed_seconds, 900); assert.equal(data.counts.total, null);
  assert.equal(buildProgress({ ...settings, timingEvents: [row], alive: () => false }).status, 'NOT_STARTED');
  assert.equal(buildProgress({ ...settings, timingEvents: [{ ...row, stage: 'A03' }] }).status, 'NOT_STARTED');
});

test('an A04 retry keeps the old preparation error historical after a valid new call', () => {
  const settings = options(); settings.rootState.analysis = { status: 'COMPLETE', stage: 'A04' };
  settings.rootState.full_pipeline = { status: 'FAILED', stage: 'A04', updated_at: iso(10), error: 'A04_GLOBAL_GROUPING_INPUT_BUDGET_EXCEEDED' };
  settings.stages['04_quadrant'] = { requests: 1, completed: 1, valid: 1, status: 'COLLECTED', updated_at: iso(300) };
  const row = start('q', 'q', 100, { stage: '04_quadrant' });
  const data = buildProgress({ ...settings, timingEvents: [row, end(row, 250)] });
  assert.equal(data.status, 'COLLECTED'); assert.equal(data.issues[0].historical, true);
  assert.equal(data.issues[0].kind, 'PREPARATION'); assert.equal(data.metrics.mean_seconds, 150);
});

test('A04 failure saved directly in the stage state is visible without a root failure', () => {
  const settings = options(); settings.stages['04_quadrant'] = { status: 'PREPARATION_FAILED', error: 'Source missing', updated_at: iso(100) };
  const data = buildProgress({ ...settings, selectedStage: '04_quadrant' });
  assert.equal(data.status, 'PREPARATION_FAILED'); assert.equal(data.issues[0].message, 'Source missing');
  assert.equal(data.issues[0].source, '02_analysis/04_quadrant/state.json');
});

test('zero planned A04 requests is recorded zero; an absent A04 plan remains unknown', () => {
  const settings = { ...options(), stages: {}, selectedStage: '04_quadrant' };
  assert.equal(buildProgress(settings).records.planned, null);
  const data = buildProgress({ ...settings, stageArtifacts: { '04_quadrant': { planned: 0 } } });
  assert.deepEqual(data.records, { planned: 0, completed: 0, valid: 0, failed: 0 });
  assert.equal(data.counts.total, 0); assert.equal(data.metrics.mean_seconds, null);
});

test('limit history preserves policy changes and the reset on a new process', () => {
  const settings = options(); settings.config.analysis.schedule = { concurrency: 4 };
  const events = [
    { event: 'ANALYSIS_CODEX_STARTED', stage: '02_comparison', pending: 10, time: iso(0) },
    { event: 'ANALYSIS_SCHEDULE_CONFIGURED', schedule: { concurrency: 20 }, time: iso(10) },
    { event: 'ANALYSIS_CODEX_STARTED', stage: '02_comparison', pending: 100, time: iso(20) },
    { event: 'ANALYSIS_CPU_SAMPLE', stage: '02_comparison', current_limit: 22, cpu_percent: 35, time: iso(80) },
    { event: 'ANALYSIS_CODEX_STARTED', stage: '02_comparison', pending: 70, time: iso(100) }
  ];
  const data = buildProgress({ ...settings, events });
  assert.deepEqual(data.charts.limits.map(row => row.limit), [4, 20, 22, 20, 20]);
  assert.equal(data.charts.limits[3].at, baseTime + 100000);
});

test('CPU measurement failures stay missing instead of being drawn as zero', () => {
  const data = buildProgress({ ...options(), events: [
    { event: 'ANALYSIS_CPU_SAMPLE', stage: '02_comparison', cpu_percent: 35, time: iso(60) },
    { event: 'ANALYSIS_CPU_SAMPLE', stage: '02_comparison', cpu_percent: null, error_type: 'Unavailable', time: iso(120) }
  ] });
  assert.deepEqual(data.charts.cpu.map(row => row.percent), [35, null]);
});

test('CPU gaps between scheduler sessions break the line without interpolated samples', () => {
  const data = buildProgress({ ...options(), events: [
    { event: 'ANALYSIS_CPU_SAMPLE', stage: '02_comparison', cpu_percent: 35, interval_seconds: 60, time: iso(60) },
    { event: 'ANALYSIS_CPU_SAMPLE', stage: '02_comparison', cpu_percent: 24, interval_seconds: 60, time: iso(800) }
  ] });
  assert.deepEqual(data.charts.cpu.map(row => row.percent), [35, null, 24]);
  assert.equal(data.charts.cpu[1].reason, 'UNMEASURED_INTERVAL');
});

test('progress API uses small records, rejects unsafe reads, and remains read-only', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-progress-'));
  const run = '20260927-exp-999', folder = path.join(root, run);
  await fs.mkdir(path.join(folder, '02_analysis/02_comparison'), { recursive: true });
  const write = (file, data) => fs.writeFile(path.join(folder, file), JSON.stringify(data));
  await write('config.json', { layout_version: 2, evaluation: { models: [] }, analysis: { backend: 'codex' } });
  await write('state.json', { status: 'FINISHED' });
  await write('02_analysis/02_comparison/state.json', { requests: 557, valid: 194, completed: 198 });
  const server = createServer({ root });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await fs.rm(root, { recursive: true, force: true }); });
  const url = `http://127.0.0.1:${server.address().port}`;
  const response = await fetch(`${url}/api/runs/${run}/progress`);
  assert.equal(response.status, 200); assert.equal((await response.json()).counts.waiting, 359);
  assert.equal((await fetch(`${url}/api/runs/${run}/progress?stage=../bad`)).status, 400);
  assert.equal((await fetch(`${url}/api/runs/${run}/progress`, { method: 'POST' })).status, 405);
  assert.match(await (await fetch(`${url}/?run=${run}&tab=progress`)).text(), /progress-dashboard.mjs/);
  const target = path.join(root, 'outside.json'); await fs.writeFile(target, '{}');
  await fs.symlink(target, path.join(folder, '02_analysis/scheduler.json'));
  assert.equal((await fetch(`${url}/api/runs/${run}/progress`)).status, 403);
});

test('A04 API reads its plan and the exact failed attempt without returning request payloads', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-a04-progress-'));
  const run = '20261003-exp-999', folder = path.join(root, run), stageFolder = path.join(folder, '02_analysis/04_quadrant');
  await fs.mkdir(path.join(stageFolder, 'calls/q1/attempt-001'), { recursive: true });
  const write = (file, data) => fs.writeFile(path.join(folder, file), JSON.stringify(data));
  await write('config.json', { layout_version: 2, evaluation: { models: [] }, analysis: { backend: 'codex' } });
  await write('state.json', { status: 'FINISHED', analysis: { status: 'RUNNING', stage: 'A04' } });
  await fs.writeFile(path.join(stageFolder, 'manifest.jsonl'), JSON.stringify({ trial_id: 'q1', input: 'PRIVATE_FROZEN_PAYLOAD' }) + '\n');
  const row = start('q1', 'q1', 0, { stage: '04_quadrant' });
  await fs.writeFile(path.join(folder, '02_analysis/timing-events.jsonl'), [row, end(row, 300, 'UNKNOWN_DELIVERY')].map(JSON.stringify).join('\n') + '\n');
  await write('02_analysis/04_quadrant/calls/q1/attempt-001/result.json', { trial_id: 'q1', status: 'UNKNOWN_DELIVERY', error: 'Provider timeout', response: 'PRIVATE_RESPONSE' });
  const server = createServer({ root }); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); await fs.rm(root, { recursive: true, force: true }); });
  const url = `http://127.0.0.1:${server.address().port}/api/runs/${run}/progress?stage=04_quadrant`;
  const response = await fetch(url), data = await response.json();
  assert.equal(response.status, 200); assert.equal(data.counts.total, 1); assert.equal(data.records.completed, 1);
  assert.equal(data.counts.errors, 1); assert.equal(data.issues[0].message, 'Provider timeout');
  assert.match(data.issues[0].source, /attempt-001\/result\.json/);
  assert.doesNotMatch(JSON.stringify(data), /PRIVATE_FROZEN_PAYLOAD|PRIVATE_RESPONSE/);
  const outside = path.join(root, 'outside.json'); await fs.writeFile(outside, '{}');
  await fs.rm(path.join(stageFolder, 'manifest.jsonl')); await fs.symlink(outside, path.join(stageFolder, 'manifest.jsonl'));
  assert.equal((await fetch(url)).status, 403);
});
