/** Describe saved Luna results without a model call or a new score. */
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Repository } from '../../../viewer/repository.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../../..');
const sourceRoot = path.join(root, 'reports/experiments-run');
const output = path.join(root, 'reports/run/20260923-experiment-improvement/03-research/20260924-content-analysis');
const ids = ['20260923-exp-007', '20260923-exp-008'];
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const readHash = async relative => hash(await fs.readFile(path.join(root, relative)));
const write = async (name, value) => fs.writeFile(path.join(output, name), value);
const json = value => JSON.stringify(value, null, 2) + '\n';
const number = value => value.toLocaleString('ko-KR');

async function main() {
  const repo = new Repository(sourceRoot), generatedAt = new Date().toISOString();
  const sourceHashes = {}, runs = [], snapshots = new Map();
  for (const id of ids) {
    const snap = await repo.snapshot(id);
    snapshots.set(id, snap);
    if (snap.stale) throw Error(`${id}The storage is being updated.`);
    const profile = repo.overview(snap, {}).content_analysis.models;
    const model = profile.find(item => item.key === 'luna-api');
    if (!model) throw Error(`${id}: no results from luna-api.`);
    const originals = snap.rows.filter(row => row.model === model.key && row.variant === 'ORIGINAL');
    const variantRows = snap.rows.filter(row => row.model === model.key && row.variant !== 'ORIGINAL');
    const summary = { id, model: model.key, original_cases: model.cases, original_requests: model.originals,
      original_numeric_matches: originals.filter(row => row.checks?.numeric_comparison?.matches === true).length,
      original_numeric_mismatches: originals.filter(row => row.checks?.numeric_comparison?.matches === false).length,
      original_numeric_unevaluated: originals.filter(row => typeof row.checks?.numeric_comparison?.matches !== 'boolean').length,
      baseline: Object.fromEntries(Object.entries(model.baseline).map(([group, entry]) => [group, { count: entry.count, cases: entry.cases.map(pair => pair.case) }])),
      observations: model.observations,
      variants: model.variants.map(item => ({ variant: item.variant, cells: item.cells.map(({ cases, ...cell }) => cell) })),
      variant_requests: variantRows.length, semantic_reviewed: model.variants.flatMap(item => item.cells).reduce((n, cell) => n + cell.semantic_reviewed, 0) };
    runs.push(summary);
    for (const relative of [`reports/experiments-run/${id}/config.json`, `reports/experiments-run/${id}/01-input/private.jsonl`, `reports/experiments-run/${id}/${model.key}/03-results/results.jsonl`]) sourceHashes[relative] = await readHash(relative);
  }
  const validation = { checked_at: generatedAt, new_model_calls: 0, checks: runs.map(run => ({ run: run.id,
    original_cases: run.original_cases === 100, original_requests: run.original_requests === 200,
    original_partition: Object.values(run.baseline).reduce((n, group) => n + group.count, 0) === run.original_cases,
    numeric_partition: run.original_numeric_matches + run.original_numeric_mismatches + run.original_numeric_unevaluated === run.original_requests,
    variant_requests: run.variant_requests === 2800,
    variant_cells: run.variants.length === 7 && run.variants.every(item => item.cells.length === 4 && item.cells.every(cell => cell.total === 100)) })) };
  if (validation.checks.some(entry => Object.entries(entry).some(([key, value]) => key !== 'run' && !value))) throw Error('The denominator test for the storage result failed.');
  const requestHashes = {};
  for (const id of ids) {
    requestHashes[id] = {};
    for (const reasoning of ['off', 'on']) {
      const snap = snapshots.get(id);
      const row = snap.rows.find(value => value.model === 'luna-api' && value.case === 'test-0267' && value.variant === 'ORIGINAL' && value.reasoning === reasoning);
      if (!row) throw Error(`${id}: test-0267 ${reasoning} There\x27s no raw response.`);
      const response = await repo.response(snap, row);
      requestHashes[id][reasoning] = hash(JSON.stringify(response.request));
    }
  }
  for (const reasoning of ['off', 'on']) if (requestHashes[ids[0]][reasoning] !== requestHashes[ids[1]][reasoning]) throw Error(`test-0267 ${reasoning}: The two execution requests are different.`);
  const lines = ['# Original R0/R1 numeric transitions and 7The species modification conditions observed', '', `Generation ${generatedAt}. Saved ${ids.join(', ')}I read it. Call the new model. 0That one.`, '',
    '## Original 100The number of lines matched', '', '|Turn around.|They\x27re both in the same place.|R0 million.|R10,000.|They\x27re both inconsistent.|Equal underestimating|The individual numbers match.200|', '|---|---:|---:|---:|---:|---:|---:|',
    ...runs.map(run => `|${run.id}|${run.baseline.both_match.count}|${run.baseline.off_only.count}|${run.baseline.on_only.count}|${run.baseline.both_mismatch.count}|${run.baseline.unevaluated.count}|${run.original_numeric_matches}/200|`), '',
    'R0 is the arithmetic mean, R1 is the arithectic mean, and both of these conditions are in the same principle, unless we can compare the numbers. 4Put it in the matching/dismatching box. \x60Equal underestimating\x60So one side of the number can be a matching number, so the individual 200The number of responses matched the sum of the 4The sum of the canes can\x27t be the same.', '',
    '## Reversal and repetition of the variation', ''];
  for (const run of runs) lines.push(`- ${run.id}R0: The corresponding element ${run.baseline.off_only.count}items${run.baseline.off_only.count ? ` — ${run.baseline.off_only.cases.join(', ')}` : ''}R10,000 is the same. ${run.baseline.on_only.count}— ${run.baseline.on_only.cases.join(', ')}.`);
  lines.push('', 'exp-008 \x60test-0267\x60R0 million gold number plus43,920It\x27s a match.007R is equal to R1 +43,920The corresponding R0 of the two executions, the requested object in R1 is the SHA-256And we compared the same request to the same request. 55,509and 11,589And the unambiguous interpretation of cash flow is the opposite. It\x27s a candidate to read the answer, not a general effect of the inference setup or a correct judgment of the explanatory logic.', '',
    '## Variant 7The way we use the type x four conditions', '',
    'Each run is 28The whole value of the cell is [summary.json].](summary.json)Each cell has a plan. 100Keeping up with the request, we separated the form-pass, numerical answer, and null-use inconsistencies. When we look at P0-R0 / P0- R1 / P1-R0 /P1-R1 sequentially by type, we don\x27t interpret the increase in null as an appropriate ubo enhancement.', '',
    '|Turn around.|Request for modification|Explanatory semantic assessment.|Not evaluated|', '|---|---:|---:|---:|',
    ...runs.map(run => `|${run.id}|${number(run.variant_requests)}|${run.semantic_reviewed}|${number(run.variant_requests - run.semantic_reviewed)}|`), '',
    '### The following form read the observation signal', '',
    'The figure below is a surface signal obtained after processing a storage response, where multiple signals can be attached to a response, so the sum of the columns is not a transformation request number, nor is it a logical error rate.', '',
    '|Turn around.|No numeric answer|No exact match of quotes|Empty evidence|Output truncated|', '|---|---:|---:|---:|---:|',
    ...runs.map(run => { const count = tag => run.observations.find(item => item.tag === tag)?.count ?? 0;
      return `|${run.id}|${count('NUMERIC_ANSWER_ABSENT')}|${count('QUOTE_NOT_EXACT_SUBSTRING')}|${count('EMPTY_EVIDENCE')}|${count('OUTPUT_TRUNCATED')}|`; }), '',
    'private variation of the input \x60semantic_answerability=NOT_ESTABLISHED\x60and \x60human_decision=PENDING\x60It\x27s not going to be a randomly generated denominator of numerical correctness, logical correctness and e-relevantness.](../../../../../docs/02-experiments/02_analysis/01_response_review/README.md)We need to confirm it first and then connect it to a separate review.', '',
    '## Relationships to be verified in papers', '',
    '1. We\x27re going to show how the R1 matches change, depending on whether the gold matches the original R0, and we\x27re going backwards and downwards.',
    '2. We compare the null/number response transitions of four conditions per variant type and the form failure to a primitive set, which is the behavior difference.',
    '3. Once the criteria for content judgment are established, we add a cross-section separating the probability of answering, the appropriateness of behavior, the explanatory logic, and the basis.',
    '4. The same request exp-007/008The transition is a search data that shows repeated fluctuations, and it\x27s generalized to have separate verification of the original and fixed criteria that weren\x27t used in development.', '');
  await fs.mkdir(output, { recursive: true });
  const template = await fs.readFile(path.join(root, 'src/finarch/documentation/templates/experiment-content-analysis-report.md'), 'utf8');
  await write('README.md', template.replace('{{run_ids}}', ids.map(id => `\`${id}\``).join(', ')).replace('{{generated_at}}', generatedAt));
  await write('analysis.md', lines.join('\n'));
  await write('summary.json', json({ generated_at: generatedAt, kind: 'DESCRIPTIVE_SAVED_RESULT_CONTENT_ANALYSIS', new_model_calls: 0, request_hashes_test_0267: requestHashes, runs }));
  await write('source-hashes.json', json(sourceHashes));
  await write('validation.json', json(validation));
  await write('events.jsonl', JSON.stringify({ at: generatedAt, event: 'SAVED_CONTENT_ANALYSIS', runs: ids, new_model_calls: 0, validation: 'PASS' }) + '\n');
  for (const [relative, before] of Object.entries(sourceHashes)) if (await readHash(relative) !== before) throw Error(`${relative}The original was changed when I created the report.`);
  process.stdout.write(json({ output: path.relative(root, output), runs: ids, validation: 'PASS', new_model_calls: 0 }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
