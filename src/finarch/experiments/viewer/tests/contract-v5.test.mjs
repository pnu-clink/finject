import test from 'node:test';
import assert from 'node:assert/strict';
import { aggregate, filterRows } from '../../../../../viewer/experiments/model.mjs';

for (const format of ['FinancialAnswerV5', 'FinancialAnswerV6', 'FinancialAnswerV7']) {
  for (const answers of [[-35, 0, 12.5], [null], [-35, null]]) {
    test(`${format} ${JSON.stringify(answers)} keeps numeric absence separate from unassessed abstention`, () => {
      const rows = answers.map((answer, i) => ({
        case: `case-${i}`, experiment: 1, status: 'VALID', response: { answer },
        checks: { response_format: format, numeric_answer_present: answer !== null,
          declared_abstention: null, abstention_marker_detected: null }
      }));
      const empty = rows.filter(row => row.response.answer === null);
      const totals = aggregate(rows);
      assert.equal(totals.numeric_answers_absent, empty.length);
      assert.equal(totals.declared_abstentions, null);
      assert.equal(totals.abstention_markers, null);
      assert.deepEqual(filterRows(rows, { metric: 'numeric_answers_absent' }), empty);
      assert.deepEqual(filterRows(rows, { metric: 'declared_abstentions' }), []);
      assert.deepEqual(filterRows(rows, { metric: 'abstention_markers' }), []);
    });
  }
}

test('V4 keeps recorded declarations and marker counts without inventing numeric absence', () => {
  const rows = [true, false].map((declared, i) => ({
    case: `legacy-${i}`, experiment: 1, status: 'VALID',
    checks: { response_format: 'FinancialAnswerMagnitudeV4',
      declared_abstention: declared, abstention_marker_detected: false }
  }));
  const totals = aggregate(rows);
  assert.equal(totals.declared_abstentions, 1);
  assert.equal(totals.abstention_markers, 0);
  assert.equal(totals.numeric_answers_absent, null);
  assert.deepEqual(filterRows(rows, { metric: 'declared_abstentions' }), [rows[0]]);
  assert.deepEqual(filterRows(rows, { metric: 'numeric_answers_absent' }), []);
});

test('V5, V6 and V7 absence counts remain observed when grouped together', () => {
  const rows = ['FinancialAnswerV5', 'FinancialAnswerV6', 'FinancialAnswerV7'].map((format, i) => ({
    case: `case-${i}`, experiment: 2, status: 'VALID',
    checks: { response_format: format, numeric_answer_present: false,
      declared_abstention: null, abstention_marker_detected: null }
  }));
  const totals = aggregate(rows);
  assert.equal(totals.numeric_answers_absent, 3);
  assert.equal(totals.declared_abstentions, null);
  assert.equal(totals.abstention_markers, null);
});
