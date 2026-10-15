import { copySource, valueView } from './json-viewer.mjs';
import { verifyInputEdits, inputEditNotice, inputEditDeletions, renderInputContext } from './input-edits.mjs';
import { buildFeatureQuadrant } from './feature-quadrant.mjs';
import { pairMatrixReadiness } from './model.mjs';
import { renderAssessmentSummary, renderResponseAssessment } from './response-assessments.mjs';
import { renderRQ1Materials } from './rq1-materials.mjs';
import { renderGrounding } from './grounding-view.mjs';
import { renderSemanticOutcomes, renderOutcomeComparison } from './semantic-outcomes.mjs';

const $ = id => document.getElementById(id);
const OFFLINE = globalThis.FINARCH_EXPERIMENT_OFFLINE;
const TABS = { overview: '전체 결과', analysis: '내용 분석', conditions: '조건별 비교', models: '두 모델 나란히', case: '문항 비교', failures: '실패 분석', costs: '비용·실행', reports: '보고서·이력' };
TABS.input = '입력과 전달 경로';
TABS['pair-matrix'] = 'Pair Matrix';
TABS['analysis-failures'] = '실패·검토 불가';
TABS.grounding = '근거 타당성';
TABS.answerable = 'ANSWERABLE';
const STAGES = { input: { title: '00 Input', tabs: ['input'], flow: 'dataset results → public Q/C·precision / private 평가 자료' }, evaluation: { title: '01 Evaluation', tabs: ['overview', 'case', 'costs', 'failures'], flow: 'E01 준비 → E02 요청 → E03 LLM 실행 → E04 형식 검사' }, analysis: { title: '02 Analysis', tabs: ['analysis', 'conditions', 'models', 'grounding', 'reports'], flow: 'A01 입력·응답 내용 검토 → A02 조건·차수 비교 → A03 연구 해석' } };
const STEP_CODES = { input: '00', overview: 'E01', case: 'E02', costs: 'E03', failures: 'E04', analysis: 'A01', conditions: 'A02', models: 'A02', reports: 'A04' };
STAGES.analysis.tabs.push('answerable', 'analysis-failures');
STAGES.comparison = { title: '03 Quadrant', tabs: ['pair-matrix'], flow: 'Q01 Pair Matrix · 원본 수치 정답 여부 × 변형 대응 적절성' };
STEP_CODES['pair-matrix'] = 'Q01';
STEP_CODES.answerable = 'A05';
STEP_CODES['analysis-failures'] = 'A06';
STEP_CODES.grounding = 'A03';
const OUTCOMES = { SUPPORTED_ANSWER: '타당한 단일 답', SUPPORTED_CONDITIONAL_OR_ABSTENTION: '타당한 조건부 답·유보', UNJUSTIFIED_ABSTENTION: '불필요한 유보', UNSUPPORTED_ANSWER: '근거 없는 단정', CALCULATION_OR_REASONING_ERROR: '계산·논리 오류', EVIDENCE_ERROR: '근거 오류', UNRESOLVED: '미해결', NOT_REVIEWED: '미검토' };
const VARIANTS = { ORIGINAL: '00 · 원본', IC_VALUE_01_BEFORE: '01 · IC-value · 앞', IC_VALUE_01_AFTER: '02 · IC-value · 뒤', IC_SOURCE_A_ONLY: '03 · IC-source · 앞', IC_SOURCE_B_ONLY: '04 · IC-source · 뒤', IC_RELATION_01: '05 · IC-relation', EA_01: '06 · EA-01', EA_02: '07 · EA-02' };
const STATUS = { FINISHED: '수집 완료', INCOMPLETE: '일부 미완료', SUPERSEDED_NOT_RUN: '미호출 · 대체됨', PREPARED: '호출 준비됨', RUNNING: '실행 중', PENDING: '대기', VALID: '형식 통과', INVALID_RESPONSE: '형식·일관성 실패', OUTPUT_TRUNCATED: '출력 잘림', NOT_RUN: '미실행', AUTH_BLOCKED: '인증 차단', NOT_PLANNED: '해당 조건 없음', NO_RECORD: '결과 기록 없음', UNKNOWN_DELIVERY: '응답 확인 안 됨', READ_ERROR: '읽기 오류', FORMAT_FAILED: '형식 실패·잘림' };
STATUS.BATCH_PENDING = 'Batch 처리 중';
STATUS.COLLECTED = '저장 완료';
STATUS.REUSED = 'Evaluation 재사용';
STATUS.PAUSED_BY_USER = '사용자 요청으로 실행 일시 중지';
STATUS.RETRY_WAIT = '재시도 대기';
const TAGS = { NUMERIC_MISMATCH: '원본 숫자 불일치', SIGN_ONLY_DIFFERENCE: '부호만 다름', BASELINE_NOT_NUMERICALLY_EVALUATED: '원본 숫자 미평가', MULTIPLE_NUMERIC_TOKENS: '숫자가 여러 개 있음', ANSWER_IS_NUMBER: 'answer가 숫자 타입', ANSWER_IS_NULL: 'answer가 null', OUTPUT_TRUNCATED: '출력 토큰 한도', NULL_ANSWER: 'answer가 null', EVIDENCE_NOT_ARRAY: '근거가 배열이 아님' };
Object.assign(TAGS, { NUMERIC_MATCH: '원본 숫자 일치', SCHEMA_TYPE: '필드 타입 불일치', QUOTE_NOT_EXACT_SUBSTRING: '인용문 정확 일치 없음', ANSWER_NUMERIC_NOT_STRING: 'answer가 문자열 대신 숫자', EMPTY_EVIDENCE: '근거 배열이 비어 있음', SCHEMA_REQUIRED: '필수 필드 누락', ANSWER_NULL: 'answer가 null', JSON_PARSE_OR_TOP_LEVEL_TYPE: 'JSON 또는 최상위 타입 오류', SCHEMA_ADDITIONALPROPERTIES: '허용하지 않은 추가 필드', DECIMAL_PLACES_MISMATCH: '소수 자릿수 불일치', INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE: '형식 실패 · 진단용 숫자값은 일치', INVALID_RESPONSE: '형식·일관성 검사 실패', QUESTION_METADATA_PRECISION_CONFLICT: '질문과 메타정보의 자릿수 충돌', SCHEMA_ANSWER_FORMAT: '답변 형식·일관성 불일치', MAGNITUDE_DIFFERENCE: '숫자 크기 불일치', DECLARED_ABSTENTION: '검사 통과한 유보 선언', RAW_STATUS_ABSTAINED: '원응답 status는 abstained', ABSTAINED_WITH_BOOLEAN_SIGN: '유보 선언에 boolean 부호 있음', ABSTAINED_WITH_NUMERIC_ANSWER: '유보 선언과 숫자 답변 동시 반환' });
const METRICS = { numeric_matches: '원본풀이 정답 일치', numeric_mismatches: '원본풀이 정답 불일치', numeric_unevaluated: '원본 미평가', numeric_pending: '원본 미수집', numeric_answers_absent: '숫자 답 없음', declared_abstentions: '유보 선언', abstention_markers: '유보 표현', missing_quotes: '근거 문자열 불일치' };
const FILTERS = ['model', 'experiment', 'variant', 'prompt', 'reasoning', 'status'];
const fmt = value => value === null || value === undefined ? '미기록' : Number(value).toLocaleString('ko-KR');
const money = value => value === null || value === undefined ? '미기록' : `$${Number(value).toFixed(6)}`;
const time = value => value ? new Date(value).toLocaleString('ko-KR', { hour12: false }) : '미기록';
const label = value => STATUS[value] || value || '미기록';
const promptKey = value => value === 'P0' ? 'unguided' : value === 'P1' ? 'guided' : value;
const promptName = value => promptKey(value) === 'unguided' ? 'Unguided Solving' : promptKey(value) === 'guided' ? 'Criteria-Guided Solving' : value;
const reasoningName = value => value === 'off' ? 'Reasoning OFF' : value === 'on' ? 'Reasoning ON' : value;
const conditionName = (prompt, reasoning) => `${promptName(prompt)} · ${reasoningName(reasoning)}`;
TAGS.NUMERIC_ANSWER_ABSENT = '숫자 답 없음';
const tagLabel = value => TAGS[value] || value.replaceAll('_', ' ');
const show = value => value === undefined ? '기록 없음' : value === null ? 'null' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
const state = { run: '', tab: 'overview' };
let overview, epoch = 0, controller, documentEpoch = 0, modalEpoch = 0;
let resultResponseIndex = new Map();
let availableRuns = [];
let caseListScope = '', listedCase = '';

function el(tag, className, text) { const n = document.createElement(tag); if (className) n.className = className; if (text !== undefined) n.textContent = show(text); return n; }
function localizedValue(tag, className, record, key, prefix = '', suffix = '') {
  const ko = record.display_ko?.[key] ?? record.display?.[key] ?? record[key] ?? '', en = record.display?.[key] ?? record[key] ?? ko;
  const node = el(tag, className, prefix + ko + suffix);
  globalThis.FinarchI18n?.bindText(node, prefix + ko + suffix, (globalThis.FinarchI18n?.translate(prefix, 'en') ?? prefix) + en + suffix);
  return node;
}
function button(text, action, className = '') { const n = el('button', className, text); n.type = 'button'; n.onclick = action; return n; }
function badge(value) { const n = el('span', `badge ${['VALID', 'FINISHED'].includes(value) ? 'good' : ['INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'AUTH_BLOCKED', 'READ_ERROR'].includes(value) ? 'bad' : 'wait'}`, label(value)); if (value === 'OUTPUT_TRUNCATED') n.classList.add('truncated'); return n; }
function section(title, note, index = '') { const p = el('section', 'panel'), h = el('div', 'section-head'), t = el('div'), heading = el('h3'); if (index) heading.append(el('span', 'section-index', index)); heading.append(title); t.append(heading); if (note) t.append(el('p', '', note)); h.append(t); p.append(h); return p; }
function empty(text) { return el('div', 'empty', text); }
function note(text, kind = '') { return el('div', `notice ${kind}`, text); }
function select(options, value, callback) { const n = el('select'); for (const [id, title] of options) { const o = el('option', '', title); o.value = id; n.append(o); } n.value = value; if (callback) n.onchange = () => callback(n.value); return n; }
function table(headers, values) { const wrap = el('div', 'table-wrap'), t = el('table'), head = el('thead'), body = el('tbody'), hr = el('tr'); for (const h of headers) { const th = el('th'); if (h instanceof Node) th.append(h); else th.textContent = show(h); hr.append(th); } head.append(hr); for (const cells of values) { const row = el('tr'); for (const cell of cells) { const td = el('td'); if (cell instanceof Node) td.append(cell); else td.textContent = show(cell); row.append(td); } body.append(row); } t.append(head, body); wrap.append(t); return wrap; }
// Large runs keep closed details empty and add only one page of rows at a time.
function resultPagedDetails(title, headers, items, cellsFor, pageSize = 50) {
  const details = el('details'); details.append(el('summary', '', title));
  let rendered = 0, wrap = null, more = null;
  const addPage = () => {
    const batch = items.slice(rendered, rendered + pageSize).map(cellsFor);
    if (!wrap) { wrap = table(headers, batch); details.append(wrap); }
    else wrap.querySelector('tbody').append(...table(headers, batch).querySelectorAll('tbody tr'));
    rendered += batch.length;
    if (rendered < items.length) {
      if (!more) { more = button('', addPage, 'text-button result-more'); details.append(more); }
      more.textContent = `다음 ${Math.min(pageSize, items.length - rendered)}개 보기 · ${rendered}/${items.length}`;
    } else more?.remove();
  };
  details.addEventListener('toggle', () => { if (details.open && !wrap) addPage(); });
  return details;
}
function resultPairDetails(group, labels = ['첫 입력', '둘째 입력']) {
  const details = el('details'); details.append(el('summary', '', `문항별 응답 ${fmt(group.planned_pairs)}건 보기`));
  let offset = 0, started = false, loading = false, wrap = null, more = null;
  const addPage = async () => {
    if (loading) return;
    loading = true;
    if (more) more.disabled = true;
    try {
      const page = await get(api('analysis-pairs', { group: group.viewer_pair_index, offset }));
      if (!details.isConnected) return;
      const cells = page.pairs.map(p => [p.case, resultPairEndpoint(p.left), resultPairEndpoint(p.right)]);
      if (!wrap) { wrap = table(['문항', ...labels], cells); details.append(wrap); }
      else wrap.querySelector('tbody').append(...table(['문항', ...labels], cells).querySelectorAll('tbody tr'));
      offset += page.pairs.length;
      if (offset < page.total) {
        if (!more) { more = button('', addPage, 'text-button result-more'); details.append(more); }
        more.textContent = `다음 ${Math.min(page.page_size, page.total - offset)}쌍 보기 · ${offset}/${page.total}`;
      } else more?.remove();
    } catch (error) {
      if (error.name !== 'AbortError' && details.isConnected) details.append(note(error.message, 'danger'));
    } finally { loading = false; if (more?.isConnected) more.disabled = false; }
  };
  details.addEventListener('toggle', () => { if (details.open && !started) { started = true; addPage(); } });
  return details;
}
function disclosure(title, value, options) { const d = el('details'); d.append(el('summary', '', title), valueView(value, title, options)); return d; }
// [EV03.4] Stable panel keys keep the user's choice across renders and reloads.
const disclosurePreferences = new Map();
const disclosureStoragePrefix = 'finarch.dataset.viewer-exp.disclosure.v1:';
function restoreDisclosure(panel) {
  const key = panel.dataset.disclosureKey;
  if (!disclosurePreferences.has(key)) {
    try {
      const saved = localStorage.getItem(disclosureStoragePrefix + key);
      if (saved === 'open' || saved === 'closed') disclosurePreferences.set(key, saved === 'open');
    } catch { /* Keep the in-page preference when browser storage is unavailable. */ }
  }
  panel.open = disclosurePreferences.get(key) ?? (panel.dataset.defaultOpen !== 'false');
}
function rememberPanel(panel, key, defaultOpen = true) {
  panel.dataset.disclosureKey = key; panel.dataset.defaultOpen = String(defaultOpen); restoreDisclosure(panel);
  panel.addEventListener('toggle', () => rememberDisclosure(panel)); return panel;
}
function rememberDisclosure(panel) {
  if (!panel.isConnected) return;
  const key = panel.dataset.disclosureKey;
  disclosurePreferences.set(key, panel.open);
  try { localStorage.setItem(disclosureStoragePrefix + key, panel.open ? 'open' : 'closed'); }
  catch { /* The in-page preference still survives navigation and refresh. */ }
}
function rememberVisibleDisclosures() {
  for (const panel of $('content').querySelectorAll('details[data-disclosure-key]')) rememberDisclosure(panel);
}
async function get(url, signal = controller?.signal) { signal?.throwIfAborted(); if (OFFLINE) { const data = await OFFLINE.request(url); signal?.throwIfAborted(); return data; } const response = await fetch(url, { signal }); const data = await response.json(); if (!response.ok) throw Error(data.error || `조회 실패 (${response.status})`); return data; }
function api(route, params = {}) { return `/api/runs/${encodeURIComponent(state.run)}/${route}?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null))}`; }

async function renderAnalysisFailures() {
  const out = el('div'), documents = await get(api('documents'));
  const paths = new Map(documents.files.map(row => [row.path, row]));
  const readArtifact = async path => {
    const file = paths.get(path);
    if (!file) throw Error('A02 진단 자료가 아직 생성되지 않았습니다. 해당 run의 Analysis pipeline을 진행한 뒤 다시 읽어 주세요.');
    return JSON.parse((await get(api('file', { id: file.id }))).content);
  };
  const artifact = paths.get('02_analysis/04_failure_analysis/summary.json');
  if (!artifact) { out.append(empty('A02 진단 자료가 아직 생성되지 않았습니다. 저장된 Analysis pipeline 산출물이 필요합니다.')); return out; }
  const data = await readArtifact(artifact.path);
  const names = { COMPLETED: '검토 완료', NOT_REVIEWED: '미검토', REVIEW_FAILED: '검토 실패', NOT_REVIEWABLE: '검토 불가', SOURCE_MISSING: '입력 원문 없음' };
  const top = section('검토 상태와 진행 기준', '대상 모델의 원응답 오류와 Analysis 호출 오류를 구분합니다.', 'A02');
  top.append(table(['검토 상태', '전체 모수 대비 건수', '처리'], Object.entries(names).map(([key, name]) => [
    name, `${fmt(data.review_gate.review_status[key] || 0)} / ${fmt(data.planned)}`,
    ['NOT_REVIEWED', 'REVIEW_FAILED'].includes(key) ? '재검토 · 해결 전 A03 중단' : key === 'COMPLETED' ? '검토 완료' : '사유 보존 · A03 진행'
  ])), note(`재검토 필요 ${fmt(data.review_gate.recheck_required)}건 · ${data.review_gate.blocked ? 'A03 진행 중단' : 'A03 진행 가능'} · 진단 화면 추가 모델 호출 없음`));
  out.append(top);
  if (!data.records.length) { out.append(empty('미검토·검토 실패·검토 불가·입력 원문 없음이 없습니다.')); return out; }
  const panel = section('왜 검토하지 못했는가', 'explanation과 evidence는 Evaluation 대상 모델이 반환한 값입니다. Analysis는 원값을 보존하여 설명합니다.');
  const controls = el('div', 'section-head'), detail = el('div');
  const scope = select([['', '전체 미완료·불가'], ...Object.entries(names).filter(([key]) => key !== 'COMPLETED')], '', () => populate());
  const picker = select([], '', () => inspect(picker.value));
  scope.setAttribute('aria-label', '검토 상태'); picker.setAttribute('aria-label', '검토 문제');
  controls.append(scope, picker); panel.append(controls, detail); out.append(panel);
  let selectionEpoch = 0;
  const raw = (title, value) => { const block = section(title); const pre = el('pre', 'source-block', show(value)); pre.setAttribute('translate', 'no'); block.append(pre); return block; };
  async function inspect(responseId) {
    const version = ++selectionEpoch, row = data.records.find(item => item.response_id === responseId);
    if (!row) { detail.replaceChildren(empty('선택한 상태에 해당하는 응답이 없습니다.')); return; }
    detail.replaceChildren(note('저장된 원문·응답·검토 사유를 읽고 있습니다.'));
    try {
      const page = await readArtifact(row.page);
      if (version !== selectionEpoch || controller.signal.aborted) return;
      const record = page.records.find(item => item.response_id === responseId);
      if (!record) throw Error('A02 진단 색인에 대응하는 응답 상세가 없습니다.');
      const response = record.target_response;
      const reasons = section('Analysis 검토 사유', `${names[record.review_status]} · ${record.recheck_required ? '재검토 대상' : '사유를 보존하고 다음 단계 진행'}`);
      reasons.append(note(`대상 Evaluation 응답: ${label(record.response_status)} · Analysis 호출: ${label(record.judge_call_status)}`));
      const validationErrors = record.target_validation?.schema_errors || [];
      if (validationErrors.length) reasons.append(table(['실패 필드', '검사 규칙', '실제 검사 메시지'], validationErrors.map(error => [
        (error.path || []).join('.'), error.rule, error.message
      ])));
      for (const [field, title] of [['decision_grounding', '답·유보의 근거'], ['abstention_reason_validity', '유보 이유']]) {
        reasons.append(raw(title, record[field]?.reason), disclosure(`${title} · Analysis 인용`, record[field]?.citations));
      }
      reasons.append(disclosure('대상 Evaluation의 형식 오류', record.target_validation),
        disclosure('Analysis 호출 상태·오류', { status: record.judge_call_status, error: record.judge_error, validation_errors: record.judge_validation_errors }));
      detail.replaceChildren(reasons, raw('질문 · 실제 입력', record.public_input?.question),
        raw('문맥 · 실제 입력', record.public_input?.context),
        raw('대상 모델의 answer / classification', response && { answer: response.answer, classification: response.classification }),
        raw('대상 모델의 explanation', response?.explanation), raw('대상 모델의 evidence', response?.evidence),
        disclosure('대상 모델 원응답 전체 · 변경 없음', response));
    } catch (error) { if (error.name !== 'AbortError' && version === selectionEpoch) detail.replaceChildren(note(error.message, 'danger')); }
  }
  function populate() {
    const rows = data.records.filter(row => !scope.value || row.review_status === scope.value);
    picker.replaceChildren(...rows.map(row => { const option = el('option', '', `${row.case} · ${VARIANTS[row.variant] || row.variant} · ${conditionName(row.prompt_condition, row.reasoning)} · ${names[row.review_status]}`); option.value = row.response_id; return option; }));
    picker.disabled = !rows.length; inspect(picker.value);
  }
  populate();
  return out;
}
function readURL() { for (const key of Object.keys(state)) delete state[key]; const params = OFFLINE ? location.hash.slice(1) : location.search; Object.assign(state, { run: '', tab: 'overview' }, OFFLINE && !params ? OFFLINE.initialView : {}, Object.fromEntries(new URLSearchParams(params))); if (['discoveries', 'quadrants'].includes(state.tab)) state.tab = 'pair-matrix'; if (state.prompt) state.prompt = promptKey(state.prompt); if (OFFLINE) state.run = OFFLINE.run; if (!TABS[state.tab] || (OFFLINE && ['quadrants', 'pair-matrix'].includes(state.tab))) state.tab = 'overview'; }
function writeURL(replace = false) { const params = new URLSearchParams(Object.entries(state).filter(([, v]) => v !== '' && v != null)); history[replace ? 'replaceState' : 'pushState']({}, '', `${OFFLINE ? '#' : '?'}${params}`); }
function navigate(patch, replace = false) { Object.assign(state, patch); if (state.prompt) state.prompt = promptKey(state.prompt); writeURL(replace); load(); }
function resetFilters() { clearTimeout(searchTimer); for (const k of [...FILTERS, 'tags', 'tag_mode', 'q', 'metric', 'paired', 'sort', 'diagnostic_sort', 'offset', 'case_offset', 'comparison_offset']) delete state[k]; $('search').value = ''; writeURL(); load(); }
const ORIGINAL_METRICS = ['numeric_matches', 'numeric_mismatches', 'numeric_unevaluated', 'numeric_pending'];
function drill(patch) { navigate({ ...(ORIGINAL_METRICS.includes(patch.metric) ? { experiment: '1', variant: 'ORIGINAL' } : {}), ...patch, offset: '0', case_offset: '0', tab: 'failures' }); }
function openCase(row) { navigate({ case: row.case || row.id, variant: row.variant ?? state.variant ?? '', prompt: row.prompt ?? state.prompt ?? '', reasoning: row.reasoning ?? state.reasoning ?? '', tab: 'case' }); }

// Q01 uses the pipeline-produced F-only artifact, never discussion or observation groups.
async function renderFindingQuadrants() {
  const out = el('div', 'finding-quadrants');
  const docs = await get(api('documents'));
  const artifact = docs.files.find(file => file.path === '02_analysis/04_quadrant/01_findings/summary.json');
  if (!artifact) {
    const research = overview.results_analysis?.stages?.[2];
    if (overview.finalization?.skip_a04) { out.append(note('파이프라인 A04 연구발견 그룹화는 사용자 지시로 생략되었습니다. 현재 완료 조건에 포함하지 않습니다.')); return out; }
    out.append(note(`Q01 연구발견 그룹이 아직 저장되지 않았습니다. A03: ${label(research?.status)} · Analysis: ${label(overview.analysis_execution?.status)}. pipeline의 A04에서 그룹을 처리·검사한 뒤 표시합니다.`));
    out.append(button('A03 연구 해석 보기', () => navigate({ tab: 'reports' })));
    return out;
  }
  const data = JSON.parse((await get(api('file', { id: artifact.id }))).content);
  if (data.run !== state.run || data.scope !== 'A03_FINDINGS_ONLY') throw Error('Q01 연구발견의 회차 또는 대상 범위가 맞지 않습니다.');
  const counts = section('연구 발견을 주제별로 묶어 비교', `고유 발견 ${fmt(data.counts.findings)}개 · 주제 ${fmt(data.counts.groups)}개 · 여러 조건에 연결된 발견 ${fmt(data.counts.shared_findings)}개`, 'Q01');
  counts.append(note('각 칸은 연구 발견이 인용한 응답 조건입니다. 같은 발견이 여러 칸에 들어갈 수 있으며, 칸별 개수의 합은 고유 발견 수가 아닙니다. 요약은 A03 발견의 해석이며 응답 성공률과 구별합니다.'));
  out.append(counts);
  if (!data.groups.length) { out.append(empty('A03 연구 발견이 없습니다.')); return out; }
  const index = new Map(data.findings.map(row => [row.finding.id, row]));
  let currentGroup = data.groups.find(group => group.id === state.finding_group) || data.groups[0];
  let currentFinding = '';
  const controls = section('비슷한 특징의 발견 묶음');
  const navigation = el('div', 'finding-topic-list');
  const grid = el('div', 'finding-condition-grid');
  grid.setAttribute('aria-label', 'Unguided/Guided × Reasoning OFF/ON 연구 발견 비교');
  const detail = section('원래 연구 발견과 근거 연결');
  const picker = select([], '', id => showFinding(id));
  picker.setAttribute('aria-label', '그룹에 포함된 연구 발견 선택');
  const findingBody = el('div');
  detail.append(picker, findingBody);
  const description = el('div', 'finding-group-description');
  controls.append(navigation, description);
  out.append(controls, el('p', 'finding-axis', '위: Reasoning ON · 아래: Reasoning OFF / 왼쪽: Unguided · 오른쪽: Criteria-Guided'), grid, detail);

  function showFinding(id) {
    const linked = index.get(id);
    if (!linked) { findingBody.replaceChildren(empty('선택한 발견이 없습니다.')); return; }
    currentFinding = id; picker.value = id;
    const f = linked.finding;
    const header = localizedValue('h4', '', f, 'title', `${f.id} · `);
    const paragraphs = [header];
    for (const [key, title] of [['claim', '발견 내용'], ['alternatives', '가능한 다른 설명'], ['limitation', '한계'], ['decision', 'A03 판정']]) {
      const block = el('div', 'finding-prose');
      block.append(el('strong', '', title), localizedValue('p', '', f, key)); paragraphs.push(block);
    }
    paragraphs.push(note(linked.condition_scope === 'MULTI_CONDITION' ? '여러 조건을 비교한 발견 · 조건 연결은 공동 근거이며 한 조건만의 효과로 단정하지 않습니다.' : '인용된 응답의 조건에 연결한 발견'));
    const refs = el('div', 'finding-reference-actions');
    for (const [condition, rows] of Object.entries(linked.conditions)) {
      const [prompt, reasoning] = condition.split('/');
      refs.append(resultPagedDetails(`${conditionName(prompt, reasoning)} · 근거 응답 ${fmt(rows.length)}개`, ['문항', '유형', '실제 응답'], rows,
        row => [row.case, VARIANTS[row.variant] || row.variant, button('응답 열기', () => openCase({ ...row, prompt, reasoning }), 'text-button')], 20));
    }
    paragraphs.push(refs, disclosure('원래 F 기록 · 변경 없음', f));
    findingBody.replaceChildren(...paragraphs);
  }

  function choose(group) {
    currentGroup = group; state.finding_group = group.id; writeURL(true);
    for (const item of navigation.children) { item.classList.toggle('active', item.dataset.groupId === group.id); item.setAttribute('aria-pressed', String(item.dataset.groupId === group.id)); }
    description.replaceChildren(localizedValue('h4', '', group, 'title'), localizedValue('p', '', group, 'summary'));
    grid.replaceChildren();
    // Keep the familiar two-factor placement; the diagonal changes both settings.
    for (const condition of ['unguided/on', 'guided/on', 'unguided/off', 'guided/off']) {
      const profile = group.condition_profiles.find(row => row.condition === condition);
      const [prompt, reasoning] = condition.split('/');
      const card = section(conditionName(prompt, reasoning), `연결 발견 ${fmt(profile.finding_ids.length)}개`);
      card.classList.add('finding-condition', `finding-${prompt}-${reasoning}`);
      const displayProfile = { ...profile, display_ko: { analysis: profile.display_ko.analysis.replace(/^各 /, '각 ') } };
      card.append(localizedValue('p', 'finding-condition-analysis', displayProfile, 'analysis'));
      const uniqueRefs = new Map(profile.finding_ids.flatMap(id => (index.get(id)?.conditions[condition] || []).map(ref => [ref.response_id, ref])));
      card.append(el('p', 'small', `이 묶음의 인용 응답 ${fmt(uniqueRefs.size)}개 · 문항 ${fmt(new Set([...uniqueRefs.values()].map(row => row.case)).size)}개`));
      const quotes = el('details', 'finding-citations'); quotes.append(el('summary', '', `요약을 뒷받침하는 F 인용 ${fmt(profile.citations.length)}개`));
      for (const citation of profile.citations) {
        const quote = el('blockquote', '', citation.quote); quote.setAttribute('translate', 'no');
        quotes.append(button(`${citation.finding_id} · ${citation.field}`, () => { showFinding(citation.finding_id); detail.scrollIntoView({ block: 'start', behavior: 'smooth' }); }, 'text-button'), quote);
      }
      card.append(quotes);
      if (profile.finding_ids.length) card.append(button('연결된 발견 보기', () => { showFinding(profile.finding_ids[0]); detail.scrollIntoView({ block: 'start', behavior: 'smooth' }); }));
      grid.append(card);
    }
    picker.replaceChildren(...group.finding_ids.map(id => { const option = el('option', '', `${id} · ${index.get(id)?.finding.display_ko?.title || index.get(id)?.finding.title}`); option.value = id; return option; }));
    showFinding(group.finding_ids.includes(currentFinding) ? currentFinding : group.finding_ids[0]);
  }
  for (const group of data.groups) {
    const control = button(`${group.display_ko?.title || group.title} · ${fmt(group.finding_ids.length)}`, () => choose(group), 'finding-topic');
    control.dataset.groupId = group.id; navigation.append(control);
  }
  choose(currentGroup);
  return out;
}

// [EV23.3] Cross-run comparison is a view, not an additional experiment stage.
function renderStageMenu(stage) {
  const controls = Object.entries(STAGES).map(([key, value]) => button(value.title, () => {
    if (key === 'evaluation') { state.tab = 'overview'; resetFilters(); return; }
    navigate({ tab: value.tabs[0] });
  }, key === stage ? 'active' : ''));
  for (const control of controls) control.setAttribute('aria-current', control.classList.contains('active') ? 'page' : 'false');
  $('stages').replaceChildren(...controls);
}
function setQuadrantMode(enabled) {
  document.querySelector('.workspace').classList.toggle('quadrant-mode', enabled);
  $('tabs').hidden = enabled;
  $('run-status').hidden = enabled;
  $('html-export').hidden = enabled || !!OFFLINE;
}
function renderQuadrantShell() {
  setQuadrantMode(true);
  document.querySelector('.filter-panel').hidden = true;
  $('rounds').hidden = true;
  $('tabs').replaceChildren();
  $('warnings').replaceChildren();
  $('page-title').textContent = TABS.quadrants;
  $('run-eyebrow').textContent = 'DATASET / MODEL COMPARISON';
  $('run-description').textContent = '같은 데이터셋·입력의 저장 결과를 모으고 있습니다.';
  $('stage-flow').textContent = '데이터셋·동일 입력 선택 → 7조건 사분면 → 모델 체크 비교';
  renderStageMenu('comparison');
  $('tabs').hidden = false;
  $('tabs').replaceChildren(button('Q01 Pair Matrix', () => navigate({ tab: 'pair-matrix' }), 'active'));
}
function renderQuadrantComparison(metadata, signal) {
  const out = el('div', 'quadrant-view'), loading = note('사분면 화면을 불러오고 있습니다.');
  const frame = el('iframe', 'quadrant-frame'); frame.title = '데이터셋별 7조건 사분면과 모델 비교';
  frame.src = metadata.url;
  frame.addEventListener('load', () => {
    if (!frame.isConnected || signal.aborted) return;
    const doc = frame.contentDocument, root = doc?.querySelector('#ic-value-quadrant');
    if (!root) { loading.textContent = '비교 화면을 불러오지 못했습니다. 새로 읽기를 눌러 주세요.'; loading.classList.add('danger'); frame.hidden = true; return; }
    loading.hidden = true;
    const resize = () => { frame.style.height = `${Math.ceil(root.getBoundingClientRect().height) + 2}px`; };
    const observer = new ResizeObserver(resize); observer.observe(root); resize();
    signal.addEventListener('abort', () => observer.disconnect(), { once: true });
    // Keep the viewer's half-screen scrolling when focus is inside the chart.
    doc.addEventListener('keydown', event => {
      if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.target.closest?.('input,textarea,select,[contenteditable]')) return;
      const key = event.key.toLowerCase();
      if (key === 's' || key === 'w') { event.preventDefault(); if (!event.repeat) window.scrollBy(0, Math.round(window.innerHeight / 2) * (key === 's' ? 1 : -1)); }
    });
  });
  out.append(loading, frame);
  const inventory = el('details', 'quadrant-inventory'), statuses = { INCLUDED: '비교 포함', NO_SAVED_A02: '집계 없음', NOT_COMPARABLE: '비교 조건 미충족' };
  inventory.append(el('summary', '', `수집 범위 · ${metadata.inventory.filter(row => row.status === 'INCLUDED').length}회차 포함 / ${metadata.inventory.length}회차 확인`));
  inventory.append(table(['회차', '상태', '사유'], metadata.inventory.map(row => [row.run, statuses[row.status] || row.status, row.reason || '출처·동일 입력·분모 확인'])));
  out.append(inventory);
  return out;
}

