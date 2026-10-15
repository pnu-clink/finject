'use strict';

(() => {
  const promptName = value => ({ P0: 'Unguided Solving', P1: 'Criteria-Guided Solving' })[value] || value || '미기록';
  const reasoningName = value => ({ off: 'Reasoning OFF', on: 'Reasoning ON' })[value] || value || '미기록';
  const $ = id => document.getElementById(id);
  const number = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });
  const duration = new Intl.NumberFormat('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const variantNames = { ORIGINAL: '원문', IC_VALUE_01_BEFORE: '값 충돌 · 앞', IC_VALUE_01_AFTER: '값 충돌 · 뒤', IC_SOURCE_A_ONLY: '출처 A', IC_SOURCE_B_ONLY: '출처 B', IC_RELATION_01: '관계 충돌', EA_01: '근거 삭제 01', EA_02: '근거 삭제 02' };
  const tagNames = { ANSWER_ABSENT_FROM_EQUATION_RHS_CANDIDATE: '답·계산식 불일치 후보', DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER: '유보 선언 + 숫자', DECLARED_ABSTENTION_WITH_NON_NULL_SIGN: '유보 선언 + 부호', DECLARED_ABSTENTION_WITH_ZERO: '유보 선언 + 0', EMPTY_EVIDENCE: '빈 인용 배열', EVIDENCE_NOT_EXACT_SUBSTRING: '정확 인용 불일치', EXPLANATION_NO_COMMITMENT_CUE: '설명에 유보 표현', NON_NULL_ANSWER: 'null이 아닌 답', NULL_ANSWER: '숫자 없음 · null', NUMERIC_FIELD_PRESENT: '숫자 필드 관측', NUMERIC_FIELD_WITH_NO_COMMITMENT_CUE: '숫자 + 유보 표현', POSITIVE_ANSWER_WITH_SAME_NEGATIVE_NUMBER_CANDIDATE: '부호 불일치 후보', QUESTION_METADATA_PRECISION_CONFLICT: '질문·자릿수 지시 충돌', RAW_DECLARED_ABSTENTION: '원응답 유보 선언', SAVED_DECIMAL_PLACES_FAILURE: '저장된 자릿수 검사 실패' };
  const statusNames = { VALID: '형식 통과', INVALID_RESPONSE: '형식 실패', MISSING: '미관측', NOT_RUN: '미실행' };
  const filterIds = { variant: 'variant-filter', prompt: 'prompt-filter', reasoning: 'reasoning-filter', status: 'status-filter', tag: 'tag-filter', case: 'case-filter' };
  const state = { data: null, rows: [], filtered: [], tableRows: [], byId: new Map(), filters: {}, sort: 'completed_at', direction: -1, axis: 'completion', pendingTrial: null, page: 0, pageSize: 25, focusId: null, hoverId: null, brushIds: null, points: [], drag: null, detailCache: new Map(), detailSequence: 0, loading: false };
  const canvas = $('scatter');
  const ctx = canvas.getContext('2d');
  let dataController;
  let detailController;
  let animationPending = false;
  let plotWidth = 0;
  let plotHeight = 0;
  const plotTheme = { blue: '#367ec9', teal: '#0f9a8d', muted: '#81909d', font: 'system-ui, sans-serif' };
  const make = (tag, className, content) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (content !== undefined) el.textContent = String(content);
    return el;
  };
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const metric = (row, key) => numeric(row.metrics?.[key]) ? row.metrics[key] : null;
  const format = value => numeric(value) ? number.format(value) : '미관측';
  const variantLabel = row => variantNames[row.variant] || row.variant || '유형 미관측';
  const observed = row => row.response_object_observed !== false && row.response !== null && typeof row.response === 'object' && !Array.isArray(row.response);
  const answerState = row => {
    if (!observed(row)) return { text: '응답 미관측', kind: 'missing' };
    if (!Object.prototype.hasOwnProperty.call(row.response, 'answer')) return { text: 'answer 필드 없음', kind: 'missing' };
    if (row.response.answer === null) return { text: '숫자 없음 · null', kind: 'null' };
    const signed = row.signed_numeric_field;
    return { text: signed !== null && signed !== undefined ? String(signed) : String(row.response.answer), kind: 'value' };
  };
  const fieldText = value => value === null ? 'null' : value === undefined ? '필드 없음' : String(value);
  const samePair = (a, b) => a.case === b.case && a.variant === b.variant && a.reasoning === b.reasoning;
  const candidates = row => (row.tags || []).filter(tag => tag.includes('CANDIDATE'));
  const completedAt = row => numeric(row.timing?.ended_epoch_ms) ? row.timing.ended_epoch_ms : null;
  const clockTime = (value, date = false) => {
    if (!numeric(value)) return '미관측';
    return new Date(value).toLocaleString('ko-KR', { ...(date ? { month: '2-digit', day: '2-digit' } : {}), hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Seoul' });
  };
  const plotDatum = row => {
    const elapsed = metric(row, 'elapsed_seconds');
    if (elapsed === null || elapsed < 0) return null;
    if (state.axis === 'completion') {
      const completion = completedAt(row);
      return completion === null ? null : { x: completion, y: elapsed };
    }
    const output = metric(row, 'output_tokens');
    return output === null || output < 0 ? null : { x: elapsed, y: output };
  };
  const percentile = (values, fraction) => {
    if (!values.length) return null;
    const sortedValues = [...values].sort((a, b) => a - b);
    const index = (sortedValues.length - 1) * fraction;
    const lower = Math.floor(index), upper = Math.ceil(index);
    return sortedValues[lower] + (sortedValues[upper] - sortedValues[lower]) * (index - lower);
  };

  function renderSummary() {
    const elapsed = state.filtered.map(row => metric(row, 'elapsed_seconds')).filter(value => value !== null && value >= 0);
    $('stat-total').textContent = number.format(state.rows.length);
    $('stat-filtered').textContent = number.format(state.filtered.length);
    $('stat-failed').textContent = number.format(state.filtered.filter(row => row.saved_status === 'INVALID_RESPONSE').length);
    $('stat-null').textContent = number.format(state.filtered.filter(row => observed(row) && row.response.answer === null).length);
    const p50 = percentile(elapsed, .5), p95 = percentile(elapsed, .95);
    $('stat-p50').textContent = p50 === null ? '미관측' : duration.format(p50);
    $('stat-p95').textContent = p95 === null ? '미관측' : duration.format(p95);
    for (const id of ['stat-p50', 'stat-p95']) $(id).title = `현재 필터에서 실제 응답 시간이 관측된 ${number.format(elapsed.length)}건 기준. (n−1)×q 위치의 선형보간 분위수. 영역 선택 전 범위.`;
  }

  function setNotice(message, error = false) {
    $('load-status').textContent = message || '저장 실행 조회 · 자동 후보는 검토 대상이며 의미 적절성은 미평가입니다.';
    $('load-status').parentElement.classList.toggle('is-error', error);
  }

  function fillOptions(id, values, labels) {
    const select = $(id);
    const initial = select.firstElementChild.cloneNode(true);
    select.replaceChildren(initial);
    for (const value of values) {
      const option = make('option', '', labels[value] || value);
      option.value = value;
      select.append(option);
    }
  }

  function initFilters() {
    const params = new URLSearchParams(location.search);
    state.pendingTrial = params.get('trial') || null;
    state.axis = params.get('axis') === 'tokens' ? 'tokens' : 'completion';
    $('axis-mode').value = state.axis;
    for (const [key, id] of Object.entries(filterIds)) {
      state.filters[key] = params.get(key) || '';
      $(id).value = state.filters[key];
      $(id).addEventListener(key === 'case' ? 'input' : 'change', () => {
        state.filters[key] = $(id).value;
        state.brushIds = null;
        state.page = 0;
        updateView();
      });
    }
  }

  function updateURL() {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(state.filters)) if (value) params.set(key, value);
    if (state.focusId || state.pendingTrial) params.set('trial', state.focusId || state.pendingTrial);
    if (state.axis !== 'completion') params.set('axis', state.axis);
    const suffix = params.toString();
    history.replaceState(null, '', location.pathname + (suffix ? '?' + suffix : '') + location.hash);
  }

  function matches(row) {
    const f = state.filters;
    const query = f.case.toLowerCase().trim();
    return (!f.variant || row.variant === f.variant) && (!f.prompt || row.prompt_condition === f.prompt) &&
      (!f.reasoning || row.reasoning === f.reasoning) && (!f.status || row.saved_status === f.status) &&
      (!f.tag || (row.tags || []).includes(f.tag)) && (!query || `${row.case || ''} ${row.question_preview || ''}`.toLowerCase().includes(query));
  }

  function sorted(rows) {
    const value = row => {
      if (state.sort === 'answer') {
        const value = row.signed_numeric_field;
        return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
      }
      if (state.sort === 'elapsed_seconds' || state.sort === 'output_tokens') return metric(row, state.sort);
      if (state.sort === 'completed_at') return completedAt(row);
      return row[state.sort] ?? null;
    };
    return [...rows].sort((a, b) => {
      const av = value(a), bv = value(b);
      if (av === null && bv !== null) return 1;
      if (bv === null && av !== null) return -1;
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av ?? '').localeCompare(String(bv ?? ''), 'en', { numeric: true });
      return cmp * state.direction || String(a.trial_id).localeCompare(String(b.trial_id));
    });
  }

  function renderScope() {
    const chips = $('filter-chips');
    chips.replaceChildren();
    const labels = { variant: variantNames[state.filters.variant], prompt: state.filters.prompt ? promptName(state.filters.prompt) : '', reasoning: state.filters.reasoning ? reasoningName(state.filters.reasoning) : '', status: statusNames[state.filters.status], tag: tagNames[state.filters.tag], case: state.filters.case ? `검색: ${state.filters.case}` : '' };
    for (const [key, value] of Object.entries(state.filters)) if (value) chips.append(make('span', 'chip', labels[key] || value));
    if (!chips.childElementCount) chips.append(make('span', 'chip', '전체 입력 · 전체 조건'));
    if (state.brushIds !== null) chips.append(make('span', 'chip brush-chip', `영역 선택 ${number.format(state.tableRows.length)}개`));
    $('scope-count').textContent = `필터 ${number.format(state.filtered.length)} / 전체 ${number.format(state.rows.length)}`;
    $('clear-brush').hidden = state.brushIds === null;
    const selectionCount = state.brushIds !== null ? state.tableRows.length : state.focusId && state.filtered.some(r => r.trial_id === state.focusId) ? 1 : 0;
    $('selection-count').textContent = `선택 ${number.format(selectionCount)} / 관측 ${number.format(state.filtered.filter(observed).length)}`;
  }

  function updateView() {
    state.filtered = state.rows.filter(matches);
    state.tableRows = sorted(state.filtered.filter(row => state.brushIds === null || state.brushIds.has(row.trial_id)));
    state.page = Math.max(0, Math.min(state.page, Math.ceil(state.tableRows.length / state.pageSize) - 1));
    if (state.focusId && !state.tableRows.some(row => row.trial_id === state.focusId)) clearDetail();
    state.hoverId = null;
    $('plot-tooltip').hidden = true;
    renderScope();
    renderSummary();
    renderTable();
    requestDraw();
    updateURL();
  }

  function renderTable() {
    const body = $('response-body');
    body.replaceChildren();
    $('table-count').textContent = number.format(state.tableRows.length);
    $('table-empty').hidden = state.tableRows.length > 0;
    const fragment = document.createDocumentFragment();
    const start = state.page * state.pageSize;
    for (const row of state.tableRows.slice(start, start + state.pageSize)) {
      const tr = make('tr', 'response-row');
      tr.dataset.trialId = row.trial_id;
      tr.classList.toggle('is-selected', row.trial_id === state.focusId);
      tr.setAttribute('aria-selected', String(row.trial_id === state.focusId));
      const caseCell = make('td');
      const button = make('button', 'case-button', row.case || '문항 미관측');
      button.type = 'button';
      button.setAttribute('aria-label', `${row.case} ${variantLabel(row)} ${promptName(row.prompt_condition)} ${reasoningName(row.reasoning)} 응답 보기`);
      caseCell.append(button);
      const variant = make('td', '', variantLabel(row));
      const condition = make('td');
      condition.append(make('span', `condition-pill ${row.prompt_condition === 'P1' ? 'p1' : 'p0'}`, promptName(row.prompt_condition)), make('span', 'reasoning-label', reasoningName(row.reasoning)));
      const answer = answerState(row);
      const answerCell = make('td', answer.kind === 'value' ? 'numeric-value' : 'missing-value', answer.text);
      answerCell.title = `원응답 answer: ${fieldText(row.response?.answer)} · negative: ${fieldText(row.response?.answer_meta?.negative)}`;
      const status = make('td');
      status.append(make('span', `status-label ${row.saved_status === 'INVALID_RESPONSE' ? 'invalid' : ''}`, statusNames[row.saved_status] || row.saved_status || '미관측'));
      const tags = make('td');
      const candidateCount = candidates(row).length;
      const label = make('span', 'tag-count', candidateCount ? `후보 ${candidateCount} · 태그 ${(row.tags || []).length}` : `태그 ${(row.tags || []).length}`);
      label.title = (row.tags || []).map(tag => tagNames[tag] || tag).join('\n');
      tags.append(label);
      const completionCell = make('td', '', clockTime(completedAt(row)));
      completionCell.title = `${clockTime(completedAt(row), true)} · 한국 시각`;
      tr.append(caseCell, variant, condition, completionCell, make('td', '', format(metric(row, 'elapsed_seconds'))), make('td', '', format(metric(row, 'output_tokens'))), answerCell, status, tags);
      tr.addEventListener('click', () => selectRow(row.trial_id));
      tr.addEventListener('mouseenter', () => { state.hoverId = row.trial_id; requestDraw(); });
      tr.addEventListener('mouseleave', () => { state.hoverId = null; requestDraw(); });
      fragment.append(tr);
    }
    body.append(fragment);
    const pages = Math.ceil(state.tableRows.length / state.pageSize);
    $('page-label').textContent = pages ? `${state.page + 1} / ${pages} 페이지 · ${start + 1}–${Math.min(start + state.pageSize, state.tableRows.length)}` : '0 / 0 페이지';
    $('page-prev').disabled = state.page === 0;
    $('page-next').disabled = !pages || state.page >= pages - 1;
    for (const button of document.querySelectorAll('[data-sort]')) {
      const active = button.dataset.sort === state.sort;
      button.parentElement.setAttribute('aria-sort', active ? state.direction === 1 ? 'ascending' : 'descending' : 'none');
    }
  }

  function requestDraw() {
    if (animationPending) return;
    animationPending = true;
    requestAnimationFrame(() => { animationPending = false; drawPlot(); });
  }

  function drawPlot() {
    if (!ctx) return;
    const theme = getComputedStyle(document.documentElement);
    for (const key of ['blue', 'teal', 'muted']) plotTheme[key] = theme.getPropertyValue(`--${key}`).trim() || plotTheme[key];
    plotTheme.font = theme.fontFamily || plotTheme.font;
    const rect = $('plot-wrap').getBoundingClientRect();
    plotWidth = Math.max(1, rect.width);
    plotHeight = Math.max(1, rect.height);
    const ratio = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(plotWidth * ratio);
    canvas.height = Math.round(plotHeight * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, plotWidth, plotHeight);
    const bounds = { left: 48, right: plotWidth - 25, top: 17, bottom: plotHeight - 29 };
    const plottable = state.filtered.map(row => ({ row, value: plotDatum(row) })).filter(point => point.value !== null);
    const completionMode = state.axis === 'completion';
    let minX = 0, maxX = 1;
    if (plottable.length && completionMode) {
      minX = Math.min(...plottable.map(point => point.value.x));
      maxX = Math.max(...plottable.map(point => point.value.x));
      const padding = Math.max(1000, (maxX - minX) * .01);
      minX -= padding; maxX += padding;
    } else if (plottable.length) maxX = Math.max(1, ...plottable.map(point => point.value.x)) * 1.04;
    const maxY = Math.max(1, ...plottable.map(point => point.value.y)) * 1.06;
    const xTicks = plotWidth < 420 ? 3 : 5;
    const withDate = maxX - minX >= 86400000;
    ctx.font = `9px ${plotTheme.font}`;
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      const y = bounds.bottom - (bounds.bottom - bounds.top) * i / 5;
      ctx.strokeStyle = '#eaf0f5'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(bounds.left, y); ctx.lineTo(bounds.right, y); ctx.stroke();
      ctx.fillStyle = plotTheme.muted;
      ctx.textAlign = 'right'; ctx.fillText(number.format(maxY * i / 5), bounds.left - 10, y);
    }
    for (let i = 0; i <= xTicks; i++) {
      const x = bounds.left + (bounds.right - bounds.left) * i / xTicks;
      ctx.strokeStyle = '#eaf0f5'; ctx.beginPath(); ctx.moveTo(x, bounds.top); ctx.lineTo(x, bounds.bottom); ctx.stroke();
      const value = minX + (maxX - minX) * i / xTicks;
      ctx.fillStyle = plotTheme.muted; ctx.textAlign = i === 0 ? 'left' : i === xTicks ? 'right' : 'center';
      ctx.fillText(completionMode ? plottable.length ? clockTime(value, withDate) : '—' : number.format(value), x, bounds.bottom + 15);
    }
    ctx.fillStyle = '#74899c'; ctx.textAlign = 'left'; ctx.fillText(completionMode ? '응답 시간(초)' : '출력 토큰', bounds.left, 7);
    state.points = plottable.map(({ row, value }) => ({ row, x: bounds.left + (value.x - minX) / (maxX - minX) * (bounds.right - bounds.left), y: bounds.bottom - value.y / maxY * (bounds.bottom - bounds.top) }));
    for (const point of state.points) drawPoint(point, false);
    for (const point of state.points) if (point.row.trial_id === state.focusId || point.row.trial_id === state.hoverId) drawPoint(point, true);
    if (state.drag?.moved) {
      const { start, current } = state.drag;
      ctx.fillStyle = '#278b7c15'; ctx.strokeStyle = '#298f80'; ctx.lineWidth = 1;
      ctx.fillRect(start.x, start.y, current.x - start.x, current.y - start.y);
      ctx.setLineDash([4, 3]); ctx.strokeRect(start.x, start.y, current.x - start.x, current.y - start.y); ctx.setLineDash([]);
    }
    $('plot-empty').hidden = plottable.length > 0;
    $('axis-description').textContent = completionMode ? '가로: 완료 시각(한국 시각) · 세로: 응답 시간(초)' : '가로: 응답 시간(초) · 세로: 출력 토큰 · 점 크기 동일';
    canvas.setAttribute('aria-label', `${$('axis-description').textContent}. 점 클릭 또는 영역 드래그로 선택할 수 있습니다. 키보드로는 아래 응답 표를 사용하십시오.`);
    $('plot-empty').textContent = completionMode ? '완료 시각과 응답 시간이 있는 응답이 없습니다. 표 또는 다른 축을 확인하세요.' : '응답 시간과 출력 토큰이 있는 응답이 없습니다.';
    $('plot-count').textContent = `표시 ${number.format(plottable.length)} · ${completionMode ? '완료 시각/응답 시간' : '시간/출력'} 미관측·무효 ${number.format(state.filtered.length - plottable.length)} (표 유지)`;
  }

  function drawPoint(point, highlighted) {
    const { row, x, y } = point;
    const inBrush = state.brushIds === null || state.brushIds.has(row.trial_id);
    const color = row.prompt_condition === 'P1' ? plotTheme.teal : plotTheme.blue;
    ctx.globalAlpha = highlighted ? 1 : inBrush ? .5 : .08;
    const radius = highlighted ? 5 : 3;
    if (highlighted) { ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.stroke(); }
    ctx.beginPath();
    if (row.reasoning === 'on') { ctx.moveTo(x, y - radius); ctx.lineTo(x + radius, y); ctx.lineTo(x, y + radius); ctx.lineTo(x - radius, y); ctx.closePath(); }
    else ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill(); ctx.globalAlpha = 1;
  }

  const position = event => { const rect = canvas.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; };
  function nearest(pos) {
    let best = null, distance = 100;
    for (const point of state.points) {
      const d = (pos.x - point.x) ** 2 + (pos.y - point.y) ** 2;
      if (d < distance) { best = point; distance = d; }
    }
    return best;
  }

  function showHover(point, pos) {
    state.hoverId = point?.row.trial_id || null;
    const tooltip = $('plot-tooltip');
    tooltip.hidden = !point;
    if (point) {
      const row = point.row;
      tooltip.textContent = `${row.case} · ${variantLabel(row)}\n${promptName(row.prompt_condition)} / ${reasoningName(row.reasoning)} · ${answerState(row).text}\n완료 ${clockTime(completedAt(row), true)}\n${format(metric(row, 'elapsed_seconds'))}초 · ${format(metric(row, 'output_tokens'))} 출력 토큰`;
      tooltip.style.left = `${Math.max(5, Math.min(pos.x + 13, plotWidth - 247))}px`;
      tooltip.style.top = `${Math.max(4, Math.min(pos.y + 12, plotHeight - 97))}px`;
    }
    for (const tr of $('response-body').children) tr.classList.toggle('is-hovered', tr.dataset.trialId === state.hoverId);
    requestDraw();
  }

  function selectRow(id) {
    const row = state.byId.get(id);
    if (!row) return;
    if (state.brushIds !== null && !state.brushIds.has(id)) state.brushIds = null;
    state.tableRows = sorted(state.filtered.filter(r => state.brushIds === null || state.brushIds.has(r.trial_id)));
    const index = state.tableRows.findIndex(r => r.trial_id === id);
    if (index >= 0) state.page = Math.floor(index / state.pageSize);
    state.focusId = id;
    state.hoverId = null;
    $('plot-tooltip').hidden = true;
    renderScope(); renderTable(); requestDraw(); renderDetail(row); updateURL();
    const selected = [...$('response-body').children].find(tr => tr.dataset.trialId === id);
    if (selected) {
      const scroller = selected.closest('.table-scroll');
      const rowRect = selected.getBoundingClientRect(), scrollRect = scroller.getBoundingClientRect();
      if (rowRect.bottom > scrollRect.bottom || rowRect.top < scrollRect.top + 34) scroller.scrollTop += rowRect.top - scrollRect.top - 37;
    }
  }

  function clearDetail() {
    state.focusId = null;
    state.detailSequence++;
    detailController?.abort();
    $('detail-content').hidden = true;
    $('detail-empty').hidden = false;
    $('detail-indicator').textContent = '선택 대기';
  }

  function revealTrialFilters(row) {
    if (matches(row)) return false;
    const fields = { variant: 'variant', prompt: 'prompt_condition', reasoning: 'reasoning', status: 'saved_status' };
    for (const [filter, field] of Object.entries(fields)) if (state.filters[filter] && state.filters[filter] !== row[field]) state.filters[filter] = row[field] || '';
    if (state.filters.tag && !(row.tags || []).includes(state.filters.tag)) state.filters.tag = '';
    const query = state.filters.case.toLowerCase().trim();
    if (query && !`${row.case || ''} ${row.question_preview || ''}`.toLowerCase().includes(query)) state.filters.case = row.case || '';
    for (const [key, id] of Object.entries(filterIds)) $(id).value = state.filters[key];
    state.brushIds = null;
    return true;
  }

  function pairCard(row, condition, selected) {
    const card = make('article', `pair-card${selected ? ' focused' : ''}`);
    const top = make('div', 'pair-card-top');
    top.append(make('span', `condition-pill ${condition === 'P1' ? 'p1' : 'p0'}`, promptName(condition)));
    card.append(top);
    if (!row) { card.append(make('p', 'pair-empty', '같은 문항·유형·추론 조건의 저장 요청이 없습니다. 원문은 Unguided Solving만 계획되었습니다.')); return card; }
    const button = make('button', '', selected ? '선택됨' : '이 응답 선택');
    button.type = 'button'; button.disabled = selected;
    button.addEventListener('click', () => {
      for (const key of ['prompt', 'status', 'tag']) { state.filters[key] = ''; $(filterIds[key]).value = ''; }
      state.brushIds = null; updateView(); selectRow(row.trial_id);
    });
    top.append(button);
    const answer = answerState(row);
    card.append(make('div', `pair-answer${answer.kind !== 'value' ? ' null-answer' : ''}`, answer.text));
    card.append(make('p', 'pair-metadata', `${statusNames[row.saved_status] || row.saved_status || '미관측'} · 원응답 answer=${fieldText(row.response?.answer)} · negative=${fieldText(row.response?.answer_meta?.negative)} · scale=${fieldText(row.response?.answer_meta?.scale)}`));
    card.append(make('p', 'pair-explanation', row.response?.explanation ?? '설명 미관측'));
    const evidence = make('div', 'pair-evidence');
    evidence.append(make('h4', '', 'EVIDENCE · 원응답 인용'));
    if (Array.isArray(row.response?.evidence)) {
      if (!row.response.evidence.length) evidence.append(make('p', 'pair-empty', '빈 인용 배열 []'));
      for (const quote of row.response.evidence) evidence.append(make('blockquote', '', typeof quote === 'string' ? quote : JSON.stringify(quote)));
    } else evidence.append(make('p', 'pair-empty', '인용 필드 미관측'));
    card.append(evidence);
    return card;
  }

  function renderSources(data) {
    const links = $('source-links'); links.replaceChildren();
    for (const [key, label] of [['raw_path', 'API 원응답 경로'], ['result_path', '저장 검사 결과 경로'], ['call_path', '요청·응답 묶음 경로']]) {
      const path = data[key];
      if (typeof path !== 'string' || !path) continue;
      const record = make('div', 'source-record');
      const top = make('div', 'source-record-top');
      const copy = make('button', '', '경로 복사'); copy.type = 'button';
      copy.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(path); copy.textContent = '복사됨'; }
        catch { copy.textContent = '아래 경로를 선택해 복사'; }
      });
      top.append(make('span', '', label), copy);
      record.append(top, make('code', '', path)); links.append(record);
    }
    if (!links.childElementCount) links.append(make('span', 'muted', '저장 경로 미관측'));
  }

  async function renderDetail(row) {
    const sequence = ++state.detailSequence;
    detailController?.abort();
    $('detail-empty').hidden = true; $('detail-content').hidden = false;
    $('detail-indicator').textContent = `${promptName(row.prompt_condition)} / ${reasoningName(row.reasoning)}`;
    $('selected-case').textContent = row.case;
    $('selected-tags').replaceChildren(make('span', 'chip', variantLabel(row)), make('span', 'chip', row.schema_title || '형식 미관측'));
    $('selected-metrics').textContent = `완료 ${clockTime(completedAt(row), true)} · 소요 ${format(metric(row, 'elapsed_seconds'))}초\n입력 ${format(metric(row, 'input_tokens'))} · 출력 ${format(metric(row, 'output_tokens'))} · 추론 ${format(metric(row, 'reasoning_tokens'))} 토큰 · 비용 추정 ${metric(row, 'cost_estimate_usd') === null ? '미관측' : '$' + metric(row, 'cost_estimate_usd').toFixed(6)}`;
    $('question-text').textContent = row.question_preview || '질문 원문을 불러오고 있습니다.';
    $('pair-scope').textContent = `${row.case} · ${variantLabel(row)} · ${reasoningName(row.reasoning)} / 상세 대조는 목록의 풀이 조건 필터와 관계없이 양쪽을 표시합니다.`;
    const pairRows = state.rows.filter(other => samePair(row, other));
    $('pair-cards').replaceChildren(...['P0', 'P1'].map(condition => { const other = pairRows.find(r => r.prompt_condition === condition); return pairCard(other, condition, other?.trial_id === row.trial_id); }));
    $('observation-tags').replaceChildren(...(row.tags || []).map(tag => make('span', `observation-tag${tag.includes('CANDIDATE') ? ' candidate' : ''}`, tagNames[tag] || tag)));
    const quoteLabel = row.saved_all_quotes_present === true ? '모두 존재' : row.saved_all_quotes_present === false ? '불일치 있음' : '검사 미관측';
    $('saved-checks').textContent = `기존 인용 존재 검사: ${quoteLabel} · 의미 적절성: 미평가. 기존 수치 비교: ${row.saved_numeric_comparison ? row.saved_numeric_comparison.matches === true ? '참조 수치 일치' : row.saved_numeric_comparison.matches === false ? '참조 수치 불일치' : '판정 미관측' : '미평가'}.`;
    $('response-json').textContent = row.response === undefined ? '응답 필드 미관측' : JSON.stringify(row.response, null, 2);
    $('context-details').open = false; $('context-text').textContent = '';
    renderSources(row);
    const apply = detail => {
      if (sequence !== state.detailSequence) return;
      $('question-text').textContent = detail.question ?? row.question_preview ?? '질문 미관측';
      $('context-text').textContent = typeof detail.context === 'string' ? detail.context : detail.context == null ? '본문 미관측' : JSON.stringify(detail.context, null, 2);
      $('detail-load-status').textContent = '선택 요청에 실제 전달된 질문과 본문입니다.';
      renderSources({ ...row, ...detail });
    };
    if (state.detailCache.has(row.trial_id)) { apply(state.detailCache.get(row.trial_id)); return; }
    $('detail-load-status').textContent = '저장된 요청 본문을 불러오고 있습니다…';
    detailController = new AbortController();
    try {
      const response = await fetch('/api/dashboard/response?trial_id=' + encodeURIComponent(row.trial_id), { signal: detailController.signal, cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const detail = await response.json();
      state.detailCache.set(row.trial_id, detail); apply(detail);
    } catch (error) {
      if (error.name !== 'AbortError' && sequence === state.detailSequence) $('detail-load-status').textContent = `본문을 불러오지 못했습니다 (${error.message}). 응답을 다시 선택하거나 아래 저장 경로를 확인해 주세요.`;
    }
  }

  async function loadData(forceRefresh = false) {
    dataController?.abort(); dataController = new AbortController();
    state.loading = true; $('main').setAttribute('aria-busy', 'true'); $('refresh').disabled = true; setNotice('실제 저장 응답을 불러오고 있습니다.');
    try {
      const response = await fetch('/api/dashboard/data' + (forceRefresh ? '?refresh=1' : ''), { signal: dataController.signal, cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.rows)) throw new Error('응답 목록(rows)이 없습니다');
      state.data = data; state.rows = data.rows; state.byId = new Map(data.rows.map(row => [row.trial_id, row])); state.detailCache.clear();
      if (/^\d{8}-exp-\d{3,}$/.test(data.run_id || '')) $('experiment-viewer-link').href = `http://127.0.0.1:8894/?run=${encodeURIComponent(data.run_id)}&tab=analysis`;
      fillOptions('variant-filter', [...new Set(data.rows.map(row => row.variant).filter(Boolean))].sort((a, b) => Object.keys(variantNames).indexOf(a) - Object.keys(variantNames).indexOf(b)), variantNames);
      fillOptions('status-filter', [...new Set(data.rows.map(row => row.saved_status).filter(Boolean))].sort(), statusNames);
      fillOptions('tag-filter', [...new Set(data.rows.flatMap(row => row.tags || []))].sort(), tagNames);
      for (const [key, id] of Object.entries(filterIds)) {
        const select = $(id);
        if (select.tagName === 'SELECT' && state.filters[key] && ![...select.options].some(option => option.value === state.filters[key])) {
          const option = make('option', '', state.filters[key] + ' · 해당 값 없음'); option.value = state.filters[key]; select.append(option);
        }
        select.value = state.filters[key];
      }
      $('run-label').textContent = data.run_id || '실행 식별자 미관측';
      const variantInputCount = new Set(data.rows.filter(row => row.variant && row.variant !== 'ORIGINAL').map(row => JSON.stringify([row.case, row.variant]))).size;
      $('run-facts').textContent = `${typeof data.model === 'string' ? data.model : '모델 미관측'} · ${number.format(new Set(data.rows.map(row => row.case)).size)}원문 / ${number.format(variantInputCount)}변형`;
      const completionTimes = data.rows.map(completedAt).filter(value => value !== null);
      $('time-window').textContent = completionTimes.length ? `${clockTime(Math.min(...completionTimes), true)}–${clockTime(Math.max(...completionTimes))} KST` : '완료 시각 미관측';
      $('dataset-label').textContent = `${number.format(new Set(data.rows.map(row => row.case)).size)}개 원문 · ${number.format(data.rows.length)}개 저장 응답 · 자동 의미 채점 없음`;
      const date = data.generated_at ? new Date(data.generated_at) : null;
      $('updated-at').textContent = date && !Number.isNaN(date.getTime()) ? `자료 생성 ${date.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} KST` : '자료 생성 시각 미관측';
      const requestedTrial = state.pendingTrial;
      state.pendingTrial = null;
      const requestedRow = state.byId.get(requestedTrial);
      const adjusted = requestedRow ? revealTrialFilters(requestedRow) : false;
      updateView();
      if (requestedRow) selectRow(requestedRow.trial_id);
      else if (state.focusId && state.byId.has(state.focusId)) renderDetail(state.byId.get(state.focusId));
      setNotice(requestedTrial && !requestedRow ? '연결된 실행에서 요청한 trial을 찾지 못했습니다. 현재 필터의 응답을 표시합니다.' : adjusted ? '연결된 응답을 표시하도록 충돌한 필터를 조정했습니다.' : data.rows.length ? '' : '연결된 실행에 표시할 저장 응답이 없습니다.');
    } catch (error) {
      if (error.name !== 'AbortError') setNotice(`자료를 불러오지 못했습니다 (${error.message}). 대시보드 서버 연결을 확인한 뒤 새로고침해 주세요.${state.rows.length ? ' 기존에 불러온 자료는 그대로 표시합니다.' : ' 임의 예시 데이터는 표시하지 않습니다.'}`, true);
    } finally { state.loading = false; $('main').setAttribute('aria-busy', 'false'); $('refresh').disabled = false; }
  }

  function toggleHelp(open) {
    $('help-drawer').hidden = !open;
    $('help-backdrop').hidden = !open;
    $('main').inert = open;
    document.querySelector('.app-header').inert = open;
    (open ? $('close-help') : $('help-button')).focus();
  }

  $('help-button').addEventListener('click', () => toggleHelp(true));
  $('close-help').addEventListener('click', () => toggleHelp(false));
  $('help-backdrop').addEventListener('click', () => toggleHelp(false));
  document.addEventListener('keydown', event => {
    if ($('help-drawer').hidden) return;
    if (event.key === 'Escape') { event.preventDefault(); toggleHelp(false); }
    if (event.key === 'Tab') { event.preventDefault(); $('close-help').focus(); }
  });

  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const pos = position(event); state.drag = { start: pos, current: pos, moved: false, pointerId: event.pointerId };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    const pos = position(event);
    if (state.drag) { state.drag.current = pos; state.drag.moved ||= Math.hypot(pos.x - state.drag.start.x, pos.y - state.drag.start.y) > 6; $('plot-tooltip').hidden = true; requestDraw(); }
    else showHover(nearest(pos), pos);
  });
  canvas.addEventListener('pointerup', event => {
    if (!state.drag) return;
    const drag = state.drag; state.drag = null;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    if (drag.moved) {
      const minX = Math.min(drag.start.x, drag.current.x), maxX = Math.max(drag.start.x, drag.current.x), minY = Math.min(drag.start.y, drag.current.y), maxY = Math.max(drag.start.y, drag.current.y);
      state.brushIds = new Set(state.points.filter(point => point.x >= minX && point.x <= maxX && point.y >= minY && point.y <= maxY).map(point => point.row.trial_id));
      state.page = 0; updateView();
    } else { const point = nearest(position(event)); if (point) selectRow(point.row.trial_id); else requestDraw(); }
  });
  canvas.addEventListener('pointercancel', () => { state.drag = null; requestDraw(); });
  canvas.addEventListener('pointerleave', () => { if (!state.drag) showHover(null, { x: 0, y: 0 }); });
  $('clear-brush').addEventListener('click', () => { state.brushIds = null; state.page = 0; updateView(); });
  $('reset').addEventListener('click', () => { for (const [key, id] of Object.entries(filterIds)) { state.filters[key] = ''; $(id).value = ''; } state.brushIds = null; state.pendingTrial = null; state.page = 0; clearDetail(); updateView(); setNotice(''); });
  $('axis-mode').addEventListener('change', () => { state.axis = $('axis-mode').value; state.brushIds = null; state.page = 0; updateView(); });
  $('refresh').addEventListener('click', () => loadData(true));
  $('page-prev').addEventListener('click', () => { state.page--; renderTable(); });
  $('page-next').addEventListener('click', () => { state.page++; renderTable(); });
  $('page-size').addEventListener('change', () => { state.pageSize = Number($('page-size').value); state.page = 0; renderTable(); });
  for (const button of document.querySelectorAll('[data-sort]')) button.addEventListener('click', () => { const key = button.dataset.sort; state.direction = state.sort === key ? -state.direction : 1; state.sort = key; state.page = 0; updateView(); });
  $('show-pair').addEventListener('click', () => {
    const row = state.byId.get(state.focusId); if (!row) return;
    state.filters = { variant: row.variant, prompt: '', reasoning: row.reasoning, status: '', tag: '', case: row.case };
    for (const [key, id] of Object.entries(filterIds)) $(id).value = state.filters[key];
    state.brushIds = null; state.page = 0; updateView(); selectRow(row.trial_id);
  });
  new ResizeObserver(requestDraw).observe($('plot-wrap'));
  initFilters(); renderTable(); requestDraw(); loadData();
})();
