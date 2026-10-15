export const GROUNDING_VERDICTS = ['SUPPORTED', 'UNSUPPORTED', 'UNDETERMINED', 'NOT_APPLICABLE', 'UNREVIEWED'];
export const GROUNDING_REVIEWS = ['COMPLETED', 'NOT_REVIEWED', 'REVIEW_FAILED', 'NOT_REVIEWABLE', 'SOURCE_MISSING'];
const dimensions = ['model', 'source_type', 'variant', 'prompt_condition', 'reasoning'];
const keyOf = row => JSON.stringify(dimensions.map(key => row[key]));
const counts = (rows, pick) => rows.reduce((out, row) => { const key = pick(row); out[key] = (out[key] || 0) + 1; return out; }, {});
function validate(filters) {
  if ((filters.original && !['all', 'correct', 'incorrect'].includes(filters.original))
      || (filters.quadrant && !['1','2','3','4','unplaced'].includes(String(filters.quadrant)))
      || (filters.abstention && !GROUNDING_VERDICTS.includes(filters.abstention))
      || (filters.decision && !GROUNDING_VERDICTS.includes(filters.decision)) || (filters.review && !GROUNDING_REVIEWS.includes(filters.review))
      || (filters.prompt && !['unguided', 'guided'].includes(filters.prompt)) || (filters.reasoning && !['off', 'on'].includes(filters.reasoning)))
    throw Error('근거 타당성 필터가 올바르지 않습니다.');
}
export function groundingMatches(row, filters = {}) {
  return (!filters.model || row.model === filters.model) && (!filters.source_type || row.source_type === filters.source_type)
    && (!filters.variant || row.variant === filters.variant) && (!filters.prompt || row.prompt_condition === filters.prompt)
    && (!filters.reasoning || row.reasoning === filters.reasoning)
    && (!filters.original || filters.original === 'all' || row.original_correctness === (filters.original === 'correct'))
    && (!filters.case || row.case.includes(filters.case))
    && (!filters.abstention || row.abstention_reason_validity === filters.abstention)
    && (!filters.decision || row.decision_grounding === filters.decision)
    && (!filters.review || row.review_status === filters.review)
    && (!filters.quadrant || (filters.quadrant === 'unplaced' ? row.quadrant === null : row.quadrant === Number(filters.quadrant)));
}
export function groundingSummary(data, filters = {}) {
  validate(filters);
  const groups = new Map();
  for (const pair of data.pairs) {
    const key = keyOf(pair); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(pair);
  }
  return { ...data.metadata, groups: [...groups.values()].map(rows => {
    const originalRows = rows.filter(row => groundingMatches(row, { original: filters.original }));
    const selected = rows.filter(row => groundingMatches(row, filters)), total = rows.length;
    const placed = rows.filter(row => row.quadrant !== null).length, unplaced = selected.filter(row => row.quadrant === null);
    return { ...Object.fromEntries(dimensions.map(key => [key, rows[0][key]])), planned_pairs: total,
      original_pairs: originalRows.length, original_unevaluated: rows.filter(row => row.original_correctness === null).length,
      placed_pairs: placed, unplaced_pairs: total - placed, filtered_pairs: selected.length,
      filtered_placed: selected.length - unplaced.length, filtered_unplaced: unplaced.length,
      quadrants: Object.fromEntries([1,2,3,4].map(q => {
        const count = selected.filter(row => row.quadrant === q).length;
        return [q, { count, denominator: total, rate: total ? count / total : null }];
      })), unplaced_reasons: counts(unplaced, row => row.placement_status),
      review_status: counts(originalRows, row => row.review_status),
      abstention_reason_validity: counts(originalRows, row => row.abstention_reason_validity),
      decision_grounding: counts(originalRows, row => row.decision_grounding) };
  }) };
}
export function groundingPage(data, filters = {}) {
  validate(filters);
  const offset = Number(filters.offset || 0);
  if (!Number.isSafeInteger(offset) || offset < 0) throw Error('근거 타당성 문항 위치가 올바르지 않습니다.');
  const scope = { model: filters.model, source_type: filters.source_type, variant: filters.variant, prompt: filters.prompt, reasoning: filters.reasoning };
  const planned = data.pairs.filter(row => groundingMatches(row, scope)), rows = planned.filter(row => groundingMatches(row, filters));
  const start = Math.min(offset, rows.length);
  return { run_id: data.metadata.run_id, total: rows.length, planned_pairs: planned.length, offset: start, page_size: 20,
    pairs: rows.slice(start, start + 20) };
}