async function renderPairOutcomeMatrix() {
  const data = await get(api('pair-outcomes', { run: state.run }));
  const out = el('div', 'pair-outcome-view');
  const intro = section('Pair Outcome Matrix — 원본·변형 대응 결과표', '가로축: 원본 수치 정답 여부 (왼쪽 No / 오른쪽 Yes) · 세로축: 변형 대응 적절성 (아래 No / 위 Yes)', 'Q01');
  out.append(intro);
  if (data.status === 'NOT_PREPARED') { intro.append(note('이 회차의 Pair 집계가 아직 없습니다. pipeline의 pair-outcomes 단계에서 저장한 자료를 표시합니다.')); return out; }
  intro.append(el('p', 'small muted', '원본 축은 저장된 E04의 부호·정밀도를 반영한 수치 정답 비교입니다. 단위와 설명의 의미 정답은 별도로 채점되지 않았습니다. 변형 축은 A02의 검증된 대응 판정입니다. null 또는 classification만으로 성공을 인정하지 않습니다.'));
  const types = data.types || [], controls = el('div', 'pair-matrix-controls');
  const options = (title, key, entries) => {
    const wrap = el('label', '', title), select = el('select'); select.setAttribute('aria-label', title);
    for (const [value, text] of entries) { const o = el('option', '', text); o.value = value; select.append(o); }
    select.value = state[key] || ''; select.addEventListener('change', () => navigate({ [key]: select.value }));
    wrap.append(select); controls.append(wrap);
  };
  options('모델', 'pair_model', [['', '모델별로 모두 보기'], ...[...new Set(types.map(r => r.model))].map(v => [v, v])]);
  options('풀이 · 추론 조건', 'pair_condition', [['', '네 조건 각각 보기'], ...['unguided/off', 'unguided/on', 'guided/off', 'guided/on'].map(v => [v, conditionName(...v.split('/'))])]);
  options('원천 유형', 'pair_source', [['', '원천 유형 전체'], ...[...new Set(types.map(r => r.source_type))].map(v => [v, v])]);
  options('변형 답변 가능성', 'pair_answerability', [['', '전체 · 확정 여부 별도 표시'], ['ANSWERABLE', '확정 답변 가능'], ['UNANSWERABLE', '확정 답변 불가능'], ['NOT_ESTABLISHED', '답변 가능성 미확정']]);
  intro.append(controls, el('p', 'small muted', `집계 저장 ${time(data.created_at)} · 미수집·형식 실패·미검토는 전체 예정 Pair에 남으며 사분면 밖에 표시합니다. 답변 가능성 필터는 private 참조 분류를 사용하며 모델 응답으로 대체하지 않습니다.`));
  const selected = types.filter(r => (!state.pair_model || r.model === state.pair_model) && (!state.pair_source || r.source_type === state.pair_source) && (!state.pair_answerability || r.answerability === state.pair_answerability) && (!state.pair_condition || `${r.prompt_condition}/${r.reasoning}` === state.pair_condition));
  const groups = new Map();
  for (const r of selected) { const key = JSON.stringify([r.model, r.prompt_condition, r.reasoning]); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(r); }
  if (!groups.size) out.append(note('선택한 범위에 해당하는 저장 Pair가 없습니다. 답변 가능성 미확정 문항을 확정 집단으로 옮기지 않습니다.'));
  const names = { 1: '① 원본 정답 · 대응 성공', 2: '② 원본 오답 · 대응 성공', 3: '③ 원본 오답 · 대응 실패', 4: '④ 원본 정답 · 대응 실패' };
  for (const rows of groups.values()) {
    const first = rows[0], sum = field => rows.reduce((n, r) => n + r[field], 0);
    const panel = section(`${first.model} · ${conditionName(first.prompt_condition, first.reasoning)}`, `전체 예정 ${fmt(sum('planned_pairs'))} Pair · 사분면 배치 ${fmt(sum('placed_pairs'))} Pair · 미배치 ${fmt(sum('unplaced_pairs'))} Pair`);
    const matrix = el('div', 'pair-matrix-grid');
    for (const q of [2, 1, 3, 4]) {
      const cell = el('article', `pair-matrix-cell pair-matrix-q${q}`), total = rows.reduce((n, r) => n + r.quadrants[String(q)].count, 0);
      cell.append(el('h3', '', names[q]), el('strong', 'pair-matrix-total', `${fmt(total)} Pair`));
      cell.append(table(['변형 유형', 'Pair 건수'], Object.keys(VARIANTS).filter(v => v !== 'ORIGINAL').map(v => [VARIANTS[v], fmt(rows.filter(r => r.variant === v).reduce((n, r) => n + r.quadrants[String(q)].count, 0))])));
      matrix.append(cell);
    }
    panel.append(matrix);
    panel.append(table(['변형 유형', '예정 Pair', '사분면 배치', '미배치'], Object.keys(VARIANTS).filter(v => v !== 'ORIGINAL').map(v => { const sub = rows.filter(r => r.variant === v); return [VARIANTS[v], ...['planned_pairs', 'placed_pairs', 'unplaced_pairs'].map(k => fmt(sub.reduce((n, r) => n + r[k], 0)))]; })));
    const reasons = {}; for (const r of rows) for (const [key, n] of Object.entries(r.placement_counts)) if (key !== 'PLACED') reasons[key] = (reasons[key] || 0) + n;
    const labels = { ORIGINAL_NUMERIC_UNASSESSED: '원본 정답 미판정', VARIANT_UNAVAILABLE: '변형 미수집·형식 실패', SEMANTIC_NOT_REVIEWED: '변형 대응 미검토·판정 불가' };
    panel.append(el('p', 'small muted', Object.entries(reasons).map(([key, n]) => `${labels[key] || key} ${fmt(n)} Pair`).join(' · ') || '모든 Pair가 사분면에 배치되었습니다.'));
    const rate = q => rows.reduce((n, r) => n + r.quadrants[String(q)].count, 0);
    const conditional = (a, b) => a + b ? `${(100 * a / (a + b)).toFixed(1)}% (${fmt(a)}/${fmt(a+b)})` : '판정된 Pair 없음';
    panel.append(el('p', 'small', `판정 완료 Pair 내 대응 성공률 · 원본 정답 집단: ${conditional(rate(1), rate(4))} · 원본 오답 집단: ${conditional(rate(2), rate(3))}. 미배치 Pair가 있는 동안 전체 예정 집단의 성공률로 해석하지 않습니다.`));
    out.append(panel);
  }
  return out;
}

// [EV03.2] URL state and an abortable read prevent older responses replacing a new selection.
async function load(preserve = false) {
  const generation = ++epoch;
  if (state.tab === 'models' && ['model', 'status', 'tags', 'tag_mode', 'metric', 'paired'].some(key => state[key])) {
    for (const key of ['model', 'status', 'tags', 'tag_mode', 'metric', 'paired']) delete state[key];
    writeURL(true);
  }
  rememberVisibleDisclosures();
  const summaryText = node => globalThis.FinarchI18n?.originalText(node) ?? node?.textContent;
  const openDetails = preserve ? [...$('content').querySelectorAll('details[open]')].map(n => summaryText(n.querySelector('summary'))) : [];
  const scrollY = window.scrollY;
  controller?.abort(); controller = new AbortController();
  $('content').setAttribute('aria-busy', 'true'); $('connection-error').hidden = true;
  $('refresh').disabled = true;
  try {
    if (state.tab === 'quadrants' && !OFFLINE) {
      renderQuadrantShell();
      $('content').replaceChildren(note('저장된 A02 집계와 입력 출처를 확인하고 있습니다.'));
      const metadata = await get('/api/quadrants');
      if (generation !== epoch) return;
      $('run-description').textContent = `${metadata.datasets.map(dataset => dataset.label).join(' · ')} · 데이터셋 ${metadata.datasets.length}개 · 새 모델 호출 없음`;
      if (overview.finalization) {
    const f = overview.finalization;
    $('run-status').textContent = f.status === 'COMPLETE' ? '분석·Python 응답 분류 완료 · A04 생략' : f.status === 'WAIT_EVALUATION_AND_TRANSFER' ? 'Evaluation 완료·전송 대기 · Analysis 미시작' : f.status === 'WAIT_PYTHON_OUTCOMES' ? 'A03 수집 완료 · Python 후처리 완료 확인 대기' : 'A03 수집 완료 대기 · A04 생략';
  }
  $('loaded-at').textContent = `조회 ${time(metadata.generated_at)}`;
      $('content').replaceChildren(renderQuadrantComparison(metadata, controller.signal));
      if (preserve) window.scrollTo({ top: scrollY });
      return;
    }
    setQuadrantMode(false);
    const runs = await get('/api/runs');
    availableRuns = runs.runs;
    if (generation !== epoch) return;
    if (!runs.runs.length) { $('content').replaceChildren(empty('reports/experiments-run에 저장된 실행이 없습니다.')); $('run-select').replaceChildren(); return; }
    if (!state.run) { state.run = runs.runs.find(r => r.status === 'FINISHED')?.id || runs.runs[0].id; writeURL(true); }
    if (!runs.runs.some(run => run.id === state.run) && /^\d{8}-exp-\d{3,}$/.test(state.run)) {
      const prefix = `${state.run}-`;
      const renamed = runs.runs.filter(run => run.id.startsWith(prefix) && /^\d{8}$/.test(run.id.slice(prefix.length)));
      if (renamed.length === 1) { state.run = renamed[0].id; writeURL(true); }
    }
    $('run-select').replaceChildren(...runs.runs.map(r => { const o = el('option', '', r.id); o.value = r.id; return o; })); $('run-select').value = state.run;
    overview = await get(api('overview', state));
    if (generation !== epoch) return;
    resultResponseIndex = new Map((overview.results_analysis?.responses || []).map(row => [row.response_id, row]));
    if (overview.results_analysis && state.tab === 'models') { state.tab = 'conditions'; writeURL(true); }
    renderShell();
    const out = await ({ input: renderInput, overview: renderOverview, analysis: renderAnalysis, conditions: renderConditions, models: renderModelComparison, case: renderCase, failures: renderFailures, 'analysis-failures': renderAnalysisFailures, discoveries: renderFindingQuadrants, 'pair-matrix': renderPairOutcomeMatrix, costs: renderCosts, reports: renderReports, grounding: renderGroundingAssessment, answerable: renderAnswerable }[state.tab])();
    if (generation !== epoch) return;
    // Capture choices made while data was loading, before replacing the old panel.
    rememberVisibleDisclosures();
    for (const panel of out.querySelectorAll('details[data-disclosure-key]')) restoreDisclosure(panel);
    const focusedCondition = document.activeElement?.dataset.conditionKey;
    $('content').replaceChildren(out);
    if (focusedCondition) (out.querySelector(`[data-condition-key="${focusedCondition}"]:not(:disabled)`) ?? out.querySelector('[data-condition-key].active:not(:disabled)'))?.focus({ preventScroll: true });
    if (preserve) { for (const d of $('content').querySelectorAll('details:not([data-disclosure-key])')) d.open = openDetails.includes(summaryText(d.querySelector('summary'))); window.scrollTo({ top: scrollY }); }
  } catch (error) {
    if (error.name !== 'AbortError' && generation === epoch) {
      $('connection-error').textContent = error.message; $('connection-error').hidden = false;
      $('content').replaceChildren(empty('현재 선택의 자료를 불러오지 못했습니다. 실행 선택 또는 새로 읽기로 다시 시도해 주세요.'));
    }
  } finally { if (generation === epoch) { $('content').setAttribute('aria-busy', 'false'); $('refresh').disabled = false; } }
}

function renderShell() {
  $('progress-dashboard-link').hidden = !!OFFLINE;
  $('progress-dashboard-link').href = `/?run=${encodeURIComponent(state.run)}&tab=progress`;
  const resultTab = overview.results_analysis && ['analysis', 'conditions', 'reports', 'grounding', 'answerable', 'analysis-failures'].includes(state.tab);
  const resultTitles = { analysis: '결과 취합', conditions: '관계 비교', reports: '연구 해석', grounding: '근거 타당성', answerable: 'ANSWERABLE', 'analysis-failures': '실패·검토 불가' };
  const analysisTabs = overview.results_analysis ? ['analysis', 'conditions', 'grounding', 'reports', 'answerable', 'analysis-failures'] : STAGES.analysis.tabs;
  const analysisStage = { analysis: 0, conditions: 1, reports: 2 };
  document.querySelector('.filter-panel').hidden = !!resultTab || ['discoveries', 'pair-matrix', 'grounding', 'answerable'].includes(state.tab);
  $('page-title').textContent = (resultTab ? resultTitles[state.tab] : TABS[state.tab]); $('run-eyebrow').textContent = `EXPERIMENT RECORD / ${state.run}`;
  $('run-description').textContent = `원문 ${fmt(overview.originals)}개 · 변형 ${fmt(overview.variants)}개 · ${overview.models.length}개 모델의 저장된 결과`;
  $('run-status').replaceWith(Object.assign(badge(overview.status), { id: 'run-status' }));
  $('run-meta').replaceChildren(badge(overview.status), el('p', 'small', `저장 갱신 ${time(overview.updated_at)}`));
  if (overview.improvement?.campaign && overview.status === 'FINISHED' && !overview.semantic) {
    $('run-status').textContent = '풀이 완료 · 분석 진행 중';
  }
  if (overview.analysis_config?.enabled && overview.status === 'FINISHED') {
    const research = overview.review_stages.find(s => s.stage === 'A03-research');
    $('run-status').textContent = overview.semantic && research?.status === 'COLLECTED'
      ? '풀이·분석 수집 완료 · 사용자 검토 대기' : '풀이 완료 · 분석 진행 중';
  }
  if (overview.results_analysis) {
    const stages = overview.results_analysis.stages || [];
    const saved = stages.length === 3 && stages.every(stage => stage.status === 'COLLECTED')
      && !['RUNNING', 'BLOCKED', 'PARTIAL', 'FAILED', 'PAUSED_BY_USER'].includes(overview.analysis_execution?.status);
    const evaluation = overview.evaluation_reuse ? 'Evaluation 재사용' : 'Evaluation';
    $('run-status').textContent = saved ? `${evaluation} · 분석 저장 완료`
      : overview.analysis_execution?.status === 'PAUSED_BY_USER' ? `${label(overview.status)} · 분석 일시 중지`
      : stages.some(stage => stage.status === 'BLOCKED') ? `${evaluation} 완료 · 분석 중단·확인 필요`
      : overview.status === 'FINISHED' ? `${evaluation} 완료 · 분석 진행 중` : `${label(overview.status)} · 분석 대기`;
  }
  if (overview.finalization) {
    const f = overview.finalization;
    $('run-status').textContent = f.status === 'COMPLETE' ? '분석·Python 응답 분류 완료 · A04 생략' : f.status === 'WAIT_EVALUATION_AND_TRANSFER' ? 'Evaluation 완료·전송 대기 · Analysis 미시작' : f.status === 'WAIT_PYTHON_OUTCOMES' ? 'A03 수집 완료 · Python 후처리 완료 확인 대기' : 'A03 수집 완료 대기 · A04 생략';
  }
  $('loaded-at').textContent = `조회 ${time(overview.loaded_at)}`;
  $('warnings').replaceChildren(...overview.warnings.map(w => note(w)));
  if (overview.finalization) $('warnings').append(note(overview.finalization.explanation + ' 화면의 A04 연구 해석 메뉴는 파이프라인 A03 자료입니다. 생략 대상은 파이프라인 A04 연구발견 그룹화입니다.'));
  if (overview.evaluation_reuse) {
    const source = overview.evaluation_reuse.source_run;
    const calls = overview.evaluation_reuse.new_target_model_calls;
    const reused = note(`${source}의 Evaluation 재사용 · ${Number.isInteger(calls) ? `대상 모델 신규 호출 ${fmt(calls)}회` : '대상 모델 신규 호출 수 미기록'} · 이번 회차는 저장된 응답을 다시 분석합니다.`, 'info');
    if (!OFFLINE) reused.append(button('Evaluation 원본 보기 →', () => navigate({ run: source, tab: 'overview' }), 'text-button'));
    $('warnings').append(reused);
  }
  if (overview.review_reset) {
    $('run-status').textContent = '풀이 보존 · Codex 재검토';
    const reset = note('진행 방식 수정: 기존 동일 모델 API의 내용 판정과 개선 결론은 보류입니다. 1차 원응답부터 이 Codex 대화에서 직접 분석하고, 개선안 합의 후 재실험합니다. 현재는 자료 확인 단계이며 새 내용 판정은 시작하지 않았습니다.', 'info');
    reset.append(button('1차 확인 자료 열기 →', () => navigate({run: '20260927-exp-001', tab: 'reports'}), 'text-button'));
    $('warnings').append(reset);
  }
  const stage = Object.keys(STAGES).find(key => STAGES[key].tabs.includes(state.tab)) || 'evaluation';
  renderStageMenu(stage);
  $('stage-flow').textContent = stage === 'analysis' && overview.results_analysis ? 'A01 결과 취합 → A02 관계 비교 → A03 근거 타당성 → A04 연구 해석 → A05 ANSWERABLE → A06 실패·검토 불가' : STAGES[stage].flow;
  $('rounds').hidden = !overview.improvement?.campaign;
  if (overview.improvement?.campaign) {
    const campaign = availableRuns.filter(run => run.improvement?.campaign === overview.improvement.campaign);
    $('rounds').replaceChildren(el('strong', '', '동일 100원문 · 개선 이력'), ...[1, 2, 3].map(round => {
      const run = campaign.find(entry => entry.improvement.round === round);
      const b = button(`${round}차 · ${run ? run.semantic ? '내용 분석 저장됨' : run.status === 'FINISHED' ? '풀이 완료 · 분석 중' : label(run.status) : '앞 차수 검토 후 진행'}`, () => run && navigate({ run: run.id, case: '', tab: 'analysis' }), run?.id === state.run ? 'active' : '');
      b.disabled = !run; return b;
    }));
  }
  // [EV15.3] Number shortcuts follow only the current stage's visible tab order.
  $('tabs').replaceChildren(...(stage === 'analysis' ? analysisTabs : STAGES[stage].tabs).filter(key => !OFFLINE || !['quadrants', 'pair-matrix'].includes(key)).map((key, i) => { const b = button('', () => {
    // [EV03.5] Returning to the overview starts from the entire selected run.
    if (key === 'overview') { state.tab = key; resetFilters(); return; }
    const patch = { tab: key };
    if (key === 'models') Object.assign(patch, { model: '', status: '', tags: '', tag_mode: '', metric: '', paired: '', comparison_offset: '0' });
    if (key === 'failures' && !state.status && !state.metric && !state.tags) patch.status = 'FORMAT_FAILED';
    navigate(patch);
  }, key === state.tab ? 'active' : ''); b.dataset.shortcut = String(i + 1); b.setAttribute('aria-keyshortcuts', String(i + 1)); b.setAttribute('aria-current', key === state.tab ? 'page' : 'false'); b.append(el('span', 'tab-number', STEP_CODES[key]), overview.results_analysis && resultTitles[key] ? resultTitles[key] : TABS[key]);
    if (overview.results_analysis && Object.hasOwn(analysisStage, key)) b.append(el('small', 'result-tab-status', resultStageProgress(overview.results_analysis.stages?.[analysisStage[key]], key === 'analysis' ? '미실행 · 응답 미수집' : '미실행 · 분석 대기')));
    if (key === 'grounding') b.append(el('small', 'result-tab-status', 'A02 저장 판정'));
    return b; }));
  const setOptions = (id, entries, current) => { const control = $(id); control.replaceChildren(...entries.map(([value, text]) => { const n = el('option', '', text); n.value = value; return n; })); control.value = current || ''; };
  setOptions('filter-model', [['', '모델 전체'], ...overview.models.map(m => [m.key, m.key])], state.model);
  setOptions('filter-variant', [['', '유형 전체'], ...overview.options.variants.map(v => [v, VARIANTS[v] || v])], state.variant);
  setOptions('filter-status', [['', '상태 전체'], ['FORMAT_FAILED', '형식 실패·잘림'], ...overview.options.statuses.map(v => [v, label(v)])], state.status);
  $('filter-model').disabled = state.tab === 'models';
  $('filter-status').disabled = state.tab === 'models';
  for (const key of FILTERS) $(`filter-${key}`).value = state[key] || '';
  $('search').value = state.q || '';
  const a = overview.view.aggregate;
  $('case-pending-legend').hidden = !a.numeric_pending;
  const selected = FILTERS.filter(k => state[k]).map(k => $(`filter-${k}`).selectedOptions[0]?.textContent || state[k]);
  if (state.q) selected.push(`검색: ${state.q}`);
  if (state.metric) selected.push(METRICS[state.metric] || state.metric);
  if (state.tags) selected.push(`진단 ${state.tags.split(',').length}개`);
  if (state.paired === 'true') selected.push('모든 모델에서 숫자 비교 가능');
  $('filter-summary').textContent = state.tab === 'models'
    ? `${selected.join(' · ') || '전체 조건'} · 짝지은 조건 ${fmt(overview.model_comparison.total)}개 · 모델/반환 상태는 양쪽을 함께 표시`
    : `${selected.join(' · ') || '전체 조건'} · ${fmt(a.total)} / ${fmt(overview.view.unfiltered_total)} 요청 · 원문 ${fmt(a.cases)}개`;
  renderVisibleFilters();
  $('case-count').textContent = fmt(overview.view.case_total);
  // [EV22.2] Keep list scroll during case changes; only bring a new selection into view.
  const list = $('case-list'), scope = JSON.stringify([state.run, ...[...FILTERS, 'q', 'metric', 'tags', 'tag_mode', 'paired'].map(key => state[key] || '')]);
  const sameScope = scope === caseListScope, scrollTop = sameScope ? list.scrollTop : 0;
  const selectedChanged = listedCase !== state.case;
  list.replaceChildren(...overview.view.cases.map(c => {
    const b = button('', () => openCase(c), `case-row ${state.case === c.id ? 'selected' : ''}`); b.setAttribute('aria-label', `${c.id} 문항 열기`);
    b.setAttribute('aria-current', state.case === c.id ? 'true' : 'false');
    const top = el('div', 'case-top'), counts = el('span', 'case-counts');
    const description = el('span', 'sr-only', `원본풀이 정답 불일치 ${fmt(c.numeric_mismatches)}건, 미평가 ${fmt(c.numeric_unevaluated)}건${c.numeric_pending ? `, 미수집 ${fmt(c.numeric_pending)}건` : ''}`);
    description.id = `case-counts-${c.id}`; b.setAttribute('aria-describedby', description.id);
    for (const [kind, title, count] of [['mismatch', '불일치', c.numeric_mismatches], ['unevaluated', '미평가', c.numeric_unevaluated]]) {
      const badge = el('span', `case-count-badge ${kind}${count ? '' : ' is-zero'}`, fmt(count));
      badge.title = `원본풀이 정답 ${title} ${fmt(count)}건`; badge.setAttribute('aria-hidden', 'true'); counts.append(badge);
    }
    if (c.numeric_pending) { const badge = el('span', 'case-count-badge pending', fmt(c.numeric_pending)); badge.title = `원본풀이 응답 미수집 ${fmt(c.numeric_pending)}건`; badge.setAttribute('aria-hidden', 'true'); counts.append(badge); }
    top.append(el('span', 'mono', c.id), counts); b.append(top, description); return b;
  }));
  if (!overview.view.cases.length) list.append(el('p', 'small muted', '해당 문항이 없습니다.'));
  list.scrollTop = scrollTop;
  const current = list.querySelector('.selected');
  if (current && (!sameScope || selectedChanged)) {
    const viewport = list.getBoundingClientRect(), item = current.getBoundingClientRect();
    if (item.top < viewport.top) list.scrollTop += item.top - viewport.top;
    else if (item.bottom > viewport.bottom) list.scrollTop += item.bottom - viewport.bottom;
  }
  caseListScope = scope; listedCase = state.case;
}

// [EV21.1] Every filtering constraint introduced by a link is visible and removable.
function renderVisibleFilters() {
  const extra = $('filter-extra'); extra.replaceChildren(); extra.hidden = state.tab !== 'failures' && !state.metric && state.paired !== 'true';
  const metricLabel = el('label', '', '확인 기준');
  const options = [['', '기준 전체'], ...Object.entries(METRICS)];
  if (state.metric && !METRICS[state.metric]) options.push([state.metric, `저장된 기준: ${state.metric}`]);
  const control = select(options, state.metric || '', metric => navigate({ metric, status: metric ? '' : state.status, ...(ORIGINAL_METRICS.includes(metric) ? { experiment: '1', variant: 'ORIGINAL' } : {}), offset: '0', case_offset: '0' }));
  control.id = 'filter-metric'; metricLabel.append(control);
  const paired = el('label', 'paired-control'), box = el('input'); box.type = 'checkbox'; box.id = 'filter-paired'; box.checked = state.paired === 'true'; box.onchange = () => navigate({ paired: box.checked ? 'true' : '', offset: '0', case_offset: '0' }); paired.append(box, '모든 모델에서 숫자 비교 가능한 공통 요청만');
  extra.append(metricLabel, paired);
  const chips = $('active-filters'); chips.replaceChildren();
  const add = (text, patch) => chips.append(button(`${text} ×`, () => navigate({ ...patch, offset: '0', case_offset: '0' }), 'filter-chip'));
  for (const key of FILTERS) if (state[key]) add($(`filter-${key}`).selectedOptions[0]?.textContent || state[key], { [key]: '' });
  if (state.q) add(`검색: ${state.q}`, { q: '' });
  if (state.metric) add(`확인 기준: ${METRICS[state.metric] || state.metric}`, { metric: '' });
  if (state.paired === 'true') add('공통 요청만', { paired: '' });
  const tags = (state.tags || '').split(',').filter(Boolean);
  for (const tag of tags) add(`진단: ${tagLabel(tag)}`, { tags: tags.filter(value => value !== tag).join(',') });
  if (tags.length) chips.append(el('span', 'small muted', state.tag_mode === 'any' ? '진단 중 하나라도 포함' : '선택한 진단 모두 포함'));
  if (!chips.childNodes.length) chips.append(el('span', 'small muted', '적용 중인 필터 없음'));
}

function metric(title, value, suffix, caption, action, featured = false) {
  const n = action ? button('', action, 'metric-card') : el('div', 'metric-card');
  if (featured) n.classList.add('featured');
  const number = el('strong', '', value); if (suffix) number.append(el('small', '', suffix));
  n.append(el('span', 'metric-label', title), number, el('span', 'metric-note', caption)); if (action) n.append(el('span', 'arrow', '↗')); return n;
}
function ratio(numerator, denominator) { return `${fmt(numerator)} / ${fmt(denominator)}${denominator ? ` (${(numerator / denominator * 100).toFixed(1)}%)` : ''}`; }
const PENDING_STATUSES = ['PREPARED', 'PENDING', 'BATCH_PENDING', 'RUNNING', 'NOT_RUN', 'UNKNOWN_DELIVERY'];
function pendingCount(a) { return PENDING_STATUSES.reduce((total, status) => total + (a.statuses?.[status] || 0), 0); }
function resultStageProgress(stage, fallback = '미실행 · 분석 대기') {
  if (!stage?.status) {
    if (overview?.analysis_execution?.status === 'PAUSED_BY_USER') return label('PAUSED_BY_USER');
    if (fallback.includes('분석 대기') && overview?.results_analysis?.stages?.[1]?.status === 'BLOCKED') return 'A02 중단 · 시작 대기';
    return fallback;
  }
  const requests = Number.isInteger(stage.requests) ? stage.requests : Number.isInteger(stage.planned) ? stage.planned : null;
  const completed = Number.isInteger(stage.completed) ? stage.completed : null;
  if (requests !== null && Number.isInteger(stage.valid)) {
    const unresolved = stage.statuses?.UNKNOWN_DELIVERY || 0;
    return `${stage.status === 'BLOCKED' ? '확인 필요' : label(stage.status)} · 유효 ${fmt(stage.valid)} / ${fmt(requests)}${unresolved ? ` · 응답 미확인 ${fmt(unresolved)}건` : ''}`;
  }
  return requests !== null && completed !== null ? `${label(stage.status)} · ${fmt(completed)} / ${fmt(requests)}` : label(stage.status);
}
function statusBar(a) {
  const pending = pendingCount(a);
  const wrap = el('div', 'status-bar'), svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 100 10'); svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', `형식 통과 ${a.valid}, 형식 실패 및 잘림 ${a.failed}, 진행·미수집 ${pending}, 전체 ${a.total}`);
  let x = 0;
  for (const [amount, cls] of [[a.valid, 'bar-valid'], [a.statuses.INVALID_RESPONSE || 0, 'bar-invalid'], [a.statuses.OUTPUT_TRUNCATED || 0, 'bar-truncated'], [pending, 'bar-pending'], [Math.max(0, a.total - a.valid - a.failed - pending), 'bar-other']]) {
    const width = a.total ? amount / a.total * 100 : 0, rect = document.createElementNS(svg.namespaceURI, 'rect'); rect.setAttribute('x', x); rect.setAttribute('width', width); rect.setAttribute('height', 10); rect.setAttribute('class', cls); svg.append(rect); x += width;
  }
  wrap.append(svg); return wrap;
}

