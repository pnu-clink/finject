import { createHash } from 'node:crypto';
import { createReadStream, promises as fs } from 'node:fs';

export const RQ1_FILES = ['summary.json', 'records.jsonl', 'source-selection.jsonl']
  .map(name => `02_analysis/01_results/rq1-materials/${name}`);
const dimensions = ['metric', 'model', 'source', 'prompt_condition', 'reasoning', 'variant'];
const keyOf = row => JSON.stringify(dimensions.map(key => row[key]));
const prompt = value => ['P0', 'unguided'].includes(value) ? 'unguided' : ['P1', 'guided'].includes(value) ? 'guided' : value;
const countBy = (rows, pick) => rows.reduce((counts, row) => {
  const value = pick(row); counts[value] = (counts[value] || 0) + 1; return counts;
}, {});
const sameCounts = (actual, expected) => actual && typeof actual === 'object'
  && Object.keys({ ...actual, ...expected }).every(key => (actual[key] || 0) === (expected[key] || 0));
const ratio = (count, total) => total ? count / total : null;

// [EV26.1] Reconcile saved observations and fixed cohorts without judging their meaning.
export function validateRQ1Materials(summary, records, selection, requests, privateItems, fail) {
  const bad = message => { throw fail(`RQ1 분석자료: ${message}`, 503); };
  if (summary.schema_version !== 'RQ1MaterialsV1' || summary.basis !== 'SUBMITTED_CLASSIFICATION_NOT_SEMANTIC_SUCCESS'
      || summary.original_axis !== 'SAVED_NUMERIC_MATCH' || summary.status !== 'AVAILABLE'
      || !Array.isArray(summary.groups) || summary.inverse_reconstruction?.status !== 'TBD'
      || summary.inverse_reconstruction.result !== null) bad('집계 계약 또는 역산 상태가 올바르지 않습니다.');
  const groups = new Map(), identities = new Map(), observations = new Map();
  for (const row of records) {
    const request = requests.get(`${row.model}:${row.trial_id}`);
    if (!['OV', 'OVS', 'OVS_all', 'OR', 'OE'].includes(row.metric) || !request
        || row.response_id !== `${row.model}:${row.trial_id}`
        || ['item_id', 'case', 'variant', 'reasoning'].some(key => row[key] !== request[key])
        || row.prompt_condition !== prompt(request.prompt_condition)) bad('계획 요청과 관찰 연결이 다릅니다.');
    const original = requests.get(`${row.model}:${row.original_trial_id}`);
    if (row.original_trial_id !== null && (!original || original.item_id !== row.original_item_id || original.variant !== 'ORIGINAL'
        || prompt(original.prompt_condition) !== row.prompt_condition || original.reasoning !== row.reasoning)) bad('원본 요청의 연결이 다릅니다.');
    if (row.source !== (privateItems.get(row.original_item_id)?.source || 'NOT_RECORDED')) bad('원본 데이터 출처가 다릅니다.');
    if (![true, false, null].includes(row.x) || ![true, false, null].includes(row.y)) bad('미판정 축은 null이어야 합니다.');
    const expectedQuadrant = row.x === null || row.y === null ? null : row.y ? row.x ? 1 : 2 : row.x ? 4 : 3;
    if (row.quadrant !== expectedQuadrant || (row.prompt_condition === 'unguided' && row.y !== null)) bad('사분면 또는 분류 미요구 상태가 다릅니다.');
    const identity = `${row.metric}:${row.response_id}`;
    if (identities.has(identity)) bad('중복 관찰이 있습니다.');
    identities.set(identity, row);
    if (row.metric !== 'OVS') observations.set(`${row.model}:${row.prompt_condition}:${row.reasoning}:${row.item_id}`, row);
    const key = keyOf(row);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  for (const [id, request] of requests) {
    const variant = request.variant || '';
    const metric = variant.startsWith('IC_VALUE') ? 'OV' : variant.startsWith('IC_SOURCE') ? 'OVS_all'
      : variant.startsWith('IC_RELATION') ? 'OR' : variant.startsWith('EA_') ? 'OE' : null;
    if (metric && !identities.has(`${metric}:${id}`)) bad('전체 계획 요청 중 집계에서 빠진 문항이 있습니다.');
  }
  const cohorts = new Map(), selected = new Set();
  for (const row of selection) {
    const all = identities.get(`OVS_all:${row.response_id}`), meta = privateItems.get(all?.item_id);
    if (!all || selected.has(row.response_id) || ['model', 'source', 'variant', 'prompt_condition', 'reasoning'].some(key => row[key] !== all[key])
        || ![true, false, null].includes(row.eligible)) bad('출처 집단의 선택 기록이 다릅니다.');
    selected.add(row.response_id);
    const child = identities.get(`OVS:${row.response_id}`);
    if ((row.eligible === true) !== !!child) bad('선택 집단과 OVS 관찰 수가 다릅니다.');
    if (child) {
      const parent = observations.get(`${row.model}:${row.prompt_condition}:${row.reasoning}:${row.parent_item_id}`);
      if (!parent || parent.metric !== 'OV' || parent.x !== true || parent.y !== true
          || meta?.matched_value_parent_ids?.length !== 1 || meta.matched_value_parent_ids[0] !== row.parent_item_id
          || child.value_parent_item_id !== row.parent_item_id
          || ['x', 'y', 'quadrant', 'classification', 'original_item_id', 'response_status'].some(key => child[key] !== all[key])) bad('OV 양쪽 성공 집단의 부모 연결이 다릅니다.');
    }
    const key = keyOf({ ...row, metric: 'OVS' });
    if (!cohorts.has(key)) cohorts.set(key, []);
    cohorts.get(key).push(row);
  }
  if (selection.length !== records.filter(row => row.metric === 'OVS_all').length) bad('출처 선택 기록이 누락되었습니다.');
  const seen = new Set(), result = [];
  for (const group of summary.groups) {
    const key = keyOf(group), rows = groups.get(key) || [], cohort = cohorts.get(key);
    if (seen.has(key) || (!groups.has(key) && !cohort)) bad('집단이 누락되거나 중복되었습니다.');
    seen.add(key);
    const n = rows.length, quadrants = countBy(rows.filter(row => row.quadrant !== null), row => row.quadrant);
    const unplaced = rows.filter(row => row.quadrant === null);
    const numerator = group.metric.startsWith('OVS') ? rows.filter(row => row.y === true).length : (quadrants[1] || 0);
    const classes = countBy(rows.filter(row => row.y !== null && row.classification), row => row.classification);
    if (group.N !== n || group.denominator !== n || group.numerator !== numerator || group.fraction !== `${numerator}/${n}`
        || group.rate !== ratio(numerator, n) || group.unplaced !== unplaced.length
        || !sameCounts(group.unplaced_reasons, countBy(unplaced, row => row.placement_status))
        || !sameCounts(group.classifications, classes) || group.answerable_count !== (classes.ANSWERABLE || 0)
        || group.answerable_rate !== ratio(classes.ANSWERABLE || 0, n)
        || group.denominator_symbol !== (group.metric === 'OVS' ? 'm' : 'N')
        || !Array.isArray(group.response_ids) || group.response_ids.length !== n
        || new Set(group.response_ids).size !== n || group.response_ids.some(id => !identities.has(`${group.metric}:${id}`)
          || keyOf(identities.get(`${group.metric}:${id}`)) !== key)) bad('전체 분모·분자·미판정 집계가 원기록과 다릅니다.');
    for (const q of [1, 2, 3, 4]) {
      const cell = group.quadrants?.[q], count = quadrants[q] || 0;
      if (!cell || cell.count !== count || cell.denominator !== n || cell.fraction !== `${count}/${n}`
          || cell.ratio_of_planned !== ratio(count, n)) bad('사분면 분모 또는 비율이 다릅니다.');
    }
    if (cohort) {
      const expected = { planned_source_responses: cohort.length, eligible: cohort.filter(row => row.eligible === true).length,
        excluded: cohort.filter(row => row.eligible === false).length, undetermined: cohort.filter(row => row.eligible === null).length };
      if (!sameCounts(group.cohort, expected) || group.cohort.eligible !== n) bad('OVS의 m과 출처 집단이 다릅니다.');
    }
    result.push({ ...group, unplaced_response_statuses: countBy(unplaced, row => row.response_status),
      unplaced_observations: countBy(unplaced, row => row.observation_status),
      entries: rows.map(row => Object.fromEntries(['response_id', 'trial_id', 'case', 'item_id', 'model', 'variant',
        'prompt_condition', 'reasoning', 'quadrant', 'classification', 'response_status'].map(key => [key, row[key]]))) });
  }
  if (seen.size !== new Set([...groups.keys(), ...cohorts.keys()]).size) bad('계획 집단이 요약에서 누락되었습니다.');
  return { ...summary, groups: result };
}

export async function readRQ1Materials(snap, { safePath, readJSON, readText, artifactPaths, fail }) {
  const summary = await readJSON(snap.root, RQ1_FILES[0], true);
  if (!summary) return { status: 'NOT_PREPARED', run_id: snap.id, groups: [], inverse_reconstruction: { status: 'TBD', result: null } };
  const bad = message => { throw fail(`RQ1 분석자료: ${message}`, 503); };
  if (summary.run_id !== snap.id || summary.records_path !== RQ1_FILES[1] || summary.selection_path !== RQ1_FILES[2]
      || !summary.source_hashes || !Object.keys(summary.source_hashes).length) bad('회차 또는 자료 경로가 다릅니다.');
  const paths = artifactPaths(snap.config), requests = new Map();
  const parseRows = async relative => {
    const text = await readText(snap.root, relative, true);
    if (text === null) bad(`${relative} 저장이 끝나지 않았습니다.`);
    try { return text.split('\n').filter(line => line.trim()).map(line => JSON.parse(line)); }
    catch { bad(`${relative} 원기록을 읽지 못했습니다.`); }
  };
  const required = [`${paths.input}/private.jsonl`, `${paths.input}/public.jsonl`, '01_evaluation/04_validation/numeric-comparisons.jsonl'];
  for (const model of snap.config.models) {
    const manifest = paths.request(model.key); required.push(manifest);
    for (const row of await parseRows(manifest)) requests.set(`${model.key}:${row.trial_id}`, row);
    const results = `${paths.results(model.key)}/results.jsonl`;
    try { await fs.access(await safePath(snap.root, results)); required.push(results); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  if (required.some(relative => !Object.hasOwn(summary.source_hashes, relative))) bad('원자료 해시가 누락되었습니다.');
  for (const [relative, expected] of Object.entries(summary.source_hashes)) {
    if (!/^[a-f0-9]{64}$/.test(expected)) bad('원자료 해시가 올바르지 않습니다.');
    const digest = createHash('sha256');
    for await (const chunk of createReadStream(await safePath(snap.root, relative))) digest.update(chunk);
    if (digest.digest('hex') !== expected) bad('원자료가 집계 후 갱신되었습니다. Python 집계를 다시 저장해 주세요.');
  }
  const records = await parseRows(RQ1_FILES[1]), selection = await parseRows(RQ1_FILES[2]);
  return validateRQ1Materials(summary, records, selection, requests, snap.privateItems, fail);
}
