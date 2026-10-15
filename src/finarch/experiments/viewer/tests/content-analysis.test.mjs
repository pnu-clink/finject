import test from 'node:test';
import assert from 'node:assert/strict';
import { contentAnalysis } from '../../../../../viewer/experiments/model.mjs';

const original = (caseId, reasoning, matches, status = 'VALID') => ({
  model: 'luna', case: caseId, question: 'What changed?', experiment: 1,
  variant: 'ORIGINAL', prompt_condition: 'P0', reasoning, status,
  checks: { numeric_comparison: typeof matches === 'boolean' ? { matches, computed: matches ? '4' : '-4', gold: '4' } : null }
});
const variant = (caseId, prompt, reasoning, answer, semantic = 'NOT_REVIEWED') => ({
  model: 'luna', case: caseId, question: 'What changed?', experiment: 2,
  variant: 'EA_01', prompt_condition: prompt, reasoning, status: 'VALID',
  response: { answer }, checks: { semantic_assessment: semantic, all_quotes_present: true }
});

test('original gold pairs keep reversals and unassessed cases distinct from variant behavior', () => {
  const rows = [
    original('c1', 'off', true), original('c1', 'on', true),
    original('c2', 'off', true), original('c2', 'on', false),
    original('c3', 'off', false), original('c3', 'on', true),
    original('c4', 'off', false), original('c4', 'on', false),
    original('c5', 'off', true), original('c5', 'on', null),
    ...['c1', 'c2', 'c3', 'c4', 'c5'].flatMap((id, index) =>
      ['P0', 'P1'].flatMap(prompt => ['off', 'on'].map(reasoning => variant(id, prompt, reasoning, index === 0 ? null : 4))))
  ];
  rows.find(row => row.case === 'c2' && row.variant === 'EA_01' && row.prompt_condition === 'P0' && row.reasoning === 'off').tags =
    ['QUOTE_NOT_EXACT_SUBSTRING', 'EMPTY_EVIDENCE', 'EMPTY_EVIDENCE'];
  const snap = { config: { models: [{ key: 'luna' }] }, rows };
  const all = contentAnalysis(snap).models[0];
  assert.equal(all.cases, 5);
  assert.deepEqual(Object.fromEntries(Object.entries(all.baseline).map(([key, value]) => [key, value.count])),
    { both_match: 1, off_only: 1, on_only: 1, both_mismatch: 1, unevaluated: 1 });
  assert.equal(all.variants[0].cells[0].total, 5);
  assert.equal(all.variants[0].cells[0].null, 1);
  assert.equal(all.variants[0].cells[0].semantic_reviewed, 0);
  assert.deepEqual(all.observations, [
    { tag: 'EMPTY_EVIDENCE', count: 1, cases: 1 },
    { tag: 'QUOTE_NOT_EXACT_SUBSTRING', count: 1, cases: 1 }
  ]);
  assert.equal(all.variants[0].cells[0].empty_evidence, 1);
  assert.deepEqual(all.variants[0].cells[0].cases.find(row => row.case === 'c2').tags,
    ['QUOTE_NOT_EXACT_SUBSTRING', 'EMPTY_EVIDENCE']);
  const reverse = contentAnalysis(snap, { baseline_group: 'off_only' }).models[0];
  assert.deepEqual(reverse.baseline.off_only.cases.map(pair => pair.case), ['c2']);
  assert.equal(reverse.variants[0].cells[0].total, 1);
  assert.equal(reverse.variants[0].cells[0].numeric, 1);
  const guided = contentAnalysis(snap).models[1];
  assert.equal(guided.prompt, 'guided');
  assert.equal(guided.originals, 0);
  assert.equal(guided.baseline.unevaluated.count, 5);
  assert.equal(guided.variants[0].cells[0].cases[0].original, null);
  assert.equal(contentAnalysis(snap, { baseline_group: 'off_only' }).models[1].selected_cases, 0);
});

test('original pairs and their variants cannot cross model, prompt, case, or reasoning', () => {
  const rows = [];
  for (const model of ['luna', 'other']) for (const prompt of ['P0', 'P1']) {
    for (const reasoning of ['off', 'on']) {
      const matches = model === 'luna' ? prompt === 'P0' : reasoning === 'on';
      rows.push({ ...original('c1', reasoning, matches), model, prompt_condition: prompt });
      rows.push({ ...variant('c1', prompt, reasoning, 4), model });
    }
  }
  const snap = { rows, config: { models: [{ key: 'luna' }, { key: 'other' }] } };
  const groups = contentAnalysis(snap).models;
  assert.equal(groups.length, 4);
  assert.equal(groups[0].baseline.both_match.count, 1);
  assert.equal(groups[1].baseline.both_mismatch.count, 1);
  assert.equal(groups[2].baseline.on_only.count, 1);
  assert.equal(groups[3].baseline.on_only.count, 1);
  for (const group of groups) for (const cell of group.variants[0].cells) {
    assert.equal(cell.prompt, group.prompt);
    const matches = group.key === 'luna' ? group.prompt === 'unguided' : cell.reasoning === 'on';
    assert.equal(cell.cases[0].original.verdict, matches ? 'MATCH' : 'MISMATCH');
  }
});
