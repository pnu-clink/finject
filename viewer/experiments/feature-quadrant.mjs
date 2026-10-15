// Derive display-only shares from saved A02 candidate-choice counts.
export const FEATURE_QUADRANT_CONDITIONS = [
  { key: 'unguided/off', prompt: 'unguided', reasoning: 'off', label: 'Unguided · Reasoning OFF', direction: '기준' },
  { key: 'unguided/on', prompt: 'unguided', reasoning: 'on', label: 'Unguided · Reasoning ON', direction: '↑' },
  { key: 'guided/off', prompt: 'guided', reasoning: 'off', label: 'Criteria-Guided · Reasoning OFF', direction: '→' },
  { key: 'guided/on', prompt: 'guided', reasoning: 'on', label: 'Criteria-Guided · Reasoning ON', direction: '↗' },
];

const CHOICES = [
  { key: 'A', label: '원래 후보 A와 숫자 일치', color: '#426f9b' },
  { key: 'B', label: '추가 후보 B와 숫자 일치', color: '#287d71' },
  { key: 'OTHER', label: '두 후보와 다른 숫자', color: '#b66a24' },
  { key: 'NULL', label: 'null 답', color: '#8b4c8b' },
  { key: 'FORMAT_OR_EXECUTION_FAILED', label: '형식·실행 실패', color: '#ae4e4b' },
];
const EXTRA = {
  BOTH: '두 후보 모두와 일치', NON_NUMERIC: '숫자가 아닌 답',
  REFERENCE_MISSING: '기준값 미기록', ORIGINAL_VALUE: '원래 후보와 숫자 일치',
};
const TERMINAL_STATUSES = new Set(['VALID', 'INVALID_RESPONSE', 'OUTPUT_TRUNCATED', 'READ_ERROR', 'AUTH_BLOCKED']);

function conditionFinished(source) {
  if (!Number.isInteger(source.planned) || source.planned <= 0) return false;
  const statuses = Object.entries(source.statuses || {});
  if (!statuses.length) return source.collected === source.planned;
  return statuses.every(([status, count]) => TERMINAL_STATUSES.has(status) && Number.isInteger(count) && count >= 0)
    && statuses.reduce((total, [, count]) => total + count, 0) === source.planned;
}

export function quadrantDeltaBand(absolutePercentagePoints) {
  if (absolutePercentagePoints >= 50) return 4;
  if (absolutePercentagePoints >= 25) return 3;
  if (absolutePercentagePoints >= 10) return 2;
  return 1;
}

export function buildFeatureQuadrant(matrix, model, variant = 'IC_VALUE_01_BEFORE') {
  const cells = FEATURE_QUADRANT_CONDITIONS.map(condition => ({ ...condition,
    source: matrix?.find(row => row.model === model && row.variant === variant
      && row.prompt_condition === condition.prompt && row.reasoning === condition.reasoning) }));
  if (cells.some(cell => !cell.source)) return { status: 'MISSING', model, variant };
  if (cells.some(cell => !conditionFinished(cell.source))) return { status: 'PENDING', model, variant };
  const unknown = [...new Set(cells.flatMap(cell => Object.keys(cell.source.numeric_candidate_choices || {})))]
    .filter(key => !CHOICES.some(choice => choice.key === key)).sort();
  const choices = [...CHOICES, ...unknown.map(key => ({ key, label: EXTRA[key] || key, color: '#6a6876' }))];
  const ready = cells.map(({ source, ...condition }) => {
    const counts = Object.fromEntries(choices.map(choice => [choice.key, source.numeric_candidate_choices?.[choice.key] || 0]));
    if (Object.values(counts).some(value => !Number.isInteger(value) || value < 0)
      || Object.values(counts).reduce((sum, value) => sum + value, 0) !== source.planned) return null;
    return { ...condition, planned: source.planned, counts };
  });
  if (ready.some(cell => !cell)) return { status: 'INCONSISTENT', model, variant };
  const baseline = ready[0], changes = [];
  for (const choice of choices) for (const target of ready.slice(1)) {
    const before = baseline.counts[choice.key], after = target.counts[choice.key];
    const deltaPp = 100 * (after / target.planned - before / baseline.planned);
    changes.push({ choice: choice.key, target: target.key, before, after, deltaPp,
      band: quadrantDeltaBand(Math.abs(deltaPp)) });
  }
  const largest = changes.reduce((best, change) => !best || Math.abs(change.deltaPp) > Math.abs(best.deltaPp) ? change : best, null);
  const largestSingle = changes.filter(change => change.target !== 'guided/on')
    .reduce((best, change) => !best || Math.abs(change.deltaPp) > Math.abs(best.deltaPp) ? change : best, null);
  return { status: 'READY', model, variant, choices, cells: ready, changes, largest, largestSingle };
}