// [EV19.2] Show provenance and file locations in the same order as the saved run.
function pathCopy(value) {
  const row = el('div', 'path-copy'), status = el('span', 'path-copy-status');
  const name = value.replace(/[\\/]+$/, '').split(/[\\/]/).at(-1) || value;
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  let fallback;
  const control = button(name, async () => {
    control.disabled = true; status.textContent = '';
    try {
      await copySource(value, row); status.textContent = '경로 복사됨';
      fallback?.remove(); fallback = null;
    } catch {
      status.textContent = '복사하지 못했습니다. 아래 경로를 직접 복사해 주세요.';
      if (!fallback) { fallback = el('input', 'path-copy-fallback'); fallback.value = value; fallback.readOnly = true; fallback.setAttribute('aria-label', '직접 복사할 전체 경로'); row.append(fallback); }
      fallback.focus(); fallback.select();
    } finally { control.disabled = false; }
  }, 'path-copy-button');
  control.title = value; control.setAttribute('aria-label', `${name} · 전체 경로 복사`);
  row.append(control, status); return row;
}
function inputPath(file) {
  if (!file) return el('span', 'muted', '경로 미기록');
  const block = el('div', 'input-path');
  const caption = el('div', 'input-path-caption');
  const status = { AVAILABLE: '저장 파일 확인', MISSING: '파일 없음', UNAVAILABLE: '읽기 제한', RECORDED: '기록된 출처 · 존재 미검사', CONTRACT_PATH: '전달 규약 경로 · 존재 미검사' }[file.status];
  caption.append(el('span', '', status));
  block.append(caption, pathCopy(file.absolute_path || file.path));
  if (file.id) block.append(button('파일 보기', () => openFile(file), 'text-button'));
  return block;
}
async function renderInput() {
  const out = el('div', 'input-screen');
  out.append(await renderPurpose());
  const data = await get(api('input-flow'));
  if (!data) { out.append(note('이 HTML에는 입력 경로 기록이 없습니다. 최신 뷰어에서 다시 내보내 주세요.')); return out; }
  const intro = section('입력이 응답으로 이어지는 흐름', '선택한 회차 전체의 저장 기록입니다. 결과 필터로 입력 파일의 출처가 바뀌지는 않습니다.');
  intro.append(el('p', 'small muted', '파일명·폴더명 버튼을 누르면 전체 경로가 복사됩니다.'), el('p', 'small muted', '이 회차의 실험 폴더'), pathCopy(data.run_root));
  const flow = el('ol', 'input-flow-steps');
  for (const title of ['원천 데이터', 'public / private', '지시·응답 형식', '모델별 요청', '호출·반환 검사']) flow.append(el('li', '', title));
  intro.append(flow); out.append(intro);
  const origin = section(data.mode === 'REUSED_INPUT' ? '이전 입력을 가져옵니다' : '원천 데이터에서 대상을 정합니다', data.mode === 'REUSED_INPUT'
    ? '이 회차는 원천에서 문항을 다시 선정하지 않고 이전 회차의 public/private를 복사해 동일 입력을 사용했습니다.'
    : data.mode === 'COLLECTED_RESULTS' ? '데이터셋 전달 목록과 원본·변형 파일의 출처·해시·문항 연결을 확인한 뒤 실험 대상을 선정합니다.'
      : '저장된 원본 데이터와 변형 제작 결과에서 대상을 선정했습니다. 아래는 이 회차에 기록된 출처입니다.', '01');
  const origins = [data.reuse, ...data.reused_inputs, data.dataset_run, data.delivery_manifest].filter(Boolean);
  const originalSource = data.sources.find(item => item.variant === 'ORIGINAL')?.source ?? data.prepared_input;
  if (originalSource && !data.delivery_files?.length) origins.push(originalSource);
  origin.append(table(['원천·복사 위치', '실제 경로'], origins.map(file => [file.label, inputPath(file)])));
  if (data.delivery_files?.length) {
    origin.append(el('p', 'scope-note', 'manifest.json은 전달 파일 목록과 해시입니다. 실제 질문·본문은 아래 원본 1개 + 변형 7개 파일에서 읽습니다. 각 파일에서 선정한 문항을 public/private로 나눕니다.'),
      table(['입력 유형', '데이터셋에서 전달한 문제 파일'], data.delivery_files.map(file => [VARIANTS[file.variant] || file.variant, inputPath(file)])));
  }
  const detail = el('details', 'source-path-details'); detail.append(el('summary', '', '문항별 원본·변형의 제작 출처 확인'));
  const cases = [...new Set(data.sources.map(item => item.case))], sourceRows = el('div');
  const renderSources = id => sourceRows.replaceChildren(table(['유형', 'public/private에 기록된 원천 위치'], data.sources.filter(item => item.case === id).map(item => {
    const body = el('div');
    if (item.input_file) body.append(el('p', 'small muted', '실험 입력으로 읽는 문제 파일'), inputPath(item.input_file));
    body.append(el('p', 'small muted', item.source?.label || '제작 출처'), inputPath(item.source));
    if (item.files.length) { const files = el('details'); files.append(el('summary', '', '출처 해시가 저장된 실제 파일')); for (const file of item.files) files.append(inputPath(file)); body.append(files); }
    return [VARIANTS[item.variant] || item.variant, body];
  })));
  const chosen = cases.includes(state.case) ? state.case : cases[0], caseSelect = select(cases.map(id => [id, id]), chosen, renderSources); caseSelect.setAttribute('aria-label', '출처를 확인할 문항');
  detail.append(caseSelect, sourceRows); if (chosen) renderSources(chosen); origin.append(detail); out.append(origin);
  const split = section('모델용 문제와 평가자용 자료를 분리합니다', 'public에는 풀어야 할 질문·본문·정밀도를, private에는 정답과 제작 출처를 보존합니다. private는 풀이 모델의 입력에 합치지 않습니다.', '02');
  split.append(table(['파일', '담는 내용과 다음 용도', '이 회차의 저장 경로'], [
    ['public.jsonl', `${fmt(data.public_count)}개 항목 · ${data.public_fields.join(', ')} → 요청의 input 구성`, inputPath(data.public)],
    ['private.jsonl', `${fmt(data.private_count)}개 항목 · 정답·원본/변형 연결·제작 출처 → 원본 정답 비교와 Analysis`, inputPath(data.private)]
  ])); out.append(split);
  const contracts = section('지시와 응답 형식 네 파일을 고정합니다', '공통 지시 + 선택한 풀이 방식의 지시를 prompt로 묶고, 응답 JSON 형식을 response_schema로 함께 전달합니다. 이 회차에 복사·고정된 파일을 표시합니다.', '03');
  if (data.definition_source) contracts.append(el('p', 'small muted', '정의를 가져온 회차'), inputPath(data.definition_source));
  contracts.append(table(['역할', '고정된 실제 파일'], data.contracts.map(file => [file.label, inputPath(file)]))); out.append(contracts);
  const delivery = section('모델별 요청을 만들어 실행에 넘깁니다', 'public의 문제 + prompt + response_schema + 풀이·추론 설정 → 모델별 manifest.jsonl. 실행기는 이 요청 목록을 읽어 모델에 전달합니다. 원본 파일 경로 자체를 모델에게 보내는 것은 아닙니다.', '04');
  delivery.append(table(['모델 · 요청 수', '실제 전달 내용', '실행기가 읽는 요청 경로'], data.models.map(model => [
    `${model.model} · ${fmt(model.requests)}건`, `input: ${model.input_fields.join(', ') || '필드 미기록'} / prompt / response_schema / 호출 설정`, inputPath(model.manifest)
  ])));
  delivery.append(el('p', 'scope-note', 'public.jsonl · private.jsonl · 모델별 manifest.jsonl · events.jsonl은 서로 다른 네 종류의 산출물입니다. 모델이 여러 개면 요청 목록도 모델마다 하나씩 있습니다.'), inputPath(data.events)); out.append(delivery);
  const returned = section('호출과 반환 검사를 기록합니다', '요청 실행 뒤 원응답을 보존하고 형식·숫자 검사를 기록합니다. 아래 호출·검사 경로는 실제 저장된 한 요청의 예시이며, 결과 목록에서 각 요청을 찾을 수 있습니다.', '05');
  returned.append(table(['모델 · 전달 방식', '실제 호출 예시', '검사 원기록 예시', '반환 결과 목록'], data.models.map(model => [
    `${model.model} · ${model.transport || '전달 방식 미기록'}`, inputPath(model.call), inputPath(model.result), inputPath(model.results)
  ])));
  returned.append(button('문항의 실제 요청·응답 보기 →', () => navigate({ tab: 'case' }), 'text-button')); out.append(returned); return out;
}

function researchMarkdown(text) {
  const content = markdown(text, {});
  // Resolve only known cases in this run; other document links remain inert.
  for (const span of content.querySelectorAll('span')) {
    const match = span.textContent.match(/^(.*?) \((http:\/\/127\.0\.0\.1:8894\/\?[^)]+)\)$/);
    if (!match) continue;
    const target = new URL(match[2]), query = target.searchParams;
    if (query.get('run') !== state.run || query.get('tab') !== 'case') continue;
    const row = overview.semantic_cases.find(r => r.case === query.get('case') && r.variant === query.get('variant') && r.prompt_condition === query.get('prompt') && r.reasoning === query.get('reasoning'));
    if (!row) continue;
    span.replaceWith(button(`${row.case} · ${VARIANTS[row.variant]} · ${conditionName(row.prompt_condition, row.reasoning)}`, () => openCase({case: row.case, variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning}), 'doc-link'));
  }
  return content;
}

