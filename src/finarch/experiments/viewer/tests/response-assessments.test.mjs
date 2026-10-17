import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { Repository } from '../repository.mjs';
import { buildBundle, renderHTML } from '../export-html.mjs';
import { createOfflineStore } from '../../../../../viewer/experiments/offline.mjs';
import { assessmentShare, assessmentCitationSource, renderAssessmentSummary, renderResponseAssessment } from '../../../../../viewer/experiments/response-assessments.mjs';

const run = '20261003-exp-999';
const variants = ['IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02', 'EA_02'];
const reviewStates = ['COMPLETED', 'COMPLETED', 'COMPLETED', 'COMPLETED', 'REVIEW_FAILED', 'NOT_REVIEWABLE', 'SOURCE_MISSING', 'NOT_REVIEWED'];
const hash = text => createHash('sha256').update(text).digest('hex');
const counter = (rows, pick) => rows.reduce((out, row) => { const key = pick(row); out[key] = (out[key] || 0) + 1; return out; }, {});
function counts(rows) {
  return { planned: rows.length, review_status: counter(rows, r => r.review_status),
    adaptation_outcome: counter(rows, r => r.adaptation_success === true ? 'SUCCESS' : r.adaptation_success === false ? 'FAILURE' : 'UNDETERMINED_OR_UNREVIEWED'),
    abstention_reason_validity: counter(rows, r => r.abstention_reason_validity.verdict || 'UNREVIEWED'),
    decision_grounding: counter(rows, r => r.decision_grounding.verdict || 'UNREVIEWED') };
}
async function fixture(t, { assessments = true } = {}) {
  const root = await mkdtemp(path.join(tmpdir(), 'finarch-assessments-')), folder = path.join(root, run);
  t.after(() => rm(root, { recursive: true, force: true }));
  const write = async (name, value) => {
    const target = path.join(folder, name); await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, typeof value === 'string' ? value : JSON.stringify(value));
  };
  const rows = ['ORIGINAL', ...variants].map((variant, i) => ({
    model: 'luna', response_id: `luna:solver-${i}`, trial_id: `solver-${i}`, item_id: `case-1:${variant}`, case: 'case-1', variant,
    experiment: variant === 'ORIGINAL' ? 1 : 2,
    prompt_condition: i <= 2 ? 'P0' : i % 2 ? 'guided' : 'P1', reasoning: i % 2 ? 'on' : 'off',
    status: i === 6 ? 'INVALID_RESPONSE' : i === 8 ? 'NOT_RUN' : 'VALID', checks: {},
    response: i === 6 || i === 8 ? null : { answer: i < 2 || i === 5 ? '12' : null,
      explanation: i < 2 || i === 5 ? 'Revenue is 12.' : 'Revenue is conflicting.',
      evidence: ['Revenue 12.', 'Revenue 13.'], classification: i <= 2 ? null : 'CONFLICT' },
    call_path: `01_evaluation/03_execution/luna/${i}/call.json`, result_path: `01_evaluation/04_validation/luna/${i}/result.json`
  }));
  const requests = rows.map((row, i) => ({ ...row, input: { question: 'What is revenue?', context: i === 7 ? '' : 'Revenue 12. Revenue 13.' },
    prompt: 'Read the saved source.', response_schema: { title: 'FinancialAnswerV7', type: 'object' } }));
  const unique = [...new Map(rows.map(row => [row.item_id, row])).values()];
  await write('config.json', { layout_version: 2, models: [{ key: 'luna', model: 'Luna' }], analysis: { enabled: true, method: 'results-focused-v1' } });
  await write('00_input/public.jsonl', unique.map(row => JSON.stringify({ item_id: row.item_id, question: 'What is revenue?', context: 'Public fallback must not replace an empty actual request.' })).join('\n'));
  await write('00_input/private.jsonl', unique.map(row => JSON.stringify({ item_id: row.item_id, case: row.case, variant: row.variant, reference: { reference_answer: '12' } })).join('\n'));
  await write('01_evaluation/02_request/luna/manifest.jsonl', requests.map(row => JSON.stringify(row)).join('\n'));
  await write('01_evaluation/04_validation/luna/results.jsonl', rows.map(row => JSON.stringify(row)).join('\n'));
  await write('01_evaluation/04_validation/luna/summary.json', { planned: rows.length });
  for (const [i, row] of rows.entries()) {
    await write(row.call_path, { request: requests[i], response: row.response });
    await write(row.result_path, { status: row.status, response: row.response });
  }
  const sourceText = rows.map(row => JSON.stringify(row)).join('\n');
  await write('02_analysis/01_results/responses.jsonl', sourceText);
  await write('02_analysis/02_comparison/comparisons.json', { response_rows_sha256: hash(sourceText), overall: { response_ids: rows.map(r => r.response_id) }, matrix: [], case_profiles: [], original_groups: [], paired_groups: [] });
  await write('02_analysis/02_comparison/interpretations.jsonl', '');
  const records = rows.slice(1).map((row, i) => {
    const completed = reviewStates[i] === 'COMPLETED', nullAnswer = row.response?.answer === null;
    const verdict = i === 2 ? 'UNDETERMINED' : i === 3 ? 'UNSUPPORTED' : 'SUPPORTED';
    const judgment = field => ({ verdict: completed ? field === 'abstention_reason_validity' && !nullAnswer ? 'NOT_APPLICABLE' : verdict : null,
      reason: completed ? 'The stored source and explanation were reviewed.' : 'No validated assessment is available.',
      citations: completed && !(field === 'abstention_reason_validity' && !nullAnswer) ? [
        { source: 'context', quote: 'Revenue 12.', evidence_index: null },
        { source: 'explanation', quote: row.response.explanation, evidence_index: null },
        { source: 'evidence', quote: 'Revenue 13.', evidence_index: 1 }
      ] : [] });
    return { response_id: row.response_id, case: row.case, item_id: row.item_id, variant: row.variant, model: row.model,
      prompt_condition: row.prompt_condition, reasoning: row.reasoning, response_status: row.status,
      assessment_id: `judge-1:${row.response_id}`, trial_id: 'judge-1', rubric_version: 'ResponseGroundingV1',
      review_status: reviewStates[i], judge_call_status: i === 4 ? 'INVALID_RESPONSE' : i === 7 ? 'NOT_RUN' : 'VALID',
      abstention_reason_validity: judgment('abstention_reason_validity'), decision_grounding: judgment('decision_grounding'),
      adaptation_success: completed && i < 2 ? true : i === 3 ? false : null };
  });
  const save = async () => {
    const text = records.map(row => JSON.stringify(row)).join('\n') + '\n';
    const grouped = new Map();
    for (const row of records) {
      const keys = ['model', 'variant', 'prompt_condition', 'reasoning'], key = JSON.stringify(keys.map(k => row[k]));
      if (!grouped.has(key)) grouped.set(key, { dimensions: Object.fromEntries(keys.map(k => [k, row[k]])), records: [] });
      grouped.get(key).records.push(row);
    }
    const summary = { rubric_version: 'ResponseGroundingV1', overall: counts(records), groups: [...grouped.values()].map(g => ({ ...g.dimensions, ...counts(g.records) })), response_assessments_sha256: hash(text) };
    const coverage = { planned: records.length, review_status: summary.overall.review_status,
      response_ids_by_status: Object.fromEntries([...new Set(records.map(r => r.review_status))].map(status => [status, records.filter(r => r.review_status === status).map(r => r.response_id)])), response_assessments_sha256: hash(text) };
    await write('02_analysis/02_comparison/response-assessments.jsonl', text);
    await write('02_analysis/02_comparison/response-assessment-summary.json', summary);
    await write('02_analysis/02_comparison/response-assessment-coverage.json', coverage);
    return { summary, coverage };
  };
  const saved = assessments ? await save() : null;
  return { root, folder, rows, requests, records, saved, save, write, repository: new Repository(root) };
}

