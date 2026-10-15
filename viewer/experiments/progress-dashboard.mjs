const $ = id => document.getElementById(id);
const node = (tag, className, text) => { const out = document.createElement(tag); if (className) out.className = className; if (text !== undefined) out.textContent = text; return out; };
const svgNode = (tag, attrs = {}, text) => { const out = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [key, value] of Object.entries(attrs)) out.setAttribute(key, String(value)); if (text !== undefined) out.textContent = text; return out; };
const fmt = value => value == null ? '—' : Number(value).toLocaleString('ko-KR');
const duration = seconds => seconds == null ? '미측정' : seconds < 60 ? `${seconds.toFixed(1)}초` : `${Math.floor(Math.round(seconds) / 60)}분 ${Math.round(seconds) % 60}초`;
const clock = value => new Date(value).toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
const shortClock = value => new Date(value).toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit' });
const statuses = { RUNNING: '분석 실행 중', RETRY_WAIT: '재시도 대기', DRAINING: '진행 중 응답 수집 중', BLOCKED: '확인 필요', PARTIAL: '일부 미완료', COLLECTED: '검사 통과·수집 완료', COMPLETE: '완료', FINISHED: '수집 완료', PREPARED: '실행 대기', NOT_STARTED: '준비 전', INTERRUPTED: '실행기 종료·확인 필요', PAUSED_BY_USER: '일시 중지', VALID: '검사 통과', UNKNOWN_DELIVERY: '응답 미확인' };
Object.assign(statuses, {SKIPPED_BY_USER:'사용자 지시로 생략', WAIT_EVALUATION_AND_TRANSFER:'Evaluation 완료·전송 대기', WAIT_PYTHON_OUTCOMES:'Python 후처리 완료 확인 대기', WAIT_A03:'A03 수집 대기', WAITING:'대기'});
const colors = { completed: '#397565', running: '#4c7595', waiting: '#d9cebc', errors: '#b96354', average: '#88603d' };
Object.assign(statuses, { PREPARING: 'Python 준비 작업 중', PROVIDER_PROBE: '첫 Codex 응답 검사 대기' });
Object.assign(statuses, { FAILED: '실패', PREPARATION_FAILED: 'Python 준비·연결 오류', PROCESSING_FAILED: '분석 처리 오류',
  PROCESSING: '검사·취합 처리 중', INVALID_RESPONSE: '응답 형식·참조 검사 실패', LOCAL_PREFLIGHT_REJECTED: '호출 전 검사 실패' });
const issueKinds = { PREPARATION: 'Python 준비·연결 오류', PROCESSING: '분석 처리 오류', MODEL_CALL: '모델 요청·응답 오류' };
const errorMeaning = { A04_GLOBAL_GROUPING_INPUT_BUDGET_EXCEEDED: '연구 발견을 한 번에 묶는 입력이 허용 크기를 넘었습니다.',
  A04_REQUIRES_COMPLETED_A03: 'A03 수집 완료 기록이 없어 A04 입력을 준비하지 못했습니다.',
  A04_FROZEN_SOURCE_CHANGED: 'A04 요청 준비 이후 원천 자료가 달라졌습니다.' };
const params = new URLSearchParams(location.search);
let run = params.get('run') || '', stage = params.get('stage') || '', automatic = true, timer, controller, generation = 0;
$('stage').value = stage;

async function read(url, signal) {
  const response = await fetch(url, { cache: 'no-store', signal });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `기록 조회 실패 (${response.status})`);
  return value;
}
function setLocation() {
  const query = new URLSearchParams({ run, tab: 'progress' }); if (stage) query.set('stage', stage);
  history.replaceState({}, '', `/?${query}`);
  $('detail-link').href = `/?run=${encodeURIComponent(run)}&tab=analysis`;
}
function showTip(event, text) {
  const tip = $('tooltip'); tip.textContent = text; tip.hidden = false;
  const rect = event.target.getBoundingClientRect();
  const x = event.clientX ?? rect.left, y = event.clientY ?? rect.top;
  tip.style.left = `${Math.max(8, Math.min(x + 12, window.innerWidth - 292))}px`;
  tip.style.top = `${Math.max(8, Math.min(y + 12, window.innerHeight - 115))}px`;
}

