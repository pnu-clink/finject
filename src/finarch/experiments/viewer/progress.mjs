// Read-only operational summaries; completion means validated output, not correctness.
const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
const stamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : null;
export const PROGRESS_STAGES = { '02_comparison': 'A02 · 문항별 관계 분석', '03_research': 'A03 · 연구 해석',
  '04_quadrant': 'A04 · 연구발견 그룹화', '05_outcomes': 'Python · 응답 분류' };
const names = PROGRESS_STAGES;
const stageCodes = { A02: '02_comparison', A03: '03_research', A04: '04_quadrant' };
const percentile = (values, fraction) => values.length ? values[Math.ceil(values.length * fraction) - 1] : null;

export function selectProgressStage(rootState, scheduler, selectedStage) {
  return selectedStage || stageCodes[rootState?.analysis?.stage] ||
    stageCodes[rootState?.full_pipeline?.stage] || (names[scheduler?.stage] ? scheduler.stage : '02_comparison');
}

function pipelineFailure(rootState, stage, state, calls) {
  const pipeline = rootState?.full_pipeline;
  const target = stageCodes[pipeline?.stage] || stageCodes[rootState?.analysis?.stage];
  const stateError = state.error || state.preparation_error || state.failure?.error;
  const ownError = stateError && /FAILED|BLOCKED|PARTIAL/.test(state.status);
  const pipelineError = pipeline?.status === 'FAILED' && pipeline.error &&
    (target === stage || (stage === '04_quadrant' && String(pipeline.error).startsWith('A04_')));
  if (!ownError && !pipelineError) return null;
  const message = String(ownError ? stateError : pipeline.error);
  const at = ownError ? state.updated_at || state.completed_at : pipeline.updated_at;
  const failedAt = stamp(at);
  const newerWork = failedAt !== null && (calls.some(row => stamp(row.started_at) > failedAt)
    || (stamp(state.updated_at || state.completed_at) > failedAt && ['RUNNING', 'PREPARED', 'COLLECTED'].includes(state.status)));
  const beforeCalls = !calls.length && !number(state.completed);
  const preparationCode = ['A04_GLOBAL_GROUPING_INPUT_BUDGET_EXCEEDED', 'A04_REQUIRES_COMPLETED_A03',
    'A04_FROZEN_SOURCE_CHANGED', 'A04_FINDINGS_RUN_MISMATCH', 'A04_FINDING_INPUT_CHANGED'].includes(message);
  return { kind: beforeCalls || preparationCode || state.status === 'PREPARATION_FAILED' ? 'PREPARATION' : 'PROCESSING', status: 'FAILED',
    message, at: at || null, source: ownError ? `02_analysis/${stage}/state.json` : 'state.json · full_pipeline.error', historical: newerWork };
}

function stageRecords(state, calls = [], planned = null) {
  const total = number(state?.requests) ?? planned;
  const latest = new Map(calls.map(row => [row.trial_id, row]));
  const ended = [...latest.values()].filter(row => row.event === 'END');
  const completed = number(state?.completed) ?? (total !== null || calls.length ? ended.length : null);
  const valid = number(state?.valid) ?? (total !== null || calls.length ? ended.filter(row => row.result_status === 'VALID').length : null);
  return { planned: total, completed, valid, failed: completed === null || valid === null ? null : Math.max(0, completed - valid) };
}

