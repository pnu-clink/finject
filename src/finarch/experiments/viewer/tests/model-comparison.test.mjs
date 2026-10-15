import test from 'node:test';
import assert from 'node:assert/strict';
import { modelComparison } from '../../../../../viewer/experiments/model.mjs';

const model = key => ({ key });
const record = (caseId, provider, status, match, variant = 'ORIGINAL') => ({
  case: caseId, model: provider, trial_id: `${provider}-${caseId}`, variant,
  experiment: variant === 'ORIGINAL' ? 1 : 2, prompt_condition: 'P0', reasoning: 'off',
  status, question: `Question ${caseId}`, tags: [],
  ...(status === 'NOT_RUN' ? {} : { response: { answer: match ? '12' : '13' } }),
  checks: typeof match === 'boolean' ? { numeric_comparison: { matches: match } } : {},
});

test('pairs different provider trial IDs by the same case and condition, without treating missing or invalid results as numeric evidence', () => {
  const snap = { config: { models: [model('haiku'), model('gemini')] }, rows: [
    record('test-0002', 'gemini', 'VALID', false),
    record('test-0001', 'gemini', 'VALID', true),
    record('test-0003', 'gemini', 'NOT_RUN', null),
    record('test-0002', 'haiku', 'VALID', true),
    record('test-0001', 'haiku', 'VALID', true),
    record('test-0003', 'haiku', 'INVALID_RESPONSE', true),
  ] };
  const result = modelComparison(snap, { model: 'haiku', status: 'VALID' });
  assert.deepEqual(result.rows.map(row => row.case), ['test-0001', 'test-0002', 'test-0003']);
  assert.equal(result.both_valid, 2);
  assert.equal(result.both_numeric_compared, 2);
  assert.equal(result.both_numeric_match, 1);
  assert.equal(result.numeric_disagreement, 1);
  assert.equal(result.rows[2].models.gemini.has_answer, false);
  assert.equal(result.rows[2].models.haiku.status, 'INVALID_RESPONSE');
});

test('comparison filters common conditions and paginates paired rows after natural case sorting', () => {
  const cases = Array.from({ length: 52 }, (_, i) => `test-${String(i + 1).padStart(4, '0')}`);
  const snap = { config: { models: [model('haiku'), model('gemini')] }, rows: cases.flatMap(id => [
    record(id, 'gemini', 'NOT_RUN', null), record(id, 'haiku', 'NOT_RUN', null),
  ]) };
  const page = modelComparison(snap, { comparison_offset: '50' });
  assert.equal(page.total, 52);
  assert.deepEqual(page.rows.map(row => row.case), cases.slice(50));
  const searched = modelComparison(snap, { q: 'test-0002' });
  assert.equal(searched.total, 1);
  assert.equal(searched.rows[0].case, 'test-0002');
});