function chart(id, rows, series, { title, unit, fixedMax, threshold, domain, dots = false, step = false, height = 240 } = {}) {
  const holder = $(id); holder.replaceChildren();
  if (!rows.length) { holder.append(node('div', 'chart-empty', '아직 이 그래프에 사용할 시간 기록이 없습니다.')); return; }
  const width = Math.max(300, holder.clientWidth || (id === 'latency-chart' ? 1240 : 610)), pad = { left: 49, right: 18, top: 20, bottom: 33 };
  const times = rows.map(row => row.at), start = domain?.[0] ?? Math.min(...times), stop = domain?.[1] ?? Math.max(...times);
  const minX = stop === start ? start - 30000 : start, maxX = stop === start ? stop + 30000 : stop;
  const values = series.flatMap(line => (line.rows || rows).map(row => line.value(row))).filter(value => Number.isFinite(value));
  const maximum = fixedMax || Math.max(1, ...values) * 1.13;
  const x = value => pad.left + (value - minX) / (maxX - minX) * (width - pad.left - pad.right);
  const y = value => height - pad.bottom - value / maximum * (height - pad.top - pad.bottom);
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': title });
  svg.append(svgNode('title', {}, title), svgNode('desc', {}, `가로축 시각, 세로축 ${unit}. ${rows.length}개 시간 기록.`));
  if (threshold != null) {
    svg.append(svgNode('rect', { x: pad.left, y: pad.top, width: width - pad.left - pad.right, height: y(threshold) - pad.top, fill: '#f8eeea' }));
    svg.append(svgNode('rect', { x: pad.left, y: y(threshold), width: width - pad.left - pad.right, height: y(0) - y(threshold), fill: '#eef3ed' }));
  }
  for (let i = 0; i <= 4; i++) {
    const value = maximum * i / 4, yy = y(value);
    svg.append(svgNode('line', { x1: pad.left, x2: width - pad.right, y1: yy, y2: yy, class: 'grid-line' }));
    svg.append(svgNode('text', { x: pad.left - 9, y: yy + 3, 'text-anchor': 'end', class: 'axis-label' }, fixedMax || maximum >= 20 ? Math.round(value) : value.toFixed(1)));
    const at = minX + (maxX - minX) * i / 4;
    svg.append(svgNode('text', { x: x(at), y: height - 10, 'text-anchor': 'middle', class: 'axis-label' }, shortClock(at)));
  }
  svg.append(svgNode('text', { x: pad.left, y: 11, class: 'axis-label' }, unit));
  if (threshold != null) {
    svg.append(svgNode('line', { x1: pad.left, x2: width - pad.right, y1: y(threshold), y2: y(threshold), stroke: '#b96354', 'stroke-dasharray': '5 5' }));
    svg.append(svgNode('text', { x: width - pad.right, y: y(threshold) - 6, 'text-anchor': 'end', class: 'axis-label' }, `증가 기준 ${threshold}%`));
  }
  for (const line of series) {
    const source = line.rows || rows;
    const data = source.filter(row => Number.isFinite(line.value(row)));
    if (!data.length) continue;
    if (!line.pointsOnly) {
      const segments = []; let segment = [];
      for (const row of source) {
        if (Number.isFinite(line.value(row))) segment.push(row);
        else if (segment.length) { segments.push(segment); segment = []; }
      }
      if (segment.length) segments.push(segment);
      for (const points of segments) {
        const path = points.map((row, i) => i === 0 ? `M ${x(row.at)} ${y(line.value(row))}`
          : step ? `H ${x(row.at)} V ${y(line.value(row))}` : `L ${x(row.at)} ${y(line.value(row))}`).join(' ');
        if (line.area) svg.append(svgNode('path', { d: `${path} L ${x(points.at(-1).at)} ${y(0)} L ${x(points[0].at)} ${y(0)} Z`, fill: line.color, opacity: .13 }));
        svg.append(svgNode('path', { d: path, fill: 'none', stroke: line.color, 'stroke-width': line.dashed ? 2 : 2.3, 'stroke-dasharray': line.dashed ? '6 4' : 'none', 'stroke-linejoin': 'round', 'vector-effect': 'non-scaling-stroke' }));
      }
    }
    if (dots || line.pointsOnly) for (const row of data) {
      const text = `${clock(row.at)}\n${line.describe ? line.describe(row) : `${line.name}: ${line.value(row).toFixed(1)}${unit}`}`;
      const circle = svgNode('circle', { cx: x(row.at), cy: y(line.value(row)), r: line.pointsOnly ? 3.3 : 3,
        fill: typeof line.color === 'function' ? line.color(row) : line.color, opacity: line.pointsOnly ? .7 : 1,
        class: 'chart-point', tabindex: '0', 'aria-label': text });
      circle.append(svgNode('title', {}, text));
      circle.addEventListener('pointerenter', event => showTip(event, text));
      circle.addEventListener('pointermove', event => showTip(event, text));
      circle.addEventListener('pointerleave', () => { $('tooltip').hidden = true; });
      circle.addEventListener('focus', event => showTip(event, text));
      circle.addEventListener('blur', () => { $('tooltip').hidden = true; });
      svg.append(circle);
    }
  }
  holder.append(svg);
}