test('A02 links exact solver response IDs, preserves all five states and keeps empty observations independent', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run), view = f.repository.overview(snap, { tab: 'conditions' });
  assert.equal(view.results_analysis.response_assessment_summary.overall.planned, 8);
  assert.deepEqual(view.results_analysis.response_assessment_coverage.review_status, { COMPLETED: 4, REVIEW_FAILED: 1, NOT_REVIEWABLE: 1, SOURCE_MISSING: 1, NOT_REVIEWED: 1 });
  assert.equal(snap.resultsAnalysis.interpretations.length, 0);
  for (const [i, row] of f.rows.entries()) {
    const response = await f.repository.response(snap, row);
    assert.equal(response.response_id, row.response_id);
    assert.deepEqual(response.response_assessment, i === 0 ? null : f.records[i - 1]);
  }
  const row = f.rows[1], detail = await f.repository.detail(snap, row.case, { variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning });
  assert.equal(detail.responses[0].classification.label, '분류 미요구');
  assert.equal(detail.responses[0].response_assessment.abstention_reason_validity.verdict, 'NOT_APPLICABLE');
  assert.equal(f.records[2].adaptation_success, null);
  assert.equal(f.records[2].decision_grounding.verdict, 'UNDETERMINED');
  assert.equal(snap.resultsAnalysis.response_assessments, undefined, 'full reviews must not inflate the eager overview');
});