function semanticPanels() {
  const out = el('div'), semantic = overview.semantic;
  if (overview.review_reset) {
    out.append(note('기존 API 분석으로 만든 적절률·개선/악화 수치는 이번 재검토에서 사용하지 않습니다. 원기록은 보고서·이력에 보존했습니다. 아래 원본 숫자 일치와 숫자/null 표는 저장 응답의 관찰이며, Codex의 내용 판정과 구분합니다.', 'info'));
    return out;
  }
  const selectedAnalysis = overview.analysis_config?.backends?.[overview.analysis_config?.backend];
  const analysisName = selectedAnalysis ? `${overview.analysis_config.backend} · ${selectedAnalysis.model} · ${selectedAnalysis.reasoning_effort}` : '실행 당시 분석 기록';
  const progress = section('Analysis · 입력·응답 검토와 연구 해석', `${analysisName}. 입력을 먼저 판단한 다음 익명 응답을 검토합니다. 분석 LLM의 잠정 판정이며 사람 승인·gold와 구별합니다.`);
  progress.append(table(['단계', '상태', '분석 호출', '사용량 추정 USD'], overview.review_stages.map(stage => [
    { '01-LLM-input': 'A01 문항 답변 가능성', '02-LLM-response': 'A01 응답 내용 검토', '03-LLM-audit': 'A01 판단 재검토 (선택)', 'A03-research': 'A03 연구 해석' }[stage.stage] + (stage.shared_from_run ? ` · ${stage.shared_from_run} 공통 기준` : ''),
    stage.status === 'COLLECTED' ? `수집 완료 · 1차 검사 통과 ${stage.statuses?.VALID ?? 0}/${stage.requests}${stage.recovery ? ` · 재시도 ${stage.recovery.status === 'COLLECTED' ? `유효 ${stage.recovery.statuses?.VALID ?? 0}/${stage.recovery.requests}` : `처리 ${stage.recovery.request_counts?.completed ?? 0}/${stage.recovery.requests}`}` : ''}` : stage.status === 'BATCH_PENDING' ? 'Batch 처리 중' : stage.status === 'RUNNING' ? `검토 중 · ${stage.completed ?? 0}/${stage.requests}` : stage.status ? label(stage.status) : '미실행',
    stage.requests == null ? '—' : stage.shared_from_run ? '추가 호출 없음' : `${fmt(stage.requests)}${stage.recovery ? ` + 재시도 ${stage.recovery.requests}` : ''}`, stage.billing_mode === 'CODEX_SUBSCRIPTION' ? 'Codex 구독 · 추가 API $0' : money(stage.token_cost_estimate_usd)
  ])));
  out.append(progress);
  if (!semantic) { out.append(note('내용 검토 결과가 아직 집계되지 않았습니다. 아래 숫자 일치·null 관찰을 의미 정답률로 대신하지 않습니다.')); return out; }
  if (overview.research_review?.review_status === 'REQUIRES_ADJUDICATION') {
    out.append(note('A03 검토에서 정밀도·단위 해석과 일부 분석 판정의 일관성 문제가 확인됐습니다. 아래 수치는 원판정을 보존한 잠정 집계입니다. 비판적 검토의 실제 사례를 확인한 뒤 평가 기준을 토의해야 합니다.', 'info'));
  }
  const a = semantic.overall, cards = el('div', 'cards');
  cards.append(metric('내용 판정 가능', fmt(a.assessed), '', `계획 ${fmt(a.planned)}개 중`), metric('타당한 대응', fmt(a.appropriate), '', ratio(a.appropriate, a.assessed)), metric('미평가·미해결', fmt(a.unassessed), '', '분모와 별도 보존'), metric('재검토 불일치', fmt(a.audit_disagreements), '', '해당 응답은 미해결'));
  out.append(cards);
  if (overview.research_review?.report_ko) {
    const critique = rememberPanel(el('details', 'panel'), `critical-review-${state.run}`, false);
    critique.append(el('summary', 'section-head', 'A03 · 비판적 검토와 다음 결정 · 실제 사례와 평가 한계 펼치기'), researchMarkdown(overview.research_review.report_ko)); out.append(critique);
  }
  out.append(note('이 내용 판정·조건 비교는 선택한 차수 전체의 수치입니다. 조건별 셀을 누르면 해당 문항과 판단 근거를 확인할 수 있습니다.'));
  const matrix = section('7종 × 4조건 · 내용 적절성', '각 셀: 타당한 대응 / 내용 판정 가능 (미평가 수). 형식 통과율과 구분합니다. 표는 해당 차수 전체이며, 셀을 누르면 실제 판단 근거를 확인합니다.');
  matrix.classList.add('semantic-matrix');
  const conditions = [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']];
  for (const model of [...new Set(semantic.matrix.map(c => c.model ?? ''))]) {
    matrix.append(el('h4', '', model || '모델 구분 미기록'), table(['유형', ...conditions.map(([p, r]) => conditionName(p, r))], Object.keys(VARIANTS).filter(v => v !== 'ORIGINAL').map(variant => [VARIANTS[variant], ...conditions.map(([p, r]) => {
      const c = semantic.matrix.find(c => (c.model ?? '') === model && c.variant === variant && promptKey(c.prompt) === p && c.reasoning === r);
      return c ? button(`${ratio(c.appropriate, c.assessed)} · 미평가 ${c.unassessed}`, () => navigate({ semantic_cell: `${model}|${variant}|${p}|${r}`, tab: 'analysis' }), 'analysis-cell') : '미기록';
    })])));
  }
  out.append(matrix);
  const labels = section('Criteria-Guided Solving · 분류 기준 준수', '분류명 기재 여부와 입력 분석자의 잠정 분류와의 일치를 분리합니다. 분류명이 맞아도 풀이·근거가 타당하다는 뜻은 아닙니다.');
  labels.append(table(['모델', '유형', '추론', '분류명 기재 / 요청', '분류 일치 / 비교 가능', '실제 분류', '분류 출처', '분류·숫자 모순 / 검사'], semantic.matrix.filter(c => promptKey(c.prompt) === 'guided').sort((a, b) => (a.model ?? '').localeCompare(b.model ?? '') || Object.keys(VARIANTS).indexOf(a.variant) - Object.keys(VARIANTS).indexOf(b.variant) || a.reasoning.localeCompare(b.reasoning)).map(c => [
    c.model || '미기록', VARIANTS[c.variant], reasoningName(c.reasoning), `${c.guided_labels_present} / ${c.guided_planned}`, ratio(c.guided_classification_matches, c.guided_classification_compared),
    c.guided_stated_classifications ? Object.entries(c.guided_stated_classifications).map(([key, count]) => `${key} ${count}`).join(' · ') || '기재 없음' : '미집계',
    c.guided_classification_sources ? Object.entries(c.guided_classification_sources).map(([key, count]) => `${key === 'JSON_FIELD' ? 'JSON 필드' : key === 'LEGACY_EXPLANATION_PREFIX' ? '과거 명시 접두사' : key} ${count}`).join(' · ') || '기재 없음' : '미집계',
    c.guided_classification_answer_checked == null ? '미집계' : `${c.guided_classification_answer_mismatches} / ${c.guided_classification_answer_checked}`
  ])));
  labels.append(el('p', 'scope-note', '분류와 숫자 답의 일관성은 저장된 검사만 표시합니다. 분류 미기록이나 answer=null을 ABSTAIN으로 추정하지 않습니다. 의미상 적절성과는 별도입니다.'));
  out.append(labels);
  const conditional = section('Criteria-Guided Solving · 조건부 설명에서 얻은 정보', '조건부 선언만 늘어난 것인지, 설명에 조건별 결과가 실제로 나타났는지 구분합니다. 원문별 조건부 결과의 정확한 개수를 센 지표는 아닙니다.');
  conditional.append(table(['추론', '조건부 선언 / 요청', '분석자가 관찰한 조건부 / 검토 응답', '그중 타당한 조건부', '선언·관찰 행동 불일치 / 검토'], ['off', 'on'].map(reasoning => {
    const cells = semantic.matrix.filter(c => promptKey(c.prompt) === 'guided' && c.reasoning === reasoning);
    const total = field => cells.reduce((sum, c) => sum + (c[field] || 0), 0);
    const modes = field => cells.reduce((sum, c) => sum + (c[field]?.CONDITIONAL || 0), 0);
    return [reasoningName(reasoning), `${modes('guided_stated_modes')} / ${total('guided_planned')}`, `${modes('observed_behaviors')} / ${total('guided_mode_behavior_compared')}`, fmt(modes('appropriate_behaviors')), `${total('guided_mode_behavior_mismatches')} / ${total('guided_mode_behavior_compared')}`];
  })));
  conditional.append(el('p', 'scope-note', '타당한 조건부는 분석 통과·미해결 없음·재검토 불일치 없음인 응답만 셉니다. 행동 판정은 분석 LLM의 해석이며, 답변에 적힌 분류 문구의 영향을 받을 수 있습니다.'));
  out.append(conditional);
  const comparisons = section('A02 · 같은 문항의 개선·악화', '1→0은 타당한 대응에서 부적절한 대응으로의 악화, 0→1은 개선입니다. 미평가 짝은 따로 남깁니다. 구간은 원문 단위 재표집이며 탐색 결과입니다.');
  comparisons.append(table(['모델', '비교', '판정 가능 / 계획 짝', '개선 0→1', '악화 1→0', '차이 (오른쪽−왼쪽)', '95% 탐색 구간'], semantic.paired.map(p => [
    p.fixed_conditions?.model || '미기록', p.axis === 'prompt_condition' ? `${promptName(p.left)} → ${promptName(p.right)} · ${reasoningName(p.fixed_conditions?.reasoning)}` : `${reasoningName(p.left)} → ${reasoningName(p.right)} · ${promptName(p.fixed_conditions?.prompt)}`, `${p.assessed_pairs} / ${p.planned_pairs}`, p.transitions['0->1'] || 0, p.transitions['1->0'] || 0,
    p.difference == null ? '미평가' : `${(100 * p.difference).toFixed(1)}%p`, p.cluster_bootstrap_95?.map(v => `${(100 * v).toFixed(1)}%p`).join(' ~ ') || '미평가'
  ])));
  comparisons.append(table(['모델', '원본 숫자 결과', '조건', '변형 타당 / 판정 가능', '변형 미평가'], semantic.original_variant_relations.map(r => [
    r.model || '미기록', { ORIGINAL_NUMERIC_MATCH: '원본 일치', ORIGINAL_NUMERIC_MISMATCH: '원본 불일치', ORIGINAL_UNASSESSED: '원본 미평가', ORIGINAL_CONDITION_MISSING: '같은 조건 원본 없음' }[r.original_group] || r.original_group, conditionName(r.prompt, r.reasoning), ratio(r.appropriate, r.assessed), r.unassessed
  ])));
  out.append(comparisons);
  const parts = (state.semantic_cell || '').split('|');
  const [selectedModel, variant, prompt, reasoning] = parts.length === 4 ? parts : ['', ...parts];
  const cases = overview.semantic_cases.filter(r => (!selectedModel || r.model === selectedModel) && (variant ? r.variant === variant && promptKey(r.prompt_condition) === promptKey(prompt) && r.reasoning === reasoning : r.appropriate === false || r.audit_disagreement));
  const detail = section(variant ? `${VARIANTS[variant]} · ${conditionName(prompt, reasoning)}` : '내용 오류·재검토 불일치 사례', `해당 ${fmt(cases.length)}개 중 앞 50개입니다. 문항을 열면 풀이 응답과 분석자의 판단을 함께 봅니다.`);
  detail.append(table(['모델', '문항', '조건', '판정', '분석자의 이유', '재검토'], cases.slice(0, 50).map(r => [
    r.model || '미기록', button(r.case, () => navigate({ tab: 'case', case: r.case, model: r.model || '', variant: r.variant, prompt: r.prompt_condition, reasoning: r.reasoning }), 'cell-button mono'),
    `${VARIANTS[r.variant]} · ${conditionName(r.prompt_condition, r.reasoning)}`, OUTCOMES[r.review?.outcome] || '미검토', r.review?.reasoning || r.unassessed_reason,
    r.audit_disagreement ? '불일치 · 미해결' : r.audit ? '일치' : '표본 밖'
  ])));
  const scope = overview.improvement?.campaign ? `같은 ${fmt(overview.originals)}원문을 보며 고친 개발 실험입니다.` : `${fmt(overview.originals)}개 원본과 연결 변형의 확인용 실행입니다.`;
  const judge = selectedAnalysis ? `분석은 ${analysisName}로 수행했습니다.` : '분석 모델은 이 실행의 원기록에서 확인하십시오.';
  out.append(detail, note(`${scope} 독립 검증이나 동일 요청 반복의 안정성 검증으로 해석하지 않습니다. 동일 모델·풀이·추론의 원본 대조가 없는 응답은 대조군 미기록으로 남깁니다. ${judge} 모델 판정의 오류와 편향은 별도 검토가 필요합니다.`));
  return out;
}
// [EV03.3] Keep the selected run's purpose collapsed below the Input filters by default.
async function renderPurpose() {
  const panel = rememberPanel(el('details', 'panel input-panel'), 'input-experiment-purpose-v2', false);
  const summary = el('summary', 'section-head'), heading = el('h3');
  heading.append(el('span', 'section-index', '00'), '이 실험은 무엇을 확인하나요?');
  heading.append(el('span', 'input-condition', '실험 목적 · 비교 조건 · 실제 실행의 한계'));
  summary.append(heading, el('span', 'small muted', '접기·펼치기')); panel.append(summary);
  try {
    const documents = await get(api('documents'));
    const file = documents.files.find(file => file.path === 'EXPERIMENT-PURPOSE.md')
      || (overview.analysis_config?.enabled ? documents.files.find(file => file.path === 'README.md') : null);
    if (!file) { panel.append(note('이 실행의 목적·전제 문서가 아직 등록되지 않았습니다. 다른 실행의 정의를 대신 적용하지 않습니다.')); return panel; }
    const data = await get(api('file', { id: file.id }));
    const body = markdown(data.content, data.links); body.classList.add('document-content'); panel.append(body);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    panel.append(note(`실험 목적을 읽지 못했습니다: ${error.message}`, 'danger'));
  }
  return panel;
}
async function renderOverview() {
  const out = el('div'), a = overview.view.aggregate, cards = el('div', 'cards');
  cards.append(metric('현재 선택한 요청', fmt(a.total), '건', `${fmt(a.cases)}개 원문에서 파생된 조건`, null, true),
    metric('형식·일관성 통과', fmt(a.valid), `/ ${fmt(a.total)}`, '정답 여부와 별도로 기록한 반환 검사', () => drill({ status: 'VALID', metric: '' })),
    metric('형식 실패·출력 잘림', fmt(a.failed), `/ ${fmt(a.total)}`, '실제 실패 응답과 검사 사유 살펴보기', () => drill({ status: 'FORMAT_FAILED', metric: '' })),
    metric('원본풀이 정답 일치', a.numeric_eligible ? a.numeric_compared ? fmt(a.numeric_matches) : a.numeric_pending === a.numeric_eligible ? '수집 대기' : '미평가' : '해당 없음', a.numeric_compared ? `/ ${fmt(a.numeric_eligible)}` : '', a.numeric_eligible ? `네 조건 합계 · 조건별 결과는 아래 03에서 확인` : '현재 선택에 원본 요청이 없습니다.', a.numeric_compared ? () => drill({ status: '', metric: 'numeric_matches' }) : null));
  out.append(cards);
  const grid = el('div', 'grid-two'), results = section('모델별 반환 결과', '각 막대는 선택한 조건의 요청을 한 번씩 집계합니다.', '01');
  results.classList.add('overview-results');
  for (const m of overview.view.models) {
    const box = el('div', 'model-summary'), top = el('div', 'model-line'); top.append(el('span', 'model-title', m.key), el('span', 'small muted', `형식 통과 ${ratio(m.valid, m.total)}`)); box.append(top, statusBar(m));
    const mini = el('div', 'mini-stats');
    for (const [text, count, status] of [['통과', m.valid, 'VALID'], ['형식 실패', m.statuses.INVALID_RESPONSE || 0, 'INVALID_RESPONSE'], ['잘림', m.statuses.OUTPUT_TRUNCATED || 0, 'OUTPUT_TRUNCATED']]) mini.append(button(`${text} ${fmt(count)}`, () => drill({ model: m.key, status, metric: '' })));
    if (pendingCount(m)) mini.append(el('span', 'pending-stat', `진행·미수집 ${fmt(pendingCount(m))}`));
    box.append(mini); results.append(box);
  }
  const legend = el('div', 'legend'); for (const [cls, text] of [['valid', '형식 통과'], ['invalid', '형식·일관성 실패'], ['truncated', '출력 잘림'], ...(pendingCount(a) ? [['pending', '진행·미수집']] : []), ['other', '호출 오류 등']]) { const n = el('span'); n.append(el('i', `dot ${cls}`), text); legend.append(n); } results.append(legend);
  const scale = section('이 실행의 구성', '필터와 무관한 실행 전체의 규모입니다.', '02'); const flow = el('div', 'flow');
  for (const [i, [n, text]] of [[overview.originals, '원문'], [overview.variants, '변형'], [overview.planned, '계획 요청']].entries()) { if (i) flow.append(el('b', '', '→')); const d = el('div'); d.append(el('strong', '', fmt(n)), el('span', '', text)); flow.append(d); }
  scale.append(flow, el('p', 'scope-note', '원본·변형은 Unguided Solving·Criteria-Guided Solving × Reasoning OFF/Reasoning ON으로 구분합니다. 이 회차에 실제 저장된 요청만 집계합니다. OFF는 추론 비활성, ON은 활성입니다. 요청 수는 독립적인 원문 수와 다릅니다.'), el('p', 'small muted', `문항 수: 모델별 요청 manifest의 고유 문항 기준 · 모델 ${overview.models.length}개 · 선정 로그의 제외 기록 ${overview.selection?.exclusions == null ? '미기록' : fmt(overview.selection.exclusions) + '건'}`));
  grid.append(results, scale); out.append(grid);
  const analysis = section('숫자 비교와 분석 범위', '저장된 검사 결과를 표시합니다. 변형에는 원문 정답을 그대로 적용하지 않습니다.', '03');
  analysis.classList.add('original-comparison');
  for (const model of overview.view.original_conditions) {
    analysis.append(el('h4', '', model.model));
    const headings = ['구분', ...model.conditions.map((condition, index) => { const h = el('div', 'condition-column'); h.append(el('strong', '', `${index + 1}. ${promptName(condition.prompt)}`), el('span', '', reasoningName(condition.reasoning))); return h; })];
    const names = [['numeric_matches', '원본풀이 정답 일치'], ['numeric_mismatches', '정답 불일치'], ['numeric_unevaluated', '원본 미평가'], ['numeric_pending', '원본 미수집'], ['numeric_eligible', '원본 요청']];
    const cells = names.map(([key, title]) => [title, ...model.conditions.map(c => !c.numeric_eligible ? c.run_requests ? '선택 내 요청 없음' : '요청 없음' : key === 'numeric_eligible' ? fmt(c.numeric_eligible)
      : button(`${fmt(c[key])}${key === 'numeric_matches' ? ` / ${fmt(c.numeric_eligible)}` : ''}`, () => drill({ model: model.model, experiment: '1', variant: 'ORIGINAL', prompt: c.prompt, reasoning: c.reasoning, metric: key, status: '' }), 'cell-button'))]);
    analysis.append(table(headings, cells));
  }
  analysis.append(el('p', 'scope-note', '일치의 분모는 해당 조건의 원본 전체 요청이며, 일치 + 불일치 + 미평가 + 미수집 = 원본 요청입니다. 미수집은 아직 정답을 평가할 응답이 없다는 뜻입니다. ' + (overview.semantic ? '내용 적절성·유보 타당성은 02 Analysis에서 별도로 확인합니다. 분석 LLM의 잠정 판정이며 형식 통과와 구분합니다.' : '의미·유보 타당성은 아직 미평가이며, 형식 통과를 의미 정답으로 바꾸지 않습니다.')));
  const foot = el('div', 'toolbar');
  if (a.numeric_answers_absent != null) foot.append(button(`숫자 답 없음 ${fmt(a.numeric_answers_absent)}건`, () => drill({ metric: 'numeric_answers_absent', status: '' })), el('span', 'small muted', overview.semantic ? '유보 여부·적절성은 02 Analysis에서 별도로 확인합니다.' : '유보 여부·적절성은 미평가입니다.'));
  if (a.declared_abstentions != null) foot.append(button(`유보 선언 ${fmt(a.declared_abstentions)}건`, () => drill({ metric: 'declared_abstentions', status: '' })));
  if (a.abstention_markers != null) foot.append(button(`유보 표현 ${fmt(a.abstention_markers)}건`, () => drill({ metric: 'abstention_markers', status: '' })));
  foot.append(button('실행 보고서 읽기 →', () => navigate({ tab: 'reports' }), 'text-button')); analysis.append(foot); out.append(analysis); return out;
}

// [EV15.2] A paired original-gold view leads into the four-condition variant
// observations. Unreviewed semantics never receive a correctness percentage.
// [EV27.2] Keep the grounding display independent of A01 classification metrics.
async function renderGroundingAssessment() {
  let data;
  try { data = await get(api('grounding-pairs', { original: state.ground_original, abstention: state.ground_abstention, decision: state.ground_decision, review: state.ground_review })); }
  catch (error) { if (error.name === 'AbortError') throw error; data = { error: error.message }; }
  const out = renderGrounding(data, state, {
    choose: patch => navigate(patch),
    loadPage: filters => get(api('grounding-pairs', filters)),
    loadResponse: async (pair, original) => {
      const trial = original ? pair.original_trial_id : pair.variant_trial_id;
      if (!trial) return { model: pair.model, status: 'NOT_PLANNED', response: null };
      const detail = await get(api('case', { case: pair.case, model: pair.model, variant: original ? 'ORIGINAL' : pair.variant,
        prompt: pair.prompt_condition, reasoning: pair.reasoning }));
      const record = detail.responses.find(row => row.model === pair.model && row.trial_id === trial);
      if (!record) throw Error('이 대응쌍의 정확한 요청 ID에 연결된 응답이 없습니다.');
      return record;
    },
    openResponse: (pair, original) => {
      const clear = Object.fromEntries([...FILTERS, 'metric', 'display_metric', 'tags', 'tag_mode', 'paired', 'q', 'offset', 'case_offset', 'comparison_offset'].map(key => [key, '']));
      navigate({ ...clear, tab: 'case', case: pair.case, model: pair.model, variant: original ? 'ORIGINAL' : pair.variant,
        prompt: pair.prompt_condition, reasoning: pair.reasoning });
    },
    openValue, renderAssessment: record => renderResponseAssessment(record, { openValue })
  });
  return out;
}

async function renderAnswerable() {
  const container = el('div');
  if (!OFFLINE) container.append(await renderOutcomeComparison({load: filters => get('/api/outcome-comparison?' + new URLSearchParams(filters)), openRun: run => navigate({run, tab:'answerable', case:'', variant:'', prompt:'', reasoning:''})}));
  const out = await renderSemanticOutcomes({
    load: filters => get(api('semantic-outcomes', filters)),
    openResponse: row => navigate({ tab: 'case', case: row.case, model: row.model, variant: row.variant,
      prompt: row.prompt_condition, reasoning: row.reasoning, metric: '', status: '' })
  });
  if (overview.finalization) out.prepend(note(overview.finalization.status === 'COMPLETE' ? 'A03 수집 및 Python 후처리 완료 · A04는 사용자 지시로 생략' : '아래 저장 분류는 중간 산출물일 수 있습니다. A03 수집 및 실제 Python 후처리 완료가 확인되지 않아 Analysis 완료로 처리하지 않습니다.'));
  container.append(out);
  return container;
}

async function renderAnalysis() {
  let data;
  try { data = await get(api('rq1-materials')); }
  catch (error) { if (controller?.signal.aborted) throw error; data = { error: error.message, groups: [] }; }
  const rq1 = renderRQ1Materials(data, state, patch => navigate(patch), row => {
    const reset = Object.fromEntries([...FILTERS, 'metric', 'tags', 'paired', 'q', 'offset', 'case_offset'].map(key => [key, '']));
    navigate({ ...reset, tab: 'case', case: row.case, model: row.model, variant: row.variant, prompt: row.prompt_condition, reasoning: row.reasoning });
  });
  if (overview.results_analysis) { const out = renderResultCollection(); out.prepend(rq1); return out; }
  const out = el('div'), profile = overview.content_analysis;
  out.append(rq1);
  if (overview.improvement?.campaign || overview.semantic || overview.analysis_config?.enabled) out.append(semanticPanels());
  out.append(note('읽는 순서: 반환 형식 → 원본 Reasoning OFF/Reasoning ON의 gold 숫자 → 7종 변형 × 4조건의 관찰 → 설명·근거의 논리 검토 → 논문 비교. 여기서 gold 일치는 최종 숫자만 비교합니다. 변형의 숫자/null은 행동 관찰이며 정답 판정이 아닙니다.', 'info'));
  if (['experiment', 'variant', 'prompt', 'reasoning', 'status', 'metric', 'tags', 'paired'].some(key => state[key])) out.append(note('짝비교의 분모를 유지하기 위해 이 화면에는 모델 선택과 문항 검색만 적용합니다. 다른 상단 필터는 전체 결과·조건별 비교·실패 분석에서 사용합니다.'));
  const groupNames = { all: '전체 원문', both_match: 'Reasoning OFF·Reasoning ON 모두 일치', off_only: 'Reasoning OFF만 일치 · 역전', on_only: 'Reasoning ON만 일치 · 개선', both_mismatch: '둘 다 불일치', unevaluated: '짝 미평가' };
  for (const model of profile.models) {
    const b = model.baseline, group = profile.baseline_group;
    const first = section(`${model.key} · ${promptName(model.prompt)} · 원본 gold 짝비교`, '같은 모델·원문·풀이 방식의 Reasoning OFF와 Reasoning ON을 짝지었습니다. 형식 실패·숫자 비교 불가는 미평가로 남깁니다.', '01');
    first.append(table(['Reasoning OFF / Reasoning ON', '원문 수', '다음 단계'], [
      ['일치 / 일치', fmt(b.both_match.count), '두 조건에서 숫자 유지'],
      ['일치 / 불일치', fmt(b.off_only.count), 'Reasoning ON에서 악화한 역전 문항 검토'],
      ['불일치 / 일치', fmt(b.on_only.count), 'Reasoning ON에서 개선된 문항 검토'],
      ['불일치 / 불일치', fmt(b.both_mismatch.count), '공통 오답의 계산·해석 원인 검토'],
      ['한쪽 이상 미평가', fmt(b.unevaluated.count), '형식·관측 상태 먼저 확인']
    ]));
    const relation = el('p', 'scope-note', `Reasoning OFF 일치 원문 중 Reasoning ON도 일치: ${b.both_match.count} / ${b.both_match.count + b.off_only.count}. Reasoning OFF 불일치 원문 중 Reasoning ON 일치: ${b.on_only.count} / ${b.on_only.count + b.both_mismatch.count}. 미평가 짝 ${b.unevaluated.count}개는 두 비율에서 제외하고 별도로 남깁니다.`);
    first.append(relation);
    const choice = el('div', 'analysis-groups');
    for (const [key, name] of Object.entries(groupNames)) {
      const count = key === 'all' ? model.cases : b[key].count;
      choice.append(button(`${name} ${fmt(count)}`, () => navigate({ tab: 'analysis', baseline_group: key, analysis_cell: '' }), key === group ? 'active' : ''));
    }
    first.append(choice);
    if (group !== 'all') {
      const detail = section(`${groupNames[group]} · 실제 원문`, '문항 번호를 열어 두 추론 조건의 답·설명·근거를 대조합니다.');
      detail.append(table(['문항', 'Reasoning OFF 계산 ↔ gold', 'Reasoning ON 계산 ↔ gold', '검토'], b[group].cases.map(pair => [
        button(pair.case, () => navigate({ tab: 'case', case: pair.case, model: model.key, variant: 'ORIGINAL', prompt: model.prompt, reasoning: 'off' }), 'cell-button mono'),
        pair.off ? `${show(pair.off.computed)} ↔ ${show(pair.off.gold)} · ${pair.off.verdict}` : '기록 없음',
        pair.on ? `${show(pair.on.computed)} ↔ ${show(pair.on.gold)} · ${pair.on.verdict}` : '기록 없음',
        '설명·근거 수동 판독 필요'
      ])));
      first.append(detail);
    }
    out.append(first);
    const second = section(`${model.key} · ${promptName(model.prompt)} · 7종 변형`, `${fmt(model.selected_cases)}원문에 한정한 관찰입니다. 같은 모델·풀이 방식의 원본에만 연결합니다. 각 셀은 형식 통과 / 전체, 숫자답·null, 인용 문자열 불일치 순서입니다. 셀을 누르면 실제 문항을 봅니다.`, '02');
    second.classList.add('semantic-matrix');
    const labels = ['off', 'on'].map(reasoning => [model.prompt, reasoning]);
    second.append(table(['변형', ...labels.map(([p, r]) => conditionName(p, r))], model.variants.map(item => [VARIANTS[item.variant], ...item.cells.map(cell => {
      const key = `${model.key}|${item.variant}|${cell.prompt}|${cell.reasoning}`;
      const title = `형식 ${cell.valid}/${cell.total} · 숫자 ${cell.numeric} / null ${cell.null} · 인용 불일치 ${cell.quote_missing}`;
      return button(title, () => navigate({ tab: 'analysis', analysis_cell: key }), `analysis-cell${state.analysis_cell === key ? ' active' : ''}`);
    })])));
    const cells = model.variants.flatMap(item => item.cells), reviewed = cells.reduce((n, cell) => n + cell.semantic_reviewed, 0), total = cells.reduce((n, cell) => n + cell.total, 0);
    second.append(el('p', 'scope-note', `설명·근거의 논리 및 유보 적절성: 저장된 명시적 판정 ${fmt(reviewed)} / ${fmt(total)}응답. ${reviewed ? '판정별 근거와 검토 기준을 따로 확인해야 합니다.' : '현재 논리 정답률을 계산할 수 없습니다.'} 형식·null·인용 존재만으로 맞다/틀리다를 판정하지 않습니다.`));
    const signalMeanings = { NUMERIC_ANSWER_ABSENT: '숫자 답을 내지 않았다는 관찰입니다. 유보 타당성은 별도 내용 판정을 확인합니다.', QUOTE_NOT_EXACT_SUBSTRING: '인용문이 질문·본문에 정확히 나타나지 않음', EMPTY_EVIDENCE: '근거 배열이 비어 있음', OUTPUT_TRUNCATED: '출력 상한에 도달함' };
    if (model.observations.length) {
      const signals = section(`${model.key} · ${promptName(model.prompt)} · 내용 점검 신호`, '후처리 관찰 태그입니다. 한 응답에 여러 태그가 붙을 수 있고, 논리 오답 건수와 같지 않습니다.', '03');
      signals.append(table(['관찰 신호', '응답 수', '원문 수', '현재 해석'], model.observations.map(item => [
        tagLabel(item.tag), fmt(item.count), fmt(item.cases), signalMeanings[item.tag] || '저장된 관찰값 · 문항별 원응답 확인 필요'
      ])));
      second.append(signals);
    }
    const selected = model.variants.flatMap(item => item.cells.map(cell => ({ item, cell }))).find(({ item, cell }) => `${model.key}|${item.variant}|${cell.prompt}|${cell.reasoning}` === state.analysis_cell);
    if (selected) {
      const { item, cell } = selected, rows = cell.cases;
      const detail = section(`${VARIANTS[item.variant]} · ${conditionName(cell.prompt, cell.reasoning)} 실제 응답`, '상태·반환 답은 관찰값입니다. 문항을 눌러 설명과 근거를 읽어 논리 판정을 진행합니다.');
      detail.append(table(['문항', '반환 상태', '반환 답', '같은 조건 원본', '관찰 신호', '논리 판정'], rows.map(row => [
        button(row.case, () => navigate({ tab: 'case', case: row.case, model: model.key, variant: item.variant, prompt: cell.prompt, reasoning: cell.reasoning }), 'cell-button mono'),
        label(row.status), show(row.answer), row.original ? `${show(row.original.computed)} ↔ ${show(row.original.gold)} · ${row.original.verdict}` : '요청 없음', row.tags.length ? row.tags.map(tagLabel).join(' · ') : '기록된 표면 신호 없음',
        row.semantic === 'PASS' ? '타당 · 분석 LLM 판정' : row.semantic === 'FAIL' ? '부적절 · 분석 LLM 판정' : '미평가'
      ])));
      second.append(detail);
    }
    out.append(second);
  }
  return out;
}

function renderConditions() {
  if (overview.results_analysis) return renderResultRelationships();
  const out = el('div'), settings = el('div', 'toolbar');
  const metrics = [['valid', '형식·일관성 통과'], ['failed', '형식 실패·잘림'], ['numeric_matches', '원본 숫자 일치']];
  if (overview.view.aggregate.numeric_answers_absent != null) metrics.push(['numeric_answers_absent', '숫자 답 없음 · 의미 미평가']);
  if (overview.view.aggregate.declared_abstentions != null) metrics.push(['declared_abstentions', '유보 선언']);
  if (overview.view.aggregate.abstention_markers != null) metrics.push(['abstention_markers', '유보 표현']);
  settings.append(el('span', 'small muted', '표시 지표'), select(metrics, state.display_metric || 'valid', value => navigate({ display_metric: value })));
  const paired = el('label'), check = el('input'); check.type = 'checkbox'; check.checked = state.paired === 'true'; check.disabled = overview.models.length < 2; check.onchange = () => navigate({ paired: check.checked ? 'true' : '' }); paired.append(check, ' 모든 모델에서 숫자 비교 가능한 같은 문항만'); settings.append(paired); out.append(settings);
  if (state.paired === 'true') out.append(note(`전체 모델 공통 비교 집합: ${fmt(overview.view.aggregate.total)} / 필터 적용 전 공통선정 대상 ${fmt(overview.view.before_paired)} 요청. 원본 숫자 비교에만 적용됩니다.`));
  const metricName = state.display_metric || 'valid';
  for (const model of overview.view.models) {
    const p = section(model.key, '셀을 선택하면 그 조건의 실제 응답 목록으로 이동합니다.');
    const variants = overview.options.variants.filter(v => !state.variant || v === state.variant);
    p.append(table(['유형', ...[['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']].map(([prompt, reasoning]) => conditionName(prompt, reasoning))], variants.map(v => [VARIANTS[v], ...[['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']].map(([prompt, reasoning]) => {
      if (metricName === 'numeric_matches' && v !== 'ORIGINAL') return '해당 없음';
      const g = overview.view.groups.find(g => g.model === model.key && g.variant === v && g.prompt === prompt && g.reasoning === reasoning);
      if (!g) return '선택 내 요청 없음';
      if (g[metricName] == null) return '미평가';
      if (metricName === 'numeric_matches' && !g.numeric_compared) return '미평가';
      const b = button(ratio(g[metricName], metricName === 'numeric_matches' ? g.numeric_eligible : g.total), () => drill({ model: model.key, variant: v, prompt, reasoning, status: metricName === 'valid' ? 'VALID' : metricName === 'failed' ? 'FORMAT_FAILED' : '', metric: ['valid', 'failed'].includes(metricName) ? '' : metricName }), 'cell-button');
      return b;
    })]))); out.append(p);
  }
  out.append(note('IC-source 앞/뒤는 연결된 IC-value 부모 위치입니다. 출처를 붙인 대상도 함께 달라지므로, 표의 차이를 위치 효과 하나로 단정하지 않습니다.', 'info')); return out;
}

// [EV04.2] Render stored text as text nodes, including Markdown and evidence.
function inline(parent, text, links = {}) {
  const pattern = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;
  let at = 0;
  for (const m of text.matchAll(pattern)) {
    parent.append(text.slice(at, m.index));
    if (m[1]) { const file = links[m[2]]; parent.append(file ? button(m[1], () => openFile(file), 'doc-link') : el('span', '', `${m[1]} (${m[2]})`)); }
    else parent.append(el(m[3] ? 'strong' : 'code', '', m[3] || m[4])); at = m.index + m[0].length;
  }
  parent.append(text.slice(at));
}
function markdown(text, links = {}) {
  const out = el('div', 'prose'), lines = String(text ?? '').split('\n'); let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith('```')) { const language = line.slice(3).trim().toLowerCase(), code = []; i++; while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]); out.append(valueView(code.join('\n'), '문서의 코드', { format: ['json', 'jsonl'].includes(language) ? language : 'auto' })); i++; continue; }
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3}/.test(lines[i + 1])) {
      const split = row => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(x => x.trim());
      const headers = split(line), rows = []; i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) { rows.push(split(lines[i++]).map(c => { const span = el('span'); inline(span, c, links); return span; })); }
      out.append(table(headers, rows)); continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)/), list = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    const node = el(heading ? `h${heading[1].length}` : 'p', list ? 'list-line' : '');
    inline(node, heading ? heading[2] : list ? `• ${list[1]}` : line, links); out.append(node); i++;
  }
  return out;
}
function highlightText(host, full, quote) {
  host.replaceChildren(); let at = 0, found = false;
  if (!quote) { host.textContent = full; return false; }
  let index;
  while ((index = full.indexOf(quote, at)) >= 0) { host.append(full.slice(at, index), el('mark', 'quote-hit', quote)); at = index + quote.length; found = true; }
  host.append(full.slice(at)); return found;
}
function diffNodes(before, after) {
  const a = before.match(/\s+|[^\s]+/g) || [], b = after.match(/\s+|[^\s]+/g) || [];
  const left = el('div', 'diff-text'), right = el('div', 'diff-text');
  if (a.length * b.length > 2200000) {
    let start = 0, end = 0;
    while (start < Math.min(before.length, after.length) && before[start] === after[start]) start++;
    while (end < Math.min(before.length, after.length) - start && before[before.length - end - 1] === after[after.length - end - 1]) end++;
    left.append(before.slice(0, start), el('del', 'diff-removed', before.slice(start, before.length - end)), before.slice(before.length - end));
    right.append(after.slice(0, start), el('ins', 'diff-added', after.slice(start, after.length - end)), after.slice(after.length - end));
    return [left, right];
  }
  const width = b.length + 1, matrix = new Uint32Array((a.length + 1) * width);
  for (let x = a.length - 1; x >= 0; x--) for (let y = b.length - 1; y >= 0; y--) matrix[x * width + y] = a[x] === b[y] ? 1 + matrix[(x + 1) * width + y + 1] : Math.max(matrix[(x + 1) * width + y], matrix[x * width + y + 1]);
  let x = 0, y = 0;
  while (x < a.length || y < b.length) {
    if (a[x] === b[y] && x < a.length && y < b.length) { left.append(a[x++]); right.append(b[y++]); }
    else if (x < a.length && (y === b.length || matrix[(x + 1) * width + y] >= matrix[x * width + y + 1])) left.append(el('del', 'diff-removed', a[x++]));
    else right.append(el('ins', 'diff-added', b[y++]));
  }
  return [left, right];
}
function renderModelComparison() {
  const comparison = overview.model_comparison;
  if (comparison.models.length < 2) return empty('이 실행에는 비교할 두 번째 모델이 없습니다. 실행 기록에서 두 모델을 포함한 회차를 선택해 주세요.');
  const out = el('div');
  out.append(note('같은 문항·유형·프롬프트 조건·추론 조건으로 두 모델을 묶었습니다. 형식 통과와 gold 숫자 일치는 별개이며, 논리 정답은 별도 판정이 없으면 미평가입니다.'));
  if (comparison.additional_models) out.append(note(`이 화면은 설정 순서의 앞 두 모델을 표시합니다. 나머지 ${fmt(comparison.additional_models)}개 모델은 문항 비교에서 확인해 주세요.`));
  const cards = el('div', 'cards');
  cards.append(metric('짝지은 조건', fmt(comparison.total), '개', '같은 문항·실험 조건 기준', null, true),
    metric('양쪽 형식 통과', fmt(comparison.both_valid), `/ ${fmt(comparison.total)}`, '응답 상태가 둘 다 형식 통과', null),
    metric('양쪽 숫자 비교 가능', fmt(comparison.both_numeric_compared), `/ ${fmt(comparison.total)}`, '형식 통과 후 gold와 비교한 쌍', null),
    metric('숫자 일치 판정 차이', comparison.both_numeric_compared ? fmt(comparison.numeric_disagreement) : '미평가', comparison.both_numeric_compared ? `/ ${fmt(comparison.both_numeric_compared)}` : '', '두 쪽 모두 숫자 판정을 받은 쌍만 분모', null));
  out.append(cards);
  const panel = section('동일 조건의 두 응답', '각 칸은 반환 상태 → 답 → 원본 gold 숫자 판정 순서입니다. 문항을 누르면 두 응답의 설명·근거·실제 요청을 함께 봅니다.', '01');
  const modelCell = value => {
    const cell = el('div', 'comparison-model-cell');
    cell.append(badge(value?.status ?? 'NO_RECORD'));
    cell.append(el('strong', 'comparison-answer', value?.has_answer ? show(value.answer) : '응답 없음'));
    cell.append(el('span', 'comparison-numeric', value?.status !== 'VALID' || typeof value.numeric_match !== 'boolean'
      ? 'gold 숫자: 미평가' : value.numeric_match ? 'gold 숫자: 일치' : 'gold 숫자: 불일치'));
    if (value?.semantic) cell.append(el('span', 'comparison-semantic', `논리 판정: ${value.semantic}`));
    return cell;
  };
  const [first, second] = comparison.models;
  const rows = comparison.rows.map(row => {
    const link = button(`${row.case} · ${VARIANTS[row.variant] || row.variant}`, () => navigate({
      tab: 'case', case: row.case, variant: row.variant, prompt: row.prompt, reasoning: row.reasoning, model: '', status: '', tags: '', metric: '', paired: ''
    }), 'cell-button');
    const condition = el('div', 'comparison-condition');
    condition.append(link, el('span', 'small muted', conditionName(row.prompt, row.reasoning)));
    if (row.question) condition.append(el('span', 'comparison-question', row.question));
    const left = row.models[first], right = row.models[second];
    const assessed = [left, right].every(value => value?.status === 'VALID' && typeof value.numeric_match === 'boolean');
    const verdict = !assessed ? '숫자 짝비교 미평가'
      : left.numeric_match && right.numeric_match ? '둘 다 일치'
        : left.numeric_match ? `${first}만 일치`
          : right.numeric_match ? `${second}만 일치` : '둘 다 불일치';
    return [condition, modelCell(left), modelCell(right), el('span', `comparison-verdict${assessed ? '' : ' muted'}`, verdict)];
  });
  const list = table(['문항 · 같은 조건', first, second, 'gold 숫자 짝비교'], rows);
  list.classList.add('comparison-table'); panel.append(list);
  if (!comparison.total) panel.append(empty('선택한 문항·조건에 저장된 요청이 없습니다.'));
  const pager = el('div', 'comparison-pager'), start = comparison.offset;
  pager.append(el('span', 'small muted', comparison.total ? `${fmt(start + 1)}–${fmt(Math.min(start + comparison.page_size, comparison.total))} / ${fmt(comparison.total)} 조건` : '0 조건'));
  const previous = button('← 이전', () => navigate({ comparison_offset: String(Math.max(0, start - comparison.page_size)) }));
  previous.disabled = start === 0;
  const next = button('다음 →', () => navigate({ comparison_offset: String(start + comparison.page_size) }));
  next.disabled = start + comparison.page_size >= comparison.total;
  pager.append(previous, next); panel.append(pager); out.append(panel);
  out.append(el('p', 'scope-note', '이 표는 저장된 모델 응답만 읽습니다. 응답이 없는 칸은 값이나 정답으로 채우지 않습니다. 실제 입력·프롬프트·스키마가 같은지는 문항 비교에서 확인하세요.'));
  return out;
}
// [EV16.3] Keep all 32 cells visible while the detail selection changes.
function renderCaseHeatmap(d) {
  const panel = section('문항 결과 한눈에 보기', '행은 풀이·추론 조건, 열은 00~07 유형입니다. 색상 셀을 선택하면 아래에서 해당 답변을 확인합니다.');
  panel.classList.add('case-heatmap');
  if (!d.heatmap) { panel.append(note('히트맵 자료를 읽으려면 실험 뷰어 서버를 다시 시작해 주세요.')); return panel; }
  const legend = new Map(d.heatmap.legend.map(entry => [entry.key, entry]));
  panel.append(el('p', 'heatmap-reference', `원본 정답: ${d.heatmap.reference_answer ?? '미기록'}`));
  for (const model of d.heatmap.models) {
    const wrap = el('div', 'heatmap-model'), grid = el('table', 'heatmap-table');
    grid.append(el('caption', '', model.model));
    const header = el('thead'), headerRow = el('tr'), corner = el('th', '', '풀이 · 추론'); corner.scope = 'col'; headerRow.append(corner);
    for (const variant of d.heatmap.variants) {
      const th = el('th'), [number, ...name] = VARIANTS[variant].split(' · '); th.scope = 'col';
      th.append(el('strong', '', number), el('span', '', name.join(' · '))); headerRow.append(th);
    }
    header.append(headerRow); grid.append(header);
    const body = el('tbody');
    for (const condition of model.conditions) {
      const row = el('tr'), heading = el('th'); heading.scope = 'row';
      heading.append(el('span', '', promptName(condition.prompt)), el('span', 'heatmap-reasoning', reasoningName(condition.reasoning))); row.append(heading);
      for (const cell of condition.cells) {
        const category = legend.get(cell.color ?? cell.category), td = el('td');
        const active = cell.selectable && cell.variant === d.variant && condition.prompt === d.prompt && condition.reasoning === d.reasoning;
        const control = button(category.short, () => navigate({ variant: cell.variant, prompt: condition.prompt, reasoning: condition.reasoning }), `heatmap-cell heatmap-${cell.color ?? cell.category}${active ? ' active' : ''}`);
        if (cell.answer_text != null) {
          control.classList.add('has-value'); control.replaceChildren(el('span', 'heatmap-value', cell.answer_text));
          if (cell.reference_matches === false) { const difference = el('span', 'heatmap-difference', '≠'); difference.setAttribute('aria-hidden', 'true'); control.append(difference); }
        }
        control.disabled = !cell.selectable; control.setAttribute('aria-pressed', String(active));
        control.dataset.variant = cell.variant; control.dataset.prompt = condition.prompt; control.dataset.reasoning = condition.reasoning; control.dataset.category = cell.category;
        const cmp = cell.numeric_comparison;
        control.title = `${model.model} · ${VARIANTS[cell.variant]} · ${conditionName(condition.prompt, condition.reasoning)} · ${category.label}${cell.status !== 'NOT_PLANNED' && label(cell.status) !== category.label ? ` · ${label(cell.status)}` : ''}${typeof cmp?.matches === 'boolean' ? ` · ${show(cmp.computed)} ↔ ${show(cmp.gold ?? cmp.reference_answer)}` : ''}`;
        if (cell.answer_text != null) control.title += ` · 응답 ${cell.answer_text}${cell.reference_matches !== null ? ` · 원본 정답 ${d.heatmap.reference_answer} · ${cell.reference_matches ? '숫자 일치' : '숫자 불일치'}` : ' · 원본 정답 비교 미평가'}`;
        if (cell.classification) control.title += ` · classification: ${cell.classification.label} · ${cell.classification.definition}`;
        control.setAttribute('aria-label', control.title); td.append(control); row.append(td);
      }
      body.append(row);
    }
    grid.append(body); wrap.append(grid); panel.append(wrap);
  }
  const key = el('div', 'heatmap-legend'); key.setAttribute('aria-label', '히트맵 색상 범례');
  for (const entry of d.heatmap.legend) { const item = el('span', 'heatmap-legend-item'), swatch = el('span', `heatmap-swatch heatmap-${entry.key}`); swatch.setAttribute('aria-hidden', 'true'); item.append(swatch, entry.label); key.append(item); }
  const differenceKey = el('span', 'heatmap-legend-item'); differenceKey.append(el('span', 'heatmap-difference', '≠'), '원본 정답과 숫자가 다름'); key.append(differenceKey);
  panel.append(key, el('p', 'small muted heatmap-note', '숫자 셀은 실제 응답 값입니다. 명시된 classification이 있으면 그 분류의 색을 사용합니다. ≠는 원본 정답과의 숫자 차이이며 변형의 정오답 판정이 아닙니다. 분류·정답 비교의 의미는 범례와 셀 도움말에서 확인합니다.'));
  return panel;
}
// [EV25.2] Display the agreed axes and the unresolved denominator below E02.
function renderCasePairMatrix(d) {
  const panel = section('Pair Outcome Matrix · 원본–변형 대응 결과', '같은 모델·풀이·추론의 원본과 변형을 연결합니다. 원본의 숫자 정오답과 변형 대응의 의미 판정을 구분합니다.');
  panel.classList.add('case-pair-matrix');
  panel.append(table(['변형 대응 / 원본 풀이', '원본 오답', '원본 정답'], [
    ['대응 성공', '② · 원본 오답 / 대응 성공 · 의미 미판정', '① · 원본 정답 / 대응 성공 · 의미 미판정'],
    ['대응 실패', '③ · 원본 오답 / 대응 실패 · 의미 미판정', '④ · 원본 정답 / 대응 실패 · 의미 미판정']
  ]));
  panel.append(note('현재 E04는 형식·원본 숫자 비교를 검사합니다. 변형 대응의 의미 판정 기록이 없어 사분면 수치는 아직 계산하지 않습니다. null·숫자 일치·classification만으로 성공을 채우지 않습니다.'));
  const groups = pairMatrixReadiness(d.heatmap);
  const originalLabel = value => ({ MATCH: '원본 정답', MISMATCH: '원본 오답', UNASSESSED: '원본 미판정' })[value];
  panel.append(table(['모델', '풀이 · 추론', '원본 판정', '전체 예정 쌍', '원본 미판정', '변형 미수집·형식 실패', '변형 의미 미판정'], groups.map(group => [
    group.model, conditionName(group.prompt, group.reasoning), originalLabel(group.original_result),
    group.planned, group.original_unassessed, group.variant_unavailable, group.semantic_not_reviewed
  ])));
  const details = el('details'); details.append(el('summary', '', '유형별 원본–변형 쌍 보기'));
  details.append(table(['모델', '풀이 · 추론', '유형', '원본 판정', '변형 실행·형식 상태', '응답 형태', '분류', '사분면'], groups.flatMap(group => group.pairs.map(pair => [
    group.model, conditionName(group.prompt, group.reasoning), VARIANTS[pair.variant], originalLabel(pair.original_result),
    label(pair.status), d.heatmap.legend.find(entry => entry.key === pair.category)?.label ?? pair.category,
    group.prompt === 'unguided' && !pair.classification?.known ? '분류 미요구' : pair.classification?.label ?? '미기록',
    '배치 불가 · ' + ({ ORIGINAL_UNASSESSED: '원본 미판정', VARIANT_UNAVAILABLE: '변형 미수집·형식 실패', SEMANTIC_NOT_REVIEWED: '대응 의미 미판정' })[pair.readiness]
  ]))));
  panel.append(details, el('p', 'small muted', '전체 예정 쌍은 미수집·형식 실패·미판정을 포함합니다. 미판정을 실패율이나 0% 성공률로 표시하지 않습니다. 이 표는 저장 자료만 읽으며 모델을 호출하지 않습니다.'));
  return panel;
}
async function renderCase() {
  const caseId = state.case || overview.view.cases[0]?.id;
  if (!caseId) return empty('선택한 조건에 해당하는 문항이 없습니다. 필터를 조정해 주세요.');
  const d = await get(api('case', { ...state, case: caseId }));
  if (!state.case) { state.case = caseId; writeURL(true); }
  const out = el('div'), head = el('div', 'case-heading'); head.id = 'case-heading'; head.tabIndex = -1;
  const jumps = el('div', 'case-jumps');
  for (const [direction, title, key, neighbor] of [[-1, '← 이전', 'Q', 'previous'], [1, '다음 →', 'E', 'next']]) {
    const control = button(`${title} · ${key}`, () => moveCase(direction)); control.disabled = !overview.view.case_navigation?.[neighbor]; control.setAttribute('aria-keyshortcuts', key === 'Q' ? 'Q K' : 'E J'); jumps.append(control);
  }
  head.append(el('h3', 'mono', d.case), jumps); out.append(head, renderCaseHeatmap(d), renderCasePairMatrix(d));
  const tabs = el('div', 'variant-tabs'); tabs.setAttribute('aria-label', '문항 유형 · A 이전 / D 다음');
  for (const v of d.variants) { const control = button(VARIANTS[v], () => navigate({ variant: v, prompt: d.prompt }), v === d.variant ? 'active' : ''); control.setAttribute('aria-pressed', String(v === d.variant)); tabs.append(control); } out.append(tabs);
  const controls = el('div', 'toolbar case-controls'); controls.setAttribute('role', 'toolbar'); controls.setAttribute('aria-label', '프롬프트·추론 선택 · Z/C 조합 즉시 선택 / 개별 버튼 Space 선택');
  const combinations = el('div', 'combination-controls'); combinations.setAttribute('aria-label', '프롬프트·추론 조합과 저장된 처리 시간');
  for (const condition of d.conditions) {
    const { prompt, reasoning, available, models } = condition, active = prompt === d.prompt && reasoning === d.reasoning;
    const choice = el('div', 'combination-choice'), control = button(conditionName(prompt, reasoning), () => navigate({ prompt, reasoning }), `condition-combo${active ? ' active' : ''}`);
    control.replaceChildren(el('span', 'condition-prompt', promptName(prompt)), el('span', 'condition-reasoning', reasoningName(reasoning)));
    control.setAttribute('aria-label', conditionName(prompt, reasoning));
    control.dataset.conditionKey = `pair-${prompt}-${reasoning}`; control.disabled = !available; control.setAttribute('aria-pressed', String(active));
    const elapsed = el('div', 'condition-time'); elapsed.id = `condition-time-${prompt}-${reasoning}`; control.setAttribute('aria-describedby', elapsed.id);
    if (!available) elapsed.append(el('span', '', '요청 없음'));
    else for (const model of models) {
      const duration = model.timing_error ? '시간 읽기 오류' : model.elapsed_seconds == null ? model.status === 'NOT_PLANNED' ? '요청 없음' : '시간 미기록' : `${model.elapsed_seconds.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}초`;
      const line = el('span', '', `${models.length > 1 ? `${model.model} · ` : ''}${duration}`); line.title = `저장된 최종 시도 · ${label(model.status)}`; elapsed.append(line);
    }
    choice.append(control, elapsed); combinations.append(choice);
  }
  controls.append(combinations);
  const individual = el('div', 'individual-controls'); individual.setAttribute('aria-label', '프롬프트·추론 개별 선택');
  for (const prompt of ['unguided', 'guided']) { const control = button(promptName(prompt), () => navigate({ prompt }), prompt === d.prompt ? 'active' : ''); control.disabled = !d.conditions.some(condition => condition.prompt === prompt && condition.available); control.dataset.conditionKey = `prompt-${prompt}`; control.setAttribute('aria-pressed', String(prompt === d.prompt)); individual.append(control); }
  individual.append(el('span', 'muted', '/'));
  for (const reasoning of ['off', 'on']) { const control = button(reasoningName(reasoning), () => navigate({ reasoning }), reasoning === d.reasoning ? 'active' : ''); control.dataset.conditionKey = `reasoning-${reasoning}`; control.setAttribute('aria-pressed', String(reasoning === d.reasoning)); individual.append(control); }
  controls.append(individual);
  controls.append(button('모든 모델 나란히 보기', () => navigate({ model: '' }), 'text-button push')); out.append(controls);
  out.append(el('p', 'small muted condition-note', '조합 아래 시간은 저장된 최종 시도의 처리 시간입니다. Z/C 이동 시 조합 버튼은 즉시 선택되고, 개별 버튼은 Space로 선택합니다.'));
  out.append(el('p', 'small muted', '상태·진단 필터는 왼쪽 목록에 적용됩니다. 상세에는 선택한 문항의 같은 조건을 모델별로 함께 표시합니다.'));
  if (d.conditions_match === false) out.append(note('모델별 실제 입력·프롬프트·스키마가 다릅니다. 각 응답의 정확한 요청을 확인해 주세요.', 'danger'));
  if (d.conditions_match === true) out.append(el('p', 'small muted', '모델별 Q/C·프롬프트·응답 스키마의 JSON 내용이 같습니다.'));
  const primaryResponse = d.responses.find(r => r.request), primaryRequest = primaryResponse?.request;
  const input = primaryRequest?.input ?? d.item;
  const context = String(input?.context ?? ''), question = String(input?.question ?? '입력이 없습니다.');
  const inputEdits = await verifyInputEdits({ caseId: d.case, variant: d.variant, original: d.original, item: d.item, request: primaryRequest?.input, provenance: d.metadata?.edit_provenance });
  // [EV04.4] Native disclosure preserves keyboard control and refresh state.
  const inputPanel = rememberPanel(el('details', 'panel input-panel'), 'model-input');
  const inputSummary = el('summary', 'section-head'), inputHeading = el('h3', '', '모델에 전달한 입력');
  inputHeading.append(el('span', 'input-condition', `${VARIANTS[d.variant]} · ${conditionName(d.prompt, d.reasoning)}`));
  inputSummary.append(inputHeading, el('span', 'small muted', '접기·펼치기')); inputPanel.append(inputSummary);
  const externalKnowledge = d.metadata?.original_external_knowledge;
  if (externalKnowledge) {
    const value = externalKnowledge.used
      ? `원본 제작 시 외부지식 사용 확인: ${(externalKnowledge.used_types || []).join(', ')}`
      : '원본 제작 시 외부지식 사용 확인 조건 미충족';
    inputPanel.append(el('p', 'scope-note', `${value}. 변형 자체의 재판정이나 이 풀이 모델의 외부지식 사용 여부가 아닙니다.`));
  }
  // [EV04.5] Put question/context first, followed by the saved request components.
  const requestBlock = (key, title, value, open = false) => {
    const block = el('details', 'request-block'); block.append(el('summary', '', title));
    if (value !== undefined) block.append(valueView(value, title));
    return rememberPanel(block, key, open);
  };
  if (primaryResponse) inputPanel.append(el('p', 'small muted', `표시 기준: ${primaryResponse.model}의 저장된 요청 · 실제 호출 여부는 응답 상태에서 확인합니다.`));
  else inputPanel.append(note('정확한 요청 기록이 없습니다. Q/C는 저장된 공개 입력을 표시합니다.'));
  const requestDetails = document.createDocumentFragment();
  requestDetails.append(requestBlock('request-prompt', 'prompt', primaryRequest?.prompt ?? '프롬프트 미기록'), requestBlock('request-schema', 'JSON schema', primaryRequest?.response_schema ?? '응답 스키마 미기록'));
  const extraInput = Object.fromEntries(Object.entries(input ?? {}).filter(([key]) => !['question', 'context'].includes(key)));
  if (Object.keys(extraInput).length) requestDetails.append(requestBlock('request-extra-input', '추가 입력 · Q/C 외 필드', extraInput));
  const requestSettings = Object.fromEntries(d.responses.filter(r => r.request).map(r => [r.model, Object.fromEntries(Object.entries(r.request).filter(([key]) => !['prompt', 'response_schema', 'input'].includes(key)))]));
  if (Object.values(requestSettings).some(value => Object.keys(value).length)) requestDetails.append(requestBlock('request-settings', '요청 설정·식별 정보 · 모델별 저장 기록', requestSettings));
  const qcPanel = requestBlock('request-qc', 'Q/C · 질문과 본문', undefined, true);
  const q = el('div', 'question', question), feedback = el('p', 'quote-feedback'), contextHost = el('div', 'context-scroll'); contextHost.append(renderInputContext(context, inputEdits));
  qcPanel.append(el('h4', 'input-label', 'Q · 질문'), q, el('h4', 'input-label', 'C · 본문'));
  const contextModes = el('div', 'toolbar'); contextModes.append(button('문단·표 보기', () => { contextHost.replaceChildren(renderInputContext(context, inputEdits)); feedback.textContent = ''; }), button('원문 그대로', () => { contextHost.replaceChildren(renderInputContext(context, inputEdits, 'raw')); feedback.textContent = ''; }));
  qcPanel.append(inputEditNotice(inputEdits), contextModes, feedback, contextHost);
  const removedInput = inputEditDeletions(inputEdits); if (removedInput) qcPanel.append(removedInput); inputPanel.append(qcPanel, requestDetails);
  const analyst = el('details', 'analyst'); analyst.append(el('summary', '', '분석자용 정보 · 모델에 보내지 않은 원문 정답'), el('p', '', `원문 기준 답: ${show(d.original_metadata?.reference?.reference_answer)} · ${d.variant === 'ORIGINAL' ? '저장된 원본 숫자 비교의 기준입니다.' : '이 답을 변형 문항의 정답으로 적용하지 않습니다.'}`));
  analyst.append(el('p', '', `제작 기준 Q/C와 문자 일치: ${d.metadata?.baseline_qc_matches_generation_reference === true ? '일치 기록' : d.metadata?.baseline_qc_matches_generation_reference === false ? '차이 기록 있음' : '관련 기록 없음'} · 제작 기준 본문 사본: 파일 미포함`));
  if (d.metadata?.value_dependency || d.metadata?.value_pair) analyst.append(disclosure('IC-value 부모 연결 기록', d.metadata.value_dependency ?? d.metadata.value_pair)); inputPanel.append(analyst);
  let comparisonPanel;
  if (d.variant !== 'ORIGINAL' && d.original) {
    const diff = rememberPanel(el('details', 'panel comparison-panel'), 'case-input-diff', false); diff.append(el('summary', '', '실험 원본 ↔ 현재 입력 · 문자열 차이 보기'));
    const columns = el('div', 'diff-columns'); const [left, right] = diffNodes(`Question: ${d.original.question}\n\n${d.original.context}`, `Question: ${question}\n\n${context}`);
    for (const [title, body] of [['실험 원본 · 삭제 부분', left], ['현재 전달 입력 · 추가 부분', right]]) { const col = el('div'); col.append(el('h4', '', title), body); columns.append(col); }
    diff.append(el('p', 'small muted', '문자열 차이 표시이며 의미 판정이 아닙니다.'), columns); comparisonPanel = diff;
  }
  const highlight = (quote, request) => {
    inputPanel.open = true; qcPanel.open = true;
    if (JSON.stringify(request?.input) !== JSON.stringify(primaryRequest?.input)) { feedback.textContent = '모델별 입력이 달라 이 공통 본문에서 강조하지 않았습니다. 해당 모델의 정확한 요청을 확인해 주세요.'; return; }
    const foundC = !!quote && context.includes(quote), foundQ = highlightText(q, question, quote); contextHost.replaceChildren(renderInputContext(context, inputEdits, 'raw', quote));
    feedback.textContent = foundC || foundQ ? '인용문이 실제 입력과 정확히 일치합니다. 문자열 일치는 내용 타당성 평가와 별개입니다.' : '정확 일치 없음 · 수신한 인용문을 수정하거나 보정하지 않았습니다.';
    const match = inputPanel.querySelector('mark'); match?.scrollIntoView({ block: 'center', behavior: 'smooth' }); if (!match) inputPanel.scrollIntoView({ block: 'start' });
  };
  const responses = el('div', 'responses');
  for (const r of d.responses) {
    const card = el('article', 'response-card'), top = el('div', 'response-top'), responseStatus = el('div', 'response-status');
    responseStatus.append(badge(r.status));
    if (r.status === 'OUTPUT_TRUNCATED' && (r.diagnostic?.tags?.includes('OUTPUT_TRUNCATED') || r.finish_reason === 'max_tokens')) responseStatus.append(el('span', 'response-diagnostic', tagLabel('OUTPUT_TRUNCATED')));
    top.append(el('h3', '', r.model), responseStatus); card.append(top);
    if (r.missing) card.append(empty('이 조건의 요청이 없습니다.'));
    if (r.status === 'NOT_RUN') card.append(note('이 요청은 준비됐지만 아직 모델을 호출하지 않았습니다.'));
    if (r.missing_result) card.append(note('연결된 검사 원기록이 없습니다. 저장 요약과 호출 JSON을 구분해 확인해 주세요.'));
    const response = r.response, meta = response?.answer_meta ?? (response && 'negative' in response ? { negative: response.negative, scale: response.scale } : null);
    const cmp = r.checks?.numeric_comparison;
    // [EV12.3] Null is a display placeholder; the saved response and its status stay distinct.
    const hasAnswer = response != null && Object.hasOwn(response, 'answer');
    const answer = response == null ? '응답 없음' : hasAnswer && response.answer !== null ? `${typeof response.answer === 'string' && meta?.negative === true ? '−' : ''}${show(response.answer)}` : 'Null';
    const answerValue = el('div', 'answer', answer);
    if (!hasAnswer || response.answer === null) {
      answerValue.title = hasAnswer ? '반환된 answer 값은 null입니다.' : response == null ? '완성된 응답 본문이 없습니다. 수신한 원문은 원기록에서 확인합니다.' : '응답에 answer 필드가 없습니다.';
      answerValue.setAttribute('aria-label', `${answer} · ${answerValue.title}`);
    }
    const answerSummary = el('div', `answer-summary${cmp?.matches === true ? ' answer-match' : ''}`), answerLabel = el('p', 'answer-label', '모델이 반환한 답');
    answerLabel.append(el('span', 'response-meta', `(${r.request?.response_schema?.title || '계약 이름 미기록'}${meta ? ` · negative=${show(meta.negative)} · scale=${show(meta.scale)}` : ''}${response?.status ? ` · ${response.status}` : ''})`));
    answerSummary.append(answerLabel, answerValue);
    if (typeof cmp?.matches === 'boolean') answerSummary.append(el('p', 'answer-comparison', `저장된 숫자 비교: ${show(cmp.computed)} ↔ ${show(cmp.gold ?? cmp.reference_answer)} · ${cmp.matches ? '일치' : '불일치'}`));
    else answerSummary.append(el('p', 'answer-comparison', d.variant === 'ORIGINAL' ? '숫자 비교 미평가 · 검사 원기록에서 이유 확인' : '원문 정답과 숫자 비교: 해당 없음'));
    // [EV17.2] Keep the returned value and declared classification side by side.
    const declared = r.classification ?? { label: '미기록', definition: '명시된 분류가 저장되어 있지 않음', color: 'class-unrecorded' };
    const classificationSummary = el('div', `classification-summary heatmap-${declared.color}`);
    classificationSummary.append(el('p', 'classification-label', 'classification'), el('strong', 'classification-value', declared.label), el('p', 'classification-definition', declared.definition));
    if (declared.assessment) classificationSummary.append(el('p', 'classification-assessment', declared.assessment));
    if (declared.source) classificationSummary.append(el('p', 'classification-source', declared.source === 'JSON_FIELD' ? '모델의 반환 필드' : '과거 explanation의 명시 분류'));
    const summaryRow = el('div', 'answer-classification-row'); summaryRow.append(answerSummary, classificationSummary); card.append(summaryRow);
    if (r.schema_errors?.length) { const errors = el('div', 'notice danger'); for (const error of r.schema_errors) errors.append(el('p', '', `${error.path?.join('.') || 'response'} · ${error.message || error.rule}`)); card.append(errors); }
    if (r.error) card.append(typeof r.error === 'object' ? disclosure('오류 기록', r.error) : note(show(r.error), 'danger'));
    if (response?.explanation != null) { const explanation = el('div', `response-section response-explanation${cmp?.matches === true ? '' : ' explanation-focus'}`); explanation.append(el('h4', '', 'EXPLANATION · 반환 설명'), typeof response.explanation === 'object' ? valueView(response.explanation, '반환 설명') : el('p', 'prose', show(response.explanation))); card.append(explanation); }
    let semanticSection;
    if (r.semantic) {
      const judged = el('div', 'response-section semantic-review');
      judged.append(el('h4', '', `A01 분석 LLM · ${OUTCOMES[r.semantic.review?.outcome] || '미검토'}`));
      judged.append(el('p', 'prose', r.semantic.review?.reasoning || r.semantic.unassessed_reason));
      if (r.semantic.audit_disagreement) judged.append(note('재검토와 판단이 달라 기본 적절률에서는 미해결로 집계합니다.'));
      judged.append(disclosure('입력 상태·차원별 판단·인용·재검토 원문', r.semantic)); semanticSection = judged;
    }
    const evidence = response?.evidence;
    if (evidence != null) {
      const evidenceSection = el('div', 'response-section'); evidenceSection.append(el('h4', '', 'EVIDENCE · 선택하면 입력에서 강조'));
      const quotes = Array.isArray(evidence) ? evidence : [evidence];
      if (!Array.isArray(evidence)) evidenceSection.append(el('p', 'small muted', '배열이 아닌 원래 반환 형식을 유지해 표시합니다.'));
      if (!quotes.length) evidenceSection.append(el('p', 'muted small', '빈 근거 배열'));
      for (const quote of quotes) evidenceSection.append(typeof quote === 'string' ? button(quote, () => highlight(quote, r.request), 'evidence') : valueView(quote, '반환 근거')); card.append(evidenceSection);
    }
    if (semanticSection) card.append(semanticSection);
    card.append(renderResponseAssessment(r, { openValue }));
    if (!response && r.response_text) card.append(disclosure('수신한 응답 문자열 · JSON 미완성 가능', r.response_text, { format: 'json' }));
    const actions = el('div', 'response-actions'); actions.append(button('정확한 요청', () => openValue('정확한 요청 · 모델 입력과 프롬프트·스키마', r.request)), button('검사·진단', () => openValue('저장된 검사와 분석 · 의미 평가는 별도', { checks: r.checks, schema_errors: r.schema_errors, diagnostic: r.diagnostic })));
    if (response != null) actions.append(button('응답 JSON', () => openValue(`${r.model} · 응답 JSON`, response)));
    for (const file of r.artifacts ?? []) actions.append(button(file.label, () => openFile(file))); card.append(actions);
    const attempts = el('details'); attempts.append(el('summary', '', `시도 이력 ${r.attempts?.length ?? 0}개 · 사용량 보기`));
    for (const attempt of r.attempts ?? []) if (attempt.artifact) attempts.append(button(attempt.artifact.label, () => openFile(attempt.artifact), 'text-button'));
    attempts.append(valueView({ finish_reason: r.finish_reason, usage: r.usage }, '종료 사유·사용량')); card.append(attempts); responses.append(card);
  }
  // [EV12.1] Read the model answers first, then compare inputs and inspect the request.
  const responseSection = el('section', 'model-responses'), responseHeading = el('div', 'responses-heading'), responseTitle = el('h3', '', '모델별 답변');
  responseTitle.id = 'model-responses-heading'; responseSection.setAttribute('aria-labelledby', responseTitle.id);
  responseHeading.append(responseTitle, el('p', 'small muted', `${VARIANTS[d.variant]} · ${conditionName(d.prompt, d.reasoning)}`));
  responseSection.append(responseHeading, responses); out.append(responseSection);
  if (comparisonPanel) out.append(comparisonPanel);
  out.append(inputPanel); return out;
}

