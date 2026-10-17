(() => {
  'use strict';

  const el = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const names = {
    active: 'In progress', idle: 'Waiting', attention: 'Review required', blocked: 'Block it.',
    pending: 'Unfinished.', open: 'Confirmation', decision: 'Decision pending',
    complete: 'Complete', running: 'In progress', online: 'Normal',
    unavailable: 'No response', unknown: 'Not recorded'
  };
  const analysisNames = {COMPLETE: 'Complete', PARTIAL: 'Part of it.', BLOCKED: 'Block it.'};
  let data = null;
  const groupNames = new Map();

  function time(value) {
    if (!value) return 'Time not recorded';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Time not recorded';
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).format(date);
  }

  function groupName(id) { return groupNames.get(id) || 'Check the classification'; }
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
    return `<a href="/api/project/source?ref=${encodeURIComponent(item.sourceRef)}\x22target=\x22_blank\x22 rel=\x22noopener\x22> source code is</a>`;
  }

  function renderSummary() {
    const active = data.sessions.filter(session => session.status === 'active').length;
    const blocked = data.tasks.filter(task => ['blocked', 'attention'].includes(task.status)).length;
    const cards = [
      ['Main session', data.sessions.length, 'Full list of tasks', '#497faa'],
      ['The session is ongoing.', active, 'The conversation turn.', '#249178'],
      ['The rest of the check.', data.tasks.length, 'Save document run by default', '#c69039'],
      ['Barricade and scope', blocked, 'Running record standards', '#c65b5d']
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
        return `<button type="button" class="session-node" data-session-id="${esc(session.id)}" title="${esc(session.name)} · ${esc(names[signal(session)])}"><i class="signal ${signal(session)}" aria-hidden="true"></i><span class="node-name">${esc(session.name)}</span>${session.children.length ? `The child that actually created the node-tag. ${session.children.length}The items.${session.children.length}</span>` : ''}${outstanding ? `The number of nodes is not complete. ${outstanding}entries\x22>${outstanding}</span>` : ''}</button>`;
      }).join('');
      return `<div class="group-label"><span>${esc(group.name)}</span><span>${sessions.length}</span></div>${rows}`;
    }).join('');
    const parents = data.sessions.filter(session => session.children.length);
    const children = parents.reduce((total, session) => total + session.children.length, 0);
    el('lineage-summary').textContent = `The real relationship between parents ${parents.length} / child ${children}`;
  }

  function renderStages() {
    const completed = data.runs.filter(run => run.analysisStatus === 'COMPLETE').length;
    const unfinished = data.runs.filter(run => run.status !== 'complete').length;
    const evaluated = data.runs.filter(run => ['FINISHED', 'EVALUATION_COMPLETE'].includes(run.evaluationStatus)).length;
    const research = data.tasks.filter(task => task.group === 'research').length;
    const dataset = data.dataset;
    const stages = [
      ['01 / DATASET', 'Creating a data set', dataset ? `Source text ${dataset.originals ?? '—'} · Ready ${dataset.preparationPass ?? '—'}` : 'The storage report is unverified', dataset?.generationPass != null ? `Transformed through ${dataset.generationPass.toLocaleString('en-US')}` : 'Check the status.'],
      ['02 / EVALUATION', 'The model pool.', `${evaluated}items run collection record`, 'Form pass ≠ meaning correct answer'],
      ['03 / ANALYSIS', 'Analysis of the results', `Complete ${completed} · Check ${unfinished}`, 'A01 → A02 → A03'],
      ['04 / RESEARCH', 'Research and development', `The rest of the business. ${research}entries`, 'Results: Based on the waiting']
    ];
    el('stage-strip').innerHTML = stages.map(([code, title, detail, status]) =>
      `<div class="stage"><small>${esc(code)}</small><strong>${esc(title)}</strong><span>${esc(detail)}</span><b>${esc(status)}</b></div>`
    ).join('');
  }

  function renderPriority() {
    el('task-count').textContent = data.tasks.length;
    el('priority-list').innerHTML = data.tasks.length ? data.tasks.slice(0, 6).map(task =>
      `<button type="button" class="task-row" data-task-id="${esc(task.id)}" title="${esc(task.title)}"><i class="task-mark ${esc(task.status)}"></i><span class="task-title">${esc(task.title)}</span><span class="task-meta">${esc(groupName(task.group))} · ${esc(names[task.status] || 'Check')}</span></button>`
    ).join('') : '<p class=\x22empty\x22>There\x27s no unfinished record in the document run.</p>';
  }

  function renderActive() {
    const active = data.sessions.filter(session => session.status === 'active');
    el('active-count').textContent = active.length;
    el('active-list').innerHTML = active.length ? active.map(session =>
      `<button type="button" class="active-row" data-session-id="${esc(session.id)}"><i class="signal active"></i><span><strong>${esc(session.name)}</strong><small>${esc(session.recentTasks[0]?.text || 'Currently requested content')}</small></span></button>`
    ).join('') : '<p class=\x22empty\x22>There\x27s no session recorded as we\x27re working on it.</p>';
  }

  function renderRuns() {
    const rows = data.runs.slice(0, 6).map(run => {
      const evaluation = ['FINISHED', 'EVALUATION_COMPLETE'].includes(run.evaluationStatus) ? 'Collection completed' : 'Checking';
      return `<div class="run-row"><span class="run-name" title="${esc(run.name)}">${esc(run.name)}</span><span>${esc(evaluation)}</span><span>${badge(run.status, analysisNames[run.analysisStatus] || 'Not recorded')}</span>${sourceLink(run)}</div>`;
    }).join('');
    el('run-list').innerHTML = rows ? '<div class=\x22run-row run-head\x22><span>Save and run</span><span>The grass.</span><span>Analysis</span><span>Evidence</span></div>' + rows : '<p class=\x22empty\x22>No running state saved.</p>';
  }

  function renderAreas() {
    const rows = data.groups.filter(group => data.tasks.some(task => task.group === group.id));
    const max = Math.max(1, ...rows.map(group => data.tasks.filter(task => task.group === group.id).length));
    el('area-list').innerHTML = rows.map(group => {
      const count = data.tasks.filter(task => task.group === group.id).length;
      return `<button type="button" class="area-row" data-area-id="${esc(group.id)}"><strong>${esc(group.name)}</strong><span class="area-track"><i style="width:${Math.round(count / max * 100)}%"></i></span><b>${count}</b></button>`;
    }).join('') || '<p class=\x22empty\x22>There\x27s no unfinished record for each region.</p>';
  }

  function renderServices() {
    el('service-list').innerHTML = data.services.map(service =>
      `<span class="service-item"><i class="${esc(service.status)}"></i>${esc(service.name)} ${service.port} · ${esc(names[service.status] || 'Unverified')}</span>`
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
      `<li>${esc(request.text)}<small class="muted"> · ${esc(time(request.at))} · ${request.turnStatus === 'completed' ? 'Answer turn is complete.' : 'In progress, confirmation'}</small></li>`
    ).join('')}</ol>` : '<p class=\x22muted\x22>I didn\x27t read the last request.</p>';
    const outstanding = tasks.length ? tasks.map(task =>
      `<div class="detail-card"><strong>${esc(task.title)}</strong>${badge(task.status)}<small>${esc(task.detail)}</small>${sourceLink(task)}</div>`
    ).join('') : '<p class=\x22muted\x22>There is no unfinished record of the document run connected to this session.</p>';
    const children = session.children.length ? `<h3>The actual child session that was created. ${session.children.length}items</h3><ul>${session.children.map(child => `<li>${esc(child.name)}${child.role ? ` · ${esc(child.role)}` : ''}</li>`).join('')}</ul>` : '';
    openDialog('SESSION / ' + groupName(session.group), session.name,
      `${names[session.status] || 'Check the status.'} · ${time(session.updatedAt)} • Session ID ${session.id}`,
      `${session.lastReport ? `<h3>Last save report</h3><p>${esc(session.lastReport)}</p>` : ''}<h3>Recent user requests · maximum 3entries</h3>${requests}<h3>Related incomplete records · maximum 3entries</h3>${outstanding}${children}<p class=\x22muted\x22>Completion of the response turn of a request does not imply implementation, verification, user approval.</p>`);
  }

  function showTask(id) {
    const task = data.tasks.find(item => item.id === id);
    if (!task) return;
    openDialog('TASK / ' + groupName(task.group), task.title,
      `${names[task.status] || 'Check the status.'} · ${task.sourcePath || 'The underlying sub-record'}`,
      `<h3>The contents of the record</h3><p>${esc(task.detail)}</p><h3>The base file.</h3><p>${sourceLink(task)}</p><p class=\x22muted\x22>This item is a confirmation read from the saved document. Please confirm the completed judgment with the original and subsequent verification.</p>`);
  }

  function showTasks(group) {
    const tasks = data.tasks.filter(task => !group || task.group === group);
    openDialog('ACTION QUEUE', group ? `${groupName(group)} • What remains` : 'The rest of the job.',
      `${tasks.length}The storage and running status of the document`,
      tasks.map((task, index) => `<div class="detail-card"><strong>${index + 1}. ${esc(task.title)}</strong>${badge(task.status)}<small>${esc(task.detail)}</small>${sourceLink(task)}</div>`).join('') || '<p>There\x27s no record of it at this time.</p>');
  }

  function showLineage() {
    const parents = data.sessions.filter(session => session.children.length);
    openDialog('VERIFIED LINEAGE', 'The real parent-child relationship',
      'It shows only the relationship you read from the Codex thread_spawn_edges record.',
      parents.map(parent => `<h3>${esc(parent.name)} → Child ${parent.children.length}items</h3><ul>${parent.children.map(child => `<li>${esc(child.name)}${child.role ? ` · ${esc(child.role)}` : ''}</li>`).join('')}</ul>`).join('') || '<p class=\x22muted\x22>There\x27s no confirmed production relationship.</p>');
  }

  function render() {
    groupNames.clear();
    data.groups.forEach(group => groupNames.set(group.id, group.name));
    el('updated-at').textContent = 'Last check. ' + time(data.generatedAt);
    el('scope-note').textContent = data.scope;
    el('source-age').textContent = 'If the browser is open, 1I\x27ll update you every minute.';
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
      el('warnings').textContent = `I didn\x27t read the situation: ${error.message}Please press read again.`;
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