test('three assessment files invalidate snapshot cache and partial writes keep the last verified version', async t => {
  const f = await fixture(t), first = await f.repository.snapshot(run);
  await f.write('02_analysis/02_comparison/response-assessment-summary.json', { ...f.saved.summary, boundary: 'Updated saved boundary.' });
  const second = await f.repository.snapshot(run); assert.notEqual(second, first); assert.equal(second.stale, undefined);
  await f.write('02_analysis/02_comparison/response-assessment-coverage.json', { ...f.saved.coverage, planned: 999 });
  const stale = await f.repository.snapshot(run); assert.equal(stale.stale, true); assert.match(stale.warnings.at(-1), /\uc644\ub8cc\uc728/);
  f.records[0].decision_grounding.reason = 'A newly saved judge reason, not a new solver response.';
  await f.save();
  const refreshed = await f.repository.snapshot(run); assert.equal(refreshed.stale, undefined);
  assert.equal((await f.repository.response(refreshed, f.rows[1])).response_assessment.decision_grounding.reason, f.records[0].decision_grounding.reason);
  await f.write('02_analysis/02_comparison/response-assessments.jsonl', '{}\n');
  assert.equal((await f.repository.snapshot(run)).stale, true);
});

test('missing V1 files stay absent, while orphan IDs or inconsistent saved counts reject a fresh read', async t => {
  const f = await fixture(t, { assessments: false }), missing = await f.repository.snapshot(run);
  assert.equal(missing.resultsAnalysis.response_assessment_summary, null);
  assert.equal((await f.repository.response(missing, f.rows[1])).response_assessment_state, 'MISSING');
  await f.save(); f.repository.cache.clear();
  f.records[0].response_id = 'an-unrelated-solver-response'; await f.save();
  await assert.rejects(f.repository.snapshot(run), /\uc2e4\uc81c \ubcc0\ud615 \uc751\ub2f5/);
  f.records[0].response_id = f.rows[1].response_id; const saved = await f.save();
  await f.write('02_analysis/02_comparison/response-assessment-summary.json', { ...saved.summary, overall: { ...saved.summary.overall, decision_grounding: { SUPPORTED: 8 } } });
  await assert.rejects(f.repository.snapshot(run), /\ud310\uc815 \ubd84\ud3ec/);
});

test('offline export keeps the same summaries, reasons and source citations and inlines the renderer', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run), bundle = await buildBundle(f.repository, snap, { initialView: { tab: 'conditions' } });
  const offline = createOfflineStore(bundle), live = f.repository.overview(snap, { tab: 'conditions' });
  const stored = await offline.request(`/api/runs/${run}/overview?tab=conditions`);
  assert.deepEqual(stored.results_analysis.response_assessment_summary, live.results_analysis.response_assessment_summary);
  const row = f.rows[2], query = new URLSearchParams({ case: row.case, variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning });
  const detail = await offline.request(`/api/runs/${run}/case?${query}`);
  assert.deepEqual(detail.responses[0].response_assessment, f.records[1]);
  assert.equal(detail.responses[0].request.input.context, 'Revenue 12. Revenue 13.');
  const html = await renderHTML(bundle), script = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(match => match[1]).find(text => text.includes('const Model ='));
  assert.ok(script.includes('function renderResponseAssessment'));
  assert.ok(script.includes('function renderAssessmentSummary'));
  new vm.Script(script);
  assert.match(html, /connect-src 'none'/);
  assert.equal(bundle.stats.model_calls_added, 0);
});

