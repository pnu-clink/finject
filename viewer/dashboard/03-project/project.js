(() => {
  'use strict';

  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const names = {
    active: '작업 중', idle: '대기', attention: '검토 필요', blocked: '차단',
    pending: '미완료', open: '확인 사항', decision: '결정 대기',
    complete: '완료', running: '진행 중', online: '정상',
    unavailable: '응답 없음', unknown: '미기록'
  };
  const analysisNames = {COMPLETE: '완료', PARTIAL: '부분', BLOCKED: '차단'};
  let data = null;
  const groupNames = new Map();

  function time(value) {
    if (!value) return '시각 미기록';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '시각 미기록';
    return new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).format(date);
  }

  function groupName(id) { return groupNames.get(id) || '분류 확인'; }
  function related(session) { return data.tasks.filter(task => task.relatedSessionId === session.id); }
  function signal(session) {
    const tasks = related(session);
    if (session.status === 'active') return 'active';
    if (tasks.some(task => ['blocked', 'attention'].includes(task.status))) return 'blocked';
    if (tasks.length) return 'pending';
    return 'idle';
  }
  function badge(status, label) {
    const key = names[status] ? status : 'idle';
    return `<span class="status ${key}">${esc(label || names[key])}</span>`;
  }
  function sourceLink(item) {
    if (!item.sourceRef) return '';
    return `<a href="/api/project/source?ref=${encodeURIComponent(item.sourceRef)}" target="_blank" rel="noopener">원문 근거 ↗</a>`;
  }

  function renderSummary() {
    const active = data.sessions.filter(session => session.status === 'active').length;
    const blocked = data.tasks.filter(task => ['blocked', 'attention'].includes(task.status)).length;
    const cards = [
      ['주요 세션', data.sessions.length, '업무별 전체 목록', '#497faa'],
      ['진행 중 세션', active, '대화 턴 기준', '#249178'],
      ['남은 확인·결정', data.tasks.length, '저장 문서·run 기준', '#c69039'],
      ['막힘·검토', blocked, '실행 기록 기준', '#c65b5d']
    ];
    el('summary-grid').innerHTML = cards.map(([title, count, note, color]) =>
      `<div class="summary-card" style="--accent:${color}"><strong>${count}</strong><div><span>${esc(title)}</span><small>${esc(note)}</small></div></div>`
    ).join('');
  }

  function renderStructure() {
    const groups = data.groups.filter(group => data.sessions.some(session => session.group === group.id));
    el('structure-count').textContent = data.sessions.length;
    el('structure-list').innerHTML = groups.map(group => {
      const sessions = data.sessions.filter(session => session.group === group.id)
        .sort((a, b) => Number(b.status === 'active') - Number(a.status === 'active') ||
          String(b.updatedAt).localeCompare(String(a.updatedAt)));
      const rows = sessions.map(session => {
        const outstanding = related(session).length;
        return `<button type="button" class="session-node" data-session-id="${esc(session.id)}" title="${esc(session.name)} · ${esc(names[signal(session)])}"><i class="signal ${signal(session)}" aria-hidden="true"></i><span class="node-name">${esc(session.name)}</span>${session.children.length ? `<span class="node-tag" title="실제 생성 자식 ${session.children.length}개">↳${session.children.length}</span>` : ''}${outstanding ? `<span class="node-task-count" title="연결된 미완료 ${outstanding}건">${outstanding}</span>` : ''}</button>`;
      }).join('');
      return `<div class="group-label"><span>${esc(group.name)}</span><span>${sessions.length}</span></div>${rows}`;
    }).join('');
    const parents = data.sessions.filter(session => session.children.length);
    const children = parents.reduce((total, session) => total + session.children.length, 0);
    el('lineage-summary').textContent = `실제 생성 관계 · 부모 ${parents.length} / 자식 ${children}`;
  }

  function renderStages() {
    const completed = data.runs.filter(run => run.analysisStatus === 'COMPLETE').length;
    const unfinished = data.runs.filter(run => run.status !== 'complete').length;
    const evaluated = data.runs.filter(run => ['FINISHED', 'EVALUATION_COMPLETE'].includes(run.evaluationStatus)).length;
    const research = data.tasks.filter(task => task.group === 'research').length;
    const dataset = data.dataset;
    const stages = [
      ['01 / DATASET', '데이터셋 제작', dataset ? `원문 ${dataset.originals ?? '—'} · 준비 ${dataset.preparationPass ?? '—'}` : '저장 보고서 미확인', dataset?.generationPass != null ? `변형 통과 ${dataset.generationPass.toLocaleString('ko-KR')}` : '상태 확인'],
      ['02 / EVALUATION', '모델 풀이', `${evaluated}개 run 수집 기록`, '형식 통과 ≠ 의미 정답'],
      ['03 / ANALYSIS', '결과 분석', `완료 ${completed} · 확인 ${unfinished}`, 'A01 → A02 → A03'],
      ['04 / RESEARCH', '연구·원고', `관련 남은 일 ${research}건`, '결과·결론 근거 대기']
    ];
    el('stage-strip').innerHTML = stages.map(([code, title, detail, status]) =>
      `<div class="stage"><small>${esc(code)}</small><strong>${esc(title)}</strong><span>${esc(detail)}</span><b>${esc(status)}</b></div>`
    ).join('');
  }

  function renderPriority() {
    el('task-count').textContent = data.tasks.length;
    el('priority-list').innerHTML = data.tasks.length ? data.tasks.slice(0, 6).map(task =>
      `<button type="button" class="task-row" data-task-id="${esc(task.id)}" title="${esc(task.title)}"><i class="task-mark ${esc(task.status)}"></i><span class="task-title">${esc(task.title)}</span><span class="task-meta">${esc(groupName(task.group))} · ${esc(names[task.status] || '확인')}</span></button>`
    ).join('') : '<p class="empty">문서·run에서 읽은 미완료 기록이 없습니다.</p>';
  }

  function renderActive() {
    const active = data.sessions.filter(session => session.status === 'active');
    el('active-count').textContent = active.length;
    el('active-list').innerHTML = active.length ? active.map(session =>
      `<button type="button" class="active-row" data-session-id="${esc(session.id)}"><i class="signal active"></i><span><strong>${esc(session.name)}</strong><small>${esc(session.recentTasks[0]?.text || '현재 요청 내용 미기록')}</small></span></button>`
    ).join('') : '<p class="empty">현재 작업 중으로 기록된 세션이 없습니다.</p>';
  }

  function renderRuns() {
    const rows = data.runs.slice(0, 6).map(run => {
      const evaluation = ['FINISHED', 'EVALUATION_COMPLETE'].includes(run.evaluationStatus) ? '수집 완료' : '확인 중';
      return `<div class="run-row"><span class="run-name" title="${esc(run.name)}">${esc(run.name)}</span><span>${esc(evaluation)}</span><span>${badge(run.status, analysisNames[run.analysisStatus] || '미기록')}</span>${sourceLink(run)}</div>`;
    }).join('');
    el('run-list').innerHTML = rows ? '<div class="run-row run-head"><span>저장 실행</span><span>풀이</span><span>Analysis</span><span>근거</span></div>' + rows : '<p class="empty">저장된 실행 상태가 없습니다.</p>';
  }

  function renderAreas() {
    const rows = data.groups.filter(group => data.tasks.some(task => task.group === group.id));
    const max = Math.max(1, ...rows.map(group => data.tasks.filter(task => task.group === group.id).length));
    el('area-list').innerHTML = rows.map(group => {
      const count = data.tasks.filter(task => task.group === group.id).length;
      return `<button type="button" class="area-row" data-area-id="${esc(group.id)}"><strong>${esc(group.name)}</strong><span class="area-track"><i style="width:${Math.round(count / max * 100)}%"></i></span><b>${count}</b></button>`;
    }).join('') || '<p class="empty">영역별 미완료 기록이 없습니다.</p>';
  }

  function renderServices() {
    el('service-list').innerHTML = data.services.map(service =>
      `<span class="service-item"><i class="${esc(service.status)}"></i>${esc(service.name)} ${service.port} · ${esc(names[service.status] || '확인 불가')}</span>`
    ).join('');
  }

  function openDialog(kicker, title, subtitle, body) {
    el('dialog-kicker').textContent = kicker;
    el('dialog-title').textContent = title;
    el('dialog-subtitle').textContent = subtitle;
    el('dialog-body').innerHTML = body;
    if (!el('detail-dialog').open) el('detail-dialog').showModal();
  }

  function showSession(id) {
    const session = data.sessions.find(item => item.id === id);
    if (!session) return;
    const tasks = related(session).slice(0, 3);
    const requests = session.recentTasks.length ? `<ol>${session.recentTasks.map(request =>
      `<li>${esc(request.text)}<small class="muted"> · ${esc(time(request.at))} · ${request.turnStatus === 'completed' ? '응답 턴 완료' : '진행·확인 중'}</small></li>`
    ).join('')}</ol>` : '<p class="muted">최근 요청을 읽지 못했습니다.</p>';
    const outstanding = tasks.length ? tasks.map(task =>
      `<div class="detail-card"><strong>${esc(task.title)}</strong>${badge(task.status)}<small>${esc(task.detail)}</small>${sourceLink(task)}</div>`
    ).join('') : '<p class="muted">이 세션에 연결된 문서·run 미완료 기록은 없습니다.</p>';
    const children = session.children.length ? `<h3>실제 생성된 자식 세션 ${session.children.length}개</h3><ul>${session.children.map(child => `<li>${esc(child.name)}${child.role ? ` · ${esc(child.role)}` : ''}</li>`).join('')}</ul>` : '';
    openDialog('SESSION / ' + groupName(session.group), session.name,
      `${names[session.status] || '상태 확인'} · ${time(session.updatedAt)} · 세션 ID ${session.id}`,
      `${session.lastReport ? `<h3>마지막 저장 보고</h3><p>${esc(session.lastReport)}</p>` : ''}<h3>최근 사용자 요청 · 최대 3건</h3>${requests}<h3>관련 미완료 기록 · 최대 3건</h3>${outstanding}${children}<p class="muted">요청의 응답 턴 완료는 구현·검증·사용자 승인을 뜻하지 않습니다.</p>`);
  }

  function showTask(id) {
    const task = data.tasks.find(item => item.id === id);
    if (!task) return;
    openDialog('TASK / ' + groupName(task.group), task.title,
      `${names[task.status] || '상태 확인'} · ${task.sourcePath || '근거 미기록'}`,
      `<h3>저장 기록의 내용</h3><p>${esc(task.detail)}</p><h3>근거 파일</h3><p>${sourceLink(task)}</p><p class="muted">이 항목은 저장 문서·실행 상태에서 읽은 확인 사항입니다. 완료 판단은 원문과 후속 검증을 함께 확인해 주세요.</p>`);
  }

  function showTasks(group) {
    const tasks = data.tasks.filter(task => !group || task.group === group);
    openDialog('ACTION QUEUE', group ? `${groupName(group)} · 남은 일` : '전체 남은 일',
      `${tasks.length}건 · 저장 문서와 실행 상태 기준`,
      tasks.map((task, index) => `<div class="detail-card"><strong>${index + 1}. ${esc(task.title)}</strong>${badge(task.status)}<small>${esc(task.detail)}</small>${sourceLink(task)}</div>`).join('') || '<p>현재 기록된 항목이 없습니다.</p>');
  }

  function showLineage() {
    const parents = data.sessions.filter(session => session.children.length);
    openDialog('VERIFIED LINEAGE', '실제 부모·자식 생성 관계',
      'Codex thread_spawn_edges 기록에서 읽은 관계만 표시합니다.',
      parents.map(parent => `<h3>${esc(parent.name)} → 자식 ${parent.children.length}개</h3><ul>${parent.children.map(child => `<li>${esc(child.name)}${child.role ? ` · ${esc(child.role)}` : ''}</li>`).join('')}</ul>`).join('') || '<p class="muted">확인된 생성 관계가 없습니다.</p>');
  }

  function render() {
    groupNames.clear();
    data.groups.forEach(group => groupNames.set(group.id, group.name));
    el('updated-at').textContent = '마지막 확인 ' + time(data.generatedAt);
    el('scope-note').textContent = data.scope;
    el('source-age').textContent = '브라우저가 열려 있으면 1분마다 갱신';
    el('warnings').hidden = !data.warnings.length;
    el('warnings').textContent = data.warnings.join(' · ');
    renderSummary(); renderStructure(); renderStages(); renderPriority();
    renderActive(); renderRuns(); renderAreas(); renderServices();
    el('main').setAttribute('aria-busy', 'false');
  }

  async function refresh() {
    el('refresh').disabled = true;
    try {
      const response = await fetch('/api/project/status', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
      render();
    } catch (error) {
      el('warnings').hidden = false;
      el('warnings').textContent = `현황을 읽지 못했습니다: ${error.message}. 새로 읽기를 눌러 다시 시도해 주세요.`;
      el('main').setAttribute('aria-busy', 'false');
    } finally {
      el('refresh').disabled = false;
    }
  }

  el('refresh').addEventListener('click', refresh);
  el('all-tasks').addEventListener('click', () => data && showTasks());
  el('lineage-open').addEventListener('click', () => data && showLineage());
  el('close-detail').addEventListener('click', () => el('detail-dialog').close());
  el('detail-dialog').addEventListener('click', event => {
    if (event.target === el('detail-dialog')) el('detail-dialog').close();
  });
  document.addEventListener('click', event => {
    if (!data) return;
    const session = event.target.closest('[data-session-id]');
    const task = event.target.closest('[data-task-id]');
    const area = event.target.closest('[data-area-id]');
    if (session) showSession(session.dataset.sessionId);
    else if (task) showTask(task.dataset.taskId);
    else if (area) showTasks(area.dataset.areaId);
  });
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 60_000);
  refresh();
})();
