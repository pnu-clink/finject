export const RQ1_METRICS = {
  OV: { label: 'OV · 값 충돌', question: '원본 문제를 잘 푸는 모델이 값의 충돌도 찾아내나요?', target: 'CONFLICT', symbol: 'm/N' },
  OVS: { label: 'OVS · OV 성공 집단의 출처', question: '값의 충돌을 찾은 문항에 출처를 주면 응답이 어떻게 달라지나요?', target: 'CONFLICT', symbol: 'k/m' },
  OVS_all: { label: 'OVS_all · 전체 출처', question: '전체 IC-source 문항에서 CONFLICT를 얼마나 제출했나요?', target: 'CONFLICT', symbol: 'l/N' },
  OR: { label: 'OR · 관계 충돌', question: '원본 문제를 잘 푸는 모델이 관계의 충돌도 찾아내나요?', target: 'CONFLICT', symbol: 'm/N' },
  OE: { label: 'OE · 근거 부족', question: '원본 문제를 잘 푸는 모델이 값이 사라진 상황을 알아보나요?', target: 'INSUFFICIENT_EVIDENCE', symbol: 'g/N' },
  inverse: { label: '3-1 · 역산 성공 (TBD)', question: '원본 값을 역산한 흔적을 근거에서 확인하는 기준은 준비 중입니다.' }
};
const variants = { IC_VALUE_01_BEFORE: 'IC-value · 앞', IC_VALUE_01_AFTER: 'IC-value · 뒤', IC_SOURCE_A_ONLY: 'IC-source · 앞',
  IC_SOURCE_B_ONLY: 'IC-source · 뒤', IC_RELATION_01: 'IC-relation', EA_01: 'EA-01', EA_02: 'EA-02' };
const conditions = [['unguided', 'off'], ['unguided', 'on'], ['guided', 'off'], ['guided', 'on']];
const labels = { ORIGINAL_UNASSESSED: '원본 정답 미평가', RESPONSE_UNAVAILABLE: '응답 미수집·형식 실패',
  CLASSIFICATION_NOT_REQUESTED: '분류 미요구', CLASSIFICATION_UNAVAILABLE: '분류 미기록', VALID: '형식 통과',
  INVALID_RESPONSE: '형식 실패', OUTPUT_TRUNCATED: '출력 잘림', NOT_COLLECTED: '미수집', NOT_RUN: '미실행',
  BATCH_PENDING: 'Batch 처리 중', OBSERVED: '분류 제출 확인' };
