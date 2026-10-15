import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { verifyInputEdits, contextBlocks } from '../../../../../viewer/experiments/input-edits.mjs';

const sha = text => createHash('sha256').update(text, 'utf8').digest('hex');
const qc = context => ({ question: 'What is the value? 😀', context });
const patch = (start, end, before, text, kind) => ({ start, end, before, text, segments: [{ kind, text }] });
const step = (variant, input, output, patches) => ({ variant, input_context_sha256: sha(input), output_context_sha256: sha(output), patches });
function fixture(variant, before, after, steps) {
  const original = qc(before), item = qc(after);
  return { caseId: 'case-1', variant, original, item, request: { ...item }, provenance: {
    schema_version: 1, status: 'VERIFIED', reason: null, offset_unit: 'unicode_code_point',
    baseline: { case: 'case-1', variant: 'ORIGINAL', question_sha256: sha(original.question), context_sha256: sha(before) },
    final: { question_sha256: sha(item.question), context_sha256: sha(after) }, steps,
    source: { comparison: '02-generation/case-1/03-validation/04-comparison.json', comparison_sha256: 'a'.repeat(64) }
  } };
}
function valueFixture() { return fixture('IC_VALUE_01_AFTER', '😀 A20.', '😀 A20. B21.', [step('IC_VALUE_01_AFTER', '😀 A20.', '😀 A20. B21.', [patch(6, 6, '', ' B21.', 'VALUE')])]); }

test('Unicode code-point insertion reconstructs exact text and UTF-16 highlight offsets', async () => {
  const result = await verifyInputEdits(valueFixture());
  assert.equal(result.status, 'VERIFIED');
  assert.deepEqual(result.spans, [{ kind: null, text: '😀 A20.', start: 0, end: 7 }, { kind: 'VALUE', text: ' B21.', start: 7, end: 12 }]);
});

test('source inserted inside a value sentence retains VALUE / SOURCE_B / VALUE', async () => {
  const f = valueFixture(), before = f.item.context, after = '😀 A20. B21 (source B).';
  f.variant = 'IC_SOURCE_B_ONLY'; f.item = qc(after); f.request = qc(after); f.provenance.final.context_sha256 = sha(after);
  f.provenance.steps.push(step(f.variant, before, after, [patch(10, 10, '', ' (source B)', 'SOURCE_B')]));
  const result = await verifyInputEdits(f);
  assert.equal(result.status, 'VERIFIED');
  assert.deepEqual(result.spans.map(s => [s.kind, s.text]), [[null, '😀 A20.'], ['VALUE', ' B21'], ['SOURCE_B', ' (source B)'], ['VALUE', '.']]);
});

test('source A marks only its attribution, preserving the independent added value', async () => {
  const f = fixture('IC_VALUE_01_BEFORE', '😀 A20.', ' B21.😀 A20.', [step('IC_VALUE_01_BEFORE', '😀 A20.', ' B21.😀 A20.', [patch(0, 0, '', ' B21.', 'VALUE')])]), before = f.item.context, after = ' B21.😀 A20 (source A).';
  f.variant = 'IC_SOURCE_A_ONLY'; f.item = qc(after); f.request = qc(after); f.provenance.final.context_sha256 = sha(after);
  f.provenance.steps.push(step(f.variant, before, after, [patch(10, 10, '', ' (source A)', 'SOURCE_A')]));
  const result = await verifyInputEdits(f);
  assert.equal(result.status, 'VERIFIED');
  assert.deepEqual(result.spans.filter(s => s.kind).map(s => [s.kind, s.text]), [['VALUE', ' B21.'], ['SOURCE_A', ' (source A)']]);
});

test('replacement segments can retain parent colors around the nested source', async () => {
  const f = valueFixture(), before = f.item.context, after = '😀 A20. B21 (B).';
  const p = patch(6, 11, ' B21.', ' B21 (B).', 'SOURCE_B');
  p.segments = [{ kind: 'VALUE', text: ' B21' }, { kind: 'SOURCE_B', text: ' (B)' }, { kind: 'VALUE', text: '.' }];
  f.variant = 'IC_SOURCE_B_ONLY'; f.item = qc(after); f.request = qc(after); f.provenance.final.context_sha256 = sha(after);
  f.provenance.steps.push(step(f.variant, before, after, [p]));
  const result = await verifyInputEdits(f);
  assert.equal(result.status, 'VERIFIED');
  assert.deepEqual(result.spans.filter(s => s.kind).map(s => s.kind), ['VALUE', 'SOURCE_B', 'VALUE']);
});