function meter(id, value, maximum, { threshold, label } = {}) {
  const holder = $(id); holder.replaceChildren();
  holder.setAttribute('role', 'img'); holder.setAttribute('aria-label', label);
  if (value == null || !maximum) { holder.classList.add('unmeasured'); return; }
  holder.classList.remove('unmeasured');
  const fill = node('span', 'meter-fill'); fill.style.width = `${Math.min(100, value / maximum * 100)}%`; holder.append(fill);
  if (threshold != null) { const marker = node('i', 'meter-threshold'); marker.style.left = `${threshold / maximum * 100}%`; holder.append(marker); }
}

function render(data) {
  const pythonOption = $('stage').querySelector('option[value="05_outcomes"]');
  if (pythonOption) pythonOption.hidden = !data.finalization;
  $('read-error').hidden = true; $('tooltip').hidden = true;
  $('run-label').textContent = data.run;
  $('title').textContent = data.stage_label;
  $('subtitle').textContent = `${data.model || '모델 미설정'} · ${data.backend || '방식 미설정'} · 분석 요청 1건을 한 단위로 집계합니다.`;
  $('status').textContent = statuses[data.status] || data.status;
  $('status').className = `status ${['RUNNING', 'PREPARING', 'PROCESSING', 'PROVIDER_PROBE', 'COLLECTED', 'COMPLETE'].includes(data.status) ? '' : 'stopped'}`;
  $('freshness').textContent = `${clock(data.observed_at)} 조회${automatic ? ' · 5초 갱신' : ' · 자동 갱신 꺼짐'}`;
  const analysis = data.analysis || {};
  $('analysis-status').textContent = `전체 Analysis 저장 상태: ${statuses[analysis.status] || analysis.status || '미기록'}${analysis.stage ? ` · 마지막 단계 ${analysis.stage}` : ''} · 실행 파이프라인: ${statuses[analysis.pipeline_status] || analysis.pipeline_status || '미기록'}. ${data.finalization ? data.finalization.explanation : 'A03 수집 완료와 전체 Analysis 완료는 별개입니다.'}`;
  const evaluation = node('div', 'phase'); evaluation.append(node('strong', '', '01 Evaluation'), node('span', '', `${fmt(data.evaluation.collected)} / ${fmt(data.evaluation.total)} 응답 · ${statuses[data.evaluation.status] || data.evaluation.status || '미기록'}`));
  $('phase-strip').replaceChildren(evaluation, ...data.phases.map(phase => {
    const item = node('div', `phase ${phase.key === data.stage ? 'active' : ''}`), facts = phase.records || {};
    item.append(node('strong', '', phase.title), node('span', `phase-status ${/FAILED|BLOCKED|INTERRUPTED/.test(phase.status) ? 'bad' : ''}`, statuses[phase.status] || phase.status),
      node('span', '', phase.description || `${phase.status === 'SKIPPED_BY_USER' ? '과거 기록 · ' : ''}계획 ${fmt(facts.planned)} · 완료 ${fmt(facts.completed)} · 유효 ${fmt(facts.valid)} · 실패 ${fmt(facts.failed)}`));
    return item;
  }));
  const facts = data.records || {};
  $('stage-records').textContent = `${data.stage_label} · 저장 기록: 계획 ${facts.planned == null ? '미확정' : `${fmt(facts.planned)}건`} / 처리 완료 ${fmt(facts.completed)} / 유효 ${fmt(facts.valid)} / 실패 ${fmt(facts.failed)} · 측정된 단계 경과 ${duration(data.metrics.stage_elapsed_seconds)}. 처리 완료는 결과가 저장된 요청 수이며 유효와 실패를 모두 포함합니다.`;
  const c = data.counts;
  const cards = [['total', '전체 요청', '선택한 분석 단계의 계획 요청'], ['completed', '유효·검사 통과', '분석 응답 계약·인용 검사 통과'], ['running', '실행 중', '실제 진행 중인 호출'], ['waiting', '대기', '아직 처리되지 않은 요청'], ['errors', '호출 오류·응답 미확인', '유효에서 제외 · 기록 보존'], ['remaining', '남은 건수', '실행 중 + 대기 + 호출 오류']];
  $('counts').replaceChildren(...cards.map(([key, title, note]) => { const card = node('article', `metric ${key}`); card.append(node('p', 'metric-title', title), node('p', 'metric-value', fmt(c[key])), node('p', 'metric-note', note)); return card; }));
  $('completion-label').textContent = c.total ? `유효 ${((c.completed / c.total) * 100).toFixed(1)}% · ${fmt(c.completed)} / ${fmt(c.total)}건` : c.total === 0 ? '계획된 모델 요청 없음 · 0건' : '전체 요청 수 확정 전';
  if (data.status === 'SKIPPED_BY_USER') $('completion-label').textContent = '사용자 지시로 생략 · 현재 완료 조건과 남은 작업에서 제외';
  if (data.stage === '05_outcomes') $('completion-label').textContent = statuses[data.status] || data.status;
  $('count-equation').textContent = c.total == null ? 'A02·A03·A04의 요청 수는 각각 계산합니다.' : `${fmt(c.total)} = 유효 ${fmt(c.completed)} + 실행 중 ${fmt(c.running)} + 대기 ${fmt(c.waiting)} + 호출 오류 ${fmt(c.errors)}`;
  $('progress-bar').replaceChildren(); $('progress-legend').replaceChildren();
  for (const [key, title] of cards.slice(1, 5)) {
    if (c.total && c[key] != null && c.consistent) { const segment = node('span', key); segment.style.width = `${c[key] / c.total * 100}%`; $('progress-bar').append(segment); }
    const entry = node('span'); entry.append(node('i', `dot ${key}`), `${title} ${fmt(c[key])}`); $('progress-legend').append(entry);
  }
  $('progress-bar').setAttribute('aria-label', $('count-equation').textContent);
  const notices = [...data.warnings];
  if (data.queue?.status === 'WAITING_FOR_ANALYSIS') notices.push(`${data.queue.after_run}의 분석 완료 후 ${data.queue.execution_scope === 'ANALYSIS_ONLY' ? 'Analysis' : 'Evaluation Batch'}를 시작하도록 대기 중입니다.`);
  $('warnings').replaceChildren(...notices.map(text => node('div', 'notice', text)), ...(data.issues || []).map(issue => {
    const block = node('div', `notice ${issue.historical ? '' : 'danger'}`);
    block.append(node('strong', '', `${issue.historical ? '이전 기록 · ' : ''}${issueKinds[issue.kind] || issue.kind} · ${statuses[issue.status] || issue.status}`));
    if (errorMeaning[issue.message]) block.append(node('p', '', errorMeaning[issue.message]));
    block.append(node('p', 'issue-message', issue.message));
    const identity = issue.trial_id ? ` · 요청 ${issue.trial_id} · 시도 ${issue.attempt ?? '미기록'}` : '';
    block.append(node('small', 'issue-source', `${issue.at ? new Date(issue.at).toLocaleString('ko-KR', { hour12: false }) : '시각 미기록'}${identity} · ${issue.source}`));
    return block;
  }));
  const m = data.metrics, sample = data.scheduler.last_cpu_sample;
  const measurements = [['건당 평균 처리시간', duration(m.mean_seconds), `검사 통과 ${fmt(m.samples)}건 기준`],
    ['현재 작업 경과', duration(data.activity?.elapsed_seconds), data.activity?.label || '진행 중인 작업 없음'],
    ['최근 20건 평균', duration(m.recent_mean_seconds), '표본이 20건 미만이면 확보한 건수 기준'],
    ['95백분위 처리시간', duration(m.p95_seconds), `중앙값 ${duration(m.p50_seconds)}`],
    ['동시 호출 한도', data.scheduler.limit == null ? '미기록' : `${fmt(data.scheduler.limit)}건`, data.scheduler.alive ? '실행기 동작 확인' : '실행 중인 Codex 실행기 없음'],
    ['마지막 CPU 평균', sample?.cpu_percent == null ? '미측정' : `${sample.cpu_percent.toFixed(1)}%`, sample?.sampled_at ? `${clock(sample.sampled_at)} 측정` : '첫 측정 구간이 끝나면 표시']];
  $('timing-metrics').replaceChildren(...measurements.map(([title, value, note]) => { const item = node('div', 'timing-metric'); item.append(node('p', '', title), node('strong', '', value), node('small', '', note)); return item; }));
  chart('latency-chart', data.charts.calls, [
    { pointsOnly: true, value: row => row.seconds / 60, color: row => row.status === 'VALID' ? colors.completed : colors.errors,
      describe: row => `${statuses[row.status] || row.status} · ${duration(row.seconds)}\n요청 ${row.trial_id.slice(0, 12)} · 시도 ${row.attempt ?? '미기록'}` },
    { rows: data.charts.averages, value: row => row.seconds / 60, color: colors.average, name: '최근 20건 평균' }
  ], { title: '개별 분석 요청의 처리시간과 최근 20건 평균', unit: '분', height: 275 });
  $('latency-note').textContent = `평균선은 검사 통과 호출만 사용합니다. 오류·시간 초과 ${fmt(m.timed_failure_count)}건은 별도 색으로 표시하며 평균에서 제외합니다. 미완료 호출의 소요 시간은 평균에 넣지 않습니다.`;
  chart('completion-chart', data.charts.history, [{ value: row => row.completed, color: colors.completed }], { title: '시간에 따른 완료 누적 건수', unit: '건', step: true });
  const policy = data.scheduler.policy?.adaptive;
  const limit = data.scheduler.limit, cpu = sample?.cpu_percent;
  $('running-now').textContent = c.running == null ? '미기록' : `${fmt(c.running)}건`;
  $('running-capacity').textContent = `${data.scheduler.alive ? '현재' : '마지막 기록'} 한도 ${fmt(limit)}건`;
  $('cpu-now').textContent = cpu == null ? '미측정' : `${cpu.toFixed(1)}%`;
  $('cpu-sampled').textContent = sample?.sampled_at ? `${clock(sample.sampled_at)} 측정${data.scheduler.alive ? '' : ' · 실행 종료'}` : '측정 기록 없음';
  $('cpu-threshold').textContent = policy?.enabled ? `${policy.cpu_threshold_percent}% 이하 → 증설 가능` : '저장된 전체 CPU 표본';
  meter('running-meter', c.running, limit, { label: `실행 중 ${fmt(c.running)}건 / 한도 ${fmt(limit)}건` });
  meter('cpu-meter', cpu, 100, { threshold: policy?.cpu_threshold_percent, label: `전체 CPU ${cpu == null ? '미측정' : `${cpu.toFixed(1)}%`}, 기준 ${fmt(policy?.cpu_threshold_percent)}%` });
  const operations = [...data.charts.history, ...data.charts.cpu, ...data.charts.limits];
  const domain = operations.length ? [Math.min(...operations.map(row => row.at)), Math.max(...operations.map(row => row.at))] : undefined;
  chart('running-chart', [...data.charts.history, ...data.charts.limits], [
    { rows: data.charts.history, value: row => row.running, color: colors.running, area: true },
    { rows: data.charts.limits, value: row => row.limit, color: colors.average, dashed: true }
  ], { title: '시간에 따른 실제 동시 호출 수와 호출 한도', unit: '건', step: true, domain });
  chart('cpu-chart', data.charts.cpu, [{ value: row => row.percent, color: colors.completed, area: true,
    describe: row => `전체 CPU ${row.percent.toFixed(1)}%\n기록된 동시 호출 한도 ${fmt(row.limit)}건` }],
    { title: '전체 CPU 사용률 표본과 증가 기준', unit: '%', fixedMax: 100, threshold: policy?.cpu_threshold_percent, dots: true, domain });
  $('cpu-note').textContent = policy?.enabled ? `${policy.interval_seconds}초마다 측정해 ${policy.cpu_threshold_percent}% 이하이고 남은 요청이 한도보다 많으면 한도를 ${policy.growth_percent}% 늘립니다. 선이 끊긴 곳은 미측정입니다. CPU는 이 컴퓨터 전체 사용률입니다.` : '기록된 전체 CPU 표본입니다. 측정하지 않은 구간의 값을 만들지 않습니다.';
  const table = node('table'), head = node('thead'), header = node('tr');
  for (const text of ['종료 시각', '요청 ID', '처리시간', '상태']) header.append(node('th', '', text)); head.append(header); table.append(head);
  const body = node('tbody');
  for (const row of data.charts.calls.slice(-12).reverse()) { const tr = node('tr'); for (const text of [clock(row.at), row.trial_id.slice(0, 10), duration(row.seconds), statuses[row.status] || row.status]) tr.append(node('td', row.status === 'VALID' ? '' : 'bad', text)); body.append(tr); }
  table.append(body); $('recent').replaceChildren(data.charts.calls.length ? table : node('div', 'chart-empty', '아직 종료한 호출이 없습니다.'));
  $('sources').textContent = `원기록: ${data.sources.join(' · ')} · 데이터 갱신 ${data.state_updated_at ? clock(data.state_updated_at) : '미기록'}`;
}