test('a changed solver body cannot inherit an earlier completed assessment; key order alone is harmless', async t => {
  const f = await fixture(t), snap = await f.repository.snapshot(run), row = f.rows[1];
  const reordered = Object.fromEntries(Object.entries(row.response).reverse());
  await f.write(row.result_path, { status: row.status, response: reordered });
  assert.equal((await f.repository.response(snap, row)).response_assessment.response_id, row.response_id);
  await f.write(row.result_path, { status: row.status, response: { ...reordered, answer: '99' } });
  await assert.rejects(f.repository.response(snap, row), /\uc751\ub2f5 \ubcf8\ubb38\uc774 \ub2e4\ub985\ub2c8\ub2e4/);
  await assert.rejects(buildBundle(f.repository, snap), /\uc751\ub2f5 \ubcf8\ubb38\uc774 \ub2e4\ub985\ub2c8\ub2e4/);
});

class FakeNode {
  constructor(tag, text = '') { this.tag = tag; this.children = []; this.attributes = {}; this.events = {}; this.className = ''; this._text = text; this.classList = { add: value => { this.className += ` ${value}`; } }; }
  append(...values) { this.children.push(...values.map(value => typeof value === 'string' ? new FakeNode('#text', value) : value)); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(key, action) { this.events[key] = action; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  set textContent(value) { this._text = String(value); this.children = []; }
}
const nodes = node => [node, ...node.children.flatMap(nodes)];
test('rendered reviews show real denominators, unjudged states and exact quoted fields without inventing scores', async t => {
  const previous = globalThis.document;
  globalThis.document = { createElement: tag => new FakeNode(tag), createTextNode: text => new FakeNode('#text', text) };
  t.after(() => { globalThis.document = previous; });
  const f = await fixture(t), snap = await f.repository.snapshot(run);
  const missing = renderAssessmentSummary(null);
  assert.match(missing.textContent, /\ud310\uc815 \uc790\ub8cc \uc5c6\uc74c/); assert.doesNotMatch(missing.textContent, /0\.0%/);
  assert.equal(assessmentShare(1, 8), '1/8 · 12.5%'); assert.equal(assessmentShare(0, 0), '0/0 · —');
  const summary = renderAssessmentSummary(snap.resultsAnalysis, { models: [{ key: 'luna' }] });
  assert.match(summary.textContent, /4\/8 · 50\.0%/); assert.match(summary.textContent, /\ud310\ub2e8 \uc720\ubcf4/); assert.match(summary.textContent, /\ubbf8\ud310\uc815 · null/);
  assert.match(summary.textContent, /\ud544\uc694\ud55c \ud1b5\ud569 \uc9d1\uacc4 \uc790\ub8cc\uac00 \uc544\uc9c1 \uc0dd\uc131\ub418\uc9c0/);
  const model = nodes(summary).find(node => node.className === 'assessment-model'); model.open = true; model.events.toggle();
  assert.match(model.textContent, /IC_VALUE_01_BEFORE/); assert.match(model.textContent, /1\/1 · 100\.0%/);
  for (const i of [1, 2, 3, 5, 6, 7, 8]) {
    const record = await f.repository.response(snap, f.rows[i]), view = renderResponseAssessment(record);
    assert.match(view.textContent, new RegExp(f.records[i - 1].review_status));
    if (i === 1) assert.match(view.textContent, /\ud574\ub2f9 \uc5c6\uc74c · NOT_APPLICABLE/);
    if (i === 3) assert.match(view.textContent, /\ud310\ub2e8 \uc720\ubcf4 · UNDETERMINED/);
    if (i >= 5) assert.match(view.textContent, /\ubbf8\ud310\uc815 · null/);
    if (i === 2) {
      const citation = f.records[1].decision_grounding.citations.at(-1);
      assert.equal(assessmentCitationSource(citation, record.request, record.response), 'Revenue 13.');
      assert.ok(nodes(view).some(node => node.tag === 'mark' && node.textContent === 'Revenue 13.'));
      record.request.input.context = 'A different condition.';
      assert.match(renderResponseAssessment(record).textContent, /\uc2e4\uc81c \uc6d0\ubb38\uc5d0\uc11c \uc778\uc6a9\uc744 \ud655\uc778\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4/);
    }
  }
});