// [EV10.2] Reuse visible actions so keyboard and pointer navigation stay identical.
function moveCase(direction) {
  if (state.tab !== 'case' || $('content').getAttribute('aria-busy') === 'true') return;
  const target = overview?.view.case_navigation?.[direction < 0 ? 'previous' : 'next'];
  if (target) navigate({ case: target.id, case_offset: '' });
}
function moveConditionFocus(direction) {
  const buttons = [...document.querySelectorAll('.case-controls [data-condition-key]:not(:disabled)')];
  let index = buttons.indexOf(document.activeElement);
  if (index < 0) index = buttons.findIndex(control => control.classList.contains('condition-combo') && control.classList.contains('active'));
  const target = index < 0 ? (direction > 0 ? buttons[0] : buttons.at(-1)) : buttons[index + direction];
  target?.focus();
  if (target?.classList.contains('condition-combo')) target.click();
}
document.addEventListener('keydown', event => {
  if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || document.querySelector('dialog[open]')) return;
  if (event.target.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="combobox"]')) return;
  const key = /^Key[A-Z]$/.test(event.code || '') ? event.code.slice(3).toLowerCase() : event.key.toLowerCase();
  if (/^[1-9]$/.test(key)) {
    const tab = document.querySelector(`#tabs [data-shortcut="${key}"]`);
    if (tab) { event.preventDefault(); if (!event.repeat) tab.click(); }
    return;
  }
  if (key === 's' || key === 'w') {
    event.preventDefault();
    if (!event.repeat) window.scrollBy(0, Math.round(window.innerHeight / 2) * (key === 's' ? 1 : -1));
    return;
  }
  if (state.tab !== 'case' || !document.querySelector('#case-heading')) return;
  const conditionArrow = event.target.closest?.('.case-controls') && ['ArrowLeft', 'ArrowRight'].includes(event.key);
  if (!conditionArrow && !['q', 'e', 'j', 'k', 'a', 'd', 'b', 'z', 'c'].includes(key)) return;
  event.preventDefault();
  if (event.repeat || $('content').getAttribute('aria-busy') === 'true') return;
  if (['q', 'e', 'j', 'k'].includes(key)) { moveCase(['q', 'k'].includes(key) ? -1 : 1); return; }
  if (['a', 'd', 'b'].includes(key)) {
    const buttons = [...document.querySelectorAll('.variant-tabs button')], index = buttons.findIndex(control => control.classList.contains('active'));
    buttons[index + (key === 'a' ? -1 : 1)]?.click(); return;
  }
  if (conditionArrow || key === 'z' || key === 'c') { moveConditionFocus(key === 'z' || event.key === 'ArrowLeft' ? -1 : 1); return; }
});