test('EA deletions stay outside reconstructed input and positions adjust across same-stage edits', async () => {
  const before = '😀 | 20 | 30 |', after = '😀 |  |  |';
  const result = await verifyInputEdits(fixture('EA_02', before, after, [step('EA_02', before, after, [patch(4, 6, '20', '', 'EA'), patch(9, 11, '30', '', 'EA')])]));
  assert.equal(result.status, 'VERIFIED'); assert.equal(result.spans.map(s => s.text).join(''), after);
  assert.deepEqual(result.deletions.map(d => [d.text, d.position, d.offset]), [['20', 4, 5], ['30', 7, 8]]);
});

test('original identical, unavailable records and unverified records remain distinct', async () => {
  const f = fixture('ORIGINAL', 'original', 'original', []);
  assert.equal((await verifyInputEdits(f)).status, 'UNCHANGED');
  for (const provenance of [undefined, { status: 'UNAVAILABLE', reason: 'No comparison' }]) assert.equal((await verifyInputEdits({ ...f, provenance })).status, 'UNAVAILABLE');
  const result = await verifyInputEdits({ ...f, provenance: { status: 'MISMATCH', reason: 'Broken replay' } });
  assert.equal(result.status, 'MISMATCH'); assert.deepEqual(result.spans, []);
});

test('hash, request, sequence, coordinates and segment failures suppress all highlighting', async t => {
  const changes = {
    'actual request differs from public': f => { f.request.context += ' changed'; },
    'actual question differs from public': f => { f.request.question += '?'; },
    'request not stored': f => { delete f.request; },
    'baseline hash': f => { f.provenance.baseline.context_sha256 = '0'.repeat(64); },
    'baseline question hash': f => { f.provenance.baseline.question_sha256 = '0'.repeat(64); },
    'baseline case': f => { f.provenance.baseline.case = 'another'; },
    'final hash': f => { f.provenance.final.context_sha256 = '0'.repeat(64); },
    'step input hash': f => { f.provenance.steps[0].input_context_sha256 = '0'.repeat(64); },
    'step output hash': f => { f.provenance.steps[0].output_context_sha256 = '0'.repeat(64); },
    'UTF-16 offset used as code point': f => { f.provenance.steps[0].patches[0].start = 7; f.provenance.steps[0].patches[0].end = 7; },
    'before mismatch': f => { f.provenance.steps[0].patches[0].before = 'wrong'; },
    'segments mismatch': f => { f.provenance.steps[0].patches[0].segments[0].text = 'different'; },
    'missing segments': f => { delete f.provenance.steps[0].patches[0].segments; },
    'question changed without an edit record': f => { f.item.question += '?'; f.request.question = f.item.question; f.provenance.final.question_sha256 = sha(f.item.question); },
    'wrong color for step': f => { f.provenance.steps[0].patches[0].segments[0].kind = 'SOURCE_A'; },
    'unknown schema': f => { f.provenance.schema_version = 2; },
    'wrong step': f => { f.provenance.steps[0].variant = 'EA_02'; },
    'ambiguous overlapping insertions': f => { f.provenance.steps[0].patches.push(structuredClone(f.provenance.steps[0].patches[0])); },
    'incomplete chain despite valid final hash': f => { f.item.context += '!'; f.request.context += '!'; f.provenance.final.context_sha256 = sha(f.item.context); }
  };
  for (const [name, mutate] of Object.entries(changes)) await t.test(name, async () => { const f = valueFixture(); mutate(f); const result = await verifyInputEdits(f); assert.equal(result.status, 'MISMATCH'); assert.deepEqual(result.spans, []); assert.deepEqual(result.deletions, []); });
});

test('formatted context maps repeated text and escaped/table pipes to exact source ranges', () => {
  const text = '😀 Same\r\n\r\n| Label | Value |\r\n| --- | ---: |\r\n| Same | **20** |\r\n| A\\|B | `1|2` |\r\n\r\nSame';
  const blocks = contextBlocks(text), table = blocks.find(b => b.type === 'table');
  assert.deepEqual(blocks.map(b => b.type), ['p', 'table', 'p']);
  assert.deepEqual(table.rows.map(row => row.map(c => text.slice(c.start, c.end))), [[' Same ', ' **20** '], [' A\\|B ', ' `1|2` ']]);
  assert.equal(text.slice(blocks[0].start, blocks[0].end), '😀 Same');
  assert.equal(text.slice(blocks[2].start, blocks[2].end), 'Same');
});