async function refresh() {
  clearTimeout(timer); controller?.abort(); controller = new AbortController(); const current = ++generation;
  $('refresh').disabled = true;
  try {
    const query = stage ? `?stage=${encodeURIComponent(stage)}` : '';
    const data = await read(`/api/runs/${encodeURIComponent(run)}/progress${query}`, controller.signal);
    if (current === generation) render(data);
  } catch (error) {
    if (error.name !== 'AbortError' && current === generation) { $('read-error').textContent = `최신 기록을 읽지 못했습니다. 화면의 이전 값을 유지합니다. ${error.message}`; $('read-error').hidden = false; }
  } finally {
    if (current === generation) { $('refresh').disabled = false; if (automatic) timer = setTimeout(refresh, 5000); }
  }
}
$('run').addEventListener('change', () => { run = $('run').value; setLocation(); refresh(); });
$('stage').addEventListener('change', () => { stage = $('stage').value; setLocation(); refresh(); });
$('refresh').addEventListener('click', refresh);
$('auto').addEventListener('click', () => {
  automatic = !automatic; $('auto').setAttribute('aria-pressed', automatic);
  $('auto').textContent = automatic ? '자동 갱신 켜짐 · 5초' : '자동 갱신 꺼짐';
  if (automatic) refresh(); else { clearTimeout(timer); $('freshness').textContent = `${$('freshness').textContent.split(' · ')[0]} · 자동 갱신 꺼짐`; }
});
try {
  const { runs } = await read('/api/runs');
  if (!runs.length) throw new Error('저장된 실행이 없습니다.');
  if (!runs.some(item => item.id === run)) run = runs.find(item => item.analysis_status === 'RUNNING')?.id || runs[0].id;
  $('run').replaceChildren(...runs.map(item => { const option = node('option', '', item.id); option.value = item.id; return option; })); $('run').value = run;
  setLocation(); await refresh();
} catch (error) { $('read-error').textContent = error.message; $('read-error').hidden = false; }
