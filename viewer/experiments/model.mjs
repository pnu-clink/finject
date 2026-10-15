// Normalize legacy saved conditions without rewriting their source artifacts.
export function promptKey(value) { return value === 'P0' ? 'unguided' : value === 'P1' ? 'guided' : value; }
export const VARIANTS = ['ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02'];
const COMPLETE = new Set(['VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED']);
const NUMERIC_PENDING = new Set(['PREPARED', 'PENDING', 'BATCH_PENDING', 'RUNNING', 'NOT_RUN', 'UNKNOWN_DELIVERY']);
const countBy = (rows, key) => rows.reduce((out, row) => { const k = key(row); out[k] = (out[k] || 0) + 1; return out; }, {});
const canonical = value => JSON.stringify(value, (key, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
const comparison = row => row.checks?.numeric_comparison;

// [EV04.3] Resolve saved conditions identically in the server and exported HTML.
export function selectCase(snap, caseId, filters = {}) {
  const items = [...snap.privateItems.values()].filter(p => p.case === caseId);
  if (!items.length) throw Object.assign(new Error('이 실행에 없는 문항입니다.'), { status: 404 });
  const available = VARIANTS.filter(v => items.some(p => p.variant === v));
  const matching = selected(snap, filters).rows.find(r => r.case === caseId);
  const variant = filters.variant || matching?.variant || available[0];
  const prompt = promptKey(filters.prompt) || promptKey(matching?.prompt_condition) || 'unguided';
  const reasoning = filters.reasoning || matching?.reasoning || 'off';
  const item = items.find(p => p.variant === variant);
  const rows = snap.config.models.filter(m => !filters.model || filters.model === m.key).map(m => ({ model: m.key,
    row: snap.rows.find(r => r.case === caseId && r.variant === variant && promptKey(r.prompt_condition) === prompt && r.reasoning === reasoning && r.model === m.key) }));
  return { caseId, items, available, variant, prompt, reasoning, item, rows };
}

// [EV11.1] Compare the four saved conditions independently of the active pair.
export function caseConditionRows(snap, selection) {
  return ['unguided', 'guided'].flatMap(prompt => ['off', 'on'].map(reasoning => {
    const rows = selection.rows.map(({ model }) => ({ model,
      row: snap.rows.find(row => row.case === selection.caseId && row.variant === selection.variant && row.model === model && promptKey(row.prompt_condition) === prompt && row.reasoning === reasoning) }));
    return { prompt, reasoning, available: rows.some(entry => !!entry.row), rows };
  }));
}
export function recordedElapsed(result, call) {
  const value = result?.elapsed_seconds ?? call?.result?.elapsed_seconds;
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}
export function conditionTimings(conditions, records) {
  return conditions.map(({ rows, ...condition }) => ({ ...condition, models: rows.map(({ model, row }) => {
    const record = row && records[`${model}:${row.trial_id}`];
    return { model, status: row?.status ?? 'NOT_PLANNED', elapsed_seconds: recordedElapsed(record), timing_error: !!record?.timing_error };
  }) }));
}
// [EV16.1] Describe observed output shapes without inferring semantic reasons.
export const RESPONSE_CLASSIFICATIONS = {
  ANSWERABLE: { short: '답 가능', definition: '주어진 정보로 유일한 최종값을 구할 수 있음', color: 'class-answerable' },
  CONFLICT: { short: '정보 충돌', definition: '관련 정보가 충돌하며 선택 기준이 없음', color: 'class-conflict' },
  INSUFFICIENT_EVIDENCE: { short: '근거 부족', definition: '필수 정보가 없고 남은 정보로 복원할 수 없음', color: 'class-insufficient' },
  UNRESOLVED: { short: '의미 모호', definition: '질문·관계의 의미가 여러 가지로 해석됨', color: 'class-unresolved' },
  ABSTAIN: { short: '풀이 미완료', definition: '입력 문제를 확정하지 못했지만 모델이 풀이·검증을 완료하지 못함', color: 'class-abstain' }
};
// [EV17.1] Read only an explicit field or the historical declaration prefix.
export function responseClassification(response, prompt, variant, status, checks) {
  let value = null, source = null;
  if (response && Object.hasOwn(response, 'classification')) { value = response.classification; source = 'JSON_FIELD'; }
  else if (typeof response?.explanation === 'string') {
    const match = response.explanation.match(/^Classification: (ANSWERABLE|CONFLICT|INSUFFICIENT_EVIDENCE|UNRESOLVED); Response: (ANSWER|CONDITIONAL|ABSTAIN)\./);
    if (match) { value = match[1]; source = 'LEGACY_EXPLANATION_PREFIX'; }
  }
  const known = typeof value === 'string' && Object.hasOwn(RESPONSE_CLASSIFICATIONS, value);
  if (!known) {
    const notRequested = source === 'JSON_FIELD' && value === null && promptKey(prompt) === 'unguided';
    return { value, source, known: false, label: notRequested ? '분류 미요구' : typeof value === 'string' ? value : value == null ? '미기록' : '분류 형식 오류',
      definition: notRequested ? 'Unguided Solving은 분류를 요구하지 않음' : value == null ? '명시된 분류가 저장되어 있지 않음' : '허용된 분류명으로 확인되지 않은 반환 값',
      color: 'class-unrecorded', assessment: null };
  }
  const entry = RESPONSE_CLASSIFICATIONS[value];
  const assessed = value === 'ANSWERABLE' && variant === 'ORIGINAL' && status === 'VALID' && typeof checks?.numeric_comparison?.matches === 'boolean';
  const assessment = value === 'ANSWERABLE' ? assessed ? checks.numeric_comparison.matches ? '정답 일치' : '정답 불일치' : '정답 미평가' : null;
  const color = assessed ? checks.numeric_comparison.matches ? 'class-answerable-match' : 'class-answerable-mismatch' : entry.color;
  return { value, source, known: true, label: value, ...entry, color, assessment };
}
export const CASE_HEATMAP_LEGEND = [
  { key: 'match', label: '원본 정답 일치', short: '일치' },
  { key: 'mismatch', label: '원본 정답 불일치', short: '불일치' },
  { key: 'numeric', label: '숫자 답변', short: '숫자' },
  { key: 'null', label: 'Null 답변', short: 'Null' },
  { key: 'other', label: '기타 답변 형태', short: '기타' },
  { key: 'truncated', label: '출력 잘림', short: '잘림' },
  { key: 'invalid', label: '형식 오류', short: '형식 오류' },
  { key: 'unassessed', label: '원본 비교 미평가', short: '미평가' },
  { key: 'pending', label: '미실행·처리 중', short: '대기' },
  { key: 'missing', label: '응답 미기록', short: '미기록' },
  { key: 'read_error', label: '기록 읽기 오류', short: '읽기 오류' },
  { key: 'not_planned', label: '해당 조건 없음', short: '—' }
];
// [EV16.4] Compare exact decimal spellings without binary float coercion or rescaling.
function heatmapDecimalKey(value) {
  if (!['string', 'number'].includes(typeof value) || typeof value === 'number' && !Number.isFinite(value)) return null;
  const match = String(value).trim().match(/^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:e([+-]?\d+))?$/i);
  if (!match) return null;
  const fraction = match[3] ?? match[4] ?? '';
  let digits = ((match[2] ?? '') + fraction).replace(/^0+/, '');
  if (!digits) return '0';
  let exponent = BigInt(match[5] ?? '0') - BigInt(fraction.length);
  const trailing = digits.match(/0+$/)?.[0].length ?? 0;
  if (trailing) { digits = digits.slice(0, -trailing); exponent += BigInt(trailing); }
  return `${match[1] === '-' ? '-' : ''}${digits}e${exponent}`;
}
export function heatmapNumericAnswer(response) {
  const answer = response?.answer;
  if (heatmapDecimalKey(answer) === null) return null;
  let text = String(answer).trim();
  // Legacy V3/V4 store an unsigned magnitude plus a separate sign.
  if (typeof answer === 'string' && 'status' in response && (response.answer_meta ?? response).negative === true) {
    text = text.startsWith('-') ? text.slice(1) : `-${text.replace(/^\+/, '')}`;
  }
  return text;
}
export function caseHeatmapCategory(row, record = row) {
  if (!row) return 'not_planned';
  if (record?.read_error) return 'read_error';
  if (row.status === 'OUTPUT_TRUNCATED') return 'truncated';
  if (row.status === 'INVALID_RESPONSE') return 'invalid';
  if (['NOT_RUN', 'PENDING', 'PREPARED', 'RUNNING', 'BATCH_PENDING'].includes(row.status)) return 'pending';
  if (row.status === 'READ_ERROR') return 'read_error';
  if (row.variant === 'ORIGINAL') {
    const matches = comparison(row)?.matches;
    return row.status === 'VALID' && typeof matches === 'boolean' ? matches ? 'match' : 'mismatch' : 'unassessed';
  }
  const response = record?.response;
  if (response == null) return 'missing';
  if (!Object.hasOwn(response, 'answer')) return 'other';
  if (response.answer === null) return 'null';
  return heatmapNumericAnswer(response) !== null ? 'numeric' : 'other';
}
export function caseHeatmap(snap, selection, records = {}) {
  const rows = snap.rows.filter(row => row.case === selection.caseId);
  const gold = selection.items?.find(item => item.variant === 'ORIGINAL')?.reference?.reference_answer;
  const goldKey = heatmapDecimalKey(gold), referenceAnswer = goldKey === null ? null : String(gold).trim();
  const models = selection.rows.map(({ model }) => ({ model, conditions: ['unguided', 'guided'].flatMap(prompt => ['off', 'on'].map(reasoning => ({
    prompt, reasoning, cells: VARIANTS.map(variant => {
      const row = rows.find(row => row.model === model && row.variant === variant && promptKey(row.prompt_condition) === prompt && row.reasoning === reasoning);
      const record = row && (records[`${model}:${row.trial_id}`] ?? row);
      const category = caseHeatmapCategory(row, record);
      const classification = responseClassification(record?.response, prompt, variant, row?.status, row?.checks);
      const color = row?.status === 'VALID' && !record?.read_error && classification.known ? classification.color : category;
      const answerText = row?.status === 'VALID' && !record?.read_error ? heatmapNumericAnswer(record?.response) : null;
      return { variant, category, color, classification, status: row?.status ?? 'NOT_PLANNED', answer_text: answerText,
        reference_matches: answerText !== null && goldKey !== null ? heatmapDecimalKey(answerText) === goldKey : null,
        selectable: !!row,
        numeric_comparison: variant === 'ORIGINAL' ? comparison(row ?? {}) ?? null : null };
    })
  }))) }));
  const cells = models.flatMap(model => model.conditions.flatMap(condition => condition.cells));
  const present = new Set(['match', 'mismatch', ...cells.map(cell => cell.color)]);
  const legend = CASE_HEATMAP_LEGEND.filter(entry => present.has(entry.key));
  for (const cell of cells) if (cell.color.startsWith('class-') && !legend.some(entry => entry.key === cell.color)) {
    const c = cell.classification;
    legend.push({ key: cell.color, label: `${c.label}${c.assessment ? ` · ${c.assessment}` : ''}`, short: c.short });
  }
  return { variants: VARIANTS, reference_answer: referenceAnswer, models, legend };
}
export function assembleCase(snap, selection, responses, conditions = [], records = {}) {
  const { caseId, items, available, variant, prompt, reasoning, item } = selection;
  const requests = responses.map(r => r.request).filter(Boolean);
  const comparable = requests.map(r => canonical({ input: r.input, prompt: r.prompt, response_schema: r.response_schema }));
  return { case: caseId, variant, prompt, reasoning, variants: available, item: item ? snap.publicItems.get(item.item_id) : null,
    original: snap.publicItems.get(items.find(p => p.variant === 'ORIGINAL')?.item_id) ?? null,
    metadata: item ?? null, original_metadata: items.find(p => p.variant === 'ORIGINAL') ?? null,
    production_baseline: 'NOT_INCLUDED', conditions_match: comparable.length > 1 ? comparable.every(v => v === comparable[0]) : null,
    responses: responses.map(r => ({ ...r, classification: responseClassification(r.response, prompt, variant, r.status, r.checks) })),
    conditions, heatmap: caseHeatmap(snap, selection, records), warnings: snap.warnings };
}

// [EV25.1] Preserve every planned pair without inventing a semantic verdict.
export function pairMatrixReadiness(heatmap) {
  return (heatmap?.models || []).flatMap(model => model.conditions.map(condition => {
    const original = condition.cells.find(cell => cell.variant === 'ORIGINAL');
    const originalResult = original?.status === 'VALID' && typeof original.numeric_comparison?.matches === 'boolean'
      ? original.numeric_comparison.matches ? 'MATCH' : 'MISMATCH' : 'UNASSESSED';
    const pairs = condition.cells.filter(cell => cell.variant !== 'ORIGINAL' && cell.selectable).map(cell => ({
      variant: cell.variant, original_result: originalResult, status: cell.status,
      category: cell.category, classification: cell.classification,
      readiness: !original?.selectable || originalResult === 'UNASSESSED' ? 'ORIGINAL_UNASSESSED'
        : cell.status !== 'VALID' ? 'VARIANT_UNAVAILABLE' : 'SEMANTIC_NOT_REVIEWED'
    }));
    return { model: model.model, prompt: condition.prompt, reasoning: condition.reasoning,
      original_result: originalResult, planned: pairs.length, pairs,
      original_unassessed: pairs.filter(pair => pair.readiness === 'ORIGINAL_UNASSESSED').length,
      variant_unavailable: pairs.filter(pair => pair.readiness === 'VARIANT_UNAVAILABLE').length,
      semantic_not_reviewed: pairs.filter(pair => pair.readiness === 'SEMANTIC_NOT_REVIEWED').length };
  }));
}
export function aggregate(rows) {
  const originals = rows.filter(r => r.experiment === 1);
  const compared = originals.filter(r => typeof comparison(r)?.matches === 'boolean');
  const pending = originals.filter(r => NUMERIC_PENDING.has(r.status) && typeof comparison(r)?.matches !== 'boolean');
  const hasStructuralContract = rows.some(r => ['FinancialAnswerV5', 'FinancialAnswerV6', 'FinancialAnswerV7'].includes(r.checks?.response_format));
  return { total: rows.length, cases: new Set(rows.map(r => r.case)).size,
    statuses: countBy(rows, r => r.status), collected: rows.filter(r => COMPLETE.has(r.status)).length,
    valid: rows.filter(r => r.status === 'VALID').length,
    failed: rows.filter(r => ['INVALID_RESPONSE', 'OUTPUT_TRUNCATED'].includes(r.status)).length,
    numeric_eligible: originals.length, numeric_compared: compared.length,
    numeric_matches: compared.filter(r => comparison(r).matches).length,
    numeric_mismatches: compared.filter(r => !comparison(r).matches).length,
    numeric_unevaluated: originals.length - compared.length - pending.length,
    numeric_pending: pending.length,
    numeric_answers_absent: hasStructuralContract ? rows.filter(r => r.checks?.numeric_answer_present === false).length : null,
    declared_abstentions: hasStructuralContract && !rows.some(r => typeof r.checks?.declared_abstention === 'boolean') ? null : rows.filter(r => r.checks?.declared_abstention === true).length,
    abstention_markers: hasStructuralContract && !rows.some(r => typeof r.checks?.abstention_marker_detected === 'boolean') ? null : rows.filter(r => r.checks?.abstention_marker_detected === true).length,
    missing_quotes: rows.filter(r => r.checks?.all_quotes_present === false).length };
}

// [EV15.1] Preserve the boundary between an original's numeric gold and a
// variant's unreviewed meaning. Pair by original case, never by request count.
const originalVerdict = row => {
  if (!row || row.status !== 'VALID') return 'UNEVALUATED';
  if (comparison(row)?.matches === true) return 'MATCH';
  if (comparison(row)?.matches === false) return 'MISMATCH';
  return 'UNEVALUATED';
};
const pairGroup = (off, on) => {
  const left = originalVerdict(off), right = originalVerdict(on);
  if (left === 'UNEVALUATED' || right === 'UNEVALUATED') return 'unevaluated';
  if (left === 'MATCH' && right === 'MATCH') return 'both_match';
  if (left === 'MATCH') return 'off_only';
  if (right === 'MATCH') return 'on_only';
  return 'both_mismatch';
};
const answerKind = row => row.status !== 'VALID' ? 'unobserved'
  : row.response?.answer === null ? 'null'
  : typeof row.response?.answer === 'number' || typeof row.response?.answer === 'string' && /^[-+]?\d/.test(row.response.answer.trim()) ? 'numeric' : 'other';
const semanticVerdict = row => row.semantic?.semantic_assessed ? (row.semantic.appropriate ? 'PASS' : 'FAIL') : ['PASS', 'FAIL'].includes(row.checks?.semantic_assessment) ? row.checks.semantic_assessment : null;
export function contentAnalysis(snap, filters = {}) {
  const rows = snap.rows.filter(row => (!filters.model || row.model === filters.model)
    && (!filters.q || `${row.case} ${row.question || ''}`.toLowerCase().includes(filters.q.toLowerCase())));
  const requestedGroup = ['all', 'both_match', 'off_only', 'on_only', 'both_mismatch', 'unevaluated'].includes(filters.baseline_group)
    ? filters.baseline_group : 'all';
  return { scope: 'MODEL_AND_CASE_SEARCH; PAIRS_REQUIRE_SAME_MODEL_AND_PROMPT_AND_BOTH_REASONING_CONDITIONS', baseline_group: requestedGroup,
    models: snap.config.models.filter(model => !filters.model || model.key === filters.model).flatMap(model => ['unguided', 'guided'].map(prompt => {
      const modelRows = rows.filter(row => row.model === model.key && promptKey(row.prompt_condition) === prompt);
      const originals = modelRows.filter(row => row.variant === 'ORIGINAL');
      const pairs = new Map(modelRows.map(row => [row.case, { case: row.case }]));
      for (const row of originals) {
        if (!pairs.has(row.case)) pairs.set(row.case, { case: row.case });
        pairs.get(row.case)[row.reasoning] = row;
      }
      const cases = [...pairs.values()].sort((a, b) => a.case.localeCompare(b.case, 'en', { numeric: true })).map(pair => ({
        case: pair.case, group: pairGroup(pair.off, pair.on),
        off: pair.off ? { status: pair.off.status, verdict: originalVerdict(pair.off), computed: comparison(pair.off)?.computed ?? null, gold: comparison(pair.off)?.gold ?? null } : null,
        on: pair.on ? { status: pair.on.status, verdict: originalVerdict(pair.on), computed: comparison(pair.on)?.computed ?? null, gold: comparison(pair.on)?.gold ?? null } : null
      }));
      const groups = Object.fromEntries(['both_match', 'off_only', 'on_only', 'both_mismatch', 'unevaluated'].map(group => [group, cases.filter(pair => pair.group === group)]));
      const selectedCases = new Set((requestedGroup === 'all' ? cases : groups[requestedGroup]).map(pair => pair.case));
      const selectedVariants = modelRows.filter(row => row.variant !== 'ORIGINAL' && selectedCases.has(row.case));
      const observationCounts = new Map();
      for (const row of selectedVariants) for (const tag of new Set(row.tags || [])) {
        if (!observationCounts.has(tag)) observationCounts.set(tag, { tag, count: 0, cases: new Set() });
        const entry = observationCounts.get(tag); entry.count++; entry.cases.add(row.case);
      }
      const observations = [...observationCounts.values()].map(entry => ({ tag: entry.tag, count: entry.count, cases: entry.cases.size }))
        .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
      const variants = VARIANTS.slice(1).filter(variant => modelRows.some(row => row.variant === variant)).map(variant => ({
        variant, cells: ['off', 'on'].map(reasoning => {
          const members = modelRows.filter(row => row.variant === variant && promptKey(row.prompt_condition) === prompt && row.reasoning === reasoning && selectedCases.has(row.case));
          const reviewed = members.filter(row => semanticVerdict(row));
          return { prompt, reasoning, total: members.length, valid: members.filter(row => row.status === 'VALID').length,
            failed: members.filter(row => ['INVALID_RESPONSE', 'OUTPUT_TRUNCATED'].includes(row.status)).length,
            other_status: members.filter(row => !['VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED'].includes(row.status)).length,
            numeric: members.filter(row => answerKind(row) === 'numeric').length,
            null: members.filter(row => answerKind(row) === 'null').length,
            other_answer: members.filter(row => answerKind(row) === 'other').length,
            quote_missing: members.filter(row => row.checks?.all_quotes_present === false).length,
            quote_not_exact: members.filter(row => row.tags?.includes('QUOTE_NOT_EXACT_SUBSTRING')).length,
            empty_evidence: members.filter(row => row.tags?.includes('EMPTY_EVIDENCE')).length,
            semantic_reviewed: reviewed.length, semantic_pass: reviewed.filter(row => semanticVerdict(row) === 'PASS').length,
            semantic_fail: reviewed.filter(row => semanticVerdict(row) === 'FAIL').length,
            cases: members.map(row => ({ case: row.case, trial_id: row.trial_id, status: row.status, answer: row.response?.answer ?? null,
              tags: [...new Set(row.tags || [])], semantic: semanticVerdict(row),
              original: cases.find(pair => pair.case === row.case)?.[reasoning] ?? null })) };
        }) }));
      return { key: model.key, prompt, originals: originals.length, cases: cases.length,
        baseline: Object.fromEntries(Object.entries(groups).map(([group, list]) => [group, { count: list.length, cases: list }])),
        selected_cases: selectedCases.size, observations, variants };
    }).filter(group => group.cases)) };
}

export function filterRows(rows, filters = {}) {
  const tags = filters.tags?.split(',').filter(Boolean) || [];
  return rows.filter(r => {
    for (const [field, key] of [['model', 'model'], ['experiment', 'experiment'], ['variant', 'variant'], ['prompt', 'prompt_condition'], ['reasoning', 'reasoning']]) {
      if (filters[field] && (field === 'prompt' ? promptKey(r[key]) !== promptKey(filters[field]) : String(r[key]) !== filters[field])) return false;
    }
    if (filters.status === 'FORMAT_FAILED' ? !['INVALID_RESPONSE', 'OUTPUT_TRUNCATED'].includes(r.status) : filters.status && r.status !== filters.status) return false;
    if (filters.q && !`${r.case} ${r.question || ''}`.toLowerCase().includes(filters.q.toLowerCase())) return false;
    if (tags.length && !(filters.tag_mode === 'any' ? tags.some(t => r.tags.includes(t)) : tags.every(t => r.tags.includes(t)))) return false;
    const cmp = comparison(r);
    if (filters.metric === 'numeric_matches' && !(r.experiment === 1 && cmp?.matches === true)) return false;
    if (filters.metric === 'numeric_mismatches' && !(r.experiment === 1 && cmp?.matches === false)) return false;
    if (filters.metric === 'numeric_unevaluated' && !(r.experiment === 1 && typeof cmp?.matches !== 'boolean' && !NUMERIC_PENDING.has(r.status))) return false;
    if (filters.metric === 'numeric_pending' && !(r.experiment === 1 && NUMERIC_PENDING.has(r.status) && typeof cmp?.matches !== 'boolean')) return false;
    if (filters.metric === 'declared_abstentions' && r.checks?.declared_abstention !== true) return false;
    if (filters.metric === 'abstention_markers' && r.checks?.abstention_marker_detected !== true) return false;
    if (filters.metric === 'missing_quotes' && r.checks?.all_quotes_present !== false) return false;
    if (filters.metric === 'numeric_answers_absent' && r.checks?.numeric_answer_present !== false) return false;
    return true;
  });
}

// [EV02.1] Count saved decisions; the viewer never grades model content.
export function selected(snap, filters = {}) {
  let rows = filterRows(snap.rows, filters);
  const beforePaired = rows.length;
  if (filters.paired === 'true') {
    const keys = new Map();
    for (const r of rows) {
      if (typeof comparison(r)?.matches !== 'boolean') continue;
      const k = `${r.case}|${r.variant}|${promptKey(r.prompt_condition)}|${r.reasoning}`;
      if (!keys.has(k)) keys.set(k, new Set()); keys.get(k).add(r.model);
    }
    rows = rows.filter(r => snap.config.models.length > 1 && keys.get(`${r.case}|${r.variant}|${promptKey(r.prompt_condition)}|${r.reasoning}`)?.size === snap.config.models.length);
  }
  return { rows, beforePaired };
}
// [EV13.1] Sort the entire filtered set before pagination, independent of file order.
export function sortResponses(rows, requested = 'case_asc') {
  const fields = ['case', 'variant', 'model', 'prompt', 'reasoning', 'status', 'diagnostics'];
  const [requestedField, requestedDirection] = String(requested).split('_');
  const valid = fields.includes(requestedField) && ['asc', 'desc'].includes(requestedDirection) && `${requestedField}_${requestedDirection}` === requested;
  const field = valid ? requestedField : 'case', direction = valid ? requestedDirection : 'asc';
  const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
  const natural = (a, b) => collator.compare(String(a ?? ''), String(b ?? ''));
  const statuses = ['OUTPUT_TRUNCATED', 'INVALID_RESPONSE', 'READ_ERROR', 'AUTH_BLOCKED', 'UNKNOWN_DELIVERY', 'NOT_RUN', 'RUNNING', 'PENDING', 'VALID'];
  const ordered = (a, b, choices) => (choices.includes(a) ? choices.indexOf(a) : choices.length) - (choices.includes(b) ? choices.indexOf(b) : choices.length) || natural(a, b);
  const compareField = (a, b, key) => key === 'variant' ? ordered(a.variant, b.variant, VARIANTS)
    : key === 'status' ? Number(a.status === 'VALID') - Number(b.status === 'VALID') || ordered(a.status, b.status, statuses)
    : key === 'prompt' ? ordered(promptKey(a.prompt_condition), promptKey(b.prompt_condition), ['unguided', 'guided'])
    : key === 'diagnostics' ? new Set(a.tags).size - new Set(b.tags).size
    : natural(a[key], b[key]);
  const sorted = [...rows].sort((a, b) => {
    const primary = compareField(a, b, field) * (direction === 'desc' ? -1 : 1);
    if (primary) return primary;
    for (const key of ['case', 'variant', 'model', 'prompt', 'reasoning', 'status']) {
      const difference = compareField(a, b, key); if (difference) return difference;
    }
    return natural(a.trial_id, b.trial_id);
  });
  return { rows: sorted, sort: `${field}_${direction}` };
}
export function query(snap, filters = {}) {
  const { rows, beforePaired } = selected(snap, filters);
  const inspection = aggregate(filterRows(snap.rows, { model: filters.model, prompt: filters.prompt, reasoning: filters.reasoning, q: filters.q }));
  const groups = new Map(), caseMap = new Map();
  for (const row of rows) {
    const key = `${row.model}|${row.variant}|${promptKey(row.prompt_condition)}|${row.reasoning}`;
    if (!groups.has(key)) groups.set(key, []); groups.get(key).push(row);
    if (!caseMap.has(row.case)) caseMap.set(row.case, []); caseMap.get(row.case).push(row);
  }
  // [EV22.1] Summarize every filtered response, without choosing a representative condition.
  const cases = [...caseMap].sort(([a], [b]) => a.localeCompare(b, 'en', { numeric: true })).map(([id, values]) => {
    const classifications = new Map();
    for (const row of values) {
      let declared = responseClassification(row.response, row.prompt_condition, row.variant, row.status, row.checks);
      if (!declared.source && typeof row.checks?.reported_classification === 'string') {
        declared = responseClassification({ classification: row.checks.reported_classification }, row.prompt_condition, row.variant, row.status, row.checks);
      }
      const key = declared.known ? declared.value : !declared.source ? 'SUMMARY_NOT_RECORDED' : declared.label;
      const label = declared.known ? declared.short : !declared.source ? '요약에 분류 없음' : declared.label;
      if (!classifications.has(key)) classifications.set(key, { value: key, label, count: 0 });
      classifications.get(key).count++;
    }
    return { id, question: values[0].question, ...aggregate(values), classifications: [...classifications.values()].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value)) };
  });
  const requestedOffset = Math.max(0, Number.parseInt(filters.offset || '0', 10) || 0);
  const offset = Math.min(requestedOffset, Math.max(0, Math.floor((rows.length - 1) / 30) * 30));
  const tags = {};
  for (const r of rows) for (const tag of new Set(r.tags)) tags[tag] = (tags[tag] || 0) + 1;
  // Facet counts keep the base filters, without narrowing themselves by selected reasons.
  const tagRows = filters.tags ? selected(snap, { ...filters, tags: '' }).rows : rows, tagCounts = {};
  for (const r of tagRows) for (const tag of new Set(r.tags)) tagCounts[tag] = (tagCounts[tag] || 0) + 1;
  const sorted = sortResponses(rows, filters.sort);
  return { aggregate: aggregate(rows), unfiltered_total: snap.rows.length, before_paired: beforePaired,
    inspection_counts: inspection,
    original_conditions: snap.config.models.filter(m => !filters.model || m.key === filters.model).map(m => ({ model: m.key,
      conditions: ['unguided', 'guided'].flatMap(prompt => ['off', 'on'].map(reasoning => ({ prompt, reasoning,
        run_requests: snap.rows.filter(r => r.model === m.key && r.experiment === 1 && promptKey(r.prompt_condition) === prompt && r.reasoning === reasoning).length,
        ...aggregate(rows.filter(r => r.model === m.key && r.experiment === 1 && promptKey(r.prompt_condition) === prompt && r.reasoning === reasoning)) }))) })),
    models: snap.config.models.map(m => ({ key: m.key, ...aggregate(rows.filter(r => r.model === m.key)) })),
    groups: [...groups.values()].map(g => ({ model: g[0].model, variant: g[0].variant, prompt: promptKey(g[0].prompt_condition), reasoning: g[0].reasoning, ...aggregate(g) })),
    tags, tag_counts: tagCounts, tag_scope_total: tagRows.length, sort: sorted.sort,
    cases, case_total: cases.length, case_offset: 0,
    case_navigation: caseNavigation(cases, filters.case || cases[0]?.id),
    rows: sorted.rows.slice(offset, offset + 30).map(r => ({ model: r.model, trial_id: r.trial_id, case: r.case, question: r.question, variant: r.variant, prompt: promptKey(r.prompt_condition), reasoning: r.reasoning, status: r.status, tags: [...new Set(r.tags)], answer: r.response?.answer, numeric: comparison(r) })), offset };
}
// [EV10.1] Resolve neighbors across the complete filtered list; ignore legacy page offsets.
export function caseNavigation(cases, currentCase) {
  const index = cases.findIndex(item => item.id === currentCase);
  const at = position => position >= 0 && position < cases.length ? { id: cases[position].id, case_offset: 0 } : null;
  return { index, total: cases.length, previous: at(index - 1), next: at(index + 1) };
}
// Pair saved requests by their public experimental condition, never by provider-specific trial_id.
export function modelComparison(snap, filters = {}) {
  const models = snap.config.models.slice(0, 2).map(model => model.key);
  const scope = Object.fromEntries(['experiment', 'variant', 'prompt', 'reasoning', 'q']
    .filter(key => filters[key]).map(key => [key, filters[key]]));
  const groups = new Map();
  for (const row of filterRows(snap.rows, scope)) {
    if (!models.includes(row.model)) continue;
    const key = JSON.stringify([row.case, row.variant, promptKey(row.prompt_condition), row.reasoning]);
    if (!groups.has(key)) groups.set(key, { case: row.case, question: row.question, variant: row.variant,
      prompt: promptKey(row.prompt_condition), reasoning: row.reasoning, models: {} });
    const value = groups.get(key);
    const compared = comparison(row);
    value.models[row.model] = { status: row.status, has_answer: row.response != null && Object.hasOwn(row.response, 'answer'),
      answer: row.response?.answer ?? null, numeric_match: typeof compared?.matches === 'boolean' ? compared.matches : null,
      semantic: semanticVerdict(row) };
  }
  const order = (a, b) => a.case.localeCompare(b.case, 'en', { numeric: true })
    || VARIANTS.indexOf(a.variant) - VARIANTS.indexOf(b.variant)
    || ['unguided', 'guided'].indexOf(a.prompt) - ['unguided', 'guided'].indexOf(b.prompt) || a.reasoning.localeCompare(b.reasoning);
  const all = [...groups.values()].sort(order);
  const pair = models.slice(0, 2);
  const paired = all.filter(row => pair.length === 2 && pair.every(key => row.models[key]?.status === 'VALID'));
  const numeric = paired.filter(row => pair.every(key => typeof row.models[key].numeric_match === 'boolean'));
  const offset = Math.min(Math.max(0, Number.parseInt(filters.comparison_offset || '0', 10) || 0),
    Math.max(0, Math.floor((all.length - 1) / 50) * 50));
  return { models, additional_models: Math.max(0, snap.config.models.length - 2), scope, total: all.length, offset, page_size: 50,
    both_valid: paired.length, both_numeric_compared: numeric.length,
    both_numeric_match: numeric.filter(row => pair.every(key => row.models[key].numeric_match)).length,
    numeric_disagreement: numeric.filter(row => row.models[pair[0]].numeric_match !== row.models[pair[1]].numeric_match).length,
    rows: all.slice(offset, offset + 50) };
}
export function semanticSummary(summary) {
  if (!summary) return null;
  return { ...summary, matrix: summary.matrix?.map(row => {
    const normalized = { ...row };
    for (const [key, value] of Object.entries(row)) if (key.startsWith('p1_')) {
      const current = `guided_${key.slice(3)}`;
      if (!Object.hasOwn(row, current)) normalized[current] = value;
    }
    return normalized;
  }) };
}
// Each screen receives only the analysis records it reads. The offline snapshot
// retains the complete source and applies this same selection when navigating.
const RESULT_NUMERIC_CHOICES = new Set(['A', 'B', 'BOTH', 'OTHER', 'ORIGINAL_VALUE', 'REFERENCE_MISSING']);
// [EV24.1] Summarize paired answers before sending A02 data to the browser.
// A number is compared only when both recorded scales agree; null is a separate outcome.
export function summarizePairAnswers(group, responses) {
  const counts = { comparable: 0, numeric_same: 0, numeric_different: 0,
    numeric_to_null: 0, null_to_numeric: 0, null_same: 0, scale_unmatched: 0, other: 0 };
  const numeric = value => {
    if (typeof value !== 'number' && !(typeof value === 'string' && value.trim())) return null;
    const n = Number(value);
    return Number.isFinite(n) && (!Number.isInteger(n) || Number.isSafeInteger(n)) ? n : null;
  };
  for (const pair of group.pairs || []) {
    if (!pair.format_comparable || !pair.left || !pair.right) continue;
    counts.comparable++;
    const left = pair.left.answer, right = pair.right.answer;
    if (left === null && right === null) { counts.null_same++; continue; }
    const leftNumber = numeric(left), rightNumber = numeric(right);
    if (leftNumber !== null && right === null) { counts.numeric_to_null++; continue; }
    if (left === null && rightNumber !== null) { counts.null_to_numeric++; continue; }
    if (leftNumber === null || rightNumber === null) { counts.other++; continue; }
    const leftScale = responses.get(pair.left.response_id)?.answer_scale;
    const rightScale = responses.get(pair.right.response_id)?.answer_scale;
    if (!leftScale || leftScale !== rightScale) { counts.scale_unmatched++; continue; }
    counts[leftNumber === rightNumber ? 'numeric_same' : 'numeric_different']++;
  }
  return counts;
}
function resultPairDelta(group, responses) {
  const counts = { comparable: 0, numeric_before: 0, numeric_after: 0, null_before: 0, null_after: 0,
    up: 0, down: 0, same: 0, different_scale: 0, invalid: 0 };
  for (const pair of group.pairs || []) {
    if (!pair.format_comparable) continue;
    counts.comparable++;
    if (RESULT_NUMERIC_CHOICES.has(pair.left?.choice)) counts.numeric_before++;
    if (RESULT_NUMERIC_CHOICES.has(pair.right?.choice)) counts.numeric_after++;
    if (pair.left?.choice === 'NULL') counts.null_before++;
    if (pair.right?.choice === 'NULL') counts.null_after++;
    if (!RESULT_NUMERIC_CHOICES.has(pair.left?.choice) || !RESULT_NUMERIC_CHOICES.has(pair.right?.choice)) continue;
    const leftScale = responses.get(pair.left.response_id)?.answer_scale;
    const rightScale = responses.get(pair.right.response_id)?.answer_scale;
    if (!leftScale || leftScale !== rightScale) { counts.different_scale++; continue; }
    const numeric = value => typeof value === 'number' ? value : typeof value === 'string' && value.trim() ? Number(value) : NaN;
    const before = numeric(pair.left.answer), after = numeric(pair.right.answer);
    if (!Number.isFinite(before) || !Number.isFinite(after) || (Number.isInteger(before) && !Number.isSafeInteger(before)) || (Number.isInteger(after) && !Number.isSafeInteger(after))) { counts.invalid++; continue; }
    counts[after > before ? 'up' : after < before ? 'down' : 'same']++;
  }
  return counts;
}
// [EV20.1] Compare each saved variant with ORIGINAL for the same case, model and condition.
// Answer shape is an observation; it is not a correctness or explanation judgment.
export const RQ_VARIANTS = [
  { key: 'IC_VALUE_01_BEFORE', label: 'IC-value 앞', change: '충돌 숫자 문장을 앞에 추가' },
  { key: 'IC_VALUE_01_AFTER', label: 'IC-value 뒤', change: '충돌 숫자 문장을 뒤에 추가' },
  { key: 'IC_SOURCE_A_ONLY', label: 'IC-source 앞', change: '앞 배치에서 원래 주장에 출처 추가' },
  { key: 'IC_SOURCE_B_ONLY', label: 'IC-source 뒤', change: '뒤 배치에서 추가 주장에 출처 추가' },
  { key: 'IC_RELATION_01', label: 'IC-relation', change: '상충하는 관계 추가' },
  { key: 'EA_01', label: 'EA 앞', change: '첫 번째 선택 입력값 삭제' },
  { key: 'EA_02', label: 'EA 뒤', change: '두 번째 선택 입력값 삭제' }
];
export const RQ_CONDITIONS = [
  { prompt: 'unguided', reasoning: 'off' }, { prompt: 'unguided', reasoning: 'on' },
  { prompt: 'guided', reasoning: 'off' }, { prompt: 'guided', reasoning: 'on' }
];
export const RQ_ANSWER_CATEGORIES = [
  { key: 'numeric_same', label: '같은 수치' },
  { key: 'numeric_different', label: '다른 수치' },
  { key: 'numeric_to_null', label: '수치 → 응답 보류(null)' },
  { key: 'null_to_numeric', label: '응답 보류 → 수치' },
  { key: 'null_same', label: '응답 보류 유지' },
  { key: 'unavailable', label: '비교 불가' }
];
export const RQ_BASELINE_CATEGORIES = [
  { key: 'match', label: '원본풀이 정답 일치' },
  { key: 'mismatch', label: '원본풀이 정답 불일치' },
  { key: 'unevaluated', label: '원본 미평가' },
  { key: 'failed', label: '원본 형식 실패' },
  { key: 'missing', label: '원본 기록 확인 불가' }
];
const rqKey = (...parts) => JSON.stringify(parts);
function rqIndex(data, caseIds = null) {
  const selected = caseIds === null ? null : new Set(caseIds);
  const rows = new Map(), cases = new Map(), planned = new Map(), models = new Set();
  for (const row of data?.responses || []) {
    if (!row?.case || !row.model || !row.variant) continue;
    if (selected && !selected.has(row.case)) continue;
    const prompt = promptKey(row.prompt_condition);
    const key = rqKey(row.model, row.case, row.variant, prompt, row.reasoning);
    if (!rows.has(key)) rows.set(key, []);
    rows.get(key).push(row);
    const condition = rqKey(row.model, prompt, row.reasoning);
    if (!cases.has(condition)) cases.set(condition, new Set());
    cases.get(condition).add(row.case);
    models.add(row.model);
  }
  for (const cell of data?.comparisons?.matrix || []) {
    if (cell?.model && cell.variant) {
      models.add(cell.model);
      planned.set(rqKey(cell.model, cell.variant, promptKey(cell.prompt_condition), cell.reasoning),
        selected ? selected.size : Number.isSafeInteger(cell.planned) && cell.planned >= 0 ? cell.planned : 0);
    }
  }
  return { rows, cases, planned, models: [...models].sort() };
}
function rqDecimal(row) {
  if (typeof row.answer === 'number' && Number.isInteger(row.answer) && !Number.isSafeInteger(row.answer)) return null;
  let value = heatmapDecimalKey(row.answer);
  if (value === null) return null;
  const negative = row.answer_negative;
  if (typeof negative === 'boolean' && value !== '0') {
    if (negative && !value.startsWith('-') && typeof row.answer === 'string') value = '-' + value;
    else if (negative !== value.startsWith('-')) return null;
  }
  return value;
}
function rqAnswerKind(row) {
  if (row.answer === null) return { kind: 'null' };
  const value = rqDecimal(row);
  return value !== null && typeof row.answer_scale === 'string' && row.answer_scale
    ? { kind: 'numeric', value } : { kind: 'unknown' };
}
function rqClassify(left, right) {
  if (!left || !right) return { category: 'unavailable', reason: '응답 미기록' };
  if (left.status !== 'VALID' || right.status !== 'VALID') return { category: 'unavailable', reason: '형식 실패·미완료' };
  const before = rqAnswerKind(left), after = rqAnswerKind(right);
  if (before.kind === 'unknown' || after.kind === 'unknown') return { category: 'unavailable', reason: '답 값·단위 확인 불가' };
  if (before.kind === 'null' && after.kind === 'null') return { category: 'null_same' };
  if (before.kind === 'null') return { category: 'null_to_numeric' };
  if (after.kind === 'null') return { category: 'numeric_to_null' };
  if (left.answer_scale !== right.answer_scale) return { category: 'unavailable', reason: 'scale 다름' };
  return { category: before.value === after.value ? 'numeric_same' : 'numeric_different' };
}
function rqCell(data, index, model, variant, prompt, reasoning) {
  const conditionCases = index.cases.get(rqKey(model, prompt, reasoning)) || new Set();
  const pairs = [];
  const counts = Object.fromEntries(RQ_ANSWER_CATEGORIES.map(item => [item.key, 0]));
  const unavailableReasons = {};
  for (const caseId of [...conditionCases].sort()) {
    const original = index.rows.get(rqKey(model, caseId, 'ORIGINAL', prompt, reasoning)) || [];
    const changed = index.rows.get(rqKey(model, caseId, variant, prompt, reasoning)) || [];
    const result = original.length > 1 || changed.length > 1
      ? { category: 'unavailable', reason: '조건 중복 기록' }
      : rqClassify(original[0], changed[0]);
    counts[result.category]++;
    if (result.reason) unavailableReasons[result.reason] = (unavailableReasons[result.reason] || 0) + 1;
    pairs.push({ case: caseId, category: result.category, reason: result.reason || null,
      original: original.length === 1 ? original[0] : null, changed: changed.length === 1 ? changed[0] : null });
  }
  const recorded = pairs.length;
  const planned = Math.max(recorded, index.planned.get(rqKey(model, variant, prompt, reasoning)) || 0);
  const unrecorded = planned - recorded;
  counts.unavailable += unrecorded;
  if (unrecorded) unavailableReasons['계획된 문항의 기록 없음'] = unrecorded;
  return { model, variant, prompt, reasoning, planned, recorded, unrecorded, counts, unavailable_reasons: unavailableReasons, pairs };
}
function rqBaselineCell(index, model, prompt, reasoning) {
  const caseIds = index.cases.get(rqKey(model, prompt, reasoning)) || new Set();
  const counts = { match: 0, mismatch: 0, unevaluated: 0, failed: 0, missing: 0, null: 0 };
  const pairs = [];
  for (const caseId of [...caseIds].sort()) {
    const matches = index.rows.get(rqKey(model, caseId, 'ORIGINAL', prompt, reasoning)) || [];
    const row = matches.length === 1 ? matches[0] : null;
    const category = !row ? 'missing' : row.status !== 'VALID' ? 'failed'
      : row.original_result === 'MATCH' ? 'match'
      : row.original_result === 'MISMATCH' ? 'mismatch' : 'unevaluated';
    counts[category]++;
    if (row?.status === 'VALID' && row.answer === null) counts.null++;
    pairs.push({ case: caseId, category,
      reason: matches.length > 1 ? '조건 중복 기록' : !row ? '원본 응답 미기록' : null,
      original: row, changed: null });
  }
  const recorded = pairs.length;
  const planned = Math.max(recorded, index.planned.get(rqKey(model, 'ORIGINAL', prompt, reasoning)) || 0);
  const unrecorded = planned - recorded;
  counts.missing += unrecorded;
  return { model, variant: 'ORIGINAL', prompt, reasoning, planned, recorded, unrecorded, counts, pairs };
}
export function rqAnswerOverview(data, options = {}) {
  const index = rqIndex(data, options.caseIds ?? null);
  if (!index.models.length) return null;
  const cells = index.models.flatMap(model => RQ_VARIANTS.flatMap(({ key }) =>
    RQ_CONDITIONS.map(({ prompt, reasoning }) => {
      const { pairs, ...cell } = rqCell(data, index, model, key, prompt, reasoning);
      return cell;
    })));
  const baselines = index.models.flatMap(model => RQ_CONDITIONS.map(({ prompt, reasoning }) => {
    const { pairs, ...baseline } = rqBaselineCell(index, model, prompt, reasoning);
    return baseline;
  }));
  return { models: index.models, variants: RQ_VARIANTS, conditions: RQ_CONDITIONS,
    categories: RQ_ANSWER_CATEGORIES, baseline_categories: RQ_BASELINE_CATEGORIES, cells, baselines };
}
export function rqAnswerPage(data, filters = {}) {
  const model = filters.model, variant = filters.variant, prompt = promptKey(filters.prompt), reasoning = filters.reasoning;
  const category = filters.category || (variant === 'ORIGINAL' ? 'mismatch' : 'numeric_different');
  const offset = Number(filters.offset ?? 0);
  const baseline = variant === 'ORIGINAL';
  if (!model || !(baseline || RQ_VARIANTS.some(item => item.key === variant))
      || !RQ_CONDITIONS.some(item => item.prompt === prompt && item.reasoning === reasoning)
      || !(baseline ? RQ_BASELINE_CATEGORIES : RQ_ANSWER_CATEGORIES).some(item => item.key === category)
      || !Number.isSafeInteger(offset) || offset < 0) throw new Error('RQ 비교 선택값이 올바르지 않습니다.');
  const index = rqIndex(data, filters.caseIds ?? null);
  if (!index.models.includes(model)) throw new Error('선택한 모델의 저장 응답이 없습니다.');
  const cell = baseline ? rqBaselineCell(index, model, prompt, reasoning)
    : rqCell(data, index, model, variant, prompt, reasoning);
  const matching = cell.pairs.filter(pair => pair.category === category);
  const pageSize = 30;
  return { model, variant, prompt, reasoning, category, planned: cell.planned,
    category_total: cell.counts[category], linked_total: matching.length, unrecorded: cell.unrecorded,
    offset: Math.min(offset, matching.length), page_size: pageSize,
    pairs: matching.slice(offset, offset + pageSize).map(pair => ({ case: pair.case, category: pair.category, reason: pair.reason,
      original: pair.original ? { response_id: pair.original.response_id, status: pair.original.status, answer: pair.original.answer,
        answer_scale: pair.original.answer_scale, classification: pair.original.classification,
        original_result: pair.original.original_result } : null,
      changed: pair.changed ? { response_id: pair.changed.response_id, status: pair.changed.status, answer: pair.changed.answer,
        answer_scale: pair.changed.answer_scale, classification: pair.changed.classification } : null })) };
}
export function resultsAnalysisForTab(data, tab) {
  if (!data || !tab) return data;
  const base = { method: data.method, stages: data.stages, timing: data.timing ?? null, scheduler: data.scheduler ?? null };
  if (tab === 'analysis') {
    const comparisons = data.comparisons?.overall && Array.isArray(data.comparisons.matrix)
      ? { overall: { ...data.comparisons.overall, response_ids: undefined },
          matrix: data.comparisons.matrix.map(({ response_ids, ...cell }) => cell) } : null;
    return { ...base, comparisons,
      responses: comparisons ? data.responses.filter(row => row.variant === 'ORIGINAL' && row.original_result !== 'MATCH') : data.responses };
  }
  if (tab === 'reports') {
    const cited = new Set((data.interpretations || []).flatMap(item => (item.excerpts || []).map(excerpt => excerpt.response_id)));
    return { ...base, interpretations: data.interpretations, findings: data.findings,
      rq_answers: rqAnswerOverview(data),
      responses: data.responses.filter(row => cited.has(row.response_id)) };
  }
  if (tab === 'conditions') {
    const comparisons = data.comparisons;
    const assessments = { response_assessment_summary: data.response_assessment_summary ?? null,
      response_assessment_coverage: data.response_assessment_coverage ?? null };
    if (!comparisons?.paired_groups) return { ...base, ...assessments, comparisons: null, responses: data.responses };
    const responses = new Map(data.responses.map(row => [row.response_id, row]));
    return { ...base, ...assessments, comparisons: { ...comparisons,
      paired_groups: comparisons.paired_groups.map((group, index) => ({ ...group, pairs: undefined,
        viewer_pair_index: index, viewer_answer_changes: summarizePairAnswers(group, responses),
        viewer_delta: ['PROMPT', 'REASONING'].includes(group.axis) ? resultPairDelta(group, responses) : null })) },
      responses: data.responses };
  }
  return base;
}
export function overview(snap, filters = {}) {
  return { id: snap.id, status: snap.state?.status ?? snap.summary?.status ?? 'UNKNOWN', updated_at: snap.summary?.updated_at ?? null,
    loaded_at: snap.loaded_at, stale: !!snap.stale, warnings: snap.warnings, originals: snap.selection?.originals ?? snap.summary?.originals ?? null, variants: snap.selection?.variants ?? snap.summary?.variants ?? null,
    planned: snap.plan?.models?.reduce((n, m) => n + m.requests, 0) ?? null,
    models: snap.summaries, verification: snap.verification, diagnostics_available: snap.diagnosticsAvailable,
    finalization: snap.finalization ?? null, improvement: snap.config.improvement ?? null, semantic: semanticSummary(snap.semantic), review_stages: snap.reviewStages ?? [], research_review: snap.researchReview ?? null, review_reset: snap.reviewReset ?? null,
    analysis_config: snap.config.analysis ?? snap.semantic?.analysis_config ?? null,
    analysis_execution: snap.state?.analysis ? { status: snap.state.analysis.status ?? null, new_model_calls: snap.state.analysis.new_model_calls ?? null } : null,
    evaluation_reuse: snap.config.evaluation_reuse ?? null, results_analysis: resultsAnalysisForTab(snap.resultsAnalysis, filters.tab) ?? null,
    semantic_cases: snap.rows.filter(r => r.semantic && (!filters.model || r.model === filters.model) && (!filters.q || r.case.includes(filters.q) || r.question.toLowerCase().includes(filters.q.toLowerCase()))).map(r => ({ case: r.case, variant: r.variant, prompt: promptKey(r.prompt_condition), reasoning: r.reasoning, ...r.semantic })),
    selection: snap.selection ? { originals: snap.selection.originals, variants: snap.selection.variants, variant_counts: snap.selection.variant_counts, exclusions: snap.selection.exclusions?.length ?? null, source: snap.selection.source, manifest_files: snap.selection.manifest_files } : null,
    options: { variants: VARIANTS.filter(v => snap.rows.some(r => r.variant === v)), statuses: [...new Set(snap.rows.map(r => r.status))], tags: [...new Set(snap.rows.flatMap(r => r.tags))].sort() },
    view: query(snap, filters), content_analysis: snap.resultsAnalysis ? null : contentAnalysis(snap, filters),
    model_comparison: snap.resultsAnalysis ? null : modelComparison(snap, filters) };
}
export function exportMarkdown(snap, filters = {}) {
  filters = Object.fromEntries(['model', 'experiment', 'variant', 'prompt', 'reasoning', 'status', 'tags', 'tag_mode', 'q', 'metric', 'paired'].filter(key => filters[key]).map(key => [key, filters[key]]));
  const view = query(snap, filters);
  const { rows } = selected(snap, filters);
  const cells = v => String(v ?? '').replaceAll('|', '\\|').replaceAll('\n', ' ');
  const promptName = value => value === 'unguided' ? 'Unguided Solving' : value === 'guided' ? 'Criteria-Guided Solving' : value;
  const reasoningName = value => value === 'off' ? 'Reasoning OFF' : value === 'on' ? 'Reasoning ON' : value;
  return `# ${snap.id} · 필터된 실험 결과\n\n생성: ${new Date().toISOString()}\n\n필터: ${JSON.stringify(filters)}\n\n분모: ${view.aggregate.total} 요청 / ${view.aggregate.cases} 원문. 의미 평가 점수가 아닙니다.\n\n|모델|유형|프롬프트|추론|요청|형식 통과|숫자 비교|숫자 일치|\n|---|---|---|---|---:|---:|---:|---:|\n${view.groups.map(g => [g.model, g.variant, promptName(g.prompt), reasoningName(g.reasoning), g.total, g.valid, g.numeric_compared, g.numeric_matches].map(cells).join('|')).map(l => `|${l}|`).join('\n')}\n\n문항: ${[...new Set(rows.map(r => r.case))].sort().join(', ')}\n\n출처: 모델별 03-results/results.jsonl, analysis/response-diagnostics.jsonl\n`;
}