export function buildProgress({ id, config, rootState, stages, scheduler, timingEvents = [], events = [], plan,
  selectedStage, finalization = null, stageArtifacts = {}, now = Date.now(), alive = () => false }) {
  const stage = !selectedStage && finalization ? (finalization.a03_collected ? '05_outcomes' : '02_comparison') : selectProgressStage(rootState, scheduler, selectedStage);
  if (!names[stage]) throw new Error('UNKNOWN_PROGRESS_STAGE');
  const state = stages[stage] || {};
  const total = number(state.requests) ?? stageArtifacts[stage]?.planned ?? null;
  const spans = new Map();
  for (const row of timingEvents) {
    if (row.step !== 'model_call' || row.stage !== stage || !row.span_id) continue;
    spans.set(row.span_id, { ...spans.get(row.span_id), ...row });
  }
  const calls = [...spans.values()].filter(row => stamp(row.started_at) !== null);
  const latest = new Map();
  for (const row of calls.sort((a, b) => stamp(a.started_at) - stamp(b.started_at))) latest.set(row.trial_id, row);
  const active = [...latest.values()].filter(row => row.event !== 'END' && alive(row.pid));
  const interrupted = [...latest.values()].filter(row => row.event !== 'END' && !alive(row.pid));
  const validated = [...latest.values()].filter(row => row.event === 'END' && row.result_status === 'VALID');
  const failures = [...latest.values()].filter(row => row.event === 'END' && row.result_status !== 'VALID');
  const retrying = active.filter(row => calls.some(old => old !== row && old.trial_id === row.trial_id
    && (old.event !== 'END' || old.result_status !== 'VALID'))).length;
  const completed = Math.max(number(state.valid) ?? 0, validated.length);
  const errors = Math.max(0, (number(state.completed) ?? 0) - (number(state.valid) ?? 0) - retrying, failures.length + interrupted.length);
  const running = active.length;
  const sum = completed + running + errors;
  const counts = { total, completed: total === null ? null : completed, running: total === null ? null : running,
    waiting: total === null || sum > total ? null : total - sum, errors: total === null ? null : errors,
    remaining: total === null ? null : Math.max(0, total - completed), consistent: total === null || sum <= total };
  const timed = validated.filter(row => number(row.elapsed_seconds) !== null && row.elapsed_seconds >= 0 && stamp(row.ended_at) !== null)
    .sort((a, b) => stamp(a.ended_at) - stamp(b.ended_at));
  const durations = timed.map(row => row.elapsed_seconds).sort((a, b) => a - b);
  const mean = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null;
  const points = [...latest.values()].filter(row => row.event === 'END' && number(row.elapsed_seconds) !== null && stamp(row.ended_at) !== null)
    .sort((a, b) => stamp(a.ended_at) - stamp(b.ended_at)).map(row => ({ at: stamp(row.ended_at),
      seconds: row.elapsed_seconds, status: row.result_status || row.status, trial_id: row.trial_id, attempt: row.attempt }));
  const recent = [];
  const averages = points.flatMap(point => {
    if (point.status !== 'VALID') return [];
    recent.push(point.seconds); if (recent.length > 20) recent.shift();
    return [{ at: point.at, seconds: recent.reduce((a, b) => a + b, 0) / recent.length, samples: recent.length }];
  });
  const edges = [];
  for (const row of calls) {
    if (row.event !== 'END' && !alive(row.pid)) continue;
    edges.push({ at: stamp(row.started_at), change: 1, completed: 0 });
    if (row.event === 'END' && stamp(row.ended_at) !== null) edges.push({ at: stamp(row.ended_at), change: -1,
      completed: latest.get(row.trial_id) === row && row.result_status === 'VALID' ? 1 : 0 });
  }
  const history = []; let live = 0, done = 0;
  for (const edge of edges.sort((a, b) => a.at - b.at || a.change - b.change)) {
    live += edge.change; done += edge.completed;
    history.push({ at: edge.at, running: Math.max(0, live), completed: done });
  }
  if (history.length) history.push({ at: now, running, completed: done });
  const cpu = events.filter(row => row.event === 'ANALYSIS_CPU_SAMPLE' && row.stage === stage)
    .map(row => ({ at: stamp(row.sampled_at || row.time), percent: number(row.cpu_percent), limit: row.current_limit,
      interval_seconds: number(row.interval_seconds) })).filter(row => row.at !== null).sort((a, b) => a.at - b.at);
  // Break the plotted line across intervals for which no host sample was taken.
  const cpuWithGaps = [];
  for (const row of cpu) {
    const previous = cpuWithGaps.at(-1);
    if (previous && row.interval_seconds && row.at - previous.at > row.interval_seconds * 1500) {
      cpuWithGaps.push({ at: previous.at + 1, percent: null, limit: null, reason: 'UNMEASURED_INTERVAL' });
    }
    cpuWithGaps.push(row);
  }
  // Reconstruct limits from saved policy changes and starts, including restarts.
  // A current scheduler policy must not be projected backwards onto old calls.
  const limits = [];
  let configuredLimit = number(config?.analysis?.schedule?.concurrency);
  for (const row of [...events].sort((a, b) => stamp(a.time) - stamp(b.time))) {
    if (row.event === 'ANALYSIS_SCHEDULE_CONFIGURED') configuredLimit = number(row.schedule?.concurrency);
    if (row.stage !== stage || stamp(row.time) === null) continue;
    if (row.event === 'ANALYSIS_CODEX_STARTED' && configuredLimit !== null && number(row.pending) !== null) {
      limits.push({ at: stamp(row.time), limit: Math.min(configuredLimit, row.pending) });
    } else if (['ANALYSIS_CPU_SAMPLE', 'ANALYSIS_CONCURRENCY_CHANGED'].includes(row.event) && number(row.current_limit) !== null) {
      limits.push({ at: stamp(row.sampled_at || row.time), limit: row.current_limit });
    }
  }
  if (scheduler?.stage === stage && number(scheduler.current_limit) !== null && stamp(scheduler.updated_at) !== null) {
    limits.push({ at: stamp(scheduler.updated_at), limit: scheduler.current_limit });
  }
  limits.sort((a, b) => a.at - b.at);
  if (limits.length) limits.push({ at: now, limit: limits.at(-1).limit });
  const ownerAlive = scheduler?.stage === stage && alive(scheduler.pid);
  const policy = scheduler?.stage === stage ? scheduler.policy : null;
  const localSteps = { integrity: '입력·Evaluation 원본 무결성 검사', result_collection: 'A01 · 저장된 응답 취합',
    source_verification: 'A01 · 취합 자료 검증', relationship_aggregation: 'A02 · 관계 수치 집계',
    comparison_request_preparation: 'A02 · Codex 요청 준비', research_request_preparation: 'A03 · 연구 요청 준비',
    finding_request_preparation: 'A04 · 그룹화 요청 준비', finding_preparation: 'A04 · 그룹화 입력 준비',
    quadrant_preparation: 'A04 · 그룹화 입력 준비', quadrant_request_preparation: 'A04 · 그룹화 요청 준비',
    finding_grouping: 'A04 · 연구발견 그룹화 처리', finding_collection: 'A04 · 그룹화 결과 검사·취합' };
  const localSpans = new Map();
  for (const row of timingEvents) {
    const belongs = row.stage === stage || stageCodes[row.stage] === stage ||
      (!row.stage && (stage === '02_comparison' ? !/^(research|finding|quadrant)_/.test(row.step) :
        stage === '03_research' ? row.step === 'research_request_preparation' : /^(finding|quadrant)_/.test(row.step)));
    if (belongs && row.span_id && localSteps[row.step]) localSpans.set(row.span_id, { ...localSpans.get(row.span_id), ...row });
  }
  const preparation = !active.length && (total === null || stage === '04_quadrant')
    ? [...localSpans.values()].filter(row => row.event !== 'END' && alive(row.pid) && stamp(row.started_at) !== null)
      .sort((a, b) => stamp(b.started_at) - stamp(a.started_at))[0] : null;
  const probe = ownerAlive && running > 0 && scheduler.status === 'PROVIDER_PROBE';
  const failure = pipelineFailure(rootState, stage, state, calls);
  if (failure && preparation && stamp(failure.at) !== null && stamp(preparation.started_at) > stamp(failure.at)) failure.historical = true;
  const status = rootState?.execution_control?.analysis?.paused ? 'PAUSED_BY_USER' : preparation ? preparation.step === 'finding_grouping' || preparation.step === 'finding_collection' ? 'PROCESSING' : 'PREPARING'
    : running ? probe ? 'PROVIDER_PROBE' : scheduler?.status === 'DRAINING' ? 'DRAINING' : 'RUNNING'
    : failure && !failure.historical ? failure.kind === 'PREPARATION' ? 'PREPARATION_FAILED' : 'PROCESSING_FAILED'
    : state.status === 'RUNNING' && !ownerAlive && (state.backend || config?.analysis?.backend) === 'codex' ? 'INTERRUPTED' : state.status || 'NOT_STARTED';
  const issues = [...(failure ? [failure] : []), ...failures.map(row => {
    const detail = stageArtifacts[stage]?.failures?.find(item => item.trial_id === row.trial_id);
    return { kind: 'MODEL_CALL', status: row.result_status || row.status, trial_id: row.trial_id, attempt: row.attempt,
      message: detail?.message || row.error || row.error_type || '구체적인 오류 사유가 호출 기록에 없습니다.',
      at: row.ended_at, source: detail?.source || '02_analysis/timing-events.jsonl', historical: false };
  }), ...interrupted.map(row => ({ kind: 'MODEL_CALL', status: 'INTERRUPTED', trial_id: row.trial_id,
    message: '호출 종료 기록 없이 실행기가 종료되었습니다. 응답 여부와 시간을 확정할 수 없습니다.',
    at: row.started_at, source: '02_analysis/timing-events.jsonl', historical: false }))];
  if (errors && !failures.length && !interrupted.length) issues.push({ kind: 'MODEL_CALL', status: 'FAILED',
    message: `상태 파일에 실패·응답 미확인 ${errors}건이 있으나 개별 호출의 시간·사유가 기록되지 않았습니다.`,
    at: state.updated_at || null, source: `02_analysis/${stage}/state.json`, historical: false });
  const warnings = [];
  if (!counts.consistent) warnings.push('상태 파일과 호출 기록이 갱신 중입니다. 대기 건수는 다음 조회에서 다시 계산합니다.');
  if (errors) warnings.push(`오류·응답 미확인 ${errors}건은 완료에 포함하지 않습니다. 남은 건수에도 포함됩니다.`);
  if (interrupted.length) warnings.push(`종료 기록 없이 실행기가 사라진 호출 ${interrupted.length}건이 있습니다. 처리시간을 확정하지 않습니다.`);
  if (total === null) warnings.push('이 분석 단계의 요청 수가 아직 기록되지 않았습니다. 0건으로 간주하지 않습니다.');
  if (preparation && status === 'PREPARING') warnings.push(`${localSteps[preparation.step]} 중입니다. ${calls.length ? '이번 준비 작업의 호출 시작을 기다립니다.' : 'Codex 호출은 아직 시작하지 않았습니다.'}`);
  if (failure && !failure.historical) warnings.push(failure.kind === 'PREPARATION'
    ? 'Python 준비·연결 단계에서 중단됐습니다. 요청 수 미확정과 모델 호출 실패는 구분합니다.'
    : '분석 처리 단계의 오류가 저장됐습니다. 아래 개별 호출 오류와 함께 확인해 주세요.');
  if (probe && status === 'PROVIDER_PROBE') warnings.push(`첫 Codex 응답을 검사한 뒤 나머지 요청을 실행합니다. 실제 실행 ${running}건 · 호출 한도 ${scheduler.current_limit}건입니다.`);
  const requestCounts = Object.values(rootState?.models || {}).map(model => model.request_counts);
  const evaluationTotal = plan?.models?.reduce((sum, model) => sum + (number(model.requests) ?? 0), 0) ?? null;
  const evaluationCollected = requestCounts.length && requestCounts.every(count => number(count?.completed) !== null)
    ? requestCounts.reduce((sum, count) => sum + count.completed, 0) : rootState?.status === 'PREPARED' ? 0 : null;
  const records = stageRecords(state, calls, total);
  const starts = [...calls, ...localSpans.values()].map(row => stamp(row.started_at)).filter(value => value !== null);
  const ends = [...calls, ...localSpans.values()].map(row => stamp(row.ended_at)).filter(value => value !== null);
  const elapsed = starts.length && (running || preparation || ends.length) ? Math.max(0,
    ((running || preparation ? now : Math.max(...ends)) - Math.min(...starts)) / 1000) : null;
  const result = { run: id, observed_at: new Date(now).toISOString(), stage, stage_label: names[stage], status, counts, records, issues,
    analysis: { status: rootState?.analysis?.status || 'NOT_STARTED', stage: rootState?.analysis?.stage || null,
      pipeline_status: rootState?.full_pipeline?.status || null, execution_status: rootState?.full_pipeline?.analysis_execution || null },
    model: state.model || config?.analysis?.backends?.[config.analysis.backend]?.model || null,
    backend: state.backend || config?.analysis?.backend || null, state_updated_at: scheduler?.stage === stage ? scheduler.updated_at : state.updated_at || failure?.at || null,
    activity: preparation ? { label: localSteps[preparation.step], elapsed_seconds: Math.max(0, (now - stamp(preparation.started_at)) / 1000), processor: preparation.step === 'finding_grouping' ? 'PIPELINE' : 'PYTHON' }
      : active.length ? { label: probe ? '첫 Codex 응답 대기' : 'Codex 응답 대기',
        elapsed_seconds: Math.max(0, ...active.map(row => (now - stamp(row.started_at)) / 1000)), processor: 'LLM' } : null,
    phases: Object.entries(names).filter(([key]) => finalization || key !== '05_outcomes').map(([key, title]) => {
      const facts = stageRecords(stages[key], [], stageArtifacts[key]?.planned ?? null);
      const problem = pipelineFailure(rootState, key, stages[key] || {}, calls.filter(row => row.stage === key));
      return { key, title, total: facts.planned, completed: facts.valid, records: facts,
        status: key === stage ? status : problem && !problem.historical ? problem.kind === 'PREPARATION' ? 'PREPARATION_FAILED' : 'PROCESSING_FAILED' : stages[key]?.status || 'NOT_STARTED' };
    }),
    evaluation: { total: evaluationTotal, collected: evaluationCollected, status: rootState?.status },
    queue: rootState?.queued_execution || null,
    metrics: { samples: durations.length, stage_elapsed_seconds: elapsed, mean_seconds: mean, p50_seconds: percentile(durations, .5),
      p95_seconds: percentile(durations, .95), recent_mean_seconds: averages.at(-1)?.seconds ?? null,
      timed_failure_count: points.filter(row => row.status !== 'VALID').length },
    scheduler: { alive: ownerAlive, limit: policy ? scheduler.current_limit : null, policy,
      last_cpu_sample: scheduler?.stage === stage ? scheduler.last_cpu_sample || null : null },
    charts: { calls: points, averages, history, cpu: cpuWithGaps, limits }, warnings,
    sources: ['state.json', `02_analysis/${stage}/state.json`, '02_analysis/scheduler.json',
      '02_analysis/timing-events.jsonl', 'events.jsonl', ...(stageArtifacts[stage]?.sources || [])],
    definitions: { unit: 'One analysis request, not one Evaluation response.',
      remaining: 'total minus validated completions; includes running, waiting, and unresolved errors.',
      mean: 'Elapsed time of the latest validated attempt per request. Earlier failed attempts and unfinished calls are excluded.',
      timing: 'CLI, network and provider processing are included. Server queue and reasoning time are not separately observable.',
      history: 'History includes measured requests only; no measurements are fabricated for older runs.' } };
  if (finalization) {
    result.finalization = finalization;
    result.analysis = { ...result.analysis, status: finalization.status, pipeline_status: finalization.status,
      previous_status: rootState?.analysis?.status, stage: finalization.status === 'COMPLETE' ? 'PYTHON_OUTCOMES' : null };
    const phase = result.phases.find(p => p.key === '04_quadrant');
    phase.historical_status = phase.status; phase.status = 'SKIPPED_BY_USER'; phase.historical_records = phase.records;
    const post = result.phases.find(p => p.key === '05_outcomes');
    post.status = finalization.status === 'COMPLETE' ? 'COMPLETE' : 'WAITING';
    post.records = { planned: null, completed: null, valid: null, failed: null };
    post.description = `저장 응답 ${finalization.outcomes_total ?? '미기록'}건 · ${finalization.outcomes_status} · 실제 완료 ${finalization.status === 'COMPLETE' ? '확인' : '미확인'}`;
    result.warnings.push(finalization.explanation);
    result.sources.push('02_analysis/finalization-policy.json', '02_analysis/preparation-state.json', '02_analysis/05_outcomes/summary.json');
    if (stage === '04_quadrant' || stage === '05_outcomes') {
      result.status = stage === '04_quadrant' ? 'SKIPPED_BY_USER' : finalization.status;
      result.counts = { total: null, completed: null, running: null, waiting: null, errors: null, remaining: null, consistent: true };
      result.issues = result.issues.map(issue => ({ ...issue, historical: true }));
      result.warnings = [finalization.explanation, stage === '04_quadrant' ? '아래 호출·실패·부분 산출물은 과거 기록입니다. 현재 남은 작업이나 재시도 대상으로 세지 않습니다.' : 'Python 응답 분류는 모델 요청 진행률과 구분합니다. 저장 파일만으로 전체 완료를 판정하지 않습니다.'];
      result.activity = null;
    } else if (finalization.status === 'WAIT_EVALUATION_AND_TRANSFER' && !calls.length) {
      result.status = 'WAIT_EVALUATION_AND_TRANSFER';
      if (!requestCounts.length || requestCounts.some(count => number(count?.completed) === null)) result.evaluation.collected = null;
      result.evaluation.status = 'WAIT_EVALUATION_AND_TRANSFER';
      result.warnings.push('Evaluation 수량은 로컬 저장 기록 기준입니다. 전송 대기 중인 원격 실행의 현재 수량을 0건으로 추정하지 않습니다.');
      result.warnings.push(`최신 준비 상태를 표시합니다. 이전 루트 Analysis 상태: ${finalization.previous_analysis_status}`);
      result.phases.find(p => p.key === stage).status = result.status;
    }
  }
  return result;

}
