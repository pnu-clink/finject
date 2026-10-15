import { FINALIZATION_FILES, readFinalization } from './finalization.mjs';
import { promises as fs, createReadStream } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { buildProgress, PROGRESS_STAGES, selectProgressStage } from './progress.mjs';
import { createInterface } from 'node:readline';
import { ASSESSMENT_FILES, readAssessments, responseFingerprint } from './assessment-reader.mjs';
import { RQ1_FILES, readRQ1Materials } from './rq1-reader.mjs';
import { GROUNDING_FILES, readGroundingPairs } from './grounding-reader.mjs';
import { groundingSummary, groundingPage } from '../../../../viewer/experiments/grounding-model.mjs';

import { VARIANTS, aggregate, filterRows, selected, query, overview, exportMarkdown, selectCase, assembleCase, caseConditionRows, conditionTimings, recordedElapsed, rqAnswerOverview, rqAnswerPage } from '../../../../viewer/experiments/model.mjs';
export { VARIANTS, aggregate, filterRows };
const idFor = value => createHash('sha256').update(value).digest('hex').slice(0, 24);
const countBy = (rows, key) => rows.reduce((out, row) => { const k = key(row); out[k] = (out[k] || 0) + 1; return out; }, {});
const within = (root, target) => target === root || target.startsWith(root + path.sep);
export function artifactPaths(config) {
  const modern = config?.layout_version === 2;
  const resultsFocused = config?.analysis?.method === 'results-focused-v1'
    || (modern && config?.analysis?.enabled === true && Object.keys(config.analysis.backends || {}).length > 0);
  const input = modern ? '00_input' : '01-input';
  const validation = modern ? '01_evaluation/04_validation' : '';
  return { modern, resultsFocused, input, validation, summary: modern ? `${validation}/summary.json` : 'summary.json',
    plan: modern ? '01_evaluation/02_request/plan.json' : 'plan.json',
    diagnostics: resultsFocused ? '02_analysis/01_results' : modern ? '02_analysis/01_response_review' : 'analysis',
    diagnosticsFile: resultsFocused ? '02_analysis/01_results/responses.jsonl' : modern ? '02_analysis/01_response_review/response-diagnostics.jsonl' : 'analysis/response-diagnostics.jsonl',
    request: key => modern ? `01_evaluation/02_request/${key}/manifest.jsonl` : `${key}/01-requests/manifest.jsonl`,
    results: key => modern ? `${validation}/${key}` : `${key}/03-results` };
}
function evaluationConfig(raw) { return raw?.evaluation ? { ...raw.evaluation, layout_version: raw.layout_version, analysis: raw.analysis, evaluation_reuse: raw.evaluation_reuse, run_kind: raw.run_kind } : raw; }
async function configuredRun(root, optional = false) {
  const config = evaluationConfig(await json(root, 'config.json', optional));
  const frozen = await json(root, '02_analysis/config.json', true);
  if (frozen) {
    if (!config || !frozen.analysis || !['codex', 'api'].includes(frozen.analysis.backend)) {
      throw new ViewError('동결된 분석 설정을 읽을 수 없습니다.', 503);
    }
    config.analysis = frozen.analysis;
  }
  return config;
}
export class ViewError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}

// [EV01.1] Resolve every saved reference inside its own run, including symlinks.
export async function safePath(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative) || relative.includes('\\') || relative.split('/').includes('..')) throw new ViewError('허용되지 않은 파일 경로입니다.');
  const base = await fs.realpath(root);
  const target = path.resolve(base, relative);
  if (!within(base, target)) throw new ViewError('실행 폴더 밖의 파일은 읽을 수 없습니다.', 403);
  let current = base;
  for (const segment of relative.split('/').filter(Boolean)) {
    current = path.join(current, segment);
    const info = await fs.lstat(current);
    if (info.isSymbolicLink()) throw new ViewError('심볼릭 링크는 읽을 수 없습니다.', 403);
  }
  if (!within(base, await fs.realpath(target))) throw new ViewError('실행 폴더 밖의 파일은 읽을 수 없습니다.', 403);
  return target;
}

async function readFile(root, relative, optional = false) {
  try { return await fs.readFile(await safePath(root, relative), 'utf8'); }
  catch (error) { if (optional && error.code === 'ENOENT') return null; throw error; }
}
async function json(root, relative, optional = false) {
  const text = await readFile(root, relative, optional);
  if (text === null) return null;
  try { return JSON.parse(text); } catch { throw new ViewError(`${relative}: JSON을 읽지 못했습니다. 파일 작성이 끝난 뒤 새로 읽어 주세요.`, 503); }
}

