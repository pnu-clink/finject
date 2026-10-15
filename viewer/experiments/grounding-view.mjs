import { GROUNDING_VERDICTS, GROUNDING_REVIEWS } from './grounding-model.mjs';

const types = { IC_VALUE_01_BEFORE: '01 · IC-value · 앞', IC_VALUE_01_AFTER: '02 · IC-value · 뒤',
  IC_SOURCE_A_ONLY: '03 · IC-source · 앞', IC_SOURCE_B_ONLY: '04 · IC-source · 뒤',
  IC_RELATION_01: '05 · IC-relation', EA_01: '06 · EA-01', EA_02: '07 · EA-02' };
const conditions = [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']];
const verdicts = { SUPPORTED: '뒷받침됨', UNSUPPORTED: '뒷받침되지 않음', UNDETERMINED: '판단 유보',
  NOT_APPLICABLE: '해당 없음', UNREVIEWED: '미판정' };
const statuses = { COMPLETED: '검토 완료', NOT_REVIEWED: '미검토', REVIEW_FAILED: '검토 실패',
  NOT_REVIEWABLE: '검토 불가', SOURCE_MISSING: '입력 원문 없음', ORIGINAL_NUMERIC_UNASSESSED: '원본 수치 미평가',
  VARIANT_UNAVAILABLE: '변형 응답 미수집·형식 실패', UNDETERMINED: '두 판정으로 결론 미확정', VALID: '형식 통과' };
const captions = { 1: '원본 일치 · 근거 뒷받침됨', 2: '원본 불일치 · 근거 뒷받침됨',
  3: '원본 불일치 · 근거 뒷받침 안 됨', 4: '원본 일치 · 근거 뒷받침 안 됨' };
const number = value => value.toLocaleString('en-US');
export function groundingShare(n, total) { return `${number(n)}/${number(total)} · ${total ? `${(100*n/total).toFixed(1)}%` : '계산 불가'}`; }
export function groundingSelection(data, state = {}) {
  const groups = data.groups || [], models = [...new Set(groups.map(row => row.model))];
  const model = models.includes(state.ground_model) ? state.ground_model : models[0];
  const sources = [...new Set(groups.filter(row => row.model === model).map(row => row.source_type))];
  const source = sources.includes(state.ground_source) ? state.ground_source : sources[0];
  const scoped = groups.filter(row => row.model === model && row.source_type === source);
  const variants = Object.keys(types).filter(type => scoped.some(row => row.variant === type));
  const variant = variants.includes(state.ground_variant) ? state.ground_variant : variants[0];
  return { model, source, variant, models, sources, variants, groups: scoped.filter(row => row.variant === variant) };
}
// A distribution click uses its displayed cohort, not intersecting verdict filters.
export function groundingDrilldown(group, field, value, original = 'all') {
  return { ground_view: 'list', ground_model: group.model, ground_source: group.source_type,
    ground_variant: group.variant, ground_prompt: group.prompt_condition, ground_reasoning: group.reasoning,
    ground_original: original, ground_abstention: '', ground_decision: '', ground_review: '', [field]: value };
}
function node(tag, className = '', text) {
  const element = document.createElement(tag); element.className = className;
  if (text !== undefined) element.textContent = String(text); return element;
}
function local(tag, className, ko, en) {
  const element = node(tag, className, ko); globalThis.FinarchI18n?.bindText(element, ko, en); return element;
}
function raw(tag, className, text) { const element = node(tag, className, text); element.setAttribute('translate', 'no'); return element; }
function button(text, callback, className = '') {
  const element = node('button', className, text); element.type = 'button'; element.addEventListener('click', callback); return element;
}
function selector(label, entries, selected, choose) {
  const wrapper = node('label', 'grounding-selector'), select = node('select');
  wrapper.append(node('span', '', label)); select.setAttribute('aria-label', label);
  for (const [value, title] of entries) { const option = node('option', '', title); option.value = value; select.append(option); }
  select.value = selected || ''; select.addEventListener('change', () => choose(select.value)); wrapper.append(select); return wrapper;
}
function distribution(title, field, keys, names, counts, total, choose) {
  const section = node('div', 'grounding-distribution'); section.append(node('strong', '', title));
  for (const key of keys) {
    const count = counts?.[key] || 0, entry = button('', () => choose({ [field]: key }), `grounding-verdict grounding-${key.toLowerCase()}`);
    entry.disabled = count === 0; entry.append(node('span', '', `${names[key]} · ${key}`), raw('b', '', groundingShare(count, total))); section.append(entry);
  }
  return section;
}
function responseBlock(pair, original, record, actions) {
  const out = node('section', 'grounding-response'), title = original ? '원본 응답' : '변형 응답';
  const header = node('div', 'grounding-response-header'), link = button('E02 문항 비교 ↗', () => actions.openResponse(pair, original), 'text-button');
  link.disabled = !record.trial_id; header.append(node('h5', '', title), link); out.append(header);
  out.append(raw('p', 'small muted', `${record.model} · ${record.trial_id || '요청 없음'} · ${statuses[record.status] || record.status}`));
  if (record.response) {
    out.append(raw('strong', 'grounding-answer', record.response.answer ?? 'null'));
    for (const [field, label] of [['explanation', 'Explanation'], ['evidence', 'Evidence']]) {
      out.append(node('h6', '', label), raw('div', 'prose', Array.isArray(record.response[field]) ? record.response[field].join('\n') : record.response[field] || '미기록'));
    }
    out.append(button('응답 JSON', () => actions.openValue(title, record.response), 'text-button'));
  } else out.append(node('p', 'notice', '저장된 응답 본문이 없습니다.'));
  const request = node('details', 'grounding-request'); request.append(node('summary', '', '이 응답의 실제 입력 Q/C'));
  request.append(raw('p', 'prose', record.request?.input?.question || '질문 미기록'), raw('div', 'source-text', record.request?.input?.context || '본문 미기록'));
  out.append(request);
  if (!original) out.append(actions.renderAssessment(record));
  return out;
}
function pairDetails(pair, actions) {
  const detail = node('details', 'grounding-pair'), summary = node('summary');
  summary.append(raw('strong', '', pair.case), node('span', '', pair.quadrant ? `${['','①','②','③','④'][pair.quadrant]} ${captions[pair.quadrant]}` : statuses[pair.placement_status] || pair.placement_status));
  summary.append(node('small', '', `${pair.model} · ${pair.prompt_condition === 'unguided' ? 'Unguided' : 'Criteria-Guided'} · Reasoning ${pair.reasoning.toUpperCase()}`));
  summary.append(node('small', '', `유보 이유: ${verdicts[pair.abstention_reason_validity]} · 답·유보의 근거: ${verdicts[pair.decision_grounding]} · ${statuses[pair.review_status]}`));
  detail.append(summary); let loading = false, loaded = false, previousBody;
  detail.addEventListener('toggle', async () => {
    if (!detail.open || loading || loaded) return; loading = true;
    previousBody?.remove();
    const body = node('div', 'grounding-pair-body'); previousBody = body;
    body.append(node('p', '', '원본과 변형의 정확한 응답을 읽는 중입니다.')); detail.append(body);
    try {
      const records = await Promise.all([actions.loadResponse(pair, true), actions.loadResponse(pair, false)]);
      if (!detail.isConnected) return;
      body.replaceChildren(...records.map((record, index) => responseBlock(pair, index === 0, record, actions))); loaded = true;
    } catch (error) {
      if (error.name !== 'AbortError') body.replaceChildren(node('p', 'notice danger', error.message));
    } finally { loading = false; }
  });
  return detail;
}
function caseList(group, filters, actions) {
  const details = node('details', 'grounding-cases'), summary = node('summary', '', '문항별 원본·변형·두 판정 확인');
  const body = node('div', 'grounding-case-list'); details.append(summary, body);
  let category = '', offset = 0, search = '', loading = false, started = false, queued = false;
  const load = async () => {
    if (loading) { queued = true; return; } loading = true;
    const requested = { category, offset, search };
    summary.textContent = `${category === 'unplaced' ? '미배치' : category ? captions[category] : '전체'} 문항 · 읽는 중`;
    try {
      const page = await actions.loadPage({ ...filters, model: group.model, source_type: group.source_type, variant: group.variant,
        prompt: group.prompt_condition, reasoning: group.reasoning, quadrant: category, case: search, offset: String(offset), mode: 'pairs' });
      if (!details.isConnected || requested.category !== category || requested.offset !== offset || requested.search !== search) return;
      summary.textContent = `${category === 'unplaced' ? '미배치' : category ? captions[category] : '전체'} · ${number(page.total)}문항 / 계획 ${number(page.planned_pairs)}`;
      const find = node('div', 'grounding-pager'), input = node('input'); input.type = 'search'; input.value = search; input.placeholder = 'test-0008'; input.setAttribute('aria-label', '근거 타당성 문항 검색');
      const apply = () => { search = input.value.trim(); offset = 0; load(); };
      input.addEventListener('keydown', event => { if (event.key === 'Enter') apply(); });
      find.append(input, button('찾기', apply)); body.replaceChildren(find);
      for (const pair of page.pairs) body.append(pairDetails(pair, actions));
      if (!page.pairs.length) body.append(node('p', 'small muted', '해당 문항이 없습니다.'));
      const pager = node('div', 'grounding-pager');
      for (const [title, start, disabled] of [['← 이전', page.offset - page.page_size, page.offset === 0], ['다음 →', page.offset + page.page_size, page.offset + page.page_size >= page.total]]) {
        const change = button(title, () => { offset = start; load(); }); change.disabled = disabled; pager.append(change);
      }
      pager.append(node('small', '', `${page.total ? page.offset + 1 : 0}–${Math.min(page.offset + page.page_size, page.total)} / ${number(page.total)}`)); body.append(pager); started = true;
    } catch (error) { if (error.name !== 'AbortError') body.replaceChildren(node('p', 'notice danger', error.message)); }
    finally { loading = false; if (queued && details.isConnected) { queued = false; load(); } }
  };
  details.addEventListener('toggle', () => { if (details.open && !started) load(); });
  return { element: details, show: selected => { category = selected == null ? '' : String(selected); offset = 0; search = ''; details.open = true; load(); } };
}
function conditionCard(group, condition, filters, actions) {
  const card = node('article', 'grounding-condition-card');
  card.append(node('h4', '', condition[0] === 'unguided' ? 'Unguided Solving' : 'Criteria-Guided Solving'), node('p', 'grounding-condition-name', `Reasoning ${condition[1].toUpperCase()}`));
  if (!group) { card.append(node('p', 'notice', '계획 0 · 0/0 · 계산 불가')); return card; }
  const N = group.planned_pairs;
  card.append(node('p', 'small muted', `원본 선택 ${number(group.original_pairs)}건 · 원본 미평가 ${number(group.original_unevaluated)}건(전체에 포함)`));
  card.append(node('p', 'grounding-plan', `전체 계획 ${number(N)} · 배치 ${number(group.placed_pairs)} · 미배치 ${number(group.unplaced_pairs)}`));
  if (filters.abstention || filters.decision || filters.review || (filters.original && filters.original !== 'all')) card.append(node('p', 'grounding-filtered', `필터 결과 ${groundingShare(group.filtered_pairs, N)} · 배치 ${number(group.filtered_placed)} · 미배치 ${number(group.filtered_unplaced)}`));
  card.append(node('p', 'grounding-axis', '↑ 변형의 답·유보 근거가 뒷받침됨'));
  const matrix = node('div', 'grounding-grid');
  for (const q of [2,1,3,4]) {
    const cell = group.quadrants[q], box = button('', () => actions.showList(group, q), `grounding-cell grounding-cell-${q}`); box.disabled = !cell.count;
    box.append(node('small', '', `${['','①','②','③','④'][q]} ${captions[q]}`), raw('strong', '', groundingShare(cell.count, N))); matrix.append(box);
  }
  card.append(matrix, node('p', 'grounding-axis', '← 원본 수치 불일치 | 일치 →'), node('p', 'grounding-axis', '↓ 변형의 답·유보 근거가 뒷받침 안 됨'));
  const unplaced = button(`미배치 ${groundingShare(group.filtered_unplaced, N)}`, () => actions.showList(group, 'unplaced'), 'grounding-unplaced'); unplaced.disabled = !group.filtered_unplaced; card.append(unplaced);
  if (group.filtered_unplaced) card.append(node('p', 'grounding-reasons', Object.entries(group.unplaced_reasons).map(([reason, count]) => `${statuses[reason] || reason} ${number(count)}`).join(' / ')));
  const breakdown = node('details', 'grounding-breakdown'); breakdown.append(node('summary', '', filters.original && filters.original !== 'all' ? '선택한 원본 집단의 두 판정·검토 상태' : '계획 전체의 두 판정·검토 상태'));
  breakdown.append(distribution('유보 이유의 타당성', 'ground_abstention', GROUNDING_VERDICTS, verdicts, group.abstention_reason_validity, N, patch => actions.openVerdict(group, patch)),
    distribution('답·유보 결정의 근거', 'ground_decision', GROUNDING_VERDICTS, verdicts, group.decision_grounding, N, patch => actions.openVerdict(group, patch)),
    distribution('검토 상태', 'ground_review', GROUNDING_REVIEWS, statuses, group.review_status, N, patch => actions.openVerdict(group, patch)));
  card.append(breakdown, button('조건 전체 문항 확인', () => actions.showList(group), 'text-button')); return card;
}

// [EV27.2] Plot saved grounding verdicts, including Unguided classification=null.
export function renderGrounding(data, state = {}, actions) {
  const out = node('section', 'panel grounding-view'); out.setAttribute('aria-label', '근거 타당성 사분면');
  out.append(local('h3', '', '근거 타당성 · 원본과 변형', 'Grounding assessment · original and variant'),
    local('p', 'small muted', 'A03 화면 · 자료는 A02의 저장된 응답 판정입니다. 새 모델 호출이나 의미 정답 판정을 하지 않습니다.', 'A03 display · saved A02 response assessments. No new model call or semantic gold annotation.'));
  if (data.error || data.status === 'NOT_PREPARED') {
    out.append(node('p', 'notice', data.error || (data.assessments_available ? 'A02 판정은 있으나 기존 대응쌍 집계가 없습니다. 기존 pair 집계가 필요합니다.' : '이 회차에는 A02 근거 판정과 대응쌍 집계가 저장되지 않았습니다.'))); return out;
  }
  const navigation = node('div', 'grounding-types'); navigation.setAttribute('aria-label', '근거 타당성 보기');
  for (const [key, title] of [['quadrants', '사분면'], ['list', '판정 목록']]) {
    const tab = button(title, () => actions.choose({ ground_view: key }), (state.ground_view || 'quadrants') === key ? 'active' : '');
    tab.setAttribute('aria-pressed', String((state.ground_view || 'quadrants') === key)); navigation.append(tab);
  }
  out.append(navigation);
  const selection = groundingSelection(data, state), filters = { original: state.ground_original || 'all', abstention: state.ground_abstention || '', decision: state.ground_decision || '', review: state.ground_review || '' };
  const controls = node('div', 'grounding-controls');
  controls.append(selector('근거 모델', selection.models.map(value => [value, value]), selection.model, value => actions.choose({ ground_model: value, ground_source: '', ground_variant: '' })),
    selector('근거 데이터셋', selection.sources.map(value => [value, value]), selection.source, value => actions.choose({ ground_source: value, ground_variant: '' })));
  const verdictOptions = [['', '판정 전체'], ...GROUNDING_VERDICTS.map(key => [key, `${verdicts[key]} · ${key}`])];
  controls.append(selector('Original 정답 여부', [['all', '전체'], ['correct', '맞음'], ['incorrect', '틀림']], filters.original, value => actions.choose({ ground_original: value })),
    selector('유보 이유', verdictOptions, filters.abstention, value => actions.choose({ ground_abstention: value })),
    selector('답·유보의 근거', verdictOptions, filters.decision, value => actions.choose({ ground_decision: value })),
    selector('근거 검토 상태', [['', '검토 전체'], ...GROUNDING_REVIEWS.map(key => [key, `${statuses[key]} · ${key}`])], filters.review, value => actions.choose({ ground_review: value })),
    button('판정 필터 초기화', () => actions.choose({ ground_original: 'all', ground_abstention: '', ground_decision: '', ground_review: '' }), 'text-button'));
  if (state.ground_view === 'list') controls.append(
    selector('목록 풀이 조건', [['', '전체'], ['unguided', 'Unguided Solving'], ['guided', 'Criteria-Guided Solving']], state.ground_prompt, value => actions.choose({ ground_prompt: value })),
    selector('목록 추론 설정', [['', '전체'], ['off', 'Reasoning OFF'], ['on', 'Reasoning ON']], state.ground_reasoning, value => actions.choose({ ground_reasoning: value })));
  out.append(controls);
  const tabs = node('div', 'grounding-types'); tabs.setAttribute('aria-label', '근거 타당성 변형 유형');
  for (const type of selection.variants) { const tab = button(types[type], () => actions.choose({ ground_variant: type }), type === selection.variant ? 'active' : ''); tab.setAttribute('aria-pressed', String(type === selection.variant)); tabs.append(tab); }
  if (state.ground_view === 'list') {
    out.append(tabs, node('p', 'small muted', '선택한 조건과 판정에 해당하는 문항입니다. 문항을 펼치면 두 판정의 이유·인용과 실제 응답을 확인합니다.'));
    const list = caseList({ model: selection.model, source_type: selection.source, variant: selection.variant,
      prompt_condition: state.ground_prompt || '', reasoning: state.ground_reasoning || '' }, filters, actions);
    out.append(list.element); list.element.open = true; return out;
  }
  out.append(tabs, node('p', 'grounding-scope', '가로축은 원본의 저장된 숫자 정답 일치 여부입니다. 단위·설명 전체의 의미 정답은 아닙니다. 세로축은 A02의 답·유보 근거 판정입니다.'));
  const cards = node('div', 'grounding-condition-cards'), lists = node('div', 'grounding-selected-cases');
  const scopedActions = { ...actions, openVerdict: (group, patch) => {
    const [field, value] = Object.entries(patch)[0]; actions.choose(groundingDrilldown(group, field, value, filters.original));
  }, showList: (group, category) => {
    const list = caseList(group, filters, actions);
    lists.replaceChildren(node('h4', '', `${types[group.variant]} · ${group.prompt_condition === 'unguided' ? 'Unguided Solving' : 'Criteria-Guided Solving'} · Reasoning ${group.reasoning.toUpperCase()}`), list.element);
    list.show(category); lists.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } };
  for (const condition of conditions) cards.append(conditionCard(selection.groups.find(group => group.prompt_condition === condition[0] && group.reasoning === condition[1]), condition, filters, scopedActions));
  out.append(cards, node('p', 'small muted', '각 비율의 분모는 조건별 계획 전체입니다. 필터를 선택해도 분모는 줄이지 않습니다. 두 판정·검토 상태 분포에는 Original 선택이 적용됩니다. 전체를 선택하면 같은 모델·데이터셋·유형·조건의 A02 분포와 같습니다. IC-source도 해당 유형 전체를 사용하며 기존 OV 성공 집단의 OVS와 구분합니다.'), lists);
  const rules = node('details', 'grounding-rules'); rules.append(node('summary', '', '두 판정을 합치는 기준과 해석 범위'));
  rules.append(node('p', '', '숫자 답은 decision_grounding으로 구분합니다. abstention_reason_validity의 NOT_APPLICABLE(해당 없음)은 실패가 아닙니다. null 답은 두 판정이 모두 SUPPORTED이면 위쪽, 하나라도 UNSUPPORTED이면 아래쪽입니다. 그 밖의 UNDETERMINED나 미검토·검토 실패는 사분면 밖에 둡니다.'),
    node('p', '', 'UNDETERMINED는 분석 LLM의 판단 유보입니다. 문제풀이 모델의 classification=UNRESOLVED와 다른 항목입니다. 저장된 LLM 판정은 사람의 의미 정답 확정이나 답변 가능성 gold가 아니므로 기권 TP/FP/FN/TN으로 해석하지 않습니다.'),
    node('p', 'small muted', `전체 회차 A02 검토: ${Object.entries(data.review_coverage || {}).map(([key, count]) => `${statuses[key] || key} ${number(count)}`).join(' / ') || '미기록'}`));
  out.append(rules); return out;
}
