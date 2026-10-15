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
    if (snap.stale) throw Error(`${id}: 저장 자료가 갱신 중입니다.`);
    const profile = repo.overview(snap, {}).content_analysis.models;
    const model = profile.find(item => item.key === 'luna-api');
    if (!model) throw Error(`${id}: luna-api 결과가 없습니다.`);
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
  if (validation.checks.some(entry => Object.entries(entry).some(([key, value]) => key !== 'run' && !value))) throw Error('저장 결과 분모 검사가 실패했습니다.');
  const requestHashes = {};
  for (const id of ids) {
    requestHashes[id] = {};
    for (const reasoning of ['off', 'on']) {
      const snap = snapshots.get(id);
      const row = snap.rows.find(value => value.model === 'luna-api' && value.case === 'test-0267' && value.variant === 'ORIGINAL' && value.reasoning === reasoning);
      if (!row) throw Error(`${id}: test-0267 ${reasoning} 원응답이 없습니다.`);
      const response = await repo.response(snap, row);
      requestHashes[id][reasoning] = hash(JSON.stringify(response.request));
    }
  }
  for (const reasoning of ['off', 'on']) if (requestHashes[ids[0]][reasoning] !== requestHashes[ids[1]][reasoning]) throw Error(`test-0267 ${reasoning}: 두 실행의 요청이 다릅니다.`);
  const lines = ['# 원본 R0/R1 숫자 전이와 7종 변형 조건 관찰', '', `생성 ${generatedAt}. 저장된 ${ids.join(', ')}만 읽었습니다. 새 모델 호출 0건.`, '',
    '## 원본 100문항의 숫자 일치 짝', '', '|회차|둘 다 일치|R0만|R1만|둘 다 불일치|짝 미평가|개별 숫자 일치/200|', '|---|---:|---:|---:|---:|---:|---:|',
    ...runs.map(run => `|${run.id}|${run.baseline.both_match.count}|${run.baseline.off_only.count}|${run.baseline.on_only.count}|${run.baseline.both_mismatch.count}|${run.baseline.unevaluated.count}|${run.original_numeric_matches}/200|`), '',
    'R0는 추론 끔, R1은 추론 켬입니다. 같은 원문에서 두 조건 모두 숫자 비교가 가능한 경우만 4개 일치/불일치 칸에 넣습니다. 별도 `짝 미평가`의 한쪽은 숫자 일치가 있을 수 있으므로 개별 200응답의 숫자 일치 합계와 4개 칸의 합이 같지 않을 수 있습니다.', '',
    '## 역전과 반복 변동', ''];
  for (const run of runs) lines.push(`- ${run.id}: R0만 일치한 원문 ${run.baseline.off_only.count}개${run.baseline.off_only.count ? ` — ${run.baseline.off_only.cases.join(', ')}` : ''}. R1만 일치한 원문 ${run.baseline.on_only.count}개 — ${run.baseline.on_only.cases.join(', ')}.`);
  lines.push('', 'exp-008의 `test-0267`은 R0만 gold 숫자 +43,920에 일치합니다. exp-007에서는 같은 문항의 R1만 +43,920에 일치했습니다. 두 실행의 해당 R0끼리, R1끼리의 요청 객체 직렬화 SHA-256을 비교해 같은 요청임을 확인했습니다. 계산에 쓴 55,509와 11,589는 같고 현금흐름의 부호 해석이 반대로 바뀝니다. 응답을 읽어 확인할 후보이지 추론 설정의 일반적 인과 효과나 설명 논리의 정답 판정은 아닙니다.', '',
    '## 변형 7종 × 네 조건의 사용법', '',
    '각 실행의 28셀 전체 값은 [summary.json](summary.json)에 있습니다. 셀마다 계획 100요청을 유지하며 형식 통과·숫자 답·null·인용 불일치를 분리했습니다. 유형별로 P0-R0 / P0-R1 / P1-R0 / P1-R1을 나란히 볼 때, null이 늘어난 것을 적절한 유보 향상으로 해석하지 않습니다.', '',
    '|회차|변형 요청|명시적 의미 판정|미평가|', '|---|---:|---:|---:|',
    ...runs.map(run => `|${run.id}|${number(run.variant_requests)}|${run.semantic_reviewed}|${number(run.variant_requests - run.semantic_reviewed)}|`), '',
    '### 형식 다음에 읽을 관찰 신호', '',
    '아래 수치는 저장 응답을 후처리해 얻은 표면 신호입니다. 한 응답에 여러 신호가 붙을 수 있어 열의 합은 변형 요청 수가 아니며, 논리 오답률도 아닙니다.', '',
    '|회차|숫자 답 없음|인용 정확 일치 없음|빈 근거|출력 잘림|', '|---|---:|---:|---:|---:|',
    ...runs.map(run => { const count = tag => run.observations.find(item => item.tag === tag)?.count ?? 0;
      return `|${run.id}|${count('NUMERIC_ANSWER_ABSENT')}|${count('QUOTE_NOT_EXACT_SUBSTRING')}|${count('EMPTY_EVIDENCE')}|${count('OUTPUT_TRUNCATED')}|`; }), '',
    'private 변형 입력의 `semantic_answerability=NOT_ESTABLISHED`와 `human_decision=PENDING`이 남아 있습니다. 숫자 정답·논리 정답·유보 적절성의 분모를 임의로 만들어 채점하지 않습니다. [판정 절차](../../../../../docs/02-experiments/02_analysis/01_response_review/README.md)를 먼저 확정한 뒤 별도의 검토 결과로 연결해야 합니다.', '',
    '## 논문에서 검증할 관계', '',
    '1. 원본 R0의 gold 일치 여부에 따라 R1의 일치가 어떻게 바뀌는지, 역전과 미평가 원문을 별도로 제시합니다.',
    '2. 변형 유형별 네 조건의 null/숫자 답 전환과 형식 실패를 원문 묶음으로 비교합니다. 이는 행동 차이입니다.',
    '3. 내용 판정 기준이 확정되면 답변 가능성, 행동 적절성, 설명 논리, 근거 지지를 분리한 교차표를 추가합니다.',
    '4. 동일 요청 exp-007/008의 전환은 반복 변동을 보여 주는 탐색 자료입니다. 개발에 사용하지 않은 원문과 고정된 기준의 별도 확인이 있어야 일반화합니다.', '');
  await fs.mkdir(output, { recursive: true });
  const template = await fs.readFile(path.join(root, 'src/finarch/documentation/templates/experiment-content-analysis-report.md'), 'utf8');
  await write('README.md', template.replace('{{run_ids}}', ids.map(id => `\`${id}\``).join(', ')).replace('{{generated_at}}', generatedAt));
  await write('analysis.md', lines.join('\n'));
  await write('summary.json', json({ generated_at: generatedAt, kind: 'DESCRIPTIVE_SAVED_RESULT_CONTENT_ANALYSIS', new_model_calls: 0, request_hashes_test_0267: requestHashes, runs }));
  await write('source-hashes.json', json(sourceHashes));
  await write('validation.json', json(validation));
  await write('events.jsonl', JSON.stringify({ at: generatedAt, event: 'SAVED_CONTENT_ANALYSIS', runs: ids, new_model_calls: 0, validation: 'PASS' }) + '\n');
  for (const [relative, before] of Object.entries(sourceHashes)) if (await readHash(relative) !== before) throw Error(`${relative}: 보고서 생성 중 원본이 바뀌었습니다.`);
  process.stdout.write(json({ output: path.relative(root, output), runs: ids, validation: 'PASS', new_model_calls: 0 }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
