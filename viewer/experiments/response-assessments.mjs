const REVIEW_STATES = [
  ['COMPLETED', '검토 완료', 'Completed'], ['NOT_REVIEWED', '미검토', 'Not reviewed'],
  ['REVIEW_FAILED', '검토 실패', 'Review failed'], ['NOT_REVIEWABLE', '검토 불가', 'Not reviewable'],
  ['SOURCE_MISSING', '입력 원문 없음', 'Source missing']
];
const VERDICTS = [
  ['SUPPORTED', '뒷받침됨', 'Supported'], ['UNSUPPORTED', '뒷받침되지 않음', 'Unsupported'],
  ['UNDETERMINED', '판단 유보', 'Undetermined'], ['NOT_APPLICABLE', '해당 없음', 'Not applicable'],
  ['UNREVIEWED', '미판정 · null', 'Unjudged · null']
];
const FIELDS = [
  ['abstention_reason_validity', '기권 이유의 타당성', 'Abstention reason validity'],
  ['decision_grounding', '최종 답변의 근거', 'Decision grounding']
];

function element(tag, className = '', text) {
  const node = document.createElement(tag); node.className = className;
  if (text !== undefined) node.textContent = String(text); return node;
}
function localized(tag, className, ko, en) {
  const node = element(tag, className, ko);
  globalThis.FinarchI18n?.bindText(node, ko, en); return node;
}
function raw(tag, className, text) {
  const node = element(tag, className, text); node.setAttribute('translate', 'no'); return node;
}
function panel(ko, en, className = '') {
  const node = element('section', `panel response-assessments ${className}`);
  node.append(localized('h3', '', ko, en)); return node;
}
function grid(headers, rows) {
  const wrap = element('div', 'table-wrap'), table = element('table'), head = element('thead'), tr = element('tr'), body = element('tbody');
  for (const label of headers) { const th = element('th'); th.append(label); tr.append(th); }
  head.append(tr);
  for (const cells of rows) {
    const row = element('tr');
    for (const content of cells) { const td = element('td'); td.append(content); row.append(td); }
    body.append(row);
  }
  table.append(head, body); wrap.append(table); return wrap;
}
export function assessmentShare(n, total) {
  return `${n}/${total} · ${total > 0 ? `${(100 * n / total).toFixed(1)}%` : '—'}`;
}
function distribution(counts, total, labels = VERDICTS) {
  const box = element('div', 'assessment-distribution');
  for (const [key, ko, en] of labels) {
    const value = counts?.[key] || 0;
    const line = element('div', `assessment-count assessment-${key.toLowerCase()}${value ? '' : ' is-zero'}`);
    line.append(localized('span', '', ko, en), raw('strong', '', assessmentShare(value, total))); box.append(line);
  }
  return box;
}
function jsonButton(ko, en, value, openValue) {
  if (!openValue) return null;
  const button = localized('button', 'text-button', ko, en); button.type = 'button';
  button.onclick = () => openValue(ko, value); return button;
}
function rqBoundary() {
  return localized('p', 'small muted assessment-boundary',
    'RQ1 원본 정답 × 변형 답변의 적절성: 필요한 통합 집계 자료가 아직 생성되지 않았습니다. 후보 A/B 사분면이나 adaptation_success만으로 최종 RQ1 결과를 표시하지 않습니다.',
    'RQ1 original correctness × variant appropriateness: the required joint aggregation is not available. Candidate A/B quadrants and adaptation_success alone are not the final RQ1 result.');
}

