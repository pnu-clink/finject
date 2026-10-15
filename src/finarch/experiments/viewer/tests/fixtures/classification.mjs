import { promises as fs } from 'node:fs';
import path from 'node:path';
import { VARIANTS } from '../../../../../../viewer/experiments/model.mjs';

// Local display fixture only. No provider calls or production artifacts.
export async function classificationFixture(root) {
  const run = '20260927-exp-999', folder = path.join(root, run);
  const write = async (name, value, lines = false) => {
    const target = path.join(folder, name); await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, lines ? value.map(row => JSON.stringify(row)).join('\n') : JSON.stringify(value));
  };
  const values = ['ANSWERABLE', 'ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED', 'ABSTAIN', 'ANSWERABLE', 'ABSTAIN'];
  for (const model of ['fixture-v7', 'fixture-legacy']) {
    const modelRows = [], modelRequests = [];
    for (const [i, variant] of VARIANTS.entries()) for (const prompt of i || model === 'fixture-v7' ? ['P0', 'P1'] : ['P0']) for (const reasoning of ['off', 'on']) {
      const trial = `${variant}-${prompt}-${reasoning}`, value = values[i], answer = prompt === 'P0' || value === 'ANSWERABLE' ? i === 6 || !i && prompt === 'P1' && reasoning === 'on' ? 21 : 20 : null;
      const row = { case: 'fixture-0001', item_id: variant, trial_id: trial, variant, prompt_condition: model === 'fixture-v7' ? prompt === 'P0' ? 'unguided' : 'guided' : prompt, reasoning, model, experiment: i ? 2 : 1, status: 'VALID', call_path: `${model}/calls/${trial}.json`, result_path: `${model}/results/${trial}.json`, checks: { response_format: model === 'fixture-v7' ? 'FinancialAnswerV7' : 'FinancialAnswerV6', numeric_answer_present: answer !== null, ...(i ? {} : { numeric_comparison: { computed: String(answer), gold: '20', matches: answer === 20 } }) } };
      const response = { answer, answer_meta: { negative: answer === null ? null : false, scale: answer === null ? null : 'million' }, explanation: 'Local synthetic display fixture. Sales total is 20.', evidence: ['Sales total is 20.'] };
      if (model === 'fixture-v7') response.classification = prompt === 'P0' ? null : value;
      else if (prompt === 'P1' && value !== 'ABSTAIN') response.explanation = `Classification: ${value}; Response: ${answer === null ? 'ABSTAIN' : 'ANSWER'}. ${response.explanation}`;
      const request = { ...row, input: { question: 'What is total sales?', context: 'Sales total is 20.' }, prompt: 'Local display fixture.', response_schema: { title: model === 'fixture-v7' ? 'FinancialAnswerV7' : 'FinancialAnswerV6', type: 'object' } };
      await write(row.call_path, { request, response }); await write(row.result_path, { response, elapsed_seconds: 0 });
      modelRows.push(row); modelRequests.push(request);
    }
    await write(`${model}/03-results/results.jsonl`, modelRows, true); await write(`${model}/01-requests/manifest.jsonl`, modelRequests, true);
  }
  await write('config.json', { models: ['fixture-v7', 'fixture-legacy'].map(key => ({ key, model: key })) });
  await write('state.json', { status: 'FINISHED' }); await write('summary.json', { status: 'FINISHED', originals: 1, variants: 7 });
  await write('plan.json', { models: ['fixture-v7', 'fixture-legacy'].map(key => ({ key, requests: key === 'fixture-v7' ? 32 : 30 })) });
  await write('01-input/public.jsonl', VARIANTS.map(item_id => ({ item_id, question: 'What is total sales?', context: 'Sales total is 20.' })), true);
  await write('01-input/private.jsonl', VARIANTS.map(variant => ({ item_id: variant, case: 'fixture-0001', variant, reference: { reference_answer: '20' } })), true);
  await write('02_analysis/02_comparison/summary.json', {
    overall: { planned: 62, assessed: 0, appropriate: 0, unassessed: 62, audit_disagreements: 0 }, paired: [],
    matrix: ['fixture-v7', 'fixture-legacy'].map(model => {
      const prefix = model === 'fixture-v7' ? 'guided_' : 'p1_';
      const counts = { planned: 2, labels_present: 2, classification_compared: 0, classification_matches: 0,
        stated_classifications: { ANSWERABLE: 2 }, classification_sources: { [model === 'fixture-v7' ? 'JSON_FIELD' : 'LEGACY_EXPLANATION_PREFIX']: 2 },
        classification_answer_checked: 2, classification_answer_mismatches: 0 };
      return { model, variant: 'EA_01', prompt: model === 'fixture-v7' ? 'guided' : 'P1', reasoning: 'on', assessed: 0, appropriate: 0, unassessed: 2,
        ...Object.fromEntries(Object.entries(counts).map(([key, value]) => [prefix + key, value])) };
    }),
    original_variant_relations: [{ model: 'fixture-legacy', original_group: 'ORIGINAL_CONDITION_MISSING', prompt: 'P1', reasoning: 'on', assessed: 0, appropriate: 0, unassessed: 14 }]
  });
  return { run, folder };
}