const RESPONSE_COLUMNS = [['case', '문항'], ['variant', '유형'], ['model', '모델'], ['prompt', '프롬프트'], ['reasoning', '추론'], ['status', '반환 형식'], ['diagnostics', '진단 사유']];
function responseList() {
  const rows = overview.view.rows;
  if (!rows.length) return empty('조건에 맞는 응답이 없습니다. 위의 진단 선택을 해제하거나 결과 필터를 바꿔 주세요.');
  const box = el('div'), [sortField, sortDirection] = overview.view.sort.split('_');
  const list = table([...RESPONSE_COLUMNS.map(([, name]) => name), '원본풀이 정답 비교'], rows.map(r => {
    const first = el('div', 'failure-case'); first.append(button(r.case, () => openCase(r), 'cell-button mono'));
    return [first, VARIANTS[r.variant] || r.variant, r.model, promptName(r.prompt), reasoningName(r.reasoning), badge(r.status), r.tags.map(tagLabel).sort((a, b) => a.localeCompare(b, 'ko')).join(' · ') || '진단 사유 없음', r.variant !== 'ORIGINAL' ? '변형 · 정답 비교 대상 아님' : r.numeric?.matches === true ? '정답 일치' : r.numeric?.matches === false ? `정답 불일치 · ${show(r.numeric.computed)} ↔ ${show(r.numeric.gold ?? r.numeric.reference_answer)}` : '미평가'];
  }));
  list.classList.add('failure-table');
  for (const [i, [field, name]] of RESPONSE_COLUMNS.entries()) {
    const th = list.querySelectorAll('th')[i], active = sortField === field;
    const direction = active ? sortDirection === 'asc' ? 'desc' : 'asc' : field === 'diagnostics' ? 'desc' : 'asc';
    th.setAttribute('aria-sort', active ? sortDirection === 'asc' ? 'ascending' : 'descending' : 'none');
    const control = button(`${name} ${active ? sortDirection === 'asc' ? '↑' : '↓' : '↕'}`, () => navigate({ sort: `${field}_${direction}`, offset: '0' }), 'sort-heading');
    control.title = field === 'diagnostics' ? '저장된 진단 사유 개수로 정렬' : field === 'status' ? '오름차순: 출력 잘림 → 형식 실패 → 그 외 상태 → 형식 통과' : `${name} ${direction === 'asc' ? '오름차순' : '내림차순'} 정렬`;
    th.replaceChildren(control);
  }
  box.append(list);
  const p = el('div', 'pager'), offset = overview.view.offset, total = overview.view.aggregate.total;
  const prev = button('← 이전 30건', () => navigate({ offset: String(Math.max(0, offset - 30)) })), next = button('다음 30건 →', () => navigate({ offset: String(offset + 30) })); prev.disabled = offset === 0; next.disabled = offset + 30 >= total;
  p.append(prev, el('span', 'small muted', `${offset + 1}–${Math.min(offset + 30, total)} / ${fmt(total)} 요청`), next); box.append(p); return box;
}
function renderFailures() {
  // [EV13.2] Keep reasons above the results, with independent facet counts and visible sorting.
  const out = el('div', 'failure-screen'), a = overview.view.aggregate, selected = [...new Set((state.tags || '').split(',').filter(Boolean))];
  const purposes = section('무엇을 확인하시겠습니까?', '형식 검사와 원본 정답 비교는 서로 다른 기준입니다. 한 응답이 두 기준에 해당할 수 있습니다.');
  const countsByPurpose = overview.view.inspection_counts, choices = el('div', 'inspection-choices');
  const definitions = [
    ['format', '형식 문제', countsByPurpose.failed, 'JSON·응답 형식 오류와 출력 잘림', { status: 'FORMAT_FAILED', metric: '' }],
    ['mismatch', '원본풀이 정답 불일치', countsByPurpose.numeric_mismatches, '원본 정답과 반환 숫자가 다른 요청', { status: '', metric: 'numeric_mismatches', experiment: '1', variant: 'ORIGINAL' }],
    ['unassessed', '원본 미평가', countsByPurpose.numeric_unevaluated, '원본 정답 비교 결과가 없는 요청', { status: '', metric: 'numeric_unevaluated', experiment: '1', variant: 'ORIGINAL' }],
    ['all', '전체 응답', countsByPurpose.total, '통과·불일치·미평가를 모두 확인', { status: '', metric: '' }]
  ];
  const active = state.metric === 'numeric_mismatches' ? 'mismatch' : state.metric === 'numeric_unevaluated' ? 'unassessed' : !state.metric && ['FORMAT_FAILED', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED'].includes(state.status) ? 'format' : !state.metric && !state.status ? 'all' : '';
  for (const [key, title, count, description, patch] of definitions) {
    const choice = button('', () => navigate({ experiment: '', variant: '', tags: '', tag_mode: '', paired: '', offset: '0', case_offset: '0', ...patch }), `inspection-choice${active === key ? ' active' : ''}`);
    choice.dataset.inspection = key; choice.setAttribute('aria-pressed', String(active === key)); choice.append(el('strong', '', title), el('b', '', fmt(count)), el('span', '', description)); choices.append(choice);
  }
  purposes.append(choices, el('p', 'small muted', '각 버튼의 건수는 모델·풀이·추론·검색 조건 기준입니다. 목적을 바꾸면 유형·반환 상태·진단·공통 요청 제한을 해당 목적에 맞게 재설정합니다.'));
  const selectedPurpose = METRICS[state.metric] || (active === 'format' ? '형식 문제' : state.status ? label(state.status) : '전체 응답');
  purposes.append(el('p', 'inspection-current', `현재 확인: ${selectedPurpose} · ${fmt(a.total)}개 요청`)); out.append(purposes);
  const diagnoses = section('진단 사유로 좁히기', overview.diagnostics_available ? '아래 사유를 선택하면 응답 목록이 바뀝니다. 다시 누르면 선택을 해제합니다.' : '이 실행은 저장된 진단 분석이 없습니다.');
  diagnoses.classList.add('failure-filters');
  const tools = el('div', 'failure-filter-tools'), modes = el('label', '', '사유 결합'), order = el('label', '', '사유 정렬');
  const mode = select([['all', '선택 사유 모두 포함'], ['any', '선택 사유 중 하나라도 포함']], state.tag_mode || 'all', tag_mode => navigate({ tag_mode, offset: '0', case_offset: '0' })); mode.setAttribute('aria-label', '진단 사유 결합 방식'); modes.append(mode);
  const tagSort = select([['count', '건수 많은 순'], ['name', '이름순']], state.diagnostic_sort === 'name' ? 'name' : 'count', diagnostic_sort => navigate({ diagnostic_sort })); tagSort.setAttribute('aria-label', '진단 사유 정렬'); order.append(tagSort);
  const clear = button('진단 선택 해제', () => navigate({ tags: '', offset: '0', case_offset: '0' }), 'text-button'); clear.disabled = selected.length === 0;
  tools.append(modes, order, el('span', 'small muted', selected.length ? `${selected.length}개 사유 선택` : '진단 사유 전체'), clear); diagnoses.append(tools);
  const counts = overview.view.tag_counts, tags = el('div', 'diagnostic-chips'); tags.setAttribute('aria-label', '진단 사유 필터');
  const names = [...new Set([...Object.keys(counts), ...selected])].sort((a, b) => (state.diagnostic_sort === 'name' ? 0 : (counts[b] || 0) - (counts[a] || 0)) || tagLabel(a).localeCompare(tagLabel(b), 'ko') || a.localeCompare(b));
  for (const tag of names) {
    const active = selected.includes(tag), b = button('', () => { const values = new Set(selected); if (values.has(tag)) values.delete(tag); else values.add(tag); navigate({ tags: [...values].join(','), offset: '0', case_offset: '0' }); }, `diagnostic-chip${active ? ' active' : ''}`);
    b.dataset.tag = tag; b.setAttribute('aria-pressed', String(active));
    b.append(el('span', '', `${active ? '✓ ' : ''}${tagLabel(tag)}`), el('span', 'diagnostic-count', `${fmt(counts[tag] || 0)}건`)); tags.append(b);
  }
  diagnoses.append(names.length ? tags : el('p', 'small muted', '현재 기본 조건에 해당하는 저장 진단 사유가 없습니다.'));
  diagnoses.append(el('p', 'failure-facet-note', `사유별 건수는 위 결과 필터의 ${fmt(overview.view.tag_scope_total)}개 요청 기준입니다. 사유 선택 전 건수이며, 한 요청에 여러 사유가 있을 수 있습니다.`));
  out.append(diagnoses);
  const listing = section(`${selectedPurpose} · 응답 목록`, `${fmt(a.total)}개 요청 · ${fmt(a.cases)}개 문항. 문항 번호를 누르면 해당 응답을 엽니다.`);
  const sortTools = el('div', 'failure-result-tools'), sortLabel = el('label', '', '응답 정렬');
  const sortOptions = RESPONSE_COLUMNS.flatMap(([key, name]) => [['asc', '↑'], ['desc', '↓']].map(([direction, arrow]) => [`${key}_${direction}`, `${name}${key === 'diagnostics' ? ' 개수' : key === 'case' ? ' 번호' : ''} ${arrow}`]));
  const sort = select(sortOptions, overview.view.sort, sort => navigate({ sort, offset: '0' })); sort.setAttribute('aria-label', '응답 정렬'); sortLabel.append(sort);
  sortTools.append(sortLabel, el('span', 'small muted', '열 제목을 눌러 정렬 방향을 바꿀 수 있습니다.')); listing.append(sortTools, responseList()); out.append(listing);
  if (overview.verification) out.append(disclosure('이 실행에 저장된 분석·검증 범위', overview.verification)); return out;
}

async function renderCosts() {
  const data = await get(api('activity')), out = el('div');
  const logPanel = section('Python 실행 로그', '실제 명령어와 단계·처리 건수를 pipeline.log에서 읽습니다. 최근 60행을 5초마다 새로 읽습니다.');
  const logText = el('pre', 'mono', '로그 읽는 중…');
  logText.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;max-height:48vh;overflow:auto;font-size:12px';
  const logStatus = el('p', 'small muted');
  logPanel.append(logText, logStatus); out.append(logPanel);
  const logRun = state.run, fileRoute = api('file'), documentsRoute = api('documents');
  const refreshLog = async () => {
    if (state.run !== logRun || state.tab !== 'costs') return;
    try {
      const docs = await get(documentsRoute, null);
      const readme = docs.files.find(file => file.path === 'README.md');
      if (!readme) throw Error('실행 README가 없습니다.');
      const document = await get(`${fileRoute}&id=${encodeURIComponent(readme.id)}`, null);
      const file = document.links['pipeline.log'];
      if (!file) throw Error('이 실행의 README에 pipeline.log 링크가 없습니다.');
      const log = await get(`${fileRoute}&id=${encodeURIComponent(file.id)}`, null);
      if (state.run !== logRun || state.tab !== 'costs') return;
      const rows = log.content.trimEnd().split('\n');
      const command = rows.findLast(row => row.includes('PIPELINE_COMMAND'));
      const tail = rows.slice(-60);
      logText.textContent = [...(command && !tail.includes(command) ? [command] : []), ...tail].join('\n');
      logText.scrollTop = logText.scrollHeight;
      logStatus.textContent = `pipeline.log · 읽은 시각 ${new Date().toLocaleTimeString('ko-KR')}`;
    } catch (error) { logStatus.textContent = `로그 읽기: ${error.message}`; }
    if (!OFFLINE && logPanel.isConnected) setTimeout(refreshLog, 5000);
  };
  // Start after the returned panel is mounted; stop polling when it is removed.
  setTimeout(refreshLog, 0);
  out.append(note('이 탭은 실행 전체의 저장된 사용량·이력입니다. 위 응답 필터로 비용을 재계산하지 않습니다. 입력에 포함된 캐시 토큰, 출력에 포함된 추론 토큰은 중복 합산하지 않습니다.', 'info'));
  if (overview.evaluation_reuse) {
    const targetCalls = overview.evaluation_reuse.new_target_model_calls;
    const analysisCalls = overview.results_analysis?.stages?.find(stage => stage.stage === '03_research')?.external_model_calls;
    out.append(note(`아래 모델 사용량은 ${overview.evaluation_reuse.source_run}의 저장된 Evaluation 비용입니다. 이번 회차의 대상 모델 신규 호출은 ${Number.isInteger(targetCalls) ? `${fmt(targetCalls)}회` : '미기록'}, 별도 분석 모델 호출은 ${Number.isInteger(analysisCalls) ? `${fmt(analysisCalls)}회` : '미기록'}입니다. 중복 합산하지 않습니다.`, 'info'));
  }
  if (!overview.results_analysis && (overview.improvement?.campaign || overview.analysis_config?.enabled)) {
    const analysisCosts = section('이번 차수의 분석 비용', '풀이 비용과 별도로 집계합니다. 같은 입력의 독립 판정을 2·3차에서 참조할 경우 입력 판정 비용은 최초 차수에만 귀속합니다.');
    analysisCosts.append(table(['분석 단계', '상태', '호출 수', '사용량 추정 USD'], overview.review_stages.map(s => [s.stage, s.status || '미실행', fmt(s.requests), money(s.token_cost_estimate_usd)]))); out.append(analysisCosts);
  }
  const costs = section('모델별 사용량과 비용', '실패·재시도도 포함한 저장 집계입니다. 기록되지 않은 비용·토큰을 0으로 바꾸지 않습니다.');
  const costTable = table(['모델', '시도', '입력 토큰', '입력 중 캐시', '출력 토큰', '출력 중 추론', 'usage 없는 시도', '유료 Batch 추정', '추가 API 과금', '실제 청구'], data.models.map(m => [m.key, fmt(m.attempts), fmt(m.input_tokens), fmt(m.cache_read_tokens), fmt(m.output_tokens_including_thinking), fmt(m.reported_reasoning_output_tokens), fmt(m.attempts_without_usage), m.transport === 'codex_cli' ? '해당 없음' : money(m.paid_batch_usage_cost_estimate_usd), m.incremental_api_charge_usd == null ? '미기록' : money(m.incremental_api_charge_usd), money(m.billed_cost_usd)])); costTable.classList.add('cost-table'); costs.append(costTable, el('p', 'scope-note', '구독 CLI의 추가 API 과금 0은 구독료 0을 의미하지 않습니다. Batch 추정치는 실제 청구액이 아닙니다. 반환되지 않은 usage가 있으면 전체 사용량이 완전히 기록된 것으로 보지 않습니다.')); out.append(costs);
  const statePanel = section('모델별 실행 상태', '현재 종료 여부는 state.json을 따릅니다. 자원 측정·배치 제출의 과거 이벤트와 구분합니다.');
  statePanel.append(table(['모델', '현재 저장 상태', '처리 방식', '동시 처리 설정', '제공자 상태'], data.models.map(m => {
    const modelState = data.state?.models?.[m.key], reused = data.state?.evaluation?.status === 'REUSED';
    return [m.key, badge(modelState?.status ?? (reused ? 'REUSED' : null)), m.transport, fmt(modelState?.concurrency), modelState?.provider_status || modelState?.provider_batch_state || (reused ? `${overview.evaluation_reuse.source_run} 원본 회차 참조` : '해당 없음')];
  })));
  statePanel.append(disclosure('실행 상태·계획 원문', { state: data.state, plan: data.plan })); out.append(statePanel);
  for (const resource of data.resources || []) {
    const p = section(`${resource.model} · 저장된 자원 기록`, '시스템 전체 CPU·메모리입니다. 마지막 샘플은 종료 직전일 수 있으며 현재 실행 여부는 위의 상태를 따릅니다.');
    p.append(table(['마지막 측정', 'CPU', '메모리', '여유 메모리', '마지막 측정의 active', '실제 최대 active', '설정 상한 최대', '메모리 보류 샘플'], [[time(resource.latest?.at), `${fmt(resource.latest?.cpu_percent)}%`, `${fmt(resource.latest?.memory_percent)}%`, resource.latest?.available_memory_bytes == null ? '미기록' : `${(resource.latest.available_memory_bytes / 2 ** 30).toFixed(2)} GiB`, fmt(resource.latest?.active), fmt(resource.summary?.maximum_active), fmt(resource.summary?.maximum_limit), fmt(resource.summary?.memory_blocked_samples)]]));
    p.append(disclosure('측정·집계 원문', resource)); out.append(p);
  }
  const events = section('최근 실행 기록', 'events.jsonl에 저장된 마지막 100행을 최신순으로 읽습니다. 종료 기록을 새로 만들지 않습니다.');
  const body = el('div', 'events'); for (const event of data.events) { const d = el('details'); d.append(el('summary', '', `${event.at || event.timestamp || event.time || '시각 미기록'} · ${event.event || event.kind || event.type || '이벤트'}${event.model ? ` · ${event.model}` : ''}`), valueView(event, '실행 이벤트')); body.append(d); }
  events.append(data.events.length ? body : empty('저장된 이벤트가 없습니다.')); out.append(events); return out;
}

async function renderReports() {
  if (overview.results_analysis) return renderResultResearch();
  const data = await get(api('documents')), layout = el('div', 'document-layout');
  const list = section('보고서와 이력', '선택한 실행 안의 Markdown 문서만 읽습니다.'), nav = el('div', 'document-list'), article = section('문서 읽기', '본문의 호출·원응답 링크는 저장 파일 창으로 열립니다.'); article.id = 'document-panel';
  const files = data.files.sort((a, b) => { const rank = p => p === '02_analysis/01_response_review/00-codex-review.md' ? -2 : ({ 'EXPERIMENT-PURPOSE.md': -1, 'REPORT.md': 0, 'ANALYSIS.md': 1, 'CASE-STUDIES.md': 2, 'README.md': 3 })[p] ?? 4; return rank(a.path) - rank(b.path) || a.path.localeCompare(b.path); });
  if (overview.improvement?.campaign === '20260927-luna-three-rounds') {
    const report = el('a', 'source-link', '1·2·3차 종합 기록 · 변경 이유·결과·비용 ↗');
    report.href = 'http://127.0.0.1:8893/?run=20260927-luna-three-rounds&doc=reports%2Frun%2F20260927-luna-three-rounds%2FREADME.md'; report.target = '_blank'; report.rel = 'noopener'; list.append(report);
    const paper = el('a', 'source-link', '실험을 반영한 논문 초안 ↗');
    paper.href = 'http://127.0.0.1:8893/?run=20260924-paper-draft&doc=reports%2Frun%2F20260924-paper-draft%2FPAPER-KO.md'; paper.target = '_blank'; paper.rel = 'noopener'; list.append(paper);
  }
  const open = async file => {
    const version = ++documentEpoch;
    article.replaceChildren(el('p', 'small muted', '문서 읽는 중…'));
    try { const data = await get(api('file', { id: file.id })); if (version !== documentEpoch) return; article.replaceChildren(el('h3', 'mono', data.path)); const body = markdown(data.content, data.links); body.classList.add('document-content'); article.append(body); for (const b of nav.children) b.classList.toggle('active', b.dataset.id === file.id); }
    catch (e) { if (e.name !== 'AbortError') article.replaceChildren(note(e.message, 'danger')); }
  };
  for (const file of files) { const b = button(file.path, () => open(file)); b.dataset.id = file.id; nav.append(b); } list.append(nav); layout.append(list, article);
  if (files.length) await open(files[0]); else article.append(empty('저장된 Markdown 보고서가 없습니다.')); return layout;
}
// Results-focused analysis consumes saved aggregates and cited response records.
const RESULT_CONDITIONS = [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']];
const RESULT_CATEGORIES = { RESPONSE_PATTERNS: '① 전체 응답', ORIGINAL_VARIANT: '② 원본과 변형', CONDITION_EFFECTS: '③ 조건 효과', VARIANT_BEHAVIOR: '④ 유형별 풀이·선택', RESPONSE_ELEMENTS: '⑤ 답·분류·설명·근거', COUNTEREXAMPLES: '⑥ 반례', RESEARCH_INTERPRETATION: '⑦ 연구 해석' };
const RESULT_BASELINES = { MATCH: '원본 일치', MISMATCH: '원본 불일치', UNEVALUATED: '원본 미평가', ORIGINAL_MISSING: '원본 기록 없음' };
const RESULT_CLASSIFICATION_ORDER = ['UNGUIDED_NUMERIC', 'UNGUIDED_NULL', 'ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED'];
function resultScope(out) {
  const stages = overview.results_analysis.stages || [];
  if (!stages.some(stage => stage.status === 'COLLECTED')) {
    const paused = overview.analysis_execution?.status === 'PAUSED_BY_USER';
    out.append(note(paused
      ? `이 회차의 Analysis 실행은 사용자 요청으로 일시 중지되었습니다. 결과는 아직 저장되지 않았습니다.${overview.analysis_execution.new_model_calls === 0 ? ' 분석 모델 신규 호출 0회입니다.' : ''}`
      : '이 회차의 Analysis 결과는 아직 저장되지 않았습니다. Evaluation의 진행 상태와 분리해 표시합니다.', 'info'));
  } else if (stages.some(stage => stage.status !== 'COLLECTED')) {
    out.append(note('저장된 Analysis 단계까지만 표시합니다. 아직 미완료인 단계의 결과나 해석을 앞선 단계에서 추정하지 않습니다.', 'info'));
  } else out.append(note('이 분석은 실행 전체의 고정된 대응 비교입니다. 왼쪽 검색은 문항 탐색에만 적용됩니다. 집계 → 대응 관계 → 근거 응답 순서로 읽으며, 문항 답변 가능성을 다시 판정하지 않습니다.', 'info'));
}
function resultResponse(id) { return resultResponseIndex.get(id); }
function openResultResponse(id) {
  const r = resultResponse(id); if (!r) return;
  const patch = Object.fromEntries([...FILTERS, 'metric', 'tags', 'paired', 'q', 'offset', 'case_offset'].map(k => [k, '']));
  navigate({ ...patch, tab: 'case', case: r.case, variant: r.variant, model: r.model, prompt: r.prompt_condition, reasoning: r.reasoning });
}
function resultLink(id, short = false) {
  const r = resultResponse(id);
  return r ? button(short ? r.case : `${r.case} · ${VARIANTS[r.variant]} · ${conditionName(r.prompt_condition, r.reasoning)}`, () => openResultResponse(id), 'text-button') : el('span', 'muted', '응답 미기록');
}
function resultPairEndpoint(endpoint) {
  if (!endpoint) return el('span', 'muted', '응답 없음');
  const cell = el('div', 'result-pair-response');
  const value = endpoint.answer === null ? 'null' : endpoint.answer === undefined ? '미기록' : String(endpoint.answer);
  const scale = resultResponse(endpoint.response_id)?.answer_scale;
  cell.append(el('strong', '', `반환값 ${value}${scale ? ` · ${scale}` : ''}`));
  if (endpoint.status !== 'VALID') cell.append(el('small', 'muted', '형식 통과 전 · 답 비교에서 제외'));
  else if (endpoint.classification && !String(endpoint.classification).startsWith('UNGUIDED_'))
    cell.append(el('small', 'muted', `모델 분류: ${RESULT_CLASS_NAMES[endpoint.classification] || endpoint.classification}`));
  if (resultResponse(endpoint.response_id)) cell.append(button('응답 상세 보기', () => openResultResponse(endpoint.response_id), 'text-button'));
  return cell;
}
const RESULT_CLASS_NAMES = { ANSWERABLE: '답 가능', CONFLICT: '정보 충돌', INSUFFICIENT_EVIDENCE: '근거 부족',
  UNRESOLVED: '의미 모호', ABSTAIN: '답변 유보', CLASSIFICATION_MISSING: '분류 미기록',
  UNGUIDED_NUMERIC: '숫자 답 · 분류 미요구', UNGUIDED_NULL: 'null 답 · 분류 미요구' };
function resultClassificationLabel(row) {
  return row?.classification ?? (row && promptKey(row.prompt_condition) === 'unguided' ? 'null · 분류 미요구 (Unguided)' : '분류 미기록');
}
const RESULT_CHOICE_NAMES = { A: '원문 기준값과 일치', B: '추가 주장 기준값과 일치', BOTH: '두 기준값 모두와 일치',
  OTHER: '기록된 기준값과 다른 숫자', ORIGINAL_VALUE: '원문 기준값과 일치',
  REFERENCE_MISSING: '원문 기준값 미기록', NULL: '답 없음', NON_NUMERIC: '숫자 아닌 답' };
const resultPercent = (count, denominator) => denominator ? `${(count / denominator * 100).toFixed(1)}%` : '—';
const resultShare = (count, denominator) => `${fmt(count)}건 (${resultPercent(count, denominator)})`;
const resultTransitionEntries = counts => Object.entries(counts || {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
const resultTransitionSides = value => String(value).split(' → ');
function resultAnswerChanges(group, showDelta) {
  const cell = el('div', 'result-answer-changes'), counts = group.viewer_answer_changes;
  if (!counts?.comparable) return el('span', 'muted', '비교 가능한 답 없음');
  const items = [
    ['numeric_same', '같은 숫자', 'same'], ['numeric_different', '다른 숫자', 'different'],
    ['numeric_to_null', '숫자 → 답 없음', 'to-null'], ['null_to_numeric', '답 없음 → 숫자', 'from-null'],
    ['null_same', '둘 다 답 없음', 'null-same'], ['scale_unmatched', '단위가 달라 숫자 비교 제외', 'excluded'],
    ['other', '답 값 비교 제외', 'excluded']
  ];
  for (const [key, label, kind] of items) if (counts[key]) {
    const chip = el('span', `result-answer-change ${kind}`);
    chip.append(el('span', '', label), el('strong', '', resultShare(counts[key], counts.comparable)));
    cell.append(chip);
  }
  if (showDelta) {
    const details = el('details', 'result-secondary-detail');
    details.append(el('summary', '', '숫자 증감·답 형태 비율 더 보기'), resultAnswerDelta(group)); cell.append(details);
  }
  return cell;
}
function resultClassificationChanges(group) {
  const cell = el('div', 'result-comparison-summary'), denominator = group.comparable_pairs;
  if (group.prompt_condition === 'unguided') return el('span', 'muted', '분류를 요청하지 않은 조건입니다.');
  const entries = resultTransitionEntries(group.classification_transitions);
  if (group.axis === 'PROMPT') {
    const guided = new Map();
    for (const [name, count] of entries) {
      const right = resultTransitionSides(name)[1];
      guided.set(right, (guided.get(right) || 0) + count);
    }
    const ranked = [...guided].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    cell.append(el('span', 'muted', 'Unguided에서는 분류를 요청하지 않았습니다.'));
    if (ranked.length) cell.append(el('strong', '', `Guided 최다 분류: ${RESULT_CLASS_NAMES[ranked[0][0]] || ranked[0][0]} ${resultShare(ranked[0][1], denominator)}`));
    if (ranked.length > 1) {
      const details = el('details', 'result-secondary-detail'); details.append(el('summary', '', 'Guided 분류 전체 보기'));
      for (const [name, count] of ranked) details.append(el('div', 'result-transition-row', `${RESULT_CLASS_NAMES[name] || name} · ${resultShare(count, denominator)}`));
      cell.append(details);
    }
    return cell;
  }
  if (!entries.length) return el('span', 'muted', '분류 기록 없음');
  const same = entries.reduce((n, [name, count]) => { const [left, right] = resultTransitionSides(name); return n + (left === right ? count : 0); }, 0);
  cell.append(el('strong', '', `분류 유지 ${resultShare(same, denominator)}`), el('span', '', `분류 달라짐 ${resultShare(denominator - same, denominator)}`));
  const details = el('details', 'result-secondary-detail'); details.append(el('summary', '', '어떤 분류였는지 보기'));
  for (const [name, count] of entries) {
    const [left, right] = resultTransitionSides(name);
    const description = left === right ? `양쪽 모두 ${RESULT_CLASS_NAMES[left] || left}` : `${RESULT_CLASS_NAMES[left] || left} → ${RESULT_CLASS_NAMES[right] || right}`;
    details.append(el('div', 'result-transition-row', `${description} · ${resultShare(count, denominator)}`));
  }
  cell.append(details); return cell;
}
function resultChoiceChanges(group) {
  const entries = resultTransitionEntries(group.choice_transitions), denominator = group.comparable_pairs;
  if (!entries.length) return el('span', 'muted', '기준값 비교 기록 없음');
  const phrase = name => {
    const [left, right] = resultTransitionSides(name);
    if (left === right) return `두 입력 모두 ${RESULT_CHOICE_NAMES[left] || left}`;
    return `${RESULT_CHOICE_NAMES[left] || left} → ${RESULT_CHOICE_NAMES[right] || right}`;
  };
  const cell = el('div', 'result-comparison-summary');
  cell.append(el('strong', '', `가장 많은 경우: ${phrase(entries[0][0])} · ${resultShare(entries[0][1], denominator)}`));
  if (entries.length > 1) {
    const details = el('details', 'result-secondary-detail'); details.append(el('summary', '', '다른 기준값 비교 보기'));
    for (const [name, count] of entries.slice(1)) details.append(el('div', 'result-transition-row', `${phrase(name)} · ${resultShare(count, denominator)}`));
    cell.append(details);
  }
  return cell;
}
const RESULT_NUMERIC_CHOICES = new Set(['A', 'B', 'BOTH', 'OTHER', 'ORIGINAL_VALUE', 'REFERENCE_MISSING']);
function resultPairGroupOrder(a, b) {
  const variantOrder = Object.keys(VARIANTS);
  const fixedOrder = group => {
    if (group.axis === 'PROMPT') return group.reasoning === 'off' ? 0 : group.reasoning === 'on' ? 1 : 2;
    if (group.axis === 'REASONING') return group.prompt_condition === 'unguided' ? 0 : group.prompt_condition === 'guided' ? 1 : 2;
    const index = RESULT_CONDITIONS.findIndex(([prompt, reasoning]) => group.prompt_condition === prompt && group.reasoning === reasoning);
    return index < 0 ? RESULT_CONDITIONS.length : index;
  };
  return a.model.localeCompare(b.model) || variantOrder.indexOf(a.variant) - variantOrder.indexOf(b.variant) || fixedOrder(a) - fixedOrder(b);
}
function resultValueMovement(group) {
  const counts = group.viewer_delta ? { up: group.viewer_delta.up, down: group.viewer_delta.down, same: group.viewer_delta.same,
    differentScale: group.viewer_delta.different_scale, invalid: group.viewer_delta.invalid }
    : { up: 0, down: 0, same: 0, differentScale: 0, invalid: 0 };
  for (const pair of group.viewer_delta ? [] : group.pairs || []) {
    if (!pair.format_comparable || !RESULT_NUMERIC_CHOICES.has(pair.left.choice) || !RESULT_NUMERIC_CHOICES.has(pair.right.choice)) continue;
    const leftScale = resultResponse(pair.left.response_id)?.answer_scale, rightScale = resultResponse(pair.right.response_id)?.answer_scale;
    if (!leftScale || leftScale !== rightScale) { counts.differentScale++; continue; }
    const numberValue = value => typeof value === 'number' ? value : typeof value === 'string' && value.trim() ? Number(value) : NaN;
    const before = numberValue(pair.left.answer), after = numberValue(pair.right.answer);
    if (!Number.isFinite(before) || !Number.isFinite(after) || (Number.isInteger(before) && !Number.isSafeInteger(before)) || (Number.isInteger(after) && !Number.isSafeInteger(after))) { counts.invalid++; continue; }
    counts[after > before ? 'up' : after < before ? 'down' : 'same']++;
  }
  const compared = counts.up + counts.down + counts.same, line = el('div', 'result-value-movement');
  line.append(el('span', 'result-value-label', `반환 숫자값 · ${compared}쌍`));
  if (compared) {
    line.append(el('strong', 'result-value-up', `▲ ${counts.up}`), el('strong', 'result-value-down', `▼ ${counts.down}`), el('strong', 'result-value-same', `= ${counts.same}`));
  }
  if (counts.differentScale || counts.invalid) line.append(el('small', 'muted', `단위 다름·값 비교 불가 ${counts.differentScale + counts.invalid}쌍 제외`));
  return line;
}
function resultAnswerDelta(group) {
  const pairs = group.viewer_delta ? [] : (group.pairs || []).filter(pair => pair.format_comparable);
  const denominator = group.viewer_delta?.comparable ?? pairs.length;
  if (!denominator) return el('span', 'muted', '비교 가능한 쌍 없음');
  const counts = side => ({
    numeric: group.viewer_delta ? group.viewer_delta[`numeric_${side === 'left' ? 'before' : 'after'}`] : pairs.filter(pair => RESULT_NUMERIC_CHOICES.has(pair[side].choice)).length,
    null: group.viewer_delta ? group.viewer_delta[`null_${side === 'left' ? 'before' : 'after'}`] : pairs.filter(pair => pair[side].choice === 'NULL').length,
  });
  const before = counts('left'), after = counts('right'), content = el('div', 'result-answer-deltas');
  content.append(resultValueMovement(group));
  for (const [key, label] of [['numeric', '숫자 답'], ['null', 'null 답']]) {
    const difference = after[key] - before[key], rate = Math.abs(difference * 100 / denominator).toLocaleString('ko-KR', { maximumFractionDigits: 1 });
    const line = el('div', 'result-answer-delta');
    line.append(el('span', 'result-delta-count', `${label} ${before[key]} → ${after[key]}`));
    line.append(el('strong', `result-delta ${difference > 0 ? 'up' : difference < 0 ? 'down' : 'flat'}`, difference > 0 ? `▲ +${difference}건 · +${rate}%p` : difference < 0 ? `▼ ${difference}건 · -${rate}%p` : '— 0건 · 0%p'));
    content.append(line);
  }
  return content;
}
function renderAnalysisTiming(data) {
  const panel = section('Analysis 처리 시간', '저장된 시간 기록입니다. 화면 새로 읽기로 최신 기록을 확인합니다.');
  const seconds = value => value == null ? '미측정' : value < 60 ? `${value.toFixed(2)}초` : `${(value / 60).toFixed(1)}분`;
  const bottleneck = data.bottleneck;
  panel.append(note(bottleneck ? `${bottleneck.provisional ? '진행 중 잠정 병목' : '측정된 최대 소요 단계'}: ${bottleneck.label} · Analysis 단계 시간의 ${(bottleneck.share_of_measured_analysis_steps * 100).toFixed(1)}%` : 'Analysis 시작 전입니다. 기존 Evaluation 수집 시간부터 기록합니다.'));
  const internal = new Set(['model_call', 'state_persistence', 'codex_auth']);
  panel.append(table(['단계', '경과 시간', '완료 횟수', '진행 중'], data.steps.filter(row => !internal.has(row.step)).map(row =>
    [row.label, seconds(row.occupied_wall_seconds), fmt(row.completed), fmt(row.running)])));
  const calls = data.steps.filter(row => internal.has(row.step));
  if (calls.length) panel.append(table(['내부 처리', '경과 시간', '종료 / 진행', '중앙값', '95백분위', '최대'], calls.map(row =>
    [`${row.label}${row.stage ? ` · ${row.stage}` : ''}`, seconds(row.occupied_wall_seconds), `${fmt(row.completed)} / ${fmt(row.running)}`, seconds(row.p50_seconds), seconds(row.p95_seconds), seconds(row.max_seconds)])));
  panel.append(el('p', 'small muted', `기록 시각 ${new Date(data.updated_at).toLocaleString()} · 측정된 실행 구간의 누적 시간이며 실행기 종료 후 재개까지의 공백은 제외합니다. 상위 단계와 내부 처리는 겹치므로 합산하지 않습니다. 병렬 호출도 겹친 구간을 한 번만 셉니다. 호출 중앙값에는 실패·거절 시도도 포함됩니다. 모델 호출에는 네트워크·제공자 대기가 포함되며 내부 추론 시간은 따로 확인되지 않습니다.`));
  return panel;
}
function renderAnalysisScheduler(data) {
  const panel = section('Codex 동시 호출', '현재 실행기의 한도와 전체 CPU 측정값입니다.');
  const adaptive = data.policy?.adaptive, cpu = data.last_cpu_sample?.cpu_percent;
  panel.append(table(['동시 호출 한도', '실행 중', '대기', '누적 실패', '전체 CPU 평균', '상태'], [[
    `${fmt(data.current_limit)}건`, `${fmt(data.active_calls)}건`, `${fmt(data.queued_calls)}건`,
    data.deferred_failure_count == null ? '미기록' : `${fmt(data.deferred_failure_count)}건`,
    cpu == null ? '측정 대기 / 미확인' : `${cpu.toFixed(1)}%`, data.status]]));
  panel.append(note(adaptive?.enabled
    ? `${adaptive.interval_seconds}초마다 CPU가 ${adaptive.cpu_threshold_percent}% 이하이면 ${adaptive.growth_percent}%씩 증가합니다. 정수로 올림하며 남은 요청 수까지만 증가합니다. 초과·측정 실패 시 현재 한도를 유지합니다.`
    : '동시 호출 수를 고정하여 진행합니다.'));
  panel.append(el('p', 'small muted', `기록 시각 ${new Date(data.updated_at).toLocaleString()} · CPU는 이 컴퓨터 전체의 사용률입니다. 제공자의 처리 여유를 뜻하지 않습니다.`));
  return panel;
}
function renderResultCollection() {
  const out = el('div'), data = overview.results_analysis, c = data.comparisons;
  resultScope(out);
  if (data.scheduler) out.append(renderAnalysisScheduler(data.scheduler));
  if (data.timing) out.append(renderAnalysisTiming(data.timing));
  const saved = data.responses || [], stage = data.stages?.[0], collected = stage?.status === 'COLLECTED';
  const n = c?.overall ?? { planned: stage?.planned ?? overview.planned, format_valid: stage?.statuses?.VALID ?? null,
    numeric: saved.length ? saved.filter(r => typeof r.answer === 'number').length : null,
    null: saved.length ? saved.filter(r => r.answer === null).length : null };
  const cards = el('div', 'result-kpis');
  for (const [title, value, description] of [[collected ? '전체 응답' : '계획 요청', n.planned, collected ? `${fmt(overview.originals)}원본 · 원본 포함 ${Object.keys(VARIANTS).length}유형 · 4조건` : 'A01 응답 취합은 아직 저장되지 않음'], ['형식 통과', n.format_valid, '내용의 타당성과는 별도'], ['숫자 답', n.numeric, 'answer에 반환한 값'], ['null', n.null, '분류·설명을 함께 읽습니다']]) {
    const card = el('div', 'panel result-kpi'); card.append(el('p', 'small', title), el('strong', '', fmt(value)), el('p', 'small muted', description)); cards.append(card);
  }
  out.append(cards);
  const source = overview.evaluation_reuse?.source_run;
  const flow = section('이 회차의 단계', source ? `${source}의 Evaluation을 재사용합니다. 두 회차를 별도 실험 표본으로 합산하지 않습니다.` : '이 회차에 저장된 Evaluation과 Analysis를 단계별로 구분합니다.');
  flow.append(table(['단계', '이번 처리', '현재 상태'], [['Evaluation', source ? `${source}의 입력·요청·응답·검사 재사용` : '이 회차의 입력·요청·응답·검사', label(overview.status)], ['A01 결과 취합', collected ? `${fmt(n.planned)}응답의 저장 결과 연결` : `${fmt(n.planned)}건 계획 · A01 응답 미수집`, resultStageProgress(stage, '미실행 · 응답 미수집')], ['A02 관계 비교', '동일 조건 짝비교 + 응답 근거 해석', resultStageProgress(data.stages?.[1])], ['A03 연구 해석', '관찰·대안·한계·개선 토의', resultStageProgress(data.stages?.[2])]])); out.append(flow);
  if (!c?.overall || !Array.isArray(c.matrix)) { out.append(note(collected ? 'A02 대응 집계가 아직 저장되지 않았습니다. A01에 저장된 값만 위에 표시합니다.' : 'A01 응답 취합이 아직 저장되지 않았습니다. 위 계획 요청 수는 응답 수가 아닙니다.', 'info')); return out; }
  const originalCells = c.matrix.filter(x => x.variant === 'ORIGINAL');
  const originals = section(`원본의 기존 숫자 비교 · ${fmt(originalCells.reduce((total, cell) => total + cell.planned, 0))}응답`, `미평가 null을 불일치에 섞지 않습니다. 원본 ${fmt(overview.originals)}개에 각 조건을 연결합니다.`);
  originals.append(table(['조건', '숫자 일치', '숫자 불일치', '미평가', '전체'], originalCells.map(x => [conditionName(x.prompt_condition, x.reasoning), x.original_results.MATCH || 0, x.original_results.MISMATCH || 0, x.original_results.UNEVALUATED || 0, x.planned])));
  const unusual = data.responses.filter(r => r.variant === 'ORIGINAL' && r.original_result !== 'MATCH');
  const unusualCells = r => [resultLink(r.response_id, true), conditionName(r.prompt_condition, r.reasoning), show(r.answer), resultClassificationLabel(r), RESULT_BASELINES[r.original_result]];
  originals.append(unusual.length > 50 ? resultPagedDetails(`불일치·미평가 원본 응답 ${unusual.length}건 보기`, ['원본 응답', '조건', '모델 답', 'classification', '기존 숫자 비교'], unusual, unusualCells)
    : table(['원본 응답', '조건', '모델 답', 'classification', '기존 숫자 비교'], unusual.map(unusualCells))); out.append(originals);
  const distribution = section('모델이 반환한 classification', 'Unguided의 null 분류는 지시된 형식입니다. 분석자가 임의의 분류를 채우지 않았습니다.');
  const order = new Map(RESULT_CLASSIFICATION_ORDER.map((name, index) => [name, index]));
  const rank = name => order.get(name) ?? RESULT_CLASSIFICATION_ORDER.length;
  const classifications = Object.entries(n.classifications).sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b));
  distribution.append(table(['반환 분류 또는 Unguided 답 형태', '응답 수'], classifications));
  distribution.append(button('A02 · 유형 × 4조건과 대응 비교 →', () => navigate({ tab: 'conditions' }))); out.append(distribution); return out;
}
function resultScatter(profiles) {
  const aggregated = profiles.length > 400;
  const panel = section('원본 결과 × 변형 null 수', aggregated
    ? '큰 회차는 같은 원본 결과·null 개수·풀이/추론 조건을 묶어 건수를 표시합니다. 원을 누르면 해당 문항을 50개씩 펼쳐 볼 수 있습니다.'
    : '점 하나는 원본 1개·풀이/추론 조건 1개입니다. 세로 위치는 실제 null 개수(0–7)이며, 겹치는 점은 가로로만 벌렸습니다. 점을 누르면 문항을 엽니다.');
  const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 850 310'); svg.classList.add('result-scatter'); svg.setAttribute('role', 'group'); svg.setAttribute('aria-label', '원본 숫자 비교와 일곱 변형의 null 응답 수 산점도');
  function shape(tag, attrs, text) { const n = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text !== undefined) n.textContent = text; return n; }
  const categories = ['MATCH', 'MISMATCH', 'UNEVALUATED', 'ORIGINAL_MISSING'], colors = ['#967c62', '#328c89', '#b56843', '#69528c'];
  for (let y = 0; y <= 7; y++) { const py = 260 - y * 30; svg.append(shape('line', { x1: 50, y1: py, x2: 810, y2: py, stroke: '#e4dbce' }), shape('text', { x: 35, y: py + 4, 'text-anchor': 'end', fill: '#776451', 'font-size': 12 }, y)); }
  categories.forEach((k, i) => svg.append(shape('text', { x: 145 + i * 190, y: 295, 'text-anchor': 'middle', fill: '#5b422c', 'font-size': 13 }, RESULT_BASELINES[k])));
  const buckets = new Map(), selectedBucket = el('div', 'result-scatter-selection');
  for (const profile of profiles) {
    const key = `${profile.baseline_result}:${profile.variants.null}${aggregated ? `:${profile.prompt_condition}:${profile.reasoning}` : ''}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(profile);
  }
  const profileCells = r => [resultLink(r.original_response_id, true), conditionName(r.prompt_condition, r.reasoning), RESULT_BASELINES[r.baseline_result], r.variants.numeric, r.variants.null, r.variants.planned];
  if (aggregated) {
    for (const group of buckets.values()) {
      const first = group[0], col = categories.indexOf(first.baseline_result);
      const ci = RESULT_CONDITIONS.findIndex(([p, t]) => p === first.prompt_condition && t === first.reasoning);
      if (col < 0 || ci < 0) continue;
      const x = 145 + col * 190 + (ci - 1.5) * 27, y = 260 - first.variants.null * 30;
      const title = `${conditionName(first.prompt_condition, first.reasoning)} · ${RESULT_BASELINES[first.baseline_result]} · 변형 null ${first.variants.null}개 · ${group.length}문항`;
      const point = shape('circle', { cx: x, cy: y, r: Math.min(17, 7 + Math.sqrt(group.length)), fill: colors[ci], stroke: '#fff', 'stroke-width': 1, tabindex: 0, role: 'button' });
      const openGroup = () => { const detail = resultPagedDetails(`${title} · 근거 문항 보기`, ['원본', '조건', '원본 결과', '변형 숫자', '변형 null', '변형 전체'], group, profileCells); selectedBucket.replaceChildren(detail); detail.open = true; detail.scrollIntoView({ block: 'nearest' }); };
      point.setAttribute('aria-label', title); point.append(shape('title', {}, title)); point.addEventListener('click', openGroup);
      point.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openGroup(); } }); svg.append(point);
      svg.append(shape('text', { x, y: y + 3, 'text-anchor': 'middle', fill: '#fff', 'font-size': 9, 'pointer-events': 'none' }, group.length));
    }
  } else {
    const positions = new Map();
    for (const group of buckets.values()) {
      group.sort((a, b) => a.case.localeCompare(b.case) || a.prompt_condition.localeCompare(b.prompt_condition) || a.reasoning.localeCompare(b.reasoning));
      const gap = Math.min(12, 130 / Math.max(1, group.length - 1));
      group.forEach((profile, index) => positions.set(profile.original_response_id, (index - (group.length - 1) / 2) * gap));
    }
    for (const r of profiles) {
      const col = categories.indexOf(r.baseline_result), ci = RESULT_CONDITIONS.findIndex(([p, t]) => p === r.prompt_condition && t === r.reasoning);
      if (col < 0 || ci < 0) continue;
      const point = shape('circle', { cx: 145 + col * 190 + positions.get(r.original_response_id), cy: 260 - r.variants.null * 30, r: 5, fill: colors[ci], stroke: '#fff', 'stroke-width': 1, tabindex: 0, role: 'button' });
      const title = `${r.case} · ${conditionName(r.prompt_condition, r.reasoning)} · ${RESULT_BASELINES[r.baseline_result]} · 변형 null ${r.variants.null}/${r.variants.planned}`;
      point.setAttribute('aria-label', title); point.append(shape('title', {}, title)); point.addEventListener('click', () => openResultResponse(r.original_response_id)); point.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openResultResponse(r.original_response_id); } }); svg.append(point);
    }
  }
  panel.append(svg);
  const legend = el('div', 'result-legend'); RESULT_CONDITIONS.forEach(([p, t], i) => { const item = el('span', `result-series series-${i}`, conditionName(p, t)); legend.append(item); }); panel.append(legend);
  panel.append(selectedBucket, resultPagedDetails(`산점도 원자료 ${profiles.length}행 보기`, ['원본', '조건', '원본 결과', '변형 숫자', '변형 null', '변형 전체'], profiles, profileCells)); return panel;
}
async function renderSourceTypeRelationships(out, files, index) {
  const selected = index.types.find(item => item.source_type === state.source_type);
  const controls = section('원천 유형별 관계 비교', '동일한 완료 실험의 저장 응답을 원천 계보별로 나눕니다. 유형마다 분모가 다르며 유형 이름은 독립 벤치마크 점수가 아닙니다.');
  const chooser = el('label', 'source-type-picker', '원천 유형');
  chooser.append(select([['', `전체 · ${fmt(index.types.reduce((total, item) => total + item.case_count, 0))}문항`],
    ...index.types.map(item => [item.source_type, `${item.source_type} · ${fmt(item.case_count)}문항`])],
    selected?.source_type || '', value => navigate({ source_type: value })));
  controls.append(chooser); out.append(controls);
  if (!selected) return false;
  const summaryFile = files.find(file => file.path === `${selected.folder}/summary.json`);
  if (!summaryFile) { out.append(note('선택한 유형의 집계 파일이 없습니다.', 'danger')); return true; }
  const summary = JSON.parse((await get(api('file', { id: summaryFile.id }))).content);
  if (summary.source_type !== selected.source_type || summary.case_ids?.length !== selected.case_count) {
    out.append(note('유형별 문항 수가 색인과 다릅니다. 집계를 표시하지 않습니다.', 'danger')); return true;
  }
  out.append(note(`${summary.source_type} 원본 ${fmt(summary.case_count)}문항 · 응답 ${fmt(summary.response_count)}건 · A02 관찰 ${fmt(summary.a02_observation_count)}개. 이 화면의 모든 분모는 선택한 유형만 사용합니다.`, 'info'));
  const composition = section('이 유형의 문항 구성', '제작 당시 외부지식 사용 표기는 원본 제작 기록입니다. 모델 답변에 실제로 외부지식이 쓰였다는 뜻이 아닙니다.');
  composition.append(table(['상위 계보', '난도', '제작 당시 외부지식 사용 표기', '형식 상태'], [[
    summary.dataset_labels.join(', '), Object.entries(summary.levels).map(([key, value]) => `${key} ${fmt(value)}`).join(' · '),
    `사용 ${fmt(summary.original_external_knowledge.true)} · 미사용 ${fmt(summary.original_external_knowledge.false)}`,
    Object.entries(summary.response_status).map(([key, value]) => `${label(key)} ${fmt(value)}`).join(' · ')
  ]])); out.append(composition);
  const model = overview.models[0]?.key || 'luna-api';
  const caseButton = (caseId, variant = 'ORIGINAL', prompt = 'guided', reasoning = 'on') => button(caseId, () => navigate({
    tab: 'case', case: caseId, variant, prompt, reasoning, model,
    q: '', offset: '', case_offset: '', comparison_offset: '', metric: '', tags: '', paired: ''
  }), 'text-button');
  const baseline = section('원본의 저장된 숫자 비교', 'MATCH는 참조 숫자와의 일치입니다. 미평가와 형식 실패를 불일치로 합치지 않습니다.');
  baseline.append(table(['풀이·추론 설정', 'MATCH', 'MISMATCH', '미평가', '전체'], RESULT_CONDITIONS.map(([prompt, reasoning]) => {
    const m = summary.conditions.ORIGINAL[`${prompt}/${reasoning}`];
    return [conditionName(prompt, reasoning), fmt(m.original_result.MATCH || 0), fmt(m.original_result.MISMATCH || 0),
      fmt(m.original_result.UNEVALUATED || 0), fmt(m.planned)];
  }))); out.append(baseline);
  const matrix = section(`${summary.source_type} · 8변형 × 4조건`, '각 칸은 숫자 답 · null 답 · 형식 미통과를 별도로 셉니다. 목록에서 문항을 누르면 같은 조건의 실제 응답으로 이동합니다.');
  const rows = Object.keys(VARIANTS).map(variant => [VARIANTS[variant], ...RESULT_CONDITIONS.map(([prompt, reasoning]) => {
    const m = summary.conditions[variant][`${prompt}/${reasoning}`];
    const cell = el('div', 'result-matrix-cell');
    cell.append(el('strong', '', `숫자 ${fmt(m.numeric_answer)}/${fmt(m.planned)} · null ${fmt(m.null_answer)}/${fmt(m.planned)} · 형식 미통과 ${fmt(m.format_failed_case_ids.length)}`));
    for (const [title, ids] of [['숫자', m.numeric_case_ids], ['null', m.null_case_ids], ['형식 미통과', m.format_failed_case_ids]]) {
      if (ids.length) cell.append(resultPagedDetails(`${title} ${fmt(ids.length)}문항 보기`, ['문항'], ids,
        caseId => [caseButton(caseId, variant, prompt, reasoning)]));
    }
    return cell;
  })]);
  const matrixTable = table(['변형', ...RESULT_CONDITIONS.map(([prompt, reasoning]) => conditionName(prompt, reasoning))], rows);
  matrixTable.classList.add('result-matrix-table'); matrix.append(matrixTable); out.append(matrix);
  const cases = section('원본 문항 바로 열기', '유형에 속한 문항 전체를 50개씩 펼칩니다.');
  cases.append(resultPagedDetails(`${summary.source_type} 원본 ${fmt(summary.case_ids.length)}문항 보기`, ['문항'], summary.case_ids,
    caseId => [caseButton(caseId)])); out.append(cases);
  const observations = section('문항별 관찰과 연구 질문', 'A02에서 저장한 관찰을 유형별로 셌습니다. 아래 문장은 각 범주의 앞쪽 사례이며 대표 표본은 아닙니다. 전체 A03 주제의 주장을 유형별로 재검증한 결과도 아닙니다.');
  for (const [category, count] of Object.entries(summary.a02_categories)) {
    const block = el('details'); block.append(el('summary', '', `${RESULT_CATEGORIES[category] || category} · ${fmt(count)}개 관찰`));
    for (const item of summary.a02_examples[category] || []) {
      const article = el('article', 'result-observation');
      article.append(el('h5', '', `${item.id} · ${item.title_ko}`), el('p', '', item.observation_ko),
        el('p', 'small muted', `한계: ${item.limitation_ko}`)); block.append(article);
    }
    observations.append(block);
  }
  observations.append(table(['질문', '전체 A03 주제', '이 유형에 속한 연결 관찰 ID'], Object.entries(summary.linked_a03_observations_by_group)
    .map(([id, item]) => [item.question_id, `${id} · ${item.title_ko}`, fmt(item.observation_count)])));
  out.append(observations);
  return true;
}
function featureArrow(direction) {
  const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 72 36'); svg.setAttribute('aria-hidden', 'true');
  const paths = direction === '↑' ? ['M36 31 L36 6', 'M27 15 L36 6 L45 15']
    : direction === '→' ? ['M4 18 L65 18', 'M55 9 L65 18 L55 27']
      : ['M5 31 L62 5', 'M48 4 L62 5 L56 18'];
  for (const path of paths) {
    const line = document.createElementNS(ns, 'path'); line.setAttribute('d', path);
    line.setAttribute('fill', 'none'); line.setAttribute('stroke', 'currentColor');
    line.setAttribute('stroke-linecap', 'round'); line.setAttribute('stroke-linejoin', 'round');
    svg.append(line);
  }
  return svg;
}
function renderFeatureQuadrantSample(matrix, model) {
  const data = buildFeatureQuadrant(matrix, model, 'IC_VALUE_01_BEFORE');
  if (data.status === 'MISSING') return null;
  const panel = section(`${model} · IC-value 앞 · 네 조건 사분면`, '샘플 · 왼쪽은 풀이 기준 미제시, 오른쪽은 기준 제시 · 아래는 Reasoning OFF, 위는 ON. 출발점은 왼쪽 아래입니다.');
  panel.classList.add('feature-quadrant-panel');
  if (data.status !== 'READY') {
    panel.append(note(data.status === 'PENDING' ? '네 조건 중 Evaluation 미실행·처리 중·응답 미확인 기록이 남아 있습니다. 모든 요청의 종료 상태가 확인되면 비율과 화살표를 표시합니다.' : '저장된 후보 분류 합계가 계획 건수와 달라 사분면을 표시하지 않습니다.', 'danger'));
    return panel;
  }
  const baseline = data.cells[0], target = data.cells.find(cell => cell.key === data.largest.target);
  const largestChoice = data.choices.find(choice => choice.key === data.largest.choice);
  const singleChange = data.largestSingle;
  const singleChoice = data.choices.find(choice => choice.key === singleChange.choice);
  const singleTarget = data.cells.find(cell => cell.key === singleChange.target);
  const signed = value => `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(1)}`;
  const share = (count, total) => `${fmt(count)}/${fmt(total)} · ${(100 * count / total).toFixed(1)}%`;
  const lead = el('div', 'feature-quadrant-lead');
  lead.append(el('strong', '', `가장 큰 비율 변화 · ${largestChoice.label}`),
    el('span', '', `${share(data.largest.before, baseline.planned)} → ${share(data.largest.after, target.planned)} · ${signed(data.largest.deltaPp)}%p`),
    el('small', '', `Unguided·OFF → ${target.label}. 저장된 두 조건의 비율 차이이며, 대각선은 두 설정이 함께 달라집니다.`),
    el('small', '', `한 설정만 변경한 비교 중 최대: ${singleTarget.label}의 ${singleChoice.label} ${signed(singleChange.deltaPp)}%p`));
  panel.append(lead);
  const grid = el('div', 'feature-quadrant-grid');
  for (const key of ['unguided/on', 'guided/on', 'unguided/off', 'guided/off']) {
    const cell = data.cells.find(item => item.key === key), box = el('article', `feature-quadrant-cell${key === baseline.key ? ' baseline' : ''}`);
    const header = el('div', 'feature-quadrant-cell-head');
    header.append(el('h4', '', cell.label), el('span', '', key === baseline.key ? '출발점' : cell.direction));
    box.append(header, el('p', 'small muted', `전체 요청 ${fmt(cell.planned)}건 · 형식·실행 실패 포함`));
    const bar = el('div', 'feature-quadrant-stacked');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', `${cell.label}: ${data.choices.map(choice => `${choice.label} ${cell.counts[choice.key]}건`).join(', ')}`);
    for (const choice of data.choices) {
      const count = cell.counts[choice.key]; if (!count) continue;
      const segment = el('span'); segment.style.width = `${100 * count / cell.planned}%`;
      segment.style.backgroundColor = choice.color; segment.title = `${choice.label} · ${share(count, cell.planned)}`;
      bar.append(segment);
    }
    box.append(bar);
    const list = el('div', 'feature-quadrant-values');
    for (const choice of data.choices) {
      const row = el('div', 'feature-quadrant-value'); row.style.setProperty('--feature-color', choice.color);
      row.append(el('span', 'feature-quadrant-value-name', choice.label),
        el('strong', '', share(cell.counts[choice.key], cell.planned)));
      list.append(row);
    }
    box.append(list);
    if (key !== baseline.key) {
      const biggest = data.changes.filter(change => change.target === key)
        .reduce((best, change) => !best || Math.abs(change.deltaPp) > Math.abs(best.deltaPp) ? change : best, null);
      const choice = data.choices.find(item => item.key === biggest.choice);
      const indicator = el('div', `feature-quadrant-change feature-quadrant-card-arrow band-${biggest.band}${biggest === data.largest ? ' largest' : ''}`);
      indicator.style.setProperty('--feature-color', choice.color);
      indicator.setAttribute('aria-label', `출발점에서 ${cell.label}: 가장 큰 변화는 ${choice.label}, ${signed(biggest.deltaPp)} 퍼센트포인트`);
      indicator.append(featureArrow(cell.direction), el('span', '', `${choice.label} ${signed(biggest.deltaPp)}%p`));
      box.append(indicator);
    }
    grid.append(box);
  }
  panel.append(grid);
  const changes = el('div', 'feature-quadrant-changes');
  changes.append(el('h4', '', '출발점에서 어느 조건으로 얼마나 달라졌나요?'),
    el('p', 'small muted', '각 화살표는 같은 후보 분류의 비율 차이입니다. ↑ 추론 ON · → 기준 제시 · ↗ 두 설정 모두 변경. 굵기와 색 농도는 차이의 절댓값을 나타냅니다.'));
  const headings = el('div', 'feature-quadrant-change-head');
  headings.append(el('span', '', '반환 형태'), ...data.cells.slice(1).map(cell => el('span', '', `${cell.direction} ${cell.label}`)));
  changes.append(headings);
  for (const choice of data.choices) {
    const row = el('div', 'feature-quadrant-change-row'); row.style.setProperty('--feature-color', choice.color);
    row.append(el('strong', 'feature-quadrant-change-label', choice.label));
    for (const targetCell of data.cells.slice(1)) {
      const change = data.changes.find(item => item.choice === choice.key && item.target === targetCell.key);
      const isLargest = change === data.largest;
      const cell = el('div', `feature-quadrant-change band-${change.band}${isLargest ? ' largest' : ''}`);
      cell.setAttribute('aria-label', `${isLargest ? '가장 큰 변화, ' : ''}${choice.label}, ${targetCell.label}, ${signed(change.deltaPp)} 퍼센트포인트, ${change.after - change.before}건`);
      cell.append(featureArrow(targetCell.direction), el('span', '', `${signed(change.deltaPp)}%p`),
        el('small', '', `${change.after - change.before > 0 ? '+' : ''}${fmt(change.after - change.before)}건`));
      row.append(cell);
    }
    changes.append(row);
  }
  panel.append(changes, el('p', 'small muted feature-quadrant-legend', '화살표 기준: 10%p 미만 얇게 · 10%p 이상 중간 · 25%p 이상 굵게 · 50%p 이상 가장 굵게. A/B는 저장된 후보 숫자와의 일치이며 정답·근거 사용 판정이 아닙니다. null의 적절성도 별도 해석이 필요합니다. ↗은 두 설정이 함께 달라져 단일 요인의 효과로 읽지 않습니다.'));
  return panel;
}
async function renderResultRelationships() {
  const out = el('div'), data = overview.results_analysis, c = data.comparisons;
  out.append(renderAssessmentSummary(data, { variantNames: VARIANTS, conditionName, models: overview.models, openValue }));
  const documents = await get(api('documents'));
  const indexFile = documents.files.find(file => file.path === '02_analysis/source-types/source-type-index.json');
  if (indexFile) {
    const index = JSON.parse((await get(api('file', { id: indexFile.id }))).content);
    if (await renderSourceTypeRelationships(out, documents.files, index)) return out;
  }
  resultScope(out); if (!c || !Array.isArray(c.matrix) || !Array.isArray(c.case_profiles) || !Array.isArray(c.original_groups) || !Array.isArray(c.paired_groups)) { out.append(empty('A02 대응 집계가 아직 저장되지 않았습니다.')); return out; }
  for (const model of overview.models) {
    const featureSample = renderFeatureQuadrantSample(c.matrix, model.key);
    if (featureSample) out.append(featureSample);
    const matrix = section(`${model.key} · ${Object.keys(VARIANTS).length}유형 × 4조건`, '각 칸은 해당 조건에 저장된 응답입니다. %의 분모는 그 칸에 계획된 응답 수입니다. 숫자/null과 모델의 분류를 표시하며, 변형에 새 정오 판정을 붙이지 않습니다.');
    const matrixTable = table(['유형', ...RESULT_CONDITIONS.map(([p, t]) => conditionName(p, t))], Object.keys(VARIANTS).map(v => [VARIANTS[v], ...RESULT_CONDITIONS.map(([p, t]) => {
      const m = c.matrix.find(x => x.model === model.key && x.variant === v && x.prompt_condition === p && x.reasoning === t);
      if (!m) return '미기록';
      const cell = el('div', 'result-matrix-cell'); cell.append(el('strong', '', `숫자 ${resultShare(m.numeric, m.planned)} · null ${resultShare(m.null, m.planned)}`));
      for (const [k, n] of Object.entries(m.classifications)) cell.append(el('span', `result-class class-${k.toLowerCase()}`, `${RESULT_CLASS_NAMES[k] || k} ${resultShare(n, m.planned)}`));
      if (v === 'ORIGINAL') cell.append(el('small', '', `일치 ${m.original_results.MATCH || 0} · 불일치 ${m.original_results.MISMATCH || 0} · 미평가 ${m.original_results.UNEVALUATED || 0}`));
      cell.append(resultPagedDetails(`${m.planned}개 응답 열기`, ['문항'], m.response_ids || [], id => [resultLink(id, true)])); return cell;
    })])); matrixTable.classList.add('result-matrix-table'); matrix.append(matrixTable); out.append(matrix);
    out.append(resultScatter(c.case_profiles.filter(p => p.model === model.key)));
  }
  const baselines = section('원본 결과별로 변형 응답을 묶어 보기', '원본 수의 %는 같은 모델·풀이·추론 조건의 전체 문항 대비입니다. 변형 숫자/null의 %는 해당 행의 변형 전체 대비이며, 숫자 응답이 정답이라는 뜻은 아닙니다.');
  const originalGroups = c.original_groups.filter(g => g.baseline_result !== 'ORIGINAL_MISSING' || g.original_count);
  const originalTotals = new Map();
  for (const group of c.original_groups) {
    const key = `${group.model}:${group.prompt_condition}:${group.reasoning}`;
    originalTotals.set(key, (originalTotals.get(key) || 0) + group.original_count);
  }
  const groupedTable = table(['조건', '원본군', '원본 수', '변형 숫자', '변형 null', '변형 전체'], originalGroups.map(g => [
    conditionName(g.prompt_condition, g.reasoning), RESULT_BASELINES[g.baseline_result],
    resultShare(g.original_count, originalTotals.get(`${g.model}:${g.prompt_condition}:${g.reasoning}`)),
    resultShare(g.numeric, g.planned), resultShare(g.null, g.planned), fmt(g.planned)
  ]));
  groupedTable.classList.add('result-original-groups');
  const groupRows = [...groupedTable.querySelectorAll('tbody tr')];
  for (let start = 0, groupIndex = 0; start < originalGroups.length; groupIndex++) {
    const first = originalGroups[start];
    let end = start + 1;
    while (end < originalGroups.length && originalGroups[end].model === first.model && originalGroups[end].prompt_condition === first.prompt_condition && originalGroups[end].reasoning === first.reasoning) end++;
    for (let index = start; index < end; index++) groupRows[index].classList.add(groupIndex % 2 ? 'result-group-alt' : 'result-group-base');
    groupRows[start].classList.add('result-group-start');
    groupRows[start].cells[0].rowSpan = end - start;
    groupRows[start].cells[0].classList.add('result-group-label');
    for (let index = start + 1; index < end; index++) groupRows[index].cells[0].remove();
    start = end;
  }
  baselines.append(groupedTable); out.append(baselines);
  out.append(note('아래는 같은 문항의 두 응답을 짝지어 비교합니다. 화살표는 첫 입력의 응답 → 둘째 입력의 응답이며 시간 순서나 정오 판정이 아닙니다. 각 %의 분모는 양쪽 모두 형식을 통과한 비교 가능 문항이고, 숫자값은 단위가 같을 때만 비교합니다. “원문 기준값”은 저장된 원본 답, “추가 주장 기준값”은 저장된 대안 답입니다. “기준값과 다른 숫자”는 저장된 기준값 어느 것과도 일치하지 않는 경우입니다. 기준값과 일치해도 모델의 계산 경로나 답의 타당성이 확인된 것은 아닙니다.', 'info'));
  const axes = {
    VALUE_POSITION: { title: '추가 숫자 문장을 원문 앞/뒤로 옮기면 답이 달라지나요?',
      purpose: '같은 문항·모델·풀이·추론 조건에서 추가 숫자 문장은 그대로 두고, 01에서는 원문 앞에, 02에서는 원문 뒤에 놓았습니다. 위치에 따라 답과 분류가 얼마나 달라졌는지 봅니다.',
      labels: ['01 · 원문 앞', '02 · 원문 뒤'] },
    SOURCE_A: { title: '원문 주장에 출처를 붙이면 응답이 달라지나요?',
      purpose: '같은 01 입력에서 원문 쪽 주장에 출처를 붙인 03과 짝지었습니다. 아래 수치는 출처를 붙이기 전후의 응답 차이이며 출처의 신뢰성을 판정하지 않습니다.',
      labels: ['01 · 출처 없음', '03 · 원문 주장에 출처'] },
    SOURCE_B: { title: '추가 숫자 주장에 출처를 붙이면 응답이 달라지나요?',
      purpose: '같은 02 입력에서 추가 숫자 주장에 출처를 붙인 04와 짝지었습니다. 03과 04를 서로 비교하면 출처를 붙인 주장과 배치 위치가 모두 달라집니다.',
      labels: ['02 · 출처 없음', '04 · 추가 주장에 출처'] },
    EA_DELETION: { title: '어느 원문 정보를 지웠는지에 따라 응답이 달라지나요?',
      purpose: '06(EA-01)과 07(EA-02)은 같은 원본에서 서로 다른 항목을 각각 삭제한 입력입니다. 07이 06에서 한 번 더 삭제한 결과는 아닙니다.',
      labels: ['06 · 첫 항목 삭제', '07 · 다른 항목 삭제'] },
    PROMPT: { title: '풀이 지침을 바꾸면 응답이 달라지나요?',
      purpose: '문항·유형·모델·추론 설정을 같게 두고 Unguided Solving의 응답과 Criteria-Guided Solving의 응답을 비교합니다. Unguided에는 분류를 요청하지 않았으므로 분류 변화로 계산하지 않습니다.',
      labels: ['Unguided Solving', 'Criteria-Guided Solving'] },
    REASONING: { title: 'Reasoning OFF → Reasoning ON',
      purpose: '문항·유형·모델·풀이 지침을 같게 두고 추론 설정만 OFF에서 ON으로 바꾼 두 응답을 비교합니다.',
      labels: ['Reasoning OFF', 'Reasoning ON'] },
    MODEL: { title: '모델이 다르면 같은 입력에 어떻게 답하나요?',
      purpose: '문항·유형·풀이·추론 설정을 같게 두고 두 모델의 저장된 응답을 비교합니다. 반복 시행이나 모델 우열의 판정은 아닙니다.',
      labels: ['첫 번째 모델', '두 번째 모델'] }
  };
  for (const [axis, config] of Object.entries(axes)) {
    const groups = c.paired_groups.filter(g => g.axis === axis).sort(resultPairGroupOrder); if (!groups.length) continue;
    const panel = section(config.title, config.purpose);
    const showDelta = axis === 'PROMPT' || axis === 'REASONING';
    const cards = el('div', 'result-pair-list');
    for (const g of groups) {
      const detail = Number.isInteger(g.viewer_pair_index) ? resultPairDetails(g, config.labels)
        : resultPagedDetails(`문항별 응답 ${fmt(g.planned_pairs)}건 보기`, ['문항', ...config.labels], g.pairs || [],
          p => [p.case, resultPairEndpoint(p.left), resultPairEndpoint(p.right)]);
      const coverage = el('div', 'result-pair-coverage');
      coverage.append(el('span', 'muted', '비교 가능한 문항'), el('strong', '', ratio(g.comparable_pairs, g.planned_pairs)));
      if (g.missing_pairs || g.failed_pairs) coverage.append(el('small', 'muted', `제외: 응답 없음 ${fmt(g.missing_pairs)}건 · 형식 실패 ${fmt(g.failed_pairs)}건`));
      const condition = `${g.model} · ${g.axis === 'PROMPT' ? reasoningName(g.reasoning) : g.axis === 'REASONING' ? promptName(g.prompt_condition) : conditionName(g.prompt_condition, g.reasoning)}${VARIANTS[g.variant] ? ' · ' + VARIANTS[g.variant] : ''}`;
      const card = el('article', 'result-pair-card'), head = el('div', 'result-pair-card-head');
      head.append(el('h4', '', condition), coverage);
      const answers = el('div', 'result-pair-block'); answers.append(el('h5', '', '반환 답의 변화'), resultAnswerChanges(g, showDelta));
      const classification = el('div', 'result-pair-block'); classification.append(el('h5', '', '모델이 반환한 분류'), resultClassificationChanges(g));
      const reference = el('div', 'result-pair-block'); reference.append(el('h5', '', '저장된 기준값과 비교'), resultChoiceChanges(g));
      const side = el('div', 'result-pair-side'); side.append(classification, reference);
      const body = el('div', 'result-pair-body'); body.append(answers, side);
      card.append(head, body, detail); cards.append(card);
    }
    panel.append(cards); out.append(panel);
  }
  if (overview.models.length < 2) out.append(note('모델 간 비교는 저장된 모델이 1개여서 표시하지 않습니다. 반복 호출 안정성은 별도 반복 자료가 있어야 판단할 수 있습니다.', 'info'));
  out.append(button('A03 · 근거·반례·개선 토의 읽기 →', () => navigate({ tab: 'reports' }))); return out;
}
// [EV20.2] Keep answer-shape comparison separate from the saved A03 interpretation.
function renderRQAnswers(initialData, sourceGroups = []) {
  let data = initialData;
  const panel = section('연구 질문으로 보기', '같은 문항·모델·풀이 조건의 원본과 변형 응답을 직접 짝지어 봅니다. 답의 수치 변화는 정답·설명 타당성 판정이 아닙니다.');
  const chosen = { view: 'rq1', model: data.models[0], variant: data.variants[0].key,
    prompt: 'guided', reasoning: 'on', category: 'numeric_different', baselineCategory: 'mismatch',
    sourceType: '', wideMode: sourceGroups.length ? 'sources' : 'total', casesOpen: false };
  const top = el('div', 'rq-top'), body = el('div', 'rq-body'), dialog = el('dialog', 'rq-wide-dialog');
  const tabs = el('div', 'rq-tabs'), title = el('h4', '', '저장된 답의 변화');
  let requestSerial = 0;
  const percent = (count, total) => total ? (100 * count / total).toFixed(1) + '%' : '—';
  const currentCell = () => data.cells.find(cell => cell.model === chosen.model && cell.variant === chosen.variant
    && cell.prompt === chosen.prompt && cell.reasoning === chosen.reasoning);
  const answerText = side => side ? side.answer === null ? 'null' : side.answer === undefined ? '미기록'
    : String(side.answer) + (side.answer_scale ? ' · ' + side.answer_scale : '') : '응답 미기록';
  const conditionText = (prompt, reasoning) => conditionName(prompt, reasoning);
  const cellText = cell => {
    if (!cell?.planned) return '미기록';
    const count = cell.counts[chosen.category] || 0;
    return percent(count, cell.planned) + ' · ' + fmt(count) + '/' + fmt(cell.planned);
  };
  const categoryName = key => data.categories.find(item => item.key === key)?.label || key;
  const baselineCategoryName = key => data.baseline_categories.find(item => item.key === key)?.label || key;
  const variantName = key => key === 'ORIGINAL' ? '원본 풀이' : data.variants.find(item => item.key === key)?.label || key;
  const cellFor = (variant, prompt, reasoning) => data.cells.find(cell => cell.model === chosen.model
    && cell.variant === variant && cell.prompt === prompt && cell.reasoning === reasoning);
  const baselineFor = (prompt, reasoning) => data.baselines.find(cell => cell.model === chosen.model
    && cell.prompt === prompt && cell.reasoning === reasoning);
  const bar = cell => {
    const line = el('span', 'rq-bar');
    if (!cell?.planned) return line;
    for (const item of data.categories) {
      const count = cell.counts[item.key] || 0;
      const segment = el('span', 'rq-bar-segment rq-color-' + item.key);
      segment.style.width = (100 * count / cell.planned) + '%';
      segment.title = item.label + ': ' + fmt(count) + '/' + fmt(cell.planned) + ' (' + percent(count, cell.planned) + ')';
      if (item.key !== chosen.category) segment.classList.add('rq-dimmed');
      line.append(segment);
    }
    return line;
  };
  const legend = () => {
    const wrap = el('div', 'rq-legend');
    for (const item of data.categories) {
      const control = button(item.label, () => { chosen.category = item.key; render(); }, 'rq-legend-button');
      control.classList.toggle('active', item.key === chosen.category);
      control.prepend(el('span', 'rq-legend-dot rq-color-' + item.key));
      control.setAttribute('aria-pressed', String(item.key === chosen.category));
      wrap.append(control);
    }
    return wrap;
  };
  const caseNavigation = (caseId, variant) => {
    const clear = Object.fromEntries([...FILTERS, 'metric', 'tags', 'paired', 'q', 'offset', 'case_offset'].map(key => [key, '']));
    navigate({ ...clear, tab: 'case', case: caseId, model: chosen.model, variant,
      prompt: chosen.prompt, reasoning: chosen.reasoning });
  };
  const caseSide = (caseId, variant, heading, saved) => {
    const item = el('article', 'rq-case-side');
    item.append(el('h5', '', heading), el('strong', 'rq-answer', answerText(saved)),
      el('p', 'small muted', '형식 ' + (saved?.status ? label(saved.status) : '응답 미기록')
        + ' · 모델 분류 ' + (saved?.classification ?? (chosen.prompt === 'unguided' ? '미요구' : '미기록'))));
    if (!saved) return item;
    item.append(button('문항 비교에서 보기 →', () => caseNavigation(caseId, variant), 'text-button'));
    const detail = el('div', 'rq-case-full', '설명·evidence를 읽는 중…');
    item.append(detail);
    get(api('case', { case: caseId, variant, model: chosen.model, prompt: chosen.prompt, reasoning: chosen.reasoning }))
      .then(record => {
        if (!detail.isConnected) return;
        const response = record.responses.find(entry => entry.model === chosen.model)?.response;
        detail.replaceChildren(el('h6', '', 'EXPLANATION · 모델 설명'),
          el('p', 'rq-prose', response?.explanation || '설명 미기록'),
          el('h6', '', 'EVIDENCE · 입력 본문에서 제출한 발췌'));
        if (Array.isArray(response?.evidence) && response.evidence.length) {
          for (const quote of response.evidence) detail.append(el('blockquote', '', quote));
        } else detail.append(el('p', 'muted', 'evidence 미기록'));
      }).catch(error => { if (detail.isConnected && error.name !== 'AbortError') detail.replaceChildren(note(error.message, 'danger')); });
    return item;
  };
  const caseRow = pair => {
    const item = el('details', 'rq-case-row');
    const baseline = chosen.variant === 'ORIGINAL';
    item.append(el('summary', '', baseline
      ? pair.case + ' · 원본 ' + answerText(pair.original) + ' · ' + baselineCategoryName(pair.category)
        + (pair.reason ? ' · ' + pair.reason : '')
      : pair.case + ' · 원본 ' + answerText(pair.original) + ' → '
        + variantName(chosen.variant) + ' ' + answerText(pair.changed)
        + (pair.reason ? ' · ' + pair.reason : '')));
    item.addEventListener('toggle', () => {
      if (!item.open || item.dataset.loaded) return;
      item.dataset.loaded = 'true';
      const sides = el('div', baseline ? 'rq-case-sides rq-baseline-side' : 'rq-case-sides');
      sides.append(caseSide(pair.case, 'ORIGINAL', '원본 · ORIGINAL', pair.original));
      if (!baseline) sides.append(caseSide(pair.case, chosen.variant, '변형 · ' + variantName(chosen.variant), pair.changed));
      item.append(sides, el('p', 'small muted', 'evidence는 모델이 제출한 입력 발췌입니다. 해당 수치를 최종 계산에 사용했다는 뜻은 아닙니다.'));
    });
    return item;
  };
  const cases = () => {
    const baseline = chosen.variant === 'ORIGINAL';
    const category = baseline ? chosen.baselineCategory : chosen.category;
    const cell = baseline ? baselineFor(chosen.prompt, chosen.reasoning) : currentCell();
    const count = cell?.counts[category] || 0;
    const wrap = el('details', 'rq-cases');
    wrap.open = chosen.casesOpen;
    wrap.append(el('summary', '', variantName(chosen.variant) + ' · ' + conditionText(chosen.prompt, chosen.reasoning)
      + ' · ' + (baseline ? baselineCategoryName(category) : categoryName(category))
      + ' ' + fmt(count) + '건 · 문항 보기'));
    if (baseline) {
      const filters = el('div', 'rq-baseline-filters');
      for (const item of data.baseline_categories) {
        const control = button(item.label + ' ' + fmt(cell?.counts[item.key] || 0), () => {
          chosen.baselineCategory = item.key; chosen.casesOpen = true; render();
        }, 'rq-baseline-filter');
        control.classList.toggle('active', item.key === category);
        control.setAttribute('aria-pressed', String(item.key === category));
        filters.append(control);
      }
      wrap.append(filters);
    }
    const content = el('div', 'rq-cases-content');
    wrap.append(content);
    const serial = ++requestSerial;
    const loadPage = async offset => {
      const more = content.querySelector('.rq-more');
      if (more) more.remove();
      if (!offset) content.replaceChildren(el('p', 'small muted', '실제 저장 응답을 연결하는 중…'));
      try {
        const page = await get(api('rq-pairs', { model: chosen.model, variant: chosen.variant,
          prompt: chosen.prompt, reasoning: chosen.reasoning, category, offset, source_type: chosen.sourceType }));
        if (serial !== requestSerial || !content.isConnected) return;
        if (!offset) content.replaceChildren();
        if (!page.linked_total && !page.unrecorded) content.append(empty('해당 답 전환이 없습니다.'));
        for (const pair of page.pairs) content.append(caseRow(pair));
        if (page.unrecorded && ['unavailable', 'missing'].includes(category))
          content.append(note('계획된 문항 중 ' + fmt(page.unrecorded) + '건은 저장 응답이 없어 문항 번호를 연결할 수 없습니다.', 'info'));
        const next = page.offset + page.pairs.length;
        if (next < page.linked_total) content.append(button('다음 ' + Math.min(page.page_size, page.linked_total - next)
          + '건 보기 · ' + fmt(next) + '/' + fmt(page.linked_total), () => loadPage(next), 'text-button rq-more'));
      } catch (error) {
        if (serial === requestSerial && content.isConnected && error.name !== 'AbortError')
          content.replaceChildren(note(error.message, 'danger'));
      }
    };
    wrap.addEventListener('toggle', () => {
      chosen.casesOpen = wrap.open;
      if (wrap.open && !wrap.dataset.loaded) { wrap.dataset.loaded = 'true'; loadPage(0); }
    });
    if (wrap.open) { wrap.dataset.loaded = 'true'; loadPage(0); }
    return wrap;
  };
  const chooseCell = cell => {
    chosen.variant = cell.variant; chosen.prompt = cell.prompt; chosen.reasoning = cell.reasoning;
    chosen.casesOpen = true; render();
    requestAnimationFrame(() => (dialog.open ? dialog : body).querySelector('.rq-cases')?.scrollIntoView({ block: 'nearest' }));
  };
  const chooseBaseline = cell => {
    chosen.variant = 'ORIGINAL'; chosen.prompt = cell.prompt; chosen.reasoning = cell.reasoning;
    chosen.baselineCategory = cell.counts.mismatch ? 'mismatch'
      : cell.counts.unevaluated ? 'unevaluated' : cell.counts.failed ? 'failed' : 'match';
    chosen.casesOpen = true; render();
    requestAnimationFrame(() => (dialog.open ? dialog : body).querySelector('.rq-cases')?.scrollIntoView({ block: 'nearest' }));
  };
  const baselineButton = cell => {
    const control = button('', () => chooseBaseline(cell), 'rq-cell rq-baseline-cell');
    control.classList.toggle('selected', chosen.variant === 'ORIGINAL'
      && chosen.prompt === cell.prompt && chosen.reasoning === cell.reasoning);
    const line = el('span', 'rq-bar');
    for (const item of data.baseline_categories) {
      const count = cell.counts[item.key] || 0;
      const segment = el('span', 'rq-bar-segment rq-baseline-' + item.key);
      segment.style.width = cell.planned ? (100 * count / cell.planned) + '%' : '0%';
      segment.title = item.label + ': ' + fmt(count) + '/' + fmt(cell.planned)
        + ' (' + percent(count, cell.planned) + ')';
      line.append(segment);
    }
    const values = el('span', 'rq-baseline-values');
    values.append(el('strong', 'rq-cell-value', '정답 일치 ' + percent(cell.counts.match, cell.planned)
      + ' · ' + fmt(cell.counts.match) + '/' + fmt(cell.planned)),
    el('small', '', '불일치 ' + fmt(cell.counts.mismatch) + ' · 미평가 ' + fmt(cell.counts.unevaluated)
      + ' · 형식 실패 ' + fmt(cell.counts.failed) + ' · 기록 확인 불가 ' + fmt(cell.counts.missing)
      + ' · null ' + fmt(cell.counts.null)));
    control.append(line, values);
    control.title = '원본 풀이 · ' + conditionText(cell.prompt, cell.reasoning)
      + ' · ' + data.baseline_categories.map(item => item.label + ' ' + fmt(cell.counts[item.key])).join(' · ')
      + ' · null ' + fmt(cell.counts.null);
    return control;
  };
  const cellButton = cell => {
    const control = button('', () => chooseCell(cell), 'rq-cell');
    control.classList.toggle('selected', cell?.variant === chosen.variant && cell?.prompt === chosen.prompt
      && cell?.reasoning === chosen.reasoning);
    control.append(bar(cell), el('strong', 'rq-cell-value', cellText(cell)));
    control.title = variantName(cell?.variant) + ' · ' + conditionText(cell?.prompt, cell?.reasoning)
      + ' · ' + categoryName(chosen.category) + ' ' + cellText(cell);
    return control;
  };
  const wideMatrix = () => {
    const matrix = el('div', 'rq-wide-matrix');
    matrix.append(el('div', 'rq-wide-corner', '00 원본 풀이 → 7개 변경 유형'));
    for (const condition of data.conditions) matrix.append(el('div', 'rq-wide-heading',
      conditionText(condition.prompt, condition.reasoning)));
    const originalLabel = el('div', 'rq-wide-label rq-baseline-label');
    originalLabel.append(el('strong', '', '00 · 원본 풀이'), el('small', '', '입력을 바꾸지 않은 풀이 · 변형 비교의 기준'));
    matrix.append(originalLabel);
    for (const condition of data.conditions) matrix.append(baselineButton(baselineFor(condition.prompt, condition.reasoning)));
    for (const variant of data.variants) {
      const labelBox = el('div', 'rq-wide-label');
      labelBox.append(el('strong', '', variant.label), el('small', '', variant.change));
      matrix.append(labelBox);
      for (const condition of data.conditions)
        matrix.append(cellButton(cellFor(variant.key, condition.prompt, condition.reasoning)));
    }
    return matrix;
  };
  const sourceMatrix = group => {
    const source = group.rq_answers;
    const matrix = el('div', 'rq-wide-matrix rq-source-matrix');
    matrix.append(el('div', 'rq-wide-corner', '00 원본 풀이 → 7개 변경 유형'));
    for (const condition of source.conditions) matrix.append(el('div', 'rq-wide-heading',
      conditionText(condition.prompt, condition.reasoning)));
    const showCell = (variant, prompt, reasoning, baseline = false) => {
      chosen.sourceType = group.source_type;
      data = source;
      const picker = top.querySelector('.rq-source-choice select');
      if (picker) picker.value = group.source_type;
      chosen.variant = variant; chosen.prompt = prompt; chosen.reasoning = reasoning;
      if (baseline) {
        const cell = source.baselines.find(item => item.model === chosen.model && item.prompt === prompt && item.reasoning === reasoning);
        chosen.baselineCategory = cell?.counts.mismatch ? 'mismatch' : cell?.counts.unevaluated ? 'unevaluated' : 'match';
      }
      chosen.casesOpen = true;
      dialog.close(); render();
      requestAnimationFrame(() => body.querySelector('.rq-cases')?.scrollIntoView({ block: 'nearest' }));
    };
    const originalLabel = el('div', 'rq-wide-label rq-baseline-label');
    originalLabel.append(el('strong', '', '00 · 원본 풀이'), el('small', '', '저장된 참조 숫자와의 비교'));
    matrix.append(originalLabel);
    for (const condition of source.conditions) {
      const cell = source.baselines.find(item => item.model === chosen.model && item.prompt === condition.prompt && item.reasoning === condition.reasoning);
      const control = button('', () => showCell('ORIGINAL', condition.prompt, condition.reasoning, true), 'rq-cell rq-baseline-cell');
      const line = el('span', 'rq-bar');
      for (const item of source.baseline_categories) {
        const segment = el('span', 'rq-bar-segment rq-baseline-' + item.key);
        segment.style.width = cell?.planned ? (100 * (cell.counts[item.key] || 0) / cell.planned) + '%' : '0%';
        segment.title = `${item.label} ${fmt(cell?.counts[item.key] || 0)}/${fmt(cell?.planned || 0)}`;
        line.append(segment);
      }
      control.append(line, el('strong', 'rq-cell-value', `일치 ${percent(cell?.counts.match || 0, cell?.planned || 0)} · ${fmt(cell?.counts.match || 0)}/${fmt(cell?.planned || 0)}`));
      control.title = `${group.source_type} · 원본 · ${conditionText(condition.prompt, condition.reasoning)}`;
      matrix.append(control);
    }
    for (const variant of source.variants) {
      const rowLabel = el('div', 'rq-wide-label');
      rowLabel.append(el('strong', '', variant.label), el('small', '', variant.change)); matrix.append(rowLabel);
      for (const condition of source.conditions) {
        const cell = source.cells.find(item => item.model === chosen.model && item.variant === variant.key
          && item.prompt === condition.prompt && item.reasoning === condition.reasoning);
        const control = button('', () => showCell(variant.key, condition.prompt, condition.reasoning), 'rq-cell');
        const line = el('span', 'rq-bar');
        for (const item of source.categories) {
          const count = cell?.counts[item.key] || 0;
          const segment = el('span', 'rq-bar-segment rq-color-' + item.key);
          segment.style.width = cell?.planned ? (100 * count / cell.planned) + '%' : '0%';
          segment.title = `${item.label} ${fmt(count)}/${fmt(cell?.planned || 0)}`;
          if (item.key !== chosen.category) segment.classList.add('rq-dimmed');
          line.append(segment);
        }
        control.append(line, el('strong', 'rq-cell-value', `${percent(cell?.counts[chosen.category] || 0, cell?.planned || 0)} · ${fmt(cell?.counts[chosen.category] || 0)}/${fmt(cell?.planned || 0)}`));
        control.title = `${group.source_type} · ${variant.label} · ${conditionText(condition.prompt, condition.reasoning)} · ${categoryName(chosen.category)}`;
        matrix.append(control);
      }
    }
    return matrix;
  };
  const renderMain = () => {
    body.replaceChildren();
    const toolbar = el('div', 'rq-toolbar');
    if (chosen.view === 'rq1') {
      toolbar.append(el('h4', '', 'RQ1 · 원본 풀이와 근거 변경 후의 답'), button('한번에 보기 ⤢', () => {
        chosen.casesOpen = false; chosen.wideMode = sourceGroups.length ? 'sources' : 'total'; dialog.showModal(); renderWide();
      }, 'rq-wide-open'));
      const choice = select(data.conditions.map(item => [item.prompt + ':' + item.reasoning,
        conditionText(item.prompt, item.reasoning)]), chosen.prompt + ':' + chosen.reasoning, value => {
        [chosen.prompt, chosen.reasoning] = value.split(':'); chosen.casesOpen = false; render();
      });
      const setting = el('label', 'rq-choice', '고정할 풀이 조건 '); setting.append(choice);
      body.append(toolbar, setting, legend(), el('p', 'small muted rq-baseline-note',
        '00 원본 풀이는 저장된 정답 기준으로 파랑 일치·빨강 불일치·노랑 미평가를 표시합니다. 아래 7개 행의 색은 원본 대비 반환 답의 변화입니다.'));
      if (chosen.sourceType) body.append(el('p', 'small muted rq-source-scope',
        `${chosen.sourceType} 원본 ${fmt(sourceGroups.find(group => group.source_type === chosen.sourceType)?.case_count || 0)}문항만 집계했습니다. 전체 유형과 분모가 다릅니다.`));
      const rows = el('div', 'rq-single-rows');
      const original = el('div', 'rq-single-row rq-baseline-row');
      const originalLabel = el('div', 'rq-single-label');
      originalLabel.append(el('strong', '', '00 · 원본 풀이'),
        el('small', '', '입력을 바꾸지 않은 풀이 · 변형 비교의 기준'));
      original.append(originalLabel, baselineButton(baselineFor(chosen.prompt, chosen.reasoning)));
      rows.append(original);
      for (const variant of data.variants) {
        const cell = cellFor(variant.key, chosen.prompt, chosen.reasoning);
        const row = el('div', 'rq-single-row');
        const description = el('div', 'rq-single-label'); description.append(el('strong', '', variant.label), el('small', '', variant.change));
        row.append(description, cellButton(cell)); rows.append(row);
      }
      body.append(rows);
    } else {
      toolbar.append(el('h4', '', 'RQ2 · 같은 근거 변경에서 풀이 조건 비교'));
      const choice = select(data.variants.map(item => [item.key, item.label]), chosen.variant, value => {
        chosen.variant = value; chosen.casesOpen = false; render();
      });
      const setting = el('label', 'rq-choice', '함께 볼 근거 변경 '); setting.append(choice);
      body.append(toolbar, setting, legend());
      const columns = el('div', 'rq-rq2-grid');
      for (const condition of data.conditions) {
        const baseline = data.baselines.find(item => item.model === chosen.model && item.prompt === condition.prompt
          && item.reasoning === condition.reasoning);
        const column = el('article', 'rq-rq2-column');
        column.append(el('h5', '', conditionText(condition.prompt, condition.reasoning)),
          el('p', 'small muted', '원본 숫자 일치 ' + fmt(baseline?.counts.match || 0) + '/' + fmt(baseline?.planned || 0)
            + ' · 원본 null ' + fmt(baseline?.counts.null || 0)),
          cellButton(cellFor(chosen.variant, condition.prompt, condition.reasoning)));
        columns.append(column);
      }
      body.append(columns);
    }
    body.append(cases(), el('p', 'small muted rq-caution',
      '같은 수치는 반환 숫자만 같다는 뜻이며 정답 여부와 별개입니다. null의 이유는 문항별 classification·explanation에서 확인합니다. EA 앞/뒤는 첫째·둘째 선택 입력값을 각각 원본에서 삭제한 별도 변형입니다.'));
  };
  const renderWide = () => {
    if (!dialog.open) return;
    dialog.replaceChildren();
    const header = el('div', 'rq-wide-header');
    header.append(el('div', '', ''), button('원래 화면으로 ↙', () => dialog.close(), 'rq-wide-close'));
    const grouped = chosen.wideMode === 'sources' && sourceGroups.length;
    header.firstChild.append(el('h3', '', grouped ? 'RQ1 · 원천 유형별 그래프 한번에 보기' : 'RQ1 · 원본 풀이 + 7개 변경 유형 × 4개 풀이 조건'),
      el('p', 'small muted', grouped
        ? '네 원천 유형을 각각의 원본 문항 수로 나눠 표시합니다. 셀을 누르면 해당 유형의 문항 근거로 이동합니다.'
        : '맨 위 00 원본 풀이는 정답 일치·불일치·미평가를 표시합니다. 아래 7개 행은 같은 문항·모델·조건의 원본 → 변형 답 변화입니다.'));
    dialog.append(header, legend());
    if (sourceGroups.length) {
      const controls = el('div', 'rq-wide-modes');
      for (const [mode, caption] of [['sources', '원천 유형별 4개 그래프'], ['total', '전체 통합 그래프']]) {
        const control = button(caption, () => { chosen.wideMode = mode; renderWide(); }, 'rq-legend-button');
        control.classList.toggle('active', chosen.wideMode === mode); controls.append(control);
      }
      dialog.append(controls);
    }
    if (grouped) {
      for (const group of sourceGroups) {
        const block = el('section', 'rq-source-group');
        block.append(el('h4', '', `${group.source_type} · 원본 ${fmt(group.case_count)}문항`), sourceMatrix(group));
        dialog.append(block);
      }
    } else dialog.append(wideMatrix(), cases());
    dialog.append(el('p', 'small muted rq-caution', '분모에는 형식 실패·단위 불일치·기록 누락도 비교 불가로 포함합니다. 같은 수치는 의미 정답이 아닙니다. 원천 유형별 비율 차이는 문항 구성 차이도 함께 반영합니다.'));
  };
  const render = () => {
    requestSerial++;
    for (const tab of tabs.children) {
      tab.classList.toggle('active', tab.dataset.view === chosen.view);
      tab.setAttribute('aria-pressed', String(tab.dataset.view === chosen.view));
    }
    renderMain(); renderWide();
  };
  for (const [key, caption] of [['rq1', 'RQ1 · 근거를 바꾸면?'], ['rq2', 'RQ2 · 풀이 조건을 바꾸면?']]) {
    const control = button(caption, () => {
      chosen.view = key;
      if (key === 'rq2' && chosen.variant === 'ORIGINAL') chosen.variant = data.variants[0].key;
      chosen.casesOpen = false; render();
    }, 'rq-tab');
    control.dataset.view = key; tabs.append(control);
  }
  const modelChoice = select(data.models.map(model => [model, model]), chosen.model, value => {
    chosen.model = value; chosen.casesOpen = false; render();
  });
  const modelLabel = el('label', 'rq-model', '모델 '); modelLabel.append(modelChoice);
  top.append(title, tabs, modelLabel);
  if (sourceGroups.length) {
    const sourceChoice = select([['', '전체 · ' + fmt(sourceGroups.reduce((sum, group) => sum + group.case_count, 0)) + '문항'],
      ...sourceGroups.map(group => [group.source_type, group.source_type + ' · ' + fmt(group.case_count) + '문항'])], '', value => {
      chosen.sourceType = value;
      data = sourceGroups.find(group => group.source_type === value)?.rq_answers || initialData;
      chosen.casesOpen = false; render();
    });
    const sourceLabel = el('label', 'rq-source-choice', '원천 유형 '); sourceLabel.append(sourceChoice);
    top.append(sourceLabel);
  }
  panel.append(top, body, dialog);
  dialog.addEventListener('click', event => {
    const box = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right
      || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
  });
  dialog.addEventListener('close', () => render());
  render();
  return panel;
}
function resultResearchGroup(title, count, key, description) {
  const group = rememberPanel(el('details', 'panel result-research-group'), `${state.run}:result-research:${key}`, false);
  const summary = el('summary', 'result-research-summary'), heading = el('h3');
  heading.append(title, el('span', 'result-research-count', `${fmt(count)}건`));
  summary.append(heading, el('span', 'small muted', description), el('span', 'result-research-toggle'));
  group.append(summary); return group;
}
function renderRQSqReview(review) {
  const panel = section('RQ·SQ별 통합 검토', `논문 초안 v${review.paper_version} §3.3–3.4 · 저장된 발견의 질문별 읽기`);
  panel.append(note(review.notice_ko, 'info'));
  const groups = new Map(review.groups.map(group => [group.id, group]));
  for (const [prefix, heading] of [['RQ', '중심 연구질문'], ['SQ', '보조 연구질문']]) {
    panel.append(el('h4', 'rq-sq-section-title', heading));
    for (const question of review.questions.filter(item => item.id.startsWith(prefix))) {
      const item = rememberPanel(el('details', 'panel result-research-group rq-sq-item'), `${state.run}:rq-sq:${review.paper_version}:${question.id}`, false);
      const summary = el('summary', 'result-research-summary rq-sq-summary');
      const title = el('h4'); title.append(el('strong', 'rq-sq-code', question.id), el('span', '', question.title_ko));
      const count = question.group_ids.length ? `${question.group_ids.length}개 발견 묶음` : '직접 연결된 묶음 없음';
      summary.append(title, el('span', 'small muted rq-sq-question', question.question_ko),
        el('span', `rq-sq-status ${question.group_ids.length ? '' : 'rq-sq-status-empty'}`, question.status_ko),
        el('span', 'result-research-toggle'));
      item.append(summary);
      const render = () => {
        if (item.dataset.rendered) return;
        item.dataset.rendered = 'true';
        item.append(el('p', 'rq-sq-scope', question.scope_ko));
        for (const id of question.group_ids) {
          const source = groups.get(id);
          if (!source) { item.append(note(`${id}의 저장된 내용을 찾지 못했습니다.`, 'danger')); continue; }
          const card = el('article', 'rq-sq-finding');
          card.append(el('h5', '', `${id} · ${source.title_ko}`),
            el('p', '', source.claim_ko),
            el('p', '', `근거와 비교 조건: ${source.evidence_ko}`),
            el('p', '', `반례·다른 설명: ${source.alternatives_ko}`),
            el('p', 'rq-sq-boundary', `말할 수 있는 범위: ${source.boundary_ko}`));
          const refs = el('details', 'rq-sq-references');
          refs.append(el('summary', '', `연결된 원래 발견 F ${source.primary_finding_ids.length}개 · 관찰 ${source.interpretation_ids.length}개`));
          const links = el('div', 'toolbar');
          for (const findingId of source.primary_finding_ids) links.append(button(findingId, () => {
            const target = document.getElementById(`result-finding-${findingId}`);
            if (!target) return;
            const parent = target.closest('details'); parent.open = true; rememberDisclosure(parent);
            requestAnimationFrame(() => { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); target.focus({ preventScroll: true }); });
          }, 'text-button'));
          refs.append(links); card.append(refs); item.append(card);
        }
      };
      item.addEventListener('toggle', () => { if (item.open) render(); });
      if (item.open) render();
      panel.append(item);
    }
  }
  panel.append(el('p', 'small muted rq-sq-source', `출처: ${review.paper.path} · 그룹 검토 기록: ${review.saved_review.path}. 두 자료의 SHA-256은 JSON 색인에 기록되어 있습니다.`));
  return panel;
}
async function renderResultResearch() {
  const out = el('div'), data = overview.results_analysis; resultScope(out);
  const documents = await get(api('documents'));
  const sourceTypeIndex = documents.files.find(f => f.path === '02_analysis/source-types/source-type-index.json');
  let sourceGroups = [];
  if (sourceTypeIndex && data.rq_answers) {
    try { sourceGroups = (await get(api('rq-source-summaries'))).types || []; }
    catch (error) { out.append(note(`RQ1 원천 유형별 그래프를 읽지 못했습니다: ${error.message}`, 'danger')); }
  }
  if (data.rq_answers) out.append(renderRQAnswers(data.rq_answers, sourceGroups));
  if (!Array.isArray(data.findings?.findings) || !Array.isArray(data.findings?.discussion)) { out.append(empty('A03 연구 해석이 아직 저장되지 않았습니다.')); return out; }
  if (sourceTypeIndex) {
    try {
      const saved = await get(api('file', { id: sourceTypeIndex.id }));
      const index = JSON.parse(saved.content);
      const panel = section('원천 유형별 검토', '완료된 동일 실험의 저장 응답을 원천 ID로 나눈 후속 집계입니다. 별도 실험이나 유형별 의미 정답 판정이 아닙니다.');
      for (const item of index.types || []) {
        const report = documents.files.find(f => f.path === item.review_path);
        const row = el('div', 'toolbar');
        row.append(el('span', '', `${item.source_type} · 원본 ${fmt(item.case_count)}문항 · 응답 ${fmt(item.response_count)}건 · 문항별 관찰 ${fmt(item.observation_count)}개`));
        if (report) row.append(button(`${item.source_type} 검토 보고서 보기`, () => openFile(report), 'text-button'));
        panel.append(row);
      }
      const readme = documents.files.find(f => f.path === '02_analysis/source-types/README.md');
      const comparison = documents.files.find(f => f.path === '02_analysis/source-types/overview.md');
      if (comparison) panel.append(button('네 유형 대조표', () => openFile(comparison), 'text-button'));
      if (readme) panel.append(button('읽는 순서와 범위', () => openFile(readme), 'text-button'));
      out.append(panel);
    } catch (error) { out.append(note(`원천 유형별 검토를 읽지 못했습니다: ${error.message}`, 'danger')); }
  }
  const rqSqIndex = documents.files.find(f => f.path === '02_analysis/03_research/rq-sq-review.json')
    || documents.files.find(f => f.path === '02_analysis/03_research/rq-sq-review-v026.json');
  const rqReport = documents.files.find(f => f.path === '02_analysis/03_research/rq-review.md');
  if (rqSqIndex) {
    try {
      const saved = await get(api('file', { id: rqSqIndex.id }));
      out.append(renderRQSqReview(JSON.parse(saved.content)));
    } catch (error) { out.append(note(`RQ·SQ 통합 검토를 읽지 못했습니다: ${error.message}`, 'danger')); }
  } else if (rqReport) {
    const reviewed = section('이전 RQ 체계의 통합 검토', '이 실행에는 최신 v0.26 질문별 색인이 없습니다. 아래 문서는 저장 당시의 질문 번호를 사용합니다.');
    const saved = await get(api('file', { id: rqReport.id }));
    const body = markdown(saved.content, saved.links); body.classList.add('document-content');
    reviewed.append(body); out.append(reviewed);
  }
  const research = data.stages?.[2], coverage = research?.coverage;
  const mode = research?.execution_mode === 'current_session' ? '현재 Codex 대화에서 작성' : research?.execution_mode === 'codex_cli' ? 'Codex CLI 분석' : research?.backend ? `${research.backend} 분석` : '분석 방식 미기록';
  const calls = Number.isInteger(research?.external_model_calls) ? `별도 모델 호출 ${fmt(research.external_model_calls)}회` : '별도 모델 호출 수 미기록';
  out.append(note(`${mode} · ${calls} · 전체 ${fmt(coverage?.structured_responses)}응답 집계 · ${fmt(coverage?.cited_response_count)}응답을 연결한 ${fmt(coverage?.interpretations)}개 해석. 전 문항의 의미 정답 재채점이 아닙니다.`, 'info'));
  const findings = resultResearchGroup('연구 발견', data.findings.findings.length, 'findings', '주장·다른 설명·한계와 연결된 관찰');
  const evidence = resultResearchGroup('연결한 관찰', (data.interpretations || []).length, 'observations', '응답 인용과 분석자의 해석');
  for (const f of data.findings.findings) {
    const ko = f.display_ko, panel = el('article', 'result-finding'); panel.id = `result-finding-${f.id}`; panel.tabIndex = -1;
    panel.append(localizedValue('h4', '', f, 'title', `${f.id} · `), localizedValue('p', 'result-finding-decision', f, 'decision'), localizedValue('p', '', f, 'claim'), localizedValue('p', 'small', f, 'alternatives', '다른 설명: '), localizedValue('div', 'notice', f, 'limitation', '한계: '));
    const references = el('div', 'toolbar'); for (const id of f.interpretation_ids) references.append(button(`${id} 근거`, () => {
      evidence.open = true; renderEvidence(); rememberDisclosure(evidence);
      const target = document.getElementById(`result-${id}`); if (!target) return;
      requestAnimationFrame(() => { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); target.focus({ preventScroll: true }); });
    }, 'text-button'));
    panel.append(references); findings.append(panel);
  }
  out.append(findings);
  const next = resultResearchGroup('개선 토의 안건', data.findings.discussion.length, 'discussion', '아직 실행하지 않은 다음 실험 제안');
  next.append(el('p', 'small muted', '관찰 결과와 합의가 필요한 다음 실험을 분리합니다.'), table(['안건', '제안', '이유'], data.findings.discussion.map(d => [d.id, localizedValue('span', '', d, 'proposal'), localizedValue('span', '', d, 'reason')]))); out.append(next);
  const renderEvidence = () => {
    if (evidence.dataset.rendered) return;
    evidence.dataset.rendered = 'true';
    evidence.append(el('p', 'small muted', '인용은 모델의 영어 원문입니다. 분석자의 관찰·해석 및 모델 classification과 구분합니다.'));
    for (const category of Object.keys(RESULT_CATEGORIES)) {
      const items = (data.interpretations || []).filter(i => i.category === category); if (!items.length) continue;
      evidence.append(el('h4', 'result-category', RESULT_CATEGORIES[category]));
      for (const item of items) {
        const box = el('article', 'result-observation'); box.id = `result-${item.id}`; box.tabIndex = -1;
        box.append(localizedValue('h5', '', item, 'title', `${item.id} · `), localizedValue('p', '', item, 'observation'), localizedValue('p', 'small', item, 'interpretation', '해석: '), localizedValue('p', 'small muted', item, 'limitation', '한계: '));
        const details = el('details'); details.append(el('summary', '', `실제 응답·설명 ${item.excerpts.length}건 확인`));
        for (const q of item.excerpts) { const row = resultResponse(q.response_id), block = el('div', 'result-excerpt'); block.append(resultLink(q.response_id), el('p', 'small', `모델 답 ${show(row?.answer)} · classification ${resultClassificationLabel(row)}`), el('blockquote', '', q.quote)); details.append(block); }
        box.append(details); evidence.append(box);
      }
    }
  };
  evidence.addEventListener('toggle', () => { if (evidence.open) renderEvidence(); });
  if (evidence.open) renderEvidence();
  out.append(evidence);
  const files = documents.files.filter(f => ['README.md', '02_analysis/03_research/findings.md', '02_analysis/03_research/rq-sq-review-README.md', '02_analysis/03_research/rq-sq-review.json', '02_analysis/03_research/rq-sq-review-v026-README.md', '02_analysis/03_research/rq-sq-review-v026.json', '02_analysis/03_research/rq-review.md', '02_analysis/03_research/rq-review-audit.md'].includes(f.path));
  const links = section('같은 내용을 파일로 읽기', '뷰어와 Markdown은 같은 findings.json에서 읽습니다.');
  for (const file of files) links.append(button(file.path, () => openFile(file), 'text-button')); out.append(links); return out;
}
function openValue(title, value) { modalEpoch++; $('file-title').textContent = title; $('file-body').replaceChildren(valueView(value, title)); if (!$('file-dialog').open) $('file-dialog').showModal(); }
async function openFile(file) {
  openValue(file.path || file.label, '파일 읽는 중…'); const version = modalEpoch;
  try { const data = await get(api('file', { id: file.id }), null); if (version !== modalEpoch) return; $('file-title').textContent = data.path; const extension = data.path.split('.').at(-1).toLowerCase(); $('file-body').replaceChildren(extension === 'md' ? markdown(data.content, data.links) : valueView(data.content, data.path, { format: ['json', 'jsonl'].includes(extension) ? extension : 'auto' })); }
  catch (e) { if (version === modalEpoch) $('file-body').replaceChildren(note(e.message, 'danger')); }
}

$('refresh').onclick = () => load(true);
$('run-select').onchange = () => { const run = $('run-select').value; for (const key of Object.keys(state)) delete state[key]; Object.assign(state, { run, tab: 'overview' }); writeURL(); load(); };
for (const key of FILTERS) $(`filter-${key}`).onchange = () => navigate({ [key]: $(`filter-${key}`).value, offset: '0', case_offset: '0', comparison_offset: '0' });
$('clear-filters').onclick = resetFilters;
let searchTimer;
$('search').oninput = () => { clearTimeout(searchTimer); const q = $('search').value; searchTimer = setTimeout(() => navigate({ q, offset: '0', case_offset: '0', comparison_offset: '0' }, true), 250); };
const closeFile = () => { modalEpoch++; $('file-dialog').close(); };
$('close-dialog').onclick = closeFile;
$('file-dialog').addEventListener('cancel', () => modalEpoch++);
$('export').onclick = async () => {
  try { let blob; if (OFFLINE) blob = new Blob([await OFFLINE.request(api('export', state))], { type: 'text/markdown;charset=utf-8' }); else { const response = await fetch(api('export', state)); if (!response.ok) throw Error('표를 내려받지 못했습니다.'); blob = await response.blob(); } download(blob, `${state.run}-filtered-results.md`); }
  catch (e) { openValue('내려받기 오류', e.message); }
};

// [EV08.1] Download one complete run while retaining the current screen as its opening view.
function download(blob, filename) { const url = URL.createObjectURL(blob), a = el('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000); }
let exportController;
$('html-export').onclick = () => {
  $('export-run').replaceChildren(...[...$('run-select').options].filter(o => o.value).map(o => globalThis.FinarchI18n?.clone(o) || o.cloneNode(true))); $('export-run').value = state.run;
  $('export-status').replaceChildren(); $('download-html').disabled = !$('export-run').value; $('export-dialog').showModal();
};
$('export-run').onchange = () => $('export-status').replaceChildren();
const closeExport = () => { exportController?.abort(); $('export-dialog').close(); };
$('close-export').onclick = closeExport;
$('export-dialog').addEventListener('cancel', () => exportController?.abort());
// [EV15.1] The native modal contains focus and blocks page shortcuts until closed.
const closeShortcuts = () => $('shortcut-dialog').close();
$('show-shortcuts').onclick = () => {
  $('shortcut-dialog').showModal();
  $('close-shortcuts').focus({ preventScroll: true });
};
$('close-shortcuts').onclick = closeShortcuts;
$('shortcut-dialog').addEventListener('close', () => $('show-shortcuts').focus({ preventScroll: true }));
// [EV09.5] Only clicks that start and end on the backdrop dismiss a dialog.
function closeOnBackdrop(dialog, close) {
  let startedOutside = false;
  const outside = event => {
    const box = dialog.getBoundingClientRect();
    return event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
  };
  dialog.addEventListener('pointerdown', event => { startedOutside = event.button === 0 && event.target === dialog && outside(event); });
  dialog.addEventListener('pointercancel', () => { startedOutside = false; });
  dialog.addEventListener('close', () => { startedOutside = false; });
  dialog.addEventListener('click', event => {
    const dismiss = startedOutside && event.target === dialog && outside(event);
    startedOutside = false; if (dismiss) close();
  });
}
closeOnBackdrop($('file-dialog'), closeFile);
closeOnBackdrop($('export-dialog'), closeExport);
closeOnBackdrop($('shortcut-dialog'), closeShortcuts);
$('download-html').onclick = async () => {
  const run = $('export-run').value, params = { ...(run === state.run ? state : { tab: 'overview' }), lang: globalThis.FinarchI18n?.language || 'ko' };
  const request = new AbortController(); exportController = request;
  $('download-html').disabled = true; $('export-run').disabled = true;
  $('export-status').replaceChildren(note('전체 문항·원기록을 압축하고 있습니다. 회차 크기에 따라 시간이 걸릴 수 있습니다.'));
  try {
    const response = await fetch(`/api/runs/${encodeURIComponent(run)}/export-html?${new URLSearchParams(params)}`, { signal: request.signal });
    if (!response.ok) { const data = await response.json(); throw Error(data.error || 'HTML을 만들지 못했습니다.'); }
    const blob = await response.blob(); request.signal.throwIfAborted();
    download(blob, `${run}-experiments.html`);
    $('export-status').replaceChildren(note(`${run} · ${(blob.size / 1024 / 1024).toFixed(1)} MB · 다운로드를 시작했습니다. 파일을 열어 결과를 확인해 주세요.`, 'info'));
  } catch (error) { if (error.name !== 'AbortError') $('export-status').replaceChildren(note(error.message, 'danger')); }
  finally { if (exportController === request) { exportController = null; $('download-html').disabled = false; $('export-run').disabled = false; } }
};
window.addEventListener('popstate', () => { readURL(); load(); });
window.addEventListener('pagehide', rememberVisibleDisclosures);
readURL();
if (OFFLINE) {
  $('html-export').hidden = true; $('refresh').textContent = '화면 새로 읽기 ↻'; $('run-select').disabled = true;
  document.querySelector('.skip-link').onclick = event => { event.preventDefault(); $('content').focus(); $('content').scrollIntoView(); };
  $('offline-banner').hidden = false;
  const excluded = OFFLINE.stats.unavailable_files.length;
  $('offline-banner').textContent = `오프라인 사본 · ${time(OFFLINE.exportedAt)} 내보냄 · ${fmt(OFFLINE.stats.cases)}개 문항 / ${fmt(OFFLINE.stats.requests)}개 요청 · 저장된 자료는 갱신되지 않습니다.${excluded ? ` 원문 보기의 8MB 제한 파일 ${excluded}개는 포함하지 않았습니다.` : ''}`;
  load();
} else if (location.protocol === 'file:') { $('connection-error').hidden = false; $('connection-error').textContent = '프로젝트에서 node viewer/experiments/server.mjs를 실행한 뒤 http://127.0.0.1:8894을 열어 주세요.'; $('content').replaceChildren(empty('실제 파일을 읽으려면 전용 로컬 조회 서버가 필요합니다.')); }
else load();
