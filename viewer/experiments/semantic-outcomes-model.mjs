const h1 = new Set(['IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_RELATION_01', 'EA_01', 'EA_02']);
export const outcomeCategories = ['SUPPORTED_ANSWER', 'SUPPORTED_ABSTENTION', 'UNNECESSARY_ABSTENTION', 'MISSED_ABSTENTION', 'UNCLASSIFIED'];
function outcomeKey(row) {
  if (!Object.hasOwn(row, 'semantic_answerability')) return '\0missing';
  const value = row.semantic_answerability;
  if (value === null) return '\0null';
  if (value === '') return '\0empty';
  return typeof value === 'string' && !value.startsWith('\0') ? value : '\0value:' + JSON.stringify(value);
}
export function outcomePage(summary, rows, filters = {}) {
  const scope = filters.scope || 'all';
  if (!['h1', 'variants', 'originals', 'all'].includes(scope)) throw Error('Unknown outcome scope');
  const categories = { ...Object.fromEntries(outcomeCategories.map(c => [c, c])), ...summary.categories };
  const labels = { '\0missing': '필드 누락', '\0null': 'null', '\0empty': '빈 문자열' };
  for (const row of rows) {
    const key = outcomeKey(row);
    if (!Object.hasOwn(categories, key)) Object.defineProperty(categories, key, {value: labels[key] || key.replace(/^\0value:/, ''), enumerable: true});
  }
  const codes = Object.keys(categories);
  if (filters.category && !codes.includes(filters.category)) throw Error('Unknown outcome category');
  const selected = rows.filter(r => scope === 'all' || (scope === 'originals' ? r.variant === 'ORIGINAL' : scope === 'variants' ? r.variant !== 'ORIGINAL' : h1.has(r.variant)));
  const count = items => {
    const result = Object.fromEntries(codes.map(c => [c, 0]));
    for (const row of items) result[outcomeKey(row)]++;
    return result;
  };
  const counts = count(selected), saved = summary.scopes?.[scope];
  if (saved && (selected.length !== saved.total || codes.some(c => Object.hasOwn(saved, c) && counts[c] !== saved[c]))) throw Error('Outcome counts do not match saved responses');
  const groups = new Map();
  for (const row of selected) {
    const key = JSON.stringify([row.model, row.prompt_condition, row.reasoning]);
    if (!groups.has(key)) groups.set(key, {model: row.model, prompt_condition: row.prompt_condition, reasoning: row.reasoning, total: 0, ...count([])});
    const group = groups.get(key); group.total++; group[outcomeKey(row)]++;
  }
  const matches = selected.filter(r => (!filters.category || outcomeKey(r) === filters.category)
    && (!filters.model || r.model === filters.model) && (!filters.prompt || r.prompt_condition === filters.prompt)
    && (!filters.reasoning || r.reasoning === filters.reasoning));
  const offset = Number(filters.offset || 0);
  if (!Number.isSafeInteger(offset) || offset < 0) throw Error('Invalid outcome offset');
  return { status: 'AVAILABLE', run: summary.run, generated_at: summary.generated_at, categories, codes,
    scope, total: selected.length, counts, groups: [...groups.values()].sort((a, b) => String(a.model).localeCompare(String(b.model)) || ['unguided', 'guided'].indexOf(a.prompt_condition) - ['unguided', 'guided'].indexOf(b.prompt_condition) || ['off', 'on'].indexOf(a.reasoning) - ['off', 'on'].indexOf(b.reasoning)),
    matching: matches.length, offset, next_offset: offset + 20 < matches.length ? offset + 20 : null,
    rows: matches.slice(offset, offset + 20), new_model_calls: 0 };
}
