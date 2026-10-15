import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { gzip } from 'node:zlib';
import { promisify } from 'node:util';
import { safePath, ViewError, manifestRequests, artifactPaths } from './repository.mjs';
import { assetDirectory } from './paths.mjs';
import { readSemanticOutcomeData } from './semantic-outcomes.mjs';
import { GROUNDING_FILES } from './grounding-reader.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const compress = promisify(gzip);
const changed = () => new ViewError('자료가 내보내기 중 갱신되었습니다. 저장이 끝난 뒤 다시 내보내 주세요.', 409);
const safeJSON = value => JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
const token = info => `${info.ino}:${info.size}:${info.mtimeMs}:${info.ctimeMs}`;

// [EV06.1] Freeze one complete run without writing to any experiment folder.
export async function buildBundle(repository, original, { signal, progress = () => {}, initialView = {} } = {}) {
  if (original.stale) throw new ViewError('마지막 정상 자료를 표시 중입니다. 최신 자료를 정상적으로 읽은 뒤 내보내 주세요.', 409);
  const snap = { ...original, files: new Map() }, stamps = new Map();
  const checkpoint = () => signal?.throwIfAborted();
  async function stamp(relative) {
    try { return token(await fs.stat(await safePath(snap.root, relative))); }
    catch (error) { if (error.code === 'ENOENT') return 'missing'; throw error; }
  }
  async function observe(relative) {
    checkpoint();
    const value = await stamp(relative);
    if (stamps.has(relative) && stamps.get(relative) !== value) throw changed();
    stamps.set(relative, value); return value;
  }
  async function readText(root, relative, optional = false) {
    if (await observe(relative) === 'missing' && optional) return null;
    const value = await fs.readFile(await safePath(root, relative), 'utf8');
    await observe(relative); return value;
  }
  async function readJSON(root, relative, optional) {
    const value = await readText(root, relative, optional);
    if (value === null) return null;
    try { return JSON.parse(value); } catch { throw new ViewError(`${relative}: 저장 중인 JSON은 내보낼 수 없습니다.`, 409); }
  }
  const initial = Object.fromEntries(['lang', 'tab', 'case', 'model', 'experiment', 'variant', 'prompt', 'reasoning', 'status', 'tags', 'tag_mode', 'q', 'metric', 'display_metric', 'paired', 'sort', 'diagnostic_sort', 'offset', 'case_offset', 'rq1_metric', 'rq1_model', 'rq1_source', 'rq1_variant', 'ground_view', 'ground_prompt', 'ground_reasoning', 'ground_original', 'ground_model', 'ground_source', 'ground_variant', 'ground_abstention', 'ground_decision', 'ground_review'].filter(key => initialView[key]).map(key => [key, initialView[key]]));
  const bundle = { version: 1, exported_at: new Date().toISOString(), initial_view: initial,
    run: { id: snap.id, status: snap.state?.status ?? snap.summary?.status ?? 'UNKNOWN', originals: snap.summary?.originals ?? null, variants: snap.summary?.variants ?? null, updated_at: snap.summary?.updated_at ?? null, models: snap.config.models.map(m => m.key) },
    cases: Object.create(null), files: Object.create(null), documents: [], chunks: Object.create(null),
    stats: { requests: snap.rows.length, cases: 0, files: 0, unavailable_files: [], scope: 'ENTIRE_RUN', model_calls_added: 0 } };
  const pack = async (key, value) => { checkpoint(); bundle.chunks[key] = (await compress(JSON.stringify(value), { level: 6 })).toString('base64'); };

  // Read each manifest once; share repeated input/schema/prompt objects in memory.
  const requests = new Map(), pool = new Map();
  const intern = value => { const key = JSON.stringify(value); if (!pool.has(key)) pool.set(key, value); return pool.get(key); };
  const needsRequest = new Set(snap.rows.map(r => `${r.model}:${r.trial_id}`));
  for (const model of snap.config.models) {
    const relative = artifactPaths(snap.config).request(model.key);
    if (await observe(relative) === 'missing') continue;
    for await (const request of manifestRequests(snap.root, relative)) {
        checkpoint();
        const key = `${model.key}:${request.trial_id}`;
        if (!needsRequest.has(key)) continue;
        if (requests.has(key)) throw new ViewError(`${model.key}: 요청 ID가 중복되어 내보내기를 중단했습니다.`, 409);
        for (const field of ['input', 'response_schema', 'prompt']) if (request[field] !== undefined) request[field] = intern(request[field]);
        requests.set(key, request);
    }
    await observe(relative);
  }
  pool.clear();

  const cases = new Map();
  for (const item of snap.privateItems.values()) if (!cases.has(item.case)) cases.set(item.case, []);
  for (const row of snap.rows) { if (!cases.has(row.case)) throw new ViewError(`문항 ${row.case}의 입력 자료가 없어 내보내기를 중단했습니다.`, 409); cases.get(row.case).push(row); }
  async function filesFor(ids, chunkKey) {
    const files = Object.create(null), queue = [...ids];
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i];
      if (!id || Object.hasOwn(bundle.files, id)) continue;
      bundle.files[id] = chunkKey;
      let file;
      try { file = await repository.file(snap, id, readText); }
      catch (error) {
        if (error.status !== 413) throw error;
        file = { id, path: snap.files.get(id), error: error.message };
        bundle.stats.unavailable_files.push({ path: file.path, reason: file.error });
      }
      files[id] = file;
      for (const link of Object.values(file.links ?? {})) if (link) queue.push(link.id);
    }
    return files;
  }
  for (const [caseId, rows] of cases) {
    checkpoint();
    const key = `case-${bundle.stats.cases}`, responses = Object.create(null), ids = [];
    const privateItems = [...snap.privateItems].filter(([, item]) => item.case === caseId);
    const publicItems = privateItems.map(([id]) => [id, snap.publicItems.get(id)]);
    for (const row of rows) {
      const response = await repository.response(snap, row, requests.get(`${row.model}:${row.trial_id}`) ?? null, readJSON);
      if (!response.request) throw new ViewError(`${row.model} / ${row.trial_id}: 정확한 요청 자료가 없어 내보내기를 중단했습니다.`, 409);
      responses[`${row.model}:${row.trial_id}`] = response;
      ids.push(...response.artifacts.map(a => a.id), ...response.attempts.map(a => a.artifact?.id));
    }
    const files = await filesFor(ids, key);
    await pack(key, { publicItems, privateItems, responses, files });
    bundle.cases[caseId] = key; bundle.stats.cases++;
    progress({ event: 'HTML_EXPORT_CASE', run: snap.id, completed: bundle.stats.cases, total: cases.size });
  }
  requests.clear();
  const inputFlow = await repository.input(snap), inputIds = [];
  const collectInputFiles = value => {
    if (!value || typeof value !== 'object') return;
    if (value.id && value.status === 'AVAILABLE') inputIds.push(value.id);
    for (const item of Object.values(value)) collectInputFiles(item);
  };
  collectInputFiles(inputFlow);
  await pack('input-files', { files: await filesFor(inputIds, 'input-files') });
  bundle.documents = await repository.documents(snap);
  await pack('documents', { files: await filesFor(bundle.documents.map(d => d.id), 'documents') });
  const activityFiles = ['events.jsonl', ...snap.config.models.flatMap(m => [`${m.key}/resources-latest.json`, `analysis/${m.key}-resources.json`])];
  for (const relative of activityFiles) await observe(relative);
  await pack('activity', { activity: await repository.activity(snap) });

  await observe('02_analysis/05_outcomes/summary.json');
  await observe('02_analysis/05_outcomes/responses.jsonl');
  let semanticOutcomes;
  try { semanticOutcomes = await readSemanticOutcomeData(snap.root); }
  catch (error) { semanticOutcomes = { status: 'UNAVAILABLE', error: error.message }; }
  await pack('semantic-outcomes', semanticOutcomes);

  // Keep only fields needed by shared filters and summary tables in the eager index.
  const rows = snap.rows.map(r => ({ case: r.case, model: r.model, trial_id: r.trial_id, item_id: r.item_id, experiment: r.experiment,
    variant: r.variant, prompt_condition: r.prompt_condition, reasoning: r.reasoning, status: r.status, question: r.question, tags: r.tags,
    checks: r.checks, semantic: r.semantic, response: r.response === undefined ? undefined : { answer: r.response?.answer, classification: r.response?.classification, explanation: r.response?.explanation } }));
  const index = { finalization: snap.finalization, id: snap.id, config: { models: snap.config.models.map(m => ({ key: m.key, model: m.model })), improvement: snap.config.improvement, layout_version: snap.config.layout_version, analysis: snap.config.analysis, evaluation_reuse: snap.config.evaluation_reuse, run_kind: snap.config.run_kind }, resultsAnalysis: snap.resultsAnalysis, state: snap.state, summary: snap.summary, plan: snap.plan, semantic: snap.semantic, reviewStages: snap.reviewStages, researchReview: snap.researchReview, reviewReset: snap.reviewReset,
    inputFlow, selection: snap.selection, summaries: snap.summaries, verification: snap.verification, diagnosticsAvailable: snap.diagnosticsAvailable,
    warnings: snap.warnings, loaded_at: snap.loaded_at, rows };
  index.rq1Materials = await repository.rq1Materials(snap);
  // [EV27.3] Lazy paired metadata; explanations and citations stay in case chunks.
  for (const relative of GROUNDING_FILES) await observe(relative);
  let grounding;
  try { grounding = await repository.groundingData(snap); }
  catch (error) {
    if (!(error instanceof ViewError) || error.status !== 503) throw error;
    grounding = { metadata: { run_id: snap.id, status: 'UNAVAILABLE', error: error.message }, pairs: [] };
  }
  await pack('grounding-pairs', grounding);
  await pack('index', index);
  for (const relative of stamps.keys()) await observe(relative);
  if (JSON.stringify(bundle.documents) !== JSON.stringify(await repository.documents(snap))) throw changed();
  if (snap.signature !== await repository.signature(snap.root, snap.config.models, snap.config)) throw changed();
  bundle.stats.files = Object.keys(bundle.files).length;
  return bundle;
}

