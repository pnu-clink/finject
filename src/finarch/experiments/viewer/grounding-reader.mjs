import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
export const GROUNDING_FILES = ['summary.json', 'pairs.jsonl'].map(name => `02_analysis/02_comparison/pair-outcomes/${name}`);
const groupFields = ['model', 'source_type', 'prompt_condition', 'reasoning', 'variant', 'answerability'];
const keyOf = row => JSON.stringify(groupFields.map(key => row[key]));
const prompt = value => value === 'P0' ? 'unguided' : value === 'P1' ? 'guided' : value;

// [EV27.1] Verify the existing A02 combination; never create a new judge verdict.
export function savedGroundingOutcome(review, response) {
  if (!review || review.review_status !== 'COMPLETED') return null;
  const verdicts = [review.decision_grounding.verdict];
  if (response?.answer == null) verdicts.push(review.abstention_reason_validity.verdict);
  if (verdicts.includes('UNSUPPORTED')) return false;
  return verdicts.every(value => value === 'SUPPORTED') ? true : null;
}
export function validateGroundingPairs(summary, pairs, snap, fail) {
  const bad = message => { throw fail(`근거 타당성: ${message}`, 503); };
  if (summary.schema_version !== 'RQ1PairOutcomeV2' || summary.run_id !== snap.id || !Array.isArray(summary.types)) bad('저장 pair 계약 또는 회차가 다릅니다.');
  const planned = new Map(snap.rows.map(row => [`${row.model}:${row.trial_id}`, row]));
  const seen = new Set(), byType = new Map(), output = [];
  for (const pair of pairs) {
    const key = `${pair.model}:${pair.variant_trial_id}`, changed = planned.get(key), meta = snap.privateItems.get(pair.variant_item_id);
    const originalKey = `${pair.model}:${pair.original_trial_id}`, original = planned.get(originalKey);
    if (!changed || seen.has(key) || changed.item_id !== pair.variant_item_id || changed.variant !== pair.variant || changed.case !== pair.case
        || prompt(changed.prompt_condition) !== prompt(pair.prompt_condition) || changed.reasoning !== pair.reasoning
        || changed.status !== pair.variant_status || meta?.original_item_id !== pair.original_item_id) bad('변형 요청·실제 부모·상태 연결이 다릅니다.');
    seen.add(key);
    if (pair.original_trial_id !== null && (!original || original.variant !== 'ORIGINAL' || original.item_id !== pair.original_item_id || original.case !== pair.case
        || prompt(original.prompt_condition) !== prompt(pair.prompt_condition) || original.reasoning !== pair.reasoning
        || original.status !== pair.original_status)) bad('다른 원본 또는 조건의 성적을 연결할 수 없습니다.');
    const source = snap.privateItems.get(pair.original_item_id)?.generated_metadata?.provenance?.dataset || 'NOT_RECORDED';
    if (pair.source_type !== source) bad('데이터 출처가 원본과 다릅니다.');
    const numeric = original?.diagnostic?.numeric_comparison || original?.checks?.numeric_comparison;
    const x = original?.status !== 'VALID' ? null : typeof numeric?.matches === 'boolean' ? numeric.matches
      : original?.checks?.numeric_answer_present === false ? false : null;
    if (pair.original_correctness !== x) bad('원본 축이 저장된 수치 비교와 다릅니다.');
    const responseId = snap.responseIdsByTrial.get(key), review = snap.responseAssessments?.byResponse.get(responseId);
    const solver = snap.analysisResponsesByTrial.get(key);
    if (review && (!solver || savedGroundingOutcome(review, solver.response) !== review.adaptation_success)) bad('저장된 두 판정과 결합 규칙이 다릅니다.');
    const y = changed.status === 'VALID' && review?.review_status === 'COMPLETED' ? review.adaptation_success : null;
    const q = x === null || y === null ? null : y ? x ? 1 : 2 : x ? 4 : 3;
    if (pair.variant_appropriateness !== y || pair.quadrant !== q || pair.assessment_id !== (review?.assessment_id ?? null)
        || pair.assessment_review_status !== (review?.review_status ?? null)) bad('저장 pair와 현재 A02 판정이 다릅니다. 기존 pair의 갱신이 필요합니다.');
    const reviewStatus = review?.review_status || 'NOT_REVIEWED';
    const placement = q ? 'PLACED' : x === null ? 'ORIGINAL_NUMERIC_UNASSESSED' : changed.status !== 'VALID' ? 'VARIANT_UNAVAILABLE'
      : reviewStatus !== 'COMPLETED' ? reviewStatus : 'UNDETERMINED';
    output.push({ pair_id: pair.pair_id, model: pair.model, source_type: pair.source_type, case: pair.case, variant: pair.variant,
      prompt_condition: prompt(pair.prompt_condition), reasoning: pair.reasoning, original_item_id: pair.original_item_id,
      original_trial_id: pair.original_trial_id, variant_item_id: pair.variant_item_id, variant_trial_id: pair.variant_trial_id,
      original_response_id: snap.responseIdsByTrial.get(originalKey) || null, response_id: responseId || null,
      original_correctness: x, adaptation_success: y, quadrant: q, placement_status: placement,
      review_status: reviewStatus, abstention_reason_validity: review?.abstention_reason_validity.verdict || 'UNREVIEWED',
      decision_grounding: review?.decision_grounding.verdict || 'UNREVIEWED', variant_answer_shape: pair.variant_answer_shape,
      original_status: pair.original_status, variant_status: pair.variant_status,
      original_result_path: pair.original_result_path, variant_result_path: pair.variant_result_path });
    const type = keyOf(pair); if (!byType.has(type)) byType.set(type, []); byType.get(type).push(pair);
  }
  if (snap.rows.some(row => row.variant !== 'ORIGINAL' && !seen.has(`${row.model}:${row.trial_id}`))) bad('전체 예정 변형 중 pair에 빠진 요청이 있습니다.');
  const covered = new Set();
  for (const type of summary.types) {
    const key = keyOf(type), rows = byType.get(key);
    if (!rows || covered.has(key) || type.planned_pairs !== rows.length) bad('유형별 전체 분모가 원기록과 다릅니다.');
    covered.add(key);
    const placed = rows.filter(row => row.quadrant !== null).length;
    if (type.placed_pairs !== placed || type.unplaced_pairs !== rows.length - placed) bad('배치·미배치 집계가 다릅니다.');
    for (const q of [1,2,3,4]) if (type.quadrants[q]?.count !== rows.filter(row => row.quadrant === q).length) bad('사분면 수가 원기록과 다릅니다.');
  }
  const placed = output.filter(row => row.quadrant !== null).length;
  if (covered.size !== byType.size || summary.overall.planned_pairs !== pairs.length
      || summary.overall.placed_pairs !== placed || summary.overall.unplaced_pairs !== pairs.length - placed) bad('전체 pair 집계가 다릅니다.');
  return { metadata: { run_id: snap.id, status: output.some(row => row.quadrant === null) ? 'PARTIAL' : 'AVAILABLE',
    created_at: summary.created_at ?? null, basis: 'SAVED_A02_GROUNDING_ASSESSMENTS', original_axis_scope: summary.original_axis_scope ?? null,
    review_coverage: snap.responseAssessments?.coverage?.review_status || {}, assessments_available: !!snap.responseAssessments }, pairs: output };
}
export async function readGroundingPairs(snap, { safePath, readJSON, readText, fail }) {
  const summary = await readJSON(snap.root, GROUNDING_FILES[0], true);
  if (!summary) return { metadata: { run_id: snap.id, status: 'NOT_PREPARED', assessments_available: !!snap.responseAssessments }, pairs: [] };
  if (!summary.source_hashes || !Object.keys(summary.source_hashes).length) throw fail('근거 타당성: 원자료 해시가 없습니다.', 503);
  for (const [relative, expected] of Object.entries(summary.source_hashes)) {
    const digest = createHash('sha256');
    for await (const chunk of createReadStream(await safePath(snap.root, relative))) digest.update(chunk);
    if (digest.digest('hex') !== expected) throw fail('근거 타당성: 원자료가 pair 집계 후 바뀌었습니다. 현재 판정과 맞는 기존 pair 재집계가 필요합니다.', 503);
  }
  const content = await readText(snap.root, GROUNDING_FILES[1], true);
  if (content === null) throw fail('근거 타당성: pair 저장이 끝나지 않았습니다.', 503);
  let pairs;
  try { pairs = content.split('\n').filter(line => line.trim()).map(line => JSON.parse(line)); }
  catch { throw fail('근거 타당성: pair 원기록을 읽지 못했습니다.', 503); }
  return validateGroundingPairs(summary, pairs, snap, fail);
}