// [EV20.2] Present Python's saved counts, including all missing/failure states.
export function renderAssessmentSummary(data, { variantNames = {}, conditionName, models = [], openValue } = {}) {
  const out = panel('변형 응답별 근거 검토 · A02', 'Response grounding review · A02');
  const summary = data?.response_assessment_summary, coverage = data?.response_assessment_coverage;
  if (!summary || !coverage) {
    out.append(localized('p', 'notice', '판정 자료 없음 · 미실행 또는 기존 V1 결과입니다.', 'No assessment data · not run or a historical V1 result.'), rqBoundary());
    return out;
  }
  const overall = summary.overall, total = overall.planned;
  out.append(localized('p', 'small muted',
    `저장된 A02 검토 계획 ${total}개 · 원본 제외 · 모델 × 7변형 × 풀이 조건 × 추론 설정. 모든 비율의 분모는 해당 행의 계획 수입니다.`,
    `${total} saved A02 planned reviews · ORIGINAL excluded · model × 7 variants × solving instruction × reasoning. Each percentage uses that row's planned count.`));
  const coverageBox = distribution(coverage.review_status, total, REVIEW_STATES);
  coverageBox.classList.add('assessment-coverage'); out.append(coverageBox);
  out.append(grid([localized('span', '', '판정 항목', 'Assessment'), ...VERDICTS.map(([key, ko, en]) => localized('span', '', `${ko} · ${key === 'UNREVIEWED' ? 'null' : key}`, `${en} · ${key === 'UNREVIEWED' ? 'null' : key}`))],
    FIELDS.map(([field, ko, en]) => [localized('strong', '', ko, en), ...VERDICTS.map(([key]) => raw('span', '', assessmentShare(overall[field]?.[key] || 0, total)))])));
  out.append(localized('p', 'small muted assessment-boundary',
    '숫자 응답의 기권 이유는 해당 없음입니다. null 답변도 자동으로 타당한 기권이 되지 않습니다. 판단 유보는 검토 완료 후 결론을 정하지 못한 상태이며, 미판정과 구분합니다.',
    'Abstention reason is not applicable to numeric responses. A null answer is not automatically a valid abstention. Undetermined is a completed review without a resolved verdict, distinct from unjudged.'));
  const modelOrder = [...new Set([...models.map(model => model.key), ...summary.groups.map(group => group.model)])];
  const variantOrder = Object.keys(variantNames);
  const prompt = value => value === 'P0' ? 'unguided' : value === 'P1' ? 'guided' : value;
  const conditionOrder = group => (prompt(group.prompt_condition) === 'guided' ? 2 : 0) + (group.reasoning === 'on' ? 1 : 0);
  for (const model of modelOrder) {
    const groups = summary.groups.filter(group => group.model === model);
    if (!groups.length) continue;
    groups.sort((a, b) => variantOrder.indexOf(a.variant) - variantOrder.indexOf(b.variant) || conditionOrder(a) - conditionOrder(b));
    const details = element('details', 'assessment-model'); details.append(raw('summary', '', model));
    let built = false;
    const build = () => {
      if (built || !details.open) return; built = true;
      details.append(grid([
        localized('span', '', '유형', 'Variant'), localized('span', '', '풀이 · 추론', 'Solving · reasoning'),
        localized('span', '', '계획', 'Planned'), localized('span', '', '검토 상태', 'Review status'),
        ...FIELDS.map(([, ko, en]) => localized('span', '', ko, en))
      ], groups.map(group => [
        raw('strong', '', variantNames[group.variant] || group.variant),
        raw('span', '', conditionName ? conditionName(group.prompt_condition, group.reasoning) : `${group.prompt_condition} · Reasoning ${group.reasoning.toUpperCase()}`),
        raw('span', '', group.planned), distribution(group.review_status, group.planned, REVIEW_STATES),
        ...FIELDS.map(([field]) => distribution(group[field], group.planned))
      ])));
    };
    details.addEventListener('toggle', build); out.append(details);
  }
  const json = jsonButton('판정 요약 JSON', 'Assessment summary JSON', { summary, coverage }, openValue);
  if (json) out.append(json);
  out.append(localized('p', 'small muted assessment-boundary',
    '분석 LLM의 저장 판정이며 사람의 의미 정답 확정을 뜻하지 않습니다. 관찰 글이 0개여도 응답별 판정 완료 여부는 위 수치로 따로 확인합니다.',
    'Saved analysis LLM judgments, not human-verified semantic gold. Zero pattern observations do not imply that response reviews are incomplete.'), rqBoundary());
  return out;
}