const number = value => value.toLocaleString('en-US');
export function rq1Share(count, denominator, rate = denominator ? count / denominator : null) {
  return `${number(count)}/${number(denominator)} · ${rate === null ? '계산 불가' : `${(rate * 100).toFixed(1)}%`}`;
}
export function rq1Selection(data, state = {}) {
  const groups = data.groups || [], metric = Object.hasOwn(RQ1_METRICS, state.rq1_metric) ? state.rq1_metric : 'OV';
  const models = [...new Set(groups.map(row => row.model))];
  const model = models.includes(state.rq1_model) ? state.rq1_model : models[0];
  const sources = [...new Set(groups.filter(row => row.model === model).map(row => row.source))];
  const source = sources.includes(state.rq1_source) ? state.rq1_source : sources[0];
  const rows = groups.filter(row => row.model === model && row.source === source && row.metric === metric);
  const types = Object.keys(variants).filter(type => rows.some(row => row.variant === type));
  const variant = types.includes(state.rq1_variant) ? state.rq1_variant : types[0];
  return { metric, model, source, models, sources, types, variant, groups: rows.filter(row => row.variant === variant) };
}
function node(tag, className = '', text) {
  const element = document.createElement(tag); element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function tabs(entries, selected, choose, label) {
  const strip = node('div', 'rq1-tabs'); strip.setAttribute('aria-label', label);
  for (const [key, title] of entries) {
    const button = node('button', key === selected ? 'active' : '', title); button.type = 'button';
    button.setAttribute('aria-pressed', String(key === selected)); button.addEventListener('click', () => choose(key)); strip.append(button);
  }
  return strip;
}
function selector(label, values, selected, display, choose) {
  const wrapper = node('label', 'rq1-selector'), select = node('select');
  wrapper.append(node('span', '', label)); select.setAttribute('aria-label', label);
  for (const value of values) {
    const option = node('option', '', display(value)); option.value = value; select.append(option);
  }
  select.value = selected; select.addEventListener('change', () => choose(select.value)); wrapper.append(select); return wrapper;
}
function countsLine(title, values, denominator) {
  const line = node('p', 'rq1-breakdown'); line.append(node('strong', '', `${title}: `));
  line.append(Object.entries(values || {}).map(([label, count]) => `${labels[label] || label} ${rq1Share(count, denominator)}`).join(' / ') || '없음');
  return line;
}
function conditionCard(group, metric, condition, openResponse) {
  const card = node('article', 'rq1-condition-card');
  card.append(node('h4', '', condition[0] === 'unguided' ? 'Unguided Solving' : 'Criteria-Guided Solving'),
    node('p', 'rq1-condition-name', `Reasoning ${condition[1].toUpperCase()}`));
  if (!group) { card.append(node('p', 'rq1-empty', '해당 조건은 계획에 없습니다.')); return card; }
  const spec = RQ1_METRICS[metric], denominator = group.denominator;
  const main = metric.startsWith('OVS') ? 'CONFLICT 제출' : `원본 정답 일치 + ${spec.target} 제출`;
  const unrequested = condition[0] === 'unguided';
  const mainValue = unrequested && denominator ? `미판정 · ${group.denominator_symbol}=${number(denominator)}` : rq1Share(group.numerator, denominator, group.rate);
  card.append(node('p', 'rq1-main-count', `${main} (${spec.symbol})`), node('strong', 'rq1-main-value', mainValue));
  if (metric.startsWith('OVS')) card.append(node('p', 'rq1-answerable', unrequested ? 'ANSWERABLE · 분류 미요구' : `ANSWERABLE 제출 ${rq1Share(group.answerable_count, denominator, group.answerable_rate)}`));
  if (condition[0] === 'unguided') card.append(node('p', 'rq1-unrequested', '분류 미요구 · 감지 여부 미판정'));
  const matrix = node('div', `rq1-grid${condition[0] === 'unguided' || !denominator ? ' rq1-unjudged' : ''}`);
  const captions = { 1: '원본 일치 · 제출', 2: '원본 불일치 · 제출', 3: '원본 불일치 · 다른 분류', 4: '원본 일치 · 다른 분류' };
  const details = node('details', 'rq1-cases'), summary = node('summary', '', '문항 확인'), body = node('div', 'rq1-case-rows');
  details.append(summary, body);
  const showEntries = (quadrant, offset = 0) => {
    const entries = (group.entries || []).filter(row => quadrant === undefined || row.quadrant === quadrant);
    summary.textContent = `${quadrant === undefined ? '전체 문항' : quadrant === null ? '미판정' : captions[quadrant]} · ${number(entries.length)}문항`;
    body.replaceChildren();
    for (const row of entries.slice(offset, offset + 20)) {
      const line = node('div', 'rq1-case-row'), link = node('button', 'text-button', row.case);
      link.type = 'button'; link.addEventListener('click', () => openResponse(row));
      line.append(link, node('small', '', row.classification || labels[row.response_status] || row.response_status)); body.append(line);
    }
    if (entries.length > 20) {
      const pager = node('div', 'rq1-case-pager');
      for (const [label, start, disabled] of [['← 이전', offset - 20, offset === 0], ['다음 →', offset + 20, offset + 20 >= entries.length]]) {
        const button = node('button', '', label); button.type = 'button'; button.disabled = disabled;
        button.addEventListener('click', () => showEntries(quadrant, start)); pager.append(button);
      }
      pager.append(node('small', '', `${offset + 1}–${Math.min(offset + 20, entries.length)} / ${entries.length}`)); body.append(pager);
    }
    details.open = true;
  };
  for (const q of [2, 1, 3, 4]) {
    const cell = group.quadrants[q], box = node('button', `rq1-cell rq1-cell-${q}`); box.type = 'button';
    box.disabled = cell.count === 0; box.addEventListener('click', () => showEntries(q));
    box.append(node('small', '', captions[q]), node('strong', '', unrequested && denominator ? `${cell.count}/${denominator} · 미판정` : rq1Share(cell.count, denominator, cell.ratio_of_planned)));
    matrix.append(box);
  }
  card.append(matrix, node('p', 'rq1-x-axis', '← 불일치 | 원본 정답 | 일치 →'),
    node('p', 'rq1-unplaced', `미판정 ${rq1Share(group.unplaced, denominator)}`));
  if (group.unplaced) {
    const button = node('button', 'text-button', '미판정 문항 확인'); button.type = 'button';
    button.addEventListener('click', () => showEntries(null)); card.append(button);
    card.append(countsLine('미판정 사유', group.unplaced_reasons, denominator));
    card.append(countsLine('미판정 응답 상태', group.unplaced_response_statuses, denominator));
    if (group.unplaced_observations?.CLASSIFICATION_NOT_REQUESTED && !group.unplaced_reasons.CLASSIFICATION_NOT_REQUESTED)
      card.append(node('p', 'rq1-breakdown', `분류 미요구 ${rq1Share(group.unplaced_observations.CLASSIFICATION_NOT_REQUESTED, denominator)}`));
  }
  if (group.cohort) {
    const cohort = group.cohort;
    card.append(node('p', 'rq1-cohort', `출처 전체 ${number(cohort.planned_source_responses)} · OV 성공 집단 m=${number(cohort.eligible)} · 제외 ${number(cohort.excluded)} · 집단 판정 대기 ${number(cohort.undetermined)}`));
  }
  if ((group.entries || []).length) { showEntries(undefined); details.open = false; card.append(details); }
  return card;
}

// [EV26.2] Display Python's saved counts; do not assign a semantic-success label.
export function renderRQ1Materials(data, state = {}, choose = () => {}, openResponse = () => {}) {
  const out = node('section', 'panel rq1-materials'); out.setAttribute('aria-label', 'classification 분석 자료');
  out.append(node('h3', '', 'classification 분석 자료'), node('p', 'small muted', '임시 · 원본 정답 일치와 모델의 분류 제출을 비교합니다. 설명·근거의 타당성은 별도 검토 대상입니다.'));
  const selection = rq1Selection(data, state), { metric } = selection;
  out.append(tabs(Object.entries(RQ1_METRICS).map(([key, value]) => [key, value.label]), metric,
    key => choose({ rq1_metric: key, rq1_variant: '' }), 'classification 분석 항목'));
  if (metric === 'inverse') {
    out.append(node('h4', '', '역산 성공 (TBD)'), node('p', 'rq1-empty', RQ1_METRICS.inverse.question)); return out;
  }
  if (data.error || data.status === 'NOT_PREPARED') {
    out.append(node('p', 'rq1-empty', data.error || '이 회차의 classification 집계가 아직 저장되지 않았습니다.'));
    return out;
  }
  const controls = node('div', 'rq1-controls');
  controls.append(selector('classification 모델', selection.models, selection.model, value => value, value => choose({ rq1_model: value, rq1_source: '', rq1_variant: '' })),
    selector('classification 데이터셋', selection.sources, selection.source, value => {
      const parts = value.split('/'); return value === 'NOT_RECORDED' ? '출처 미기록' : parts.slice(-2).join(' / ');
    }, value => choose({ rq1_source: value, rq1_variant: '' })));
  out.append(controls, node('p', 'rq1-question', RQ1_METRICS[metric].question));
  if (!selection.groups.length) { out.append(node('p', 'rq1-empty', '이 모델·데이터셋에는 해당 분석 항목의 계획 문항이 없습니다.')); return out; }
  out.append(tabs(selection.types.map(type => [type, variants[type]]), selection.variant,
    type => choose({ rq1_variant: type }), 'classification 변형 유형'));
  out.append(node('p', 'rq1-axis-note', `가로축: 원본 정답 불일치 ← → 일치 · 세로축: ${RQ1_METRICS[metric].target} 제출 ↑ / 다른 분류 제출 ↓`));
  if (metric === 'OVS') out.append(node('p', 'rq1-axis-note', 'm은 이 출처 유형에 연결된 OV 양쪽 성공 문항 수입니다. 원본 정답 일치가 고정되어 오른쪽 두 칸에만 놓입니다. 집단 판정 대기는 m에 넣지 않습니다.'));
  const cards = node('div', 'rq1-condition-cards');
  for (const condition of conditions) cards.append(conditionCard(selection.groups.find(group => group.prompt_condition === condition[0] && group.reasoning === condition[1]), metric, condition, openResponse));
  out.append(cards, node('p', 'small muted', '각 칸의 비율은 전체 계획 집단을 분모로 유지합니다. 분류 미요구·응답 미수집·형식 실패·원본 미평가는 미판정으로 따로 표시합니다.'));
  return out;
}