// Keep progress reads small: discard the frozen request payload and read errors only.
async function quadrantProgressArtifacts(root, timingEvents) {
  const manifest = '02_analysis/04_quadrant/manifest.jsonl';
  let planned = null;
  const ids = new Set(), sources = [], failures = [];
  let manifestPath;
  try { manifestPath = await safePath(root, manifest); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (manifestPath) {
    const input = createReadStream(manifestPath, { encoding: 'utf8' });
    const lines = createInterface({ input, crlfDelay: Infinity });
    planned = 0;
    try {
      for await (const line of lines) {
        if (!line.trim()) continue;
        let row;
        try { row = JSON.parse(line); } catch { throw new ViewError(`${manifest}: 작성이 끝난 뒤 새로 읽어 주세요.`, 503); }
        if (!/^[a-zA-Z0-9_-]{1,128}$/.test(row.trial_id) || ids.has(row.trial_id)) throw new ViewError('A04 요청 ID가 올바르지 않거나 중복됩니다.', 503);
        ids.add(row.trial_id); planned++;
      }
    } finally { lines.close(); input.destroy(); }
    sources.push(manifest);
  }
  const latest = new Map();
  for (const row of timingEvents) if (row.stage === '04_quadrant' && row.step === 'model_call' && row.trial_id) {
    const previous = latest.get(row.trial_id);
    if (!previous || Date.parse(row.started_at) >= Date.parse(previous.started_at)) latest.set(row.trial_id, row);
  }
  const failed = [...latest.values()].filter(row => row.event === 'END' && row.result_status !== 'VALID').slice(-30);
  for (const row of failed) {
    if (!Number.isInteger(row.attempt) || row.attempt < 1 || !/^[a-zA-Z0-9_-]{1,128}$/.test(row.trial_id)) continue;
    if (manifestPath && !ids.has(row.trial_id)) throw new ViewError('A04 호출 기록이 동결 요청과 맞지 않습니다.', 503);
    const relative = `02_analysis/04_quadrant/calls/${row.trial_id}/attempt-${String(row.attempt).padStart(3, '0')}/result.json`;
    const result = await json(root, relative, true);
    if (!result) continue;
    if (result.trial_id && result.trial_id !== row.trial_id) throw new ViewError('A04 오류 기록의 요청 ID가 맞지 않습니다.', 503);
    const message = result.error || result.errors || result.error_type || result.message;
    failures.push({ trial_id: row.trial_id, status: result.status, source: relative,
      message: message ? (typeof message === 'string' ? message : JSON.stringify(message)).slice(0, 4000) : null });
  }
  return { planned, failures, sources };
}

async function jsonl(root, relative, optional = false) {
  const text = await readFile(root, relative, optional);
  if (text === null) return null;
  return text.split('\n').filter(line => line.trim()).map((line, i) => {
    try { return JSON.parse(line); } catch { throw new ViewError(`${relative}: ${i + 1}행이 완성되지 않았습니다.`, 503); }
  });
}

// JSONL delimiters are LF bytes, not Unicode line separators inside JSON strings.
export async function* manifestRequests(root, relative) {
  const stream = createReadStream(await safePath(root, relative), { encoding: 'utf8' });
  let pending = '', number = 0;
  const parse = line => { try { return JSON.parse(line); } catch { throw new ViewError(`${relative}: ${number}행이 완성되지 않았습니다.`, 503); } };
  try {
    for await (const part of stream) {
      pending += part;
      let end;
      while ((end = pending.indexOf('\n')) >= 0) { const line = pending.slice(0, end); pending = pending.slice(end + 1); number++; if (line.trim()) yield parse(line); }
    }
    if (pending.trim()) { number++; yield parse(pending); }
  } finally { stream.destroy(); }
}

async function manifestSelection(root, models, events, config) {
  const items = new Map(), pairs = new Map(), files = [], requestsByModel = {}, inputFieldsByModel = {};
  for (const model of models) {
    const relative = artifactPaths(config).request(model.key), trialIds = new Set(), inputFields = new Set();
    for await (const request of manifestRequests(root, relative)) {
      const { item_id, case: caseId, experiment, variant } = request;
      if (![item_id, caseId, variant].every(value => typeof value === 'string' && value)
          || ![1, 2].includes(experiment) || (variant === 'ORIGINAL') !== (experiment === 1)) {
        throw new ViewError(`${relative}: 문항 연결 정보가 올바르지 않습니다.`, 503);
      }
      if (!request.trial_id || trialIds.has(request.trial_id)) throw new ViewError(`${relative}: 중복 또는 누락된 요청 ID입니다.`, 503);
      trialIds.add(request.trial_id);
      for (const key of Object.keys(request.input ?? {})) inputFields.add(key);
      const item = { item_id, case: caseId, experiment, variant }, pair = JSON.stringify([caseId, variant]);
      if ((items.has(item_id) && JSON.stringify(items.get(item_id)) !== JSON.stringify(item))
          || (pairs.has(pair) && pairs.get(pair) !== item_id)) throw new ViewError(`${relative}: 문항 연결 정보가 서로 다릅니다.`, 503);
      items.set(item_id, item); pairs.set(pair, item_id);
    }
    if (!trialIds.size) throw new ViewError(`${relative}: 요청 목록이 비어 있습니다.`, 503);
    files.push(relative);
    requestsByModel[model.key] = trialIds.size; inputFieldsByModel[model.key] = [...inputFields].sort();
  }
  if (!files.length) return null;
  const unique = [...items.values()], audit = [...(events || [])].reverse().find(row => row.event === 'INPUT_SELECTION');
  return { originals: unique.filter(row => row.experiment === 1).length,
    variants: unique.filter(row => row.experiment === 2).length,
    variant_counts: countBy(unique.filter(row => row.experiment === 2), row => row.variant),
    exclusions: audit?.exclusions ?? null, manifest_files: files, requests_by_model: requestsByModel, input_fields_by_model: inputFieldsByModel, source: 'MODEL_REQUEST_MANIFESTS' };
}
export class Repository {
  constructor(root) { this.root = path.resolve(root); this.cache = new Map(); this.pending = new Map(); }
  async runPath(id) {
    if (!/^\d{8}-(?:exp-\d{3,}(?:-(?:\d+|[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*))?|a100-[a-z][a-z0-9-]*|fin-o1-(?:8b|14b))$/.test(id)) throw new ViewError('실행 ID가 올바르지 않습니다.');
    try { return await safePath(this.root, id); }
    catch (error) {
      if (error.code !== 'ENOENT' || !/^\d{8}-exp-\d{3,}$/.test(id)) throw error;
      const entries = await fs.readdir(this.root, { withFileTypes: true });
      const matches = entries.filter(entry => entry.isDirectory() && entry.name.startsWith(`${id}-`) && /^(?:\d+|[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*)$/.test(entry.name.slice(id.length + 1)));
      if (matches.length === 1) return safePath(this.root, matches[0].name);
      throw error;
    }
  }
  async runs() {
    let entries;
    try { entries = await fs.readdir(this.root, { withFileTypes: true }); }
    catch (e) { if (e.code === 'ENOENT') return []; throw e; }
    return Promise.all(entries.filter(e => e.isDirectory() && /^\d{8}-(?:exp-\d{3,}(?:-(?:\d+|[a-z][a-z0-9-]*(?:\.[a-z0-9-]+)*))?|a100-[a-z][a-z0-9-]*|fin-o1-(?:8b|14b))$/.test(e.name)).sort((a, b) => b.name.localeCompare(a.name)).map(async e => {
      try {
        const root = await this.runPath(e.name);
        const config = await configuredRun(root, true);
        const [state, summary, semantic] = await Promise.all([json(root, 'state.json', true), json(root, artifactPaths(config).summary, true), json(root, '02_analysis/02_comparison/summary.json', true)]);
        return { id: e.name, status: state?.status ?? summary?.status ?? 'UNKNOWN', originals: summary?.originals ?? null, variants: summary?.variants ?? null, updated_at: summary?.updated_at ?? null, models: summary?.models?.map(m => m.model) ?? [], improvement: config?.improvement ?? null, semantic: semantic?.overall ?? null, analysis_method: config.analysis?.method ?? null, analysis_status: state?.analysis?.status ?? null, evaluation_source: config.evaluation_reuse?.source_run ?? null };
      } catch (error) { return { id: e.name, status: 'READ_ERROR', error: error.message }; }
    }));
  }
  async signature(root, models, config) {
    const paths = artifactPaths(config);
    const files = ['config.json', 'manifest.json', '02_analysis/config.json', 'state.json', paths.summary, paths.plan, 'events.jsonl', `${paths.input}/public.jsonl`, `${paths.input}/private.jsonl`, `${paths.diagnostics}/verification.json`, paths.diagnosticsFile, ...models.flatMap(m => [`${paths.results(m.key)}/results.jsonl`, `${paths.results(m.key)}/summary.json`, paths.request(m.key)])];
    files.push('01_evaluation/04_validation/numeric-comparisons.jsonl', '02_analysis/02_comparison/summary.json', '02_analysis/02_comparison/rows.jsonl', ...['01-LLM-input', '02-LLM-response', '03-LLM-audit'].map(stage => `02_analysis/01_response_review/${stage}/state.json`));
    files.push(...['01-LLM-input', '02-LLM-response', '03-LLM-audit'].map(stage => `02_analysis/01_response_review/${stage}/retry-001/state.json`));
    files.push('02_analysis/03_research/state.json', '02_analysis/01_results/state.json', '02_analysis/02_comparison/state.json', '02_analysis/02_comparison/comparisons.json', '02_analysis/02_comparison/interpretations.jsonl', '02_analysis/03_research/findings.json', '02_analysis/timing.json', '02_analysis/scheduler.json');
    files.push(...FINALIZATION_FILES, ...ASSESSMENT_FILES, ...RQ1_FILES, ...GROUNDING_FILES);
    return (await Promise.all(files.map(async f => {
      if (f === '02_analysis/scheduler.json') {
        const value = await json(root, f, true);
        if (!value) return `${f}:missing`;
        const { updated_at, ...observed } = value;
        return `${f}:${JSON.stringify(observed)}`;
      }
      try { const s = await fs.stat(await safePath(root, f)); return `${f}:${s.size}:${s.mtimeMs}`; }
      catch (e) { if (e.code === 'ENOENT') return `${f}:missing`; throw e; }
    }))).join('|');
  }
  async snapshot(id) {
    if (this.pending.has(id)) return this.pending.get(id);
    const task = this.load(id).finally(() => this.pending.delete(id));
    this.pending.set(id, task); return task;
  }
  async progress(id, selectedStage) {
    if (selectedStage && !Object.hasOwn(PROGRESS_STAGES, selectedStage)) throw new ViewError('알 수 없는 분석 단계입니다.');
    const root = await this.runPath(id);
    const config = await configuredRun(root);
    const [rootState, comparison, research, quadrant, scheduler, timingEvents, events, plan] = await Promise.all([
      json(root, 'state.json', true), json(root, '02_analysis/02_comparison/state.json', true),
      json(root, '02_analysis/03_research/state.json', true), json(root, '02_analysis/04_quadrant/state.json', true),
      json(root, '02_analysis/scheduler.json', true),
      jsonl(root, '02_analysis/timing-events.jsonl', true), jsonl(root, 'events.jsonl', true),
      json(root, artifactPaths(config).plan, true)
    ]);
    const finalization = await readFinalization(root, rootState, research);
    const alive = pid => { if (!Number.isInteger(pid) || pid < 1) return false;
      try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } };
    const stage = selectProgressStage(rootState, scheduler, selectedStage);
    const details = stage === '04_quadrant' ? await quadrantProgressArtifacts(root, timingEvents || []) : null;
    return buildProgress({ id, config, rootState, stages: { '02_comparison': comparison, '03_research': research, '04_quadrant': quadrant },
      scheduler, finalization, timingEvents: timingEvents || [], events: events || [], plan, selectedStage, alive,
      stageArtifacts: details ? { '04_quadrant': details } : {} });
  }
  // [EV01.2] Replace a cached snapshot only after a complete, stable read.
  async load(id) {
    const previous = this.cache.get(id);
    try {
      const root = await this.runPath(id);
      const config = await configuredRun(root);
      const paths = artifactPaths(config);
      if (!Array.isArray(config.models)) throw new ViewError('모델 설정이 없습니다.', 503);
      const signature = await this.signature(root, config.models, config);
      if (previous?.signature === signature) return previous;
      const [state, summary, plan, events, pub, priv, diagnostics, numericObservations, verification] = await Promise.all([
        json(root, 'state.json', true), json(root, paths.summary, true), json(root, paths.plan, true), jsonl(root, 'events.jsonl', true),
        jsonl(root, `${paths.input}/public.jsonl`), jsonl(root, `${paths.input}/private.jsonl`), jsonl(root, paths.diagnosticsFile, true),
        paths.modern ? jsonl(root, '01_evaluation/04_validation/numeric-comparisons.jsonl', true) : null,
        json(root, `${paths.diagnostics}/verification.json`, true)
      ]);
      const selection = await manifestSelection(root, config.models, events, config);
      const semantic = await json(root, '02_analysis/02_comparison/summary.json', true);
      const semanticRows = await jsonl(root, '02_analysis/02_comparison/rows.jsonl', true);
      const semanticMap = new Map((semanticRows || []).map(row => [`${row.model}:${row.trial_id}`, row]));
      if (semanticRows && semanticRows.length !== semanticMap.size) throw new ViewError('내용 판정에 중복 요청 ID가 있습니다.', 503);
      let reviewStages = await Promise.all(['01-LLM-input', '02-LLM-response', '03-LLM-audit'].map(async stage => {
        let source = root, sharedFrom = null;
        if (stage === '01-LLM-input' && config.improvement?.round > 1 && config.dataset?.reuse_input_run) {
          sharedFrom = path.basename(config.dataset.reuse_input_run);
          source = await this.runPath(sharedFrom);
        }
        const first = await json(source, `02_analysis/01_response_review/${stage}/state.json`, true);
        const recovery = await json(source, `02_analysis/01_response_review/${stage}/retry-001/state.json`, true);
        return { stage, ...first, recovery, shared_from_run: sharedFrom,
          token_cost_estimate_usd: first?.token_cost_estimate_usd == null ? null : sharedFrom ? 0 : first.token_cost_estimate_usd + (recovery?.token_cost_estimate_usd || 0) };
      }));
      if (config.analysis?.enabled) {
        const research = await json(root, '02_analysis/03_research/state.json', true);
        reviewStages.push({ stage: 'A03-research', ...research });
      }
      let resultsAnalysis = null, responseAssessments = null;
      const responseIdsByTrial = new Map(), analysisResponsesByTrial = new Map();
      if (paths.resultsFocused) {
        const [comparisons, interpretations, findings, timing, scheduler] = await Promise.all([
          json(root, '02_analysis/02_comparison/comparisons.json', true),
          jsonl(root, '02_analysis/02_comparison/interpretations.jsonl', true),
          json(root, '02_analysis/03_research/findings.json', true),
          json(root, '02_analysis/timing.json', true),
          json(root, '02_analysis/scheduler.json', true)
        ]);
        reviewStages = await Promise.all(['01_results', '02_comparison', '03_research'].map(async stage => ({ stage, ...await json(root, `02_analysis/${stage}/state.json`, true) })));
        if (comparisons && createHash('sha256').update(await readFile(root, paths.diagnosticsFile)).digest('hex') !== comparisons.response_rows_sha256) throw new ViewError('분석 집계와 응답 취합의 버전이 다릅니다.', 503);
        const ids = new Set((diagnostics || []).map(r => r.response_id));
        if (ids.size !== (diagnostics || []).length) throw new ViewError('분석 응답 ID가 중복되었습니다.', 503);
        const linkedIds = [
          ...(comparisons?.overall?.response_ids || []),
          ...(comparisons?.matrix || []).flatMap(row => row.response_ids || []),
          ...(comparisons?.case_profiles || []).map(row => row.original_response_id),
          ...(comparisons?.paired_groups || []).flatMap(group => group.pairs.flatMap(pair => [pair.left?.response_id, pair.right?.response_id].filter(Boolean))),
          ...(interpretations || []).flatMap(row => [...row.response_ids, ...row.excerpts.map(excerpt => excerpt.response_id)])
        ];
        if (linkedIds.some(id => !ids.has(id))) throw new ViewError('분석 표·근거가 실제 응답에 연결되지 않습니다.', 503);
        const interpretationIds = new Set((interpretations || []).map(row => row.id));
        if ((findings?.findings || []).some(row => row.interpretation_ids.some(id => !interpretationIds.has(id)))) throw new ViewError('연구 해석이 실제 관찰에 연결되지 않습니다.', 503);
        const [assessmentText, assessmentSummary, assessmentCoverage] = await Promise.all([
          readFile(root, ASSESSMENT_FILES[0], true), json(root, ASSESSMENT_FILES[1], true), json(root, ASSESSMENT_FILES[2], true)
        ]);
        responseAssessments = readAssessments(assessmentText, assessmentSummary, assessmentCoverage, diagnostics || [], (message, status) => new ViewError(message, status));
        for (const row of diagnostics || []) {
          const key = `${row.model}:${row.trial_id}`;
          if (responseIdsByTrial.has(key)) throw new ViewError('응답 취합에 중복된 모델·요청 ID가 있습니다.', 503);
          responseIdsByTrial.set(key, row.response_id); analysisResponsesByTrial.set(key, row);
        }
        resultsAnalysis = { method: config.analysis.method, comparisons, interpretations, findings, timing, scheduler, stages: reviewStages,
          response_assessment_summary: responseAssessments?.summary ?? null, response_assessment_coverage: responseAssessments?.coverage ?? null,
          responses: (diagnostics || []).map(r => ({ response_id: r.response_id, case: r.case, variant: r.variant, model: r.model, prompt_condition: r.prompt_condition, reasoning: r.reasoning, status: r.status, original_result: r.original_result, answer: r.response?.answer, answer_scale: r.response?.answer_meta?.scale ?? null, answer_negative: r.response?.answer_meta?.negative ?? null, classification: r.response?.classification })) };
      }
      const publicItems = new Map(pub.map(item => [item.item_id, item]));
      const privateItems = new Map(priv.map(item => [item.item_id, item]));
      const evaluationChecks = numericObservations?.length ? numericObservations : diagnostics || [];
      const diagnosticMap = new Map(evaluationChecks.map(row => [`${row.model}:${row.trial_id}`, row]));
      if (diagnosticMap.size !== evaluationChecks.length) throw new ViewError('숫자 비교 기록에 중복 요청 ID가 있습니다.', 503);
      const warnings = [], rows = [], summaries = [];
      let matchedNumericObservations = 0;
      for (const model of config.models) {
        const modelSummary = await json(root, `${paths.results(model.key)}/summary.json`, true);
        summaries.push({ ...modelSummary, key: model.key, display_name: model.model ?? model.key });
        const results = await jsonl(root, `${paths.results(model.key)}/results.jsonl`, true);
        if (!results) { warnings.push(`${model.key}: 결과 목록 미생성. 계획 요청은 요약에서만 확인할 수 있습니다.`); continue; }
        const seen = new Set();
        for (const row of results) {
          if (seen.has(row.trial_id)) throw new ViewError(`${model.key}: 중복 요청 ID가 있어 집계를 중단했습니다.`, 503);
          seen.add(row.trial_id);
          const analysisResponse = analysisResponsesByTrial.get(`${model.key}:${row.trial_id}`);
          if (analysisResponse && ['item_id', 'case', 'variant', 'prompt_condition', 'reasoning', 'status'].some(key => analysisResponse[key] !== row[key])) throw new ViewError('A01 응답 취합과 실제 요청 연결이 다릅니다.', 503);
          const diagnostic = diagnosticMap.get(`${model.key}:${row.trial_id}`);
          if (numericObservations && diagnostic && ['item_id', 'case', 'variant', 'prompt_condition', 'reasoning', 'status'].some(key => diagnostic[key] !== row[key])) throw new ViewError('숫자 비교 기록과 실제 요청 연결이 다릅니다.', 503);
          if (numericObservations && diagnostic) matchedNumericObservations++;
          const judged = semanticMap.get(`${model.key}:${row.trial_id}`);
          if (judged && ['item_id', 'case', 'variant', 'prompt_condition', 'reasoning'].some(key => judged[key] !== row[key])) throw new ViewError('내용 판정과 실제 요청 연결이 다릅니다.', 503);
          rows.push({ ...row, checks: { ...row.checks, ...diagnostic?.checks }, model: model.key, question: publicItems.get(row.item_id)?.question ?? '', tags: diagnostic?.tags ?? [], diagnostic, semantic: semanticMap.get(`${model.key}:${row.trial_id}`) ?? null });
        }
        if (modelSummary?.planned != null && modelSummary.planned !== results.length) warnings.push(`${model.key}: 계획 ${modelSummary.planned}건 / 결과 목록 ${results.length}건. 갱신 확인이 필요합니다.`);
        if (modelSummary?.statuses && JSON.stringify(Object.entries(modelSummary.statuses).sort()) !== JSON.stringify(Object.entries(countBy(results, r => r.status)).sort())) warnings.push(`${model.key}: 저장 요약과 결과 목록의 상태 수가 다릅니다.`);
      }
      if (numericObservations && (numericObservations.length !== rows.length || matchedNumericObservations !== rows.length)) throw new ViewError('숫자 비교 기록과 실제 요청의 건수가 다릅니다.', 503);
      if (state?.status && summary?.status && state.status !== summary.status) warnings.push(`실행 상태 ${state.status} / 저장 요약 ${summary.status}. 실행 상태를 우선 표시합니다.`);
      if (selection && summary && (selection.originals !== summary.originals || selection.variants !== summary.variants)) warnings.push('저장 요약의 문항 수와 요청 manifest가 다릅니다. manifest의 고유 문항 수를 표시합니다.');
      if (!diagnostics && !numericObservations) warnings.push('진단 분석이 아직 생성되지 않았습니다. 결과 목록의 기존 검사만 표시합니다.');
      if (semanticRows && rows.filter(row => row.semantic).length !== semanticRows.length) throw new ViewError('실제 요청에 없는 내용 판정이 있습니다.', 503);
      if (signature !== await this.signature(root, config.models, config)) throw new ViewError('파일이 갱신 중입니다. 잠시 뒤 새로 읽어 주세요.', 503);
      const researchReview = (events || []).filter(event => event.event === 'STUDY_CRITICAL_REVIEW').at(-1) ?? null;
      const reviewReset = (events || []).filter(event => event.event === 'USER_REVIEW_RESET').at(-1) ?? null;
      const finalization = await readFinalization(root, state, await json(root, '02_analysis/03_research/state.json', true));
      if (signature !== await this.signature(root, config.models, config)) throw new ViewError('파일이 갱신 중입니다. 새로 읽어 주세요.', 503);
      const snap = { finalization, id, root, signature, config, state, summary, plan, selection, publicItems, privateItems, rows, summaries, warnings, verification, semantic, reviewStages, researchReview, reviewReset, resultsAnalysis, responseAssessments, responseIdsByTrial, analysisResponsesByTrial, diagnosticsAvailable: diagnostics !== null || numericObservations !== null, files: new Map(), loaded_at: new Date().toISOString() };
      this.cache.set(id, snap);
      while (this.cache.size > 3) this.cache.delete(this.cache.keys().next().value);
      return snap;
    } catch (error) {
      if (previous && !(error instanceof ViewError && error.status === 403)) return { ...previous, warnings: [...previous.warnings, `마지막 정상 자료 표시 중: ${error.message}`], stale: true };
      throw error;
    }
  }
  selected(snap, filters = {}) { return selected(snap, filters); }
  query(snap, filters = {}) { return query(snap, filters); }
  overview(snap, filters = {}) { return overview(snap, filters); }
  analysisPairs(snap, filters = {}) {
    const index = Number(filters.group), requested = Number(filters.offset ?? 0);
    if (!Number.isSafeInteger(index) || index < 0 || !Number.isSafeInteger(requested) || requested < 0) throw new ViewError('대응 쌍 위치가 올바르지 않습니다.');
    const group = snap.resultsAnalysis?.comparisons?.paired_groups?.[index];
    if (!group) throw new ViewError('저장된 대응 쌍이 없습니다.', 404);
    const pageSize = 50, pairs = group.pairs || [];
    const offset = Math.min(requested, pairs.length);
    return { group: index, axis: group.axis, total: pairs.length, offset, page_size: pageSize, pairs: pairs.slice(offset, offset + pageSize) };
  }
  async sourceTypeCases(snap, sourceType) {
    const index = await json(snap.root, '02_analysis/source-types/source-type-index.json', true);
    if (!index) throw new ViewError('이 실행에는 원천 유형별 집계가 없습니다.', 404);
    if (index.run !== snap.id || !Array.isArray(index.types)) throw new ViewError('원천 유형 색인이 실행과 일치하지 않습니다.', 503);
    const item = index.types.find(entry => entry.source_type === sourceType);
    if (!item || !['FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning'].includes(sourceType)) throw new ViewError('원천 유형 선택값이 올바르지 않습니다.');
    const summary = await json(snap.root, `${item.folder}/summary.json`);
    const ids = summary?.case_ids;
    if (summary.source_type !== sourceType || !Array.isArray(ids) || ids.length !== item.case_count
        || new Set(ids).size !== ids.length || ids.some(id => typeof id !== 'string'))
      throw new ViewError('원천 유형 문항 목록이 색인과 일치하지 않습니다.', 503);
    return { source_type: sourceType, case_count: ids.length, caseIds: ids };
  }
  async rqSourceSummaries(snap) {
    if (!snap.resultsAnalysis?.responses?.length) throw new ViewError('A01 저장 응답이 아직 없습니다.', 404);
    const index = await json(snap.root, '02_analysis/source-types/source-type-index.json', true);
    if (!index) return { types: [] };
    const types = [];
    for (const item of index.types || []) {
      const source = await this.sourceTypeCases(snap, item.source_type);
      types.push({ source_type: source.source_type, case_count: source.case_count,
        rq_answers: rqAnswerOverview(snap.resultsAnalysis, { caseIds: source.caseIds }) });
    }
    return { types };
  }
  async rqPairs(snap, filters = {}) {
    if (!snap.resultsAnalysis?.responses?.length) throw new ViewError('A01 저장 응답이 아직 없습니다.', 404);
    try {
      const source = filters.source_type ? await this.sourceTypeCases(snap, filters.source_type) : null;
      return rqAnswerPage(snap.resultsAnalysis, { ...filters, caseIds: source?.caseIds });
    }
    catch (error) { if (error instanceof ViewError) throw error; throw new ViewError(error.message, 400); }
  }
  async pairOutcomes(snap) {
    const summary = await json(snap.root, '02_analysis/02_comparison/pair-outcomes/summary.json', true);
    if (!summary) return { status: 'NOT_PREPARED', run_id: snap.id, types: [] };
    if (summary.run_id !== snap.id || summary.schema_version !== 'RQ1PairOutcomeV2')
      throw new ViewError('Q01 Pair Matrix는 최신 pipeline 집계가 필요합니다.', 503);
    return summary;
  }
  async rq1Materials(snap) {
    if (!snap.rq1MaterialsPromise) {
      snap.rq1MaterialsPromise = readRQ1Materials(snap, { safePath, readJSON: json, readText: readFile, artifactPaths,
        fail: (message, status) => new ViewError(message, status) }).then(async data => {
        if (snap.signature !== await this.signature(snap.root, snap.config.models, snap.config)) throw new ViewError('RQ1 자료가 갱신 중입니다. 새로 읽어 주세요.', 503);
        return data;
      }).catch(error => { delete snap.rq1MaterialsPromise; throw error; });
    }
    return snap.rq1MaterialsPromise;
  }
  // [EV27.1] Join only saved A02 verdicts and the exact original/variant trials.
  async groundingData(snap) {
    if (!snap.groundingDataPromise) {
      snap.groundingDataPromise = readGroundingPairs(snap, { safePath, readJSON: json, readText: readFile,
        fail: (message, status) => new ViewError(message, status) }).then(async data => {
        if (snap.signature !== await this.signature(snap.root, snap.config.models, snap.config)) throw new ViewError('근거 타당성 자료가 갱신 중입니다. 새로 읽어 주세요.', 503);
        return data;
      }).catch(error => { delete snap.groundingDataPromise; throw error; });
    }
    return snap.groundingDataPromise;
  }
  async groundingPairs(snap, filters = {}) {
    if (filters.mode && !['summary', 'pairs'].includes(filters.mode)) throw new ViewError('알 수 없는 근거 타당성 조회입니다.');
    const data = await this.groundingData(snap);
    try { return filters.mode === 'pairs' ? groundingPage(data, filters) : groundingSummary(data, filters); }
    catch (error) { throw new ViewError(error.message, 400); }
  }
  async input(snap) { const { inputFlow } = await import('./input-flow.mjs'); return inputFlow(this, snap); }
  async register(snap, relative, label) {
    if (!relative) return null;
    try { const target = await safePath(snap.root, relative); if (!(await fs.stat(target)).isFile()) return null; }
    catch (error) { if (error.code === 'ENOENT') return null; throw error; }
    const id = idFor(relative); snap.files.set(id, relative); return { id, path: relative, label: label ?? relative };
  }
  async request(snap, row) {
    for await (const request of manifestRequests(snap.root, artifactPaths(snap.config).request(row.model))) if (request.trial_id === row.trial_id) return request;
    return null;
  }
  // [EV04.1] The online and offline readers use the same case selection rules.
  async detail(snap, caseId, filters = {}) {
    const selection = selectCase(snap, caseId, filters);
    const responses = [];
    for (const { model, row } of selection.rows) responses.push(row ? await this.response(snap, row) : { model, status: 'NOT_PLANNED', missing: true });
    const conditions = caseConditionRows(snap, selection), records = Object.fromEntries(responses.filter(response => response.trial_id).map(response => [`${response.model}:${response.trial_id}`, response]));
    const models = new Set(selection.rows.map(({ model }) => model));
    // [EV16.2] Read every condition for this case, without re-reading request manifests.
    await Promise.all(snap.rows.filter(row => row.case === caseId && models.has(row.model) && !records[`${row.model}:${row.trial_id}`]).map(async row => {
      try {
        const result = row.result_path ? await json(snap.root, row.result_path, true) : null;
        const call = (result?.elapsed_seconds == null || result?.response == null) && row.call_path ? await json(snap.root, row.call_path, true) : null;
        records[`${row.model}:${row.trial_id}`] = { elapsed_seconds: recordedElapsed(result, call), response: result?.response ?? call?.response ?? row.response ?? null };
      } catch { records[`${row.model}:${row.trial_id}`] = { elapsed_seconds: null, timing_error: true, read_error: true }; }
    }));
    return assembleCase(snap, selection, responses, conditionTimings(conditions, records), records);
  }
  async response(snap, row, savedRequest, readJSON = json) {
    const call = row.call_path ? await readJSON(snap.root, row.call_path, true) : null;
    const result = row.result_path ? await readJSON(snap.root, row.result_path, true) : null;
    const request = call?.request ?? (savedRequest !== undefined ? savedRequest : await this.request(snap, row));
    const response = result?.response ?? call?.response ?? row.response ?? null;
    const artifacts = (await Promise.all([
      this.register(snap, row.call_path, '호출 JSON'), this.register(snap, row.result_path, '검사 원기록'),
      this.register(snap, call?.records?.raw_response_path ?? (row.result_path ? path.posix.join(path.posix.dirname(row.result_path), 'raw-response.json') : null), '제공자 원응답')
    ])).filter(Boolean);
    const attempts = [];
    for (const attempt of call?.records?.attempts ?? []) attempts.push({ ...attempt, artifact: await this.register(snap, attempt.result_path, `${attempt.attempt} · ${attempt.status}`) });
    const responseId = snap.responseIdsByTrial?.get(`${row.model}:${row.trial_id}`) ?? null;
    const fingerprint = snap.responseAssessments?.responseFingerprints.get(responseId);
    if (fingerprint && responseFingerprint(response) !== fingerprint) throw new ViewError('A02가 검토한 응답과 현재 저장된 응답 본문이 다릅니다. 다시 취합한 자료를 확인해 주세요.', 503);
    return { model: row.model, status: row.status, trial_id: row.trial_id, response_id: responseId,
      response_assessment: snap.responseAssessments?.byResponse.get(responseId) ?? null,
      response_assessment_state: row.variant === 'ORIGINAL' ? 'ORIGINAL_EXCLUDED' : snap.responseAssessments ? 'AVAILABLE' : 'MISSING',
      response, response_text: call?.response_text ?? null,
      request, checks: row.checks ?? null, semantic: row.semantic ?? null, diagnostic: row.diagnostic ?? null, schema_errors: result?.schema_errors ?? row.schema_errors ?? [],
      error: result?.error ?? row.error, usage: result?.usage ?? null, finish_reason: result?.finish_reason ?? row.finish_reason, elapsed_seconds: recordedElapsed(result, call), artifacts, attempts,
      missing_result: !!row.result_path && !result };
  }
  async documents(snap) {
    const files = [];
    const walk = async (relative, depth) => {
      const dir = relative ? await safePath(snap.root, relative) : snap.root;
      for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
        if (entry.isSymbolicLink()) continue;
        const name = path.posix.join(relative, entry.name);
        if (entry.isFile() && (entry.name.endsWith('.md') || ['rq-sq-review-v026.json', 'rq-sq-review.json', 'source-type-index.json', 'summary.json'].includes(entry.name))) files.push(await this.register(snap, name));
        else if (entry.isDirectory() && depth > 0 && !['calls', 'remote-results', '_recovery', '01-requests', '02-batches', 'batches', '00-definition'].includes(entry.name)) await walk(name, depth - 1);
      }
    };
    await walk('', 3);
    return files.filter(Boolean).sort((a, b) => a.path.localeCompare(b.path));
  }
  async file(snap, id, readText = readFile) {
    const relative = snap.files.get(id);
    if (!relative) throw new ViewError('파일 목록을 새로 읽은 뒤 다시 선택해 주세요.', 404);
    const target = await safePath(snap.root, relative);
    const info = await fs.stat(target);
    if (info.size > 8 * 1024 * 1024) throw new ViewError('8MB를 넘는 원파일입니다. 문항별 호출 파일로 좁혀 주세요.', 413);
    const content = await readText(snap.root, relative);
    const links = {};
    if (relative.endsWith('.md')) {
      for (const match of content.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
        const href = match[1].replace(/^<|>$/g, '').split('#')[0];
        if (!href || /^[a-z][a-z0-9+.-]*:/i.test(href)) continue;
        let resolved;
        if (path.isAbsolute(href)) {
          const marker = `/experiments-run/${snap.id}/`, index = href.indexOf(marker);
          if (index < 0) continue; resolved = href.slice(index + marker.length);
        } else resolved = path.posix.normalize(path.posix.join(path.posix.dirname(relative), href));
        try { links[match[1]] = await this.register(snap, resolved); } catch { /* Keep out-of-run references as plain text. */ }
      }
    }
    return { id, path: relative, content, links };
  }
  async activity(snap) {
    let events = [];
    try {
      const file = await fs.open(await safePath(snap.root, 'events.jsonl'), 'r');
      try {
        const stat = await file.stat(), start = Math.max(0, stat.size - 180000), buffer = Buffer.alloc(stat.size - start);
        await file.read(buffer, 0, buffer.length, start);
        const lines = buffer.toString('utf8').split('\n'); if (start) lines.shift();
        events = lines.filter(l => l.trim()).flatMap(l => { try { return [JSON.parse(l)]; } catch { return []; } }).slice(-100).reverse();
      } finally { await file.close(); }
    } catch (e) { if (e.code !== 'ENOENT') throw e; }
    const resources = [];
    for (const model of snap.config.models) {
      const latest = await json(snap.root, `${model.key}/resources-latest.json`, true);
      const summary = await json(snap.root, `analysis/${model.key}-resources.json`, true);
      if (latest || summary) resources.push({ model: model.key, latest, summary });
    }
    return { state: snap.state, plan: snap.plan, events, event_limit: 100, scope: 'LATEST_SAVED_EVENTS', models: snap.summaries, resources };
  }
  export(snap, filters = {}) { return exportMarkdown(snap, filters); }
}