export function assessmentCitationSource(citation, request, response) {
  if (citation.source === 'question' || citation.source === 'context') return request?.input?.[citation.source];
  if (citation.source === 'explanation') return response?.explanation;
  if (citation.source === 'evidence' && Array.isArray(response?.evidence)) return response.evidence[citation.evidence_index];
  return undefined;
}
function citationView(citation, responseRecord) {
  const details = element('details', 'assessment-citation');
  const source = citation.source === 'evidence' ? `evidence[${citation.evidence_index}]` : citation.source;
  details.append(localized('summary', '', `${source} · 인용과 실제 원문`, `${source} · quote and actual source`), raw('blockquote', '', citation.quote));
  const text = assessmentCitationSource(citation, responseRecord.request, responseRecord.response);
  const at = typeof text === 'string' ? text.indexOf(citation.quote) : -1;
  if (at < 0) {
    details.append(localized('p', 'notice danger', '해당 응답의 실제 원문에서 인용을 확인할 수 없습니다. 다른 조건의 원문으로 대체하지 않습니다.', 'The quote cannot be found in this response’s actual source. No other condition is substituted.'));
  } else {
    const original = raw('div', 'assessment-source source-text');
    original.append(document.createTextNode(text.slice(0, at)), raw('mark', '', citation.quote), document.createTextNode(text.slice(at + citation.quote.length)));
    details.append(original);
  }
  return details;
}

// [EV20.3] Keep each judge reason and citation attached to its exact response_id.
export function renderResponseAssessment(record, { openValue } = {}) {
  const out = element('div', 'response-section response-assessments');
  out.append(localized('h4', '', '분석 LLM의 응답 검토 · A02', 'Analysis LLM response review · A02'));
  if (!record.response_assessment) {
    out.append(localized('p', 'small muted',
      record.response_assessment_state === 'ORIGINAL_EXCLUDED' ? '원본 응답은 이 두 판정의 대상에서 제외됩니다.' : record.response_assessment_state === 'AVAILABLE' ? '이 응답의 저장 판정 없음 · 미검토' : '판정 자료 없음 · 미실행 또는 기존 V1 결과입니다.',
      record.response_assessment_state === 'ORIGINAL_EXCLUDED' ? 'ORIGINAL responses are excluded from these two assessments.' : record.response_assessment_state === 'AVAILABLE' ? 'No saved assessment for this response · not reviewed' : 'No assessment data · not run or a historical V1 result.'));
    return out;
  }
  const assessment = record.response_assessment, status = REVIEW_STATES.find(([key]) => key === assessment.review_status);
  out.append(localized('strong', `assessment-status assessment-${assessment.review_status.toLowerCase()}`, `${status?.[1] || assessment.review_status} · ${assessment.review_status}`, `${status?.[2] || assessment.review_status} · ${assessment.review_status}`), raw('p', 'small muted', `response_id: ${assessment.response_id}`));
  for (const [field, ko, en] of FIELDS) {
    const judgment = assessment[field], value = judgment.verdict ?? 'UNREVIEWED', label = VERDICTS.find(([key]) => key === value);
    const box = element('div', `assessment-judgment assessment-${value.toLowerCase()}`);
    box.append(localized('h4', '', ko, en), localized('strong', '', `${label?.[1] || value} · ${judgment.verdict ?? 'null'}`, `${label?.[2] || value} · ${judgment.verdict ?? 'null'}`));
    const reason = raw('p', 'prose', judgment.reason); reason.lang = 'en'; box.append(reason);
    for (const citation of judgment.citations) box.append(citationView(citation, record));
    out.append(box);
  }
  const adaptation = assessment.adaptation_success === true ? '성공 · true' : assessment.adaptation_success === false ? '실패 · false' : '미확정 · null';
  const adaptationEn = assessment.adaptation_success === true ? 'Success · true' : assessment.adaptation_success === false ? 'Failure · false' : 'Unresolved · null';
  out.append(localized('p', 'small muted assessment-boundary', `저장된 adaptation_success: ${adaptation} · 최종 RQ1 사분면 집계와 구분합니다.`, `Saved adaptation_success: ${adaptationEn} · distinct from the final RQ1 joint quadrant.`));
  const json = jsonButton('응답 판정 JSON', 'Response assessment JSON', assessment, openValue);
  if (json) out.append(json);
  return out;
}