// [EV06.2] Inline the same application with a compressed data adapter and strict CSP.
export async function renderHTML(bundle) {
  const names = ['index.html', 'styles.css', 'model.mjs', 'offline.mjs', 'json-viewer.mjs', 'input-edits.mjs', 'feature-quadrant.mjs', 'response-assessments.mjs', 'rq1-materials.mjs', 'grounding-model.mjs', 'grounding-view.mjs', 'semantic-outcomes-model.mjs', 'semantic-outcomes.mjs', 'app.js'];
  const [template, baseCSS, model, offline, jsonViewer, inputEdits, featureQuadrant, responseAssessments, rq1Materials, groundingModel, groundingView, outcomeModel, outcomeView, app] = await Promise.all(names.map(name => fs.readFile(path.join(assetDirectory, name), 'utf8')));
  const [localeJS, localeCSS] = await Promise.all(['i18n.js', 'i18n.css'].map(name => fs.readFile(path.join(assetDirectory, '../shared', name), 'utf8')));
  const css = baseCSS + '\n' + localeCSS;
  const modelNames = [...model.matchAll(/^export (?:function|const) (\w+)/gm)].map(m => m[1]);
  const modelCode = `const Model = (() => {\n${model.replace(/^export /gm, '')}\nreturn {${modelNames.join(',')}};\n})();\nconst { pairMatrixReadiness } = Model;`;
  const adapter = offline.replace(/^import .*;\n/gm, '').replace(/^export /gm, '');
  const viewerCode = `const { copySource, valueView } = (() => {\n${jsonViewer.replace(/^export /gm, '')}\nreturn { copySource, valueView };\n})();`;
  const editsCode = `const { verifyInputEdits, inputEditNotice, inputEditDeletions, renderInputContext } = (() => {\n${inputEdits.replace(/^export /gm, '')}\nreturn { verifyInputEdits, inputEditNotice, inputEditDeletions, renderInputContext };\n})();`;
  const featureCode = `const { buildFeatureQuadrant } = (() => {\n${featureQuadrant.replace(/^export /gm, '')}\nreturn { buildFeatureQuadrant };\n})();`;
  const assessmentCode = `const { renderAssessmentSummary, renderResponseAssessment } = (() => {\n${responseAssessments.replace(/^export /gm, '')}\nreturn { renderAssessmentSummary, renderResponseAssessment };\n})();`;
  const rq1Code = `const { renderRQ1Materials } = (() => {\n${rq1Materials.replace(/^export /gm, '')}\nreturn { renderRQ1Materials };\n})();`;
  const groundingModelCode = `const { GROUNDING_VERDICTS, GROUNDING_REVIEWS, groundingSummary, groundingPage } = (() => {\n${groundingModel.replace(/^export /gm, '')}\nreturn { GROUNDING_VERDICTS, GROUNDING_REVIEWS, groundingSummary, groundingPage };\n})();`;
  const groundingViewCode = `const { renderGrounding } = (() => {\n${groundingView.replace(/^import .*;\n/gm, '').replace(/^export /gm, '')}\nreturn { renderGrounding };\n})();`;
  const outcomeCode = `const { outcomePage } = (() => {\n${outcomeModel.replace(/^export /gm, '')}\nreturn { outcomePage };\n})();\nconst { renderSemanticOutcomes } = (() => {\n${outcomeView.replace(/^export /gm, '')}\nreturn { renderSemanticOutcomes };\n})();`;
  const script = `${localeJS}\n${modelCode}\n${groundingModelCode}\n${outcomeCode}\n${adapter}\n${viewerCode}\n${editsCode}\n${featureCode}\n${assessmentCode}\n${rq1Code}\n${groundingViewCode}\nconst embedded = document.getElementById('experiment-snapshot');\nglobalThis.FINARCH_EXPERIMENT_OFFLINE = createOfflineStore(JSON.parse(embedded.textContent));\nembedded.remove();\nif (FINARCH_EXPERIMENT_OFFLINE.initialView.lang) FinarchI18n.setLanguage(FINARCH_EXPERIMENT_OFFLINE.initialView.lang, { persist: false });\n${app.replace(/^import .*;\n/gm, '')}`;
  if (/<\/script/i.test(script) || /<\/style/i.test(css)) throw Error('Unsafe embedded source delimiter');
  const digest = value => createHash('sha256').update(value).digest('base64');
  const csp = `default-src 'none'; script-src 'sha256-${digest(script)}'; style-src 'sha256-${digest(css)}'; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`;
  const data = `<script type="application/json" id="experiment-snapshot">${safeJSON(bundle)}</script>`;
  return template.replace('<meta name="color-scheme" content="light">', `<meta name="color-scheme" content="light">\n  <meta http-equiv="Content-Security-Policy" content="${csp}">`)
    .replace('<title>FIN-ARCH · 실험 결과</title>', `<title>${bundle.run.id} · 실험 결과 · 오프라인</title>`)
    .replace('<link rel="stylesheet" href="/styles.css">', () => `<style>${css}</style>`)
    .replace('<link rel="stylesheet" href="/i18n.css">', '')
    .replace('<script src="/i18n.js" defer></script>', '')
    .replace('<script src="/app.js" type="module"></script>', '')
    .replace('</body>', () => `${data}\n<script type="module">${script}</script>\n</body>`);
}

export async function exportHTML(repository, snap, options) {
  const bundle = await buildBundle(repository, snap, options);
  return { html: await renderHTML(bundle), bundle, filename: `${snap.id}-experiments.html` };
}
