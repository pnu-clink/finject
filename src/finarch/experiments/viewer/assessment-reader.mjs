import { createHash } from 'node:crypto';

export const ASSESSMENT_FILES = [
  'response-assessments.jsonl', 'response-assessment-summary.json', 'response-assessment-coverage.json'
].map(name => `02_analysis/02_comparison/${name}`);
const fields = ['abstention_reason_validity', 'decision_grounding'];
const statuses = ['COMPLETED', 'NOT_REVIEWED', 'REVIEW_FAILED', 'NOT_REVIEWABLE', 'SOURCE_MISSING'];
const verdicts = ['SUPPORTED', 'UNSUPPORTED', 'UNDETERMINED', 'NOT_APPLICABLE', null];
const dimensions = ['model', 'variant', 'prompt_condition', 'reasoning'];
const groupKey = row => JSON.stringify(dimensions.map(key => row[key]));
export const responseFingerprint = value => createHash('sha256').update(JSON.stringify(value ?? null, (_, item) =>
  item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)).digest('hex');
const tally = (rows, pick) => rows.reduce((counts, row) => {
  const value = pick(row); counts[value] = (counts[value] || 0) + 1; return counts;
}, {});

// [EV20.1] Check saved file consistency; never create or reinterpret verdicts.
export function readAssessments(content, summary, coverage, responses, fail) {
  if (content === null && summary === null && coverage === null) return null;
  const bad = message => { throw fail(`A02 응답 판정: ${message}`, 503); };
  if (content === null || !summary || !coverage) bad('세 파일의 저장이 완료되지 않았습니다.');
  if (summary.rubric_version !== 'ResponseGroundingV1') bad('지원하지 않는 판정 기준 버전입니다.');
  const digest = createHash('sha256').update(content).digest('hex');
  if (summary.response_assessments_sha256 !== digest || coverage.response_assessments_sha256 !== digest) bad('판정 원기록과 요약·완료율의 버전이 다릅니다.');
  let records;
  try { records = content.split('\n').filter(line => line.trim()).map(line => JSON.parse(line)); }
  catch { bad('판정 JSONL을 읽지 못했습니다.'); }
  const source = new Map(responses.map(row => [row.response_id, row])), byResponse = new Map(), groups = new Map();
  for (const row of records) {
    const original = source.get(row?.response_id);
    if (!original || original.variant === 'ORIGINAL' || byResponse.has(row.response_id)) bad('실제 변형 응답에 없는 ID 또는 중복 ID입니다.');
    if ([...dimensions, 'case', 'item_id'].some(key => row[key] !== original[key]) || row.response_status !== original.status) bad('판정과 문제풀이 응답의 연결 정보가 다릅니다.');
    if (!statuses.includes(row.review_status) || ![true, false, null].includes(row.adaptation_success)) bad('검토 상태 또는 적응 판정이 올바르지 않습니다.');
    if (row.review_status !== 'COMPLETED' && row.adaptation_success !== null) bad('미완료 검토를 적응 성공·실패로 표시할 수 없습니다.');
    for (const field of fields) {
      const judgment = row[field];
      if (!judgment || !verdicts.includes(judgment.verdict) || typeof judgment.reason !== 'string' || !judgment.reason.trim() || !Array.isArray(judgment.citations)) bad('두 판정의 값·이유·인용이 올바르지 않습니다.');
      if (row.review_status !== 'COMPLETED' && (judgment.verdict !== null || judgment.citations.length)) bad('미완료 판정에는 verdict나 인용을 붙일 수 없습니다.');
      if (row.review_status === 'COMPLETED' && (judgment.verdict === null || (field === 'decision_grounding' && judgment.verdict === 'NOT_APPLICABLE'))) bad('완료된 판정의 적용 대상이 올바르지 않습니다.');
      if (row.review_status === 'COMPLETED' && field === 'abstention_reason_validity'
          && ((original.response?.answer != null) !== (judgment.verdict === 'NOT_APPLICABLE'))) bad('숫자/null 응답과 기권 이유의 적용 대상이 다릅니다.');
      for (const citation of judgment.citations) {
        if (!['question', 'context', 'explanation', 'evidence'].includes(citation?.source)
            || typeof citation.quote !== 'string' || !citation.quote
            || (citation.source === 'evidence' ? !Number.isInteger(citation.evidence_index) || citation.evidence_index < 0 : citation.evidence_index !== null)) bad('인용의 원문 위치가 올바르지 않습니다.');
      }
    }
    byResponse.set(row.response_id, row);
    const key = groupKey(row);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const matchCounts = (saved, expected) => {
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return false;
    return Object.entries(saved).every(([key, n]) => Number.isSafeInteger(n) && n >= 0 && n === (expected[key] || 0))
      && Object.entries(expected).every(([key, n]) => saved[key] === n);
  };
  const checkCounts = (saved, rows) => {
    if (!saved || saved.planned !== rows.length || !matchCounts(saved.review_status, tally(rows, row => row.review_status))) bad('계획 수·검토 상태 집계가 원기록과 다릅니다.');
    for (const field of fields) if (!matchCounts(saved[field], tally(rows, row => row[field].verdict || 'UNREVIEWED'))) bad('판정 분포 집계가 원기록과 다릅니다.');
    if (!matchCounts(saved.adaptation_outcome, tally(rows, row => row.adaptation_success === true ? 'SUCCESS' : row.adaptation_success === false ? 'FAILURE' : 'UNDETERMINED_OR_UNREVIEWED'))) bad('적응 판정 집계가 원기록과 다릅니다.');
  };
  checkCounts(summary.overall, records);
  if (!Array.isArray(summary.groups) || summary.groups.length !== groups.size) bad('조건별 집계에 누락·중복이 있습니다.');
  const seen = new Set();
  for (const group of summary.groups) {
    const key = groupKey(group);
    if (!groups.has(key) || seen.has(key)) bad('조건별 집계가 실제 판정에 연결되지 않습니다.');
    seen.add(key); checkCounts(group, groups.get(key));
  }
  if (coverage.planned !== records.length || !matchCounts(coverage.review_status, summary.overall.review_status)) bad('완료율 집계가 판정 원기록과 다릅니다.');
  const covered = new Set();
  if (!coverage.response_ids_by_status || typeof coverage.response_ids_by_status !== 'object') bad('완료율의 응답 ID가 없습니다.');
  for (const [status, ids] of Object.entries(coverage.response_ids_by_status)) {
    if (!statuses.includes(status) || !Array.isArray(ids) || ids.length !== (coverage.review_status[status] || 0)) bad('완료율의 상태별 ID 수가 다릅니다.');
    for (const id of ids) {
      if (covered.has(id) || byResponse.get(id)?.review_status !== status) bad('완료율에 누락·중복 또는 잘못 연결된 응답이 있습니다.');
      covered.add(id);
    }
  }
  if (covered.size !== records.length) bad('완료율에 판정 응답이 누락되었습니다.');
  const responseFingerprints = new Map(records.filter(row => row.review_status === 'COMPLETED').map(row => [row.response_id, responseFingerprint(source.get(row.response_id).response)]));
  return { summary, coverage, byResponse, responseFingerprints };
}
