'use strict';

(() => {
  const promptName = value => ({ P0: 'Unguided Solving', P1: 'Criteria-Guided Solving' })[value] || value || 'Not recorded';
  const reasoningName = value => ({ off: 'Reasoning OFF', on: 'Reasoning ON' })[value] || value || 'Not recorded';
  const $ = id => document.getElementById(id);
  const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
  const duration = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const variantNames = { ORIGINAL: 'Source text', IC_VALUE_01_BEFORE: 'Value collision · front', IC_VALUE_01_AFTER: 'The value of the collapse', IC_SOURCE_A_ONLY: 'Sources A', IC_SOURCE_B_ONLY: 'Sources B', IC_RELATION_01: 'Relation conflict', EA_01: 'Delete the basis 01', EA_02: 'Delete the basis 02' };
  const tagNames = { ANSWER_ABSENT_FROM_EQUATION_RHS_CANDIDATE: 'Answer: Calculation of the inconsistency candidate', DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER: 'Youbo declaration + numbers', DECLARED_ABSTENTION_WITH_NON_NULL_SIGN: 'Youbo declaration + code', DECLARED_ABSTENTION_WITH_ZERO: 'Youbo declaration + 0', EMPTY_EVIDENCE: 'The empty quotation array', EVIDENCE_NOT_EXACT_SUBSTRING: 'Accurate citation inconsistency', EXPLANATION_NO_COMMITMENT_CUE: 'Youbo in the description', NON_NULL_ANSWER: 'The answer is not null.', NULL_ANSWER: 'No number', NUMERIC_FIELD_PRESENT: 'Number field observation', NUMERIC_FIELD_WITH_NO_COMMITMENT_CUE: 'Numbers + Ubo expressions', POSITIVE_ANSWER_WITH_SAME_NEGATIVE_NUMBER_CANDIDATE: 'The name of the candidate', QUESTION_METADATA_PRECISION_CONFLICT: 'Question: The number of instructions', RAW_DECLARED_ABSTENTION: 'Raw response to the UBO declaration', SAVED_DECIMAL_PLACES_FAILURE: 'The stored digit scan failed.' };
  const statusNames = { VALID: 'Format valid', INVALID_RESPONSE: 'Format failed', MISSING: 'Unobserved', NOT_RUN: 'Not run' };
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
  const format = value => numeric(value) ? number.format(value) : 'Unobserved';
  const variantLabel = row => variantNames[row.variant] || row.variant || 'Type of mismatch';
  const observed = row => row.response_object_observed !== false && row.response !== null && typeof row.response === 'object' && !Array.isArray(row.response);
  const answerState = row => {
    if (!observed(row)) return { text: 'The response is subtractive.', kind: 'missing' };
    if (!Object.prototype.hasOwnProperty.call(row.response, 'answer')) return { text: 'No answer field', kind: 'missing' };
    if (row.response.answer === null) return { text: 'No number', kind: 'null' };
    const signed = row.signed_numeric_field;
    return { text: signed !== null && signed !== undefined ? String(signed) : String(row.response.answer), kind: 'value' };
  };
  const fieldText = value => value === null ? 'null' : value === undefined ? 'No field.' : String(value);
  const samePair = (a, b) => a.case === b.case && a.variant === b.variant && a.reasoning === b.reasoning;
  const candidates = row => (row.tags || []).filter(tag => tag.includes('CANDIDATE'));
  const completedAt = row => numeric(row.timing?.ended_epoch_ms) ? row.timing.ended_epoch_ms : null;
  const clockTime = (value, date = false) => {
    if (!numeric(value)) return 'Unobserved';
    return new Date(value).toLocaleString('en-US', { ...(date ? { month: '2-digit', day: '2-digit' } : {}), hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Seoul' });
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
    $('stat-p50').textContent = p50 === null ? 'Unobserved' : duration.format(p50);
    $('stat-p95').textContent = p95 === null ? 'Unobserved' : duration.format(p95);
    for (const id of ['stat-p50', 'stat-p95']) $(id).title = `The actual response time in the current filter is observed as ${number.format(elapsed.length)}That\x27s the standard.1) xq is the linear-intercepted atmosphere of the position.`;
  }

  function setNotice(message, error = false) {
    $('load-status').textContent = message || 'The automatic tracker is subject to review and the significance of appropriateness is underestimated.';
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
    const labels = { variant: variantNames[state.filters.variant], prompt: state.filters.prompt ? promptName(state.filters.prompt) : '', reasoning: state.filters.reasoning ? reasoningName(state.filters.reasoning) : '', status: statusNames[state.filters.status], tag: tagNames[state.filters.tag], case: state.filters.case ? `Searching: ${state.filters.case}` : '' };
    for (const [key, value] of Object.entries(state.filters)) if (value) chips.append(make('span', 'chip', labels[key] || value));
    if (!chips.childElementCount) chips.append(make('span', 'chip', 'Full input · Full condition'));
    if (state.brushIds !== null) chips.append(make('span', 'chip brush-chip', `Area selection ${number.format(state.tableRows.length)}items`));
    $('scope-count').textContent = `Filter ${number.format(state.filtered.length)} - Whole one. ${number.format(state.rows.length)}`;
    $('clear-brush').hidden = state.brushIds === null;
    const selectionCount = state.brushIds !== null ? state.tableRows.length : state.focusId && state.filtered.some(r => r.trial_id === state.focusId) ? 1 : 0;
    $('selection-count').textContent = `Select ${number.format(selectionCount)} - What? ${number.format(state.filtered.filter(observed).length)}`;
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
      const button = make('button', 'case-button', row.case || 'Article by subtraction');
      button.type = 'button';
      button.setAttribute('aria-label', `${row.case} ${variantLabel(row)} ${promptName(row.prompt_condition)} ${reasoningName(row.reasoning)} See the response.`);
      caseCell.append(button);
      const variant = make('td', '', variantLabel(row));
      const condition = make('td');
      condition.append(make('span', `condition-pill ${row.prompt_condition === 'P1' ? 'p1' : 'p0'}`, promptName(row.prompt_condition)), make('span', 'reasoning-label', reasoningName(row.reasoning)));
      const answer = answerState(row);
      const answerCell = make('td', answer.kind === 'value' ? 'numeric-value' : 'missing-value', answer.text);
      answerCell.title = `Raw response: ${fieldText(row.response?.answer)} · negative: ${fieldText(row.response?.answer_meta?.negative)}`;
      const status = make('td');
      status.append(make('span', `status-label ${row.saved_status === 'INVALID_RESPONSE' ? 'invalid' : ''}`, statusNames[row.saved_status] || row.saved_status || 'Unobserved'));
      const tags = make('td');
      const candidateCount = candidates(row).length;
      const label = make('span', 'tag-count', candidateCount ? `Candidate ${candidateCount} · Tag ${(row.tags || []).length}` : `Tag ${(row.tags || []).length}`);
      label.title = (row.tags || []).map(tag => tagNames[tag] || tag).join('\n');
      tags.append(label);
      const completionCell = make('td', '', clockTime(completedAt(row)));
      completionCell.title = `${clockTime(completedAt(row), true)} • View from South Korea`;
      tr.append(caseCell, variant, condition, completionCell, make('td', '', format(metric(row, 'elapsed_seconds'))), make('td', '', format(metric(row, 'output_tokens'))), answerCell, status, tags);
      tr.addEventListener('click', () => selectRow(row.trial_id));
      tr.addEventListener('mouseenter', () => { state.hoverId = row.trial_id; requestDraw(); });
      tr.addEventListener('mouseleave', () => { state.hoverId = null; requestDraw(); });
      fragment.append(tr);
    }
    body.append(fragment);
    const pages = Math.ceil(state.tableRows.length / state.pageSize);
    $('page-label').textContent = pages ? `${state.page + 1} / ${pages} Page · ${start + 1}–${Math.min(start + state.pageSize, state.tableRows.length)}` : '0 / 0 Page two.';
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
    ctx.fillStyle = '#74899c'; ctx.textAlign = 'left'; ctx.fillText(completionMode ? 'Answer time' : 'Output tokens', bounds.left, 7);
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
    $('axis-description').textContent = completionMode ? 'Line: completed view (Korean view) · line: response time (seconds)' : 'The response time is equal to the output token.';
    canvas.setAttribute('aria-label', `${$('axis-description').textContent}You can select either a dot click or a zone drag.`);
    $('plot-empty').textContent = completionMode ? 'No response with a completed time and a response time. Check the table or other axis.' : 'There\x27s no response with a response time and output token.';
    $('plot-count').textContent = `Showing ${number.format(plottable.length)} · ${completionMode ? 'Finished time/response time' : 'Time and effort.'} Misobservation and inactivity ${number.format(state.filtered.length - plottable.length)} (Sighs)`;
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
      tooltip.textContent = `${row.case} · ${variantLabel(row)}\n${promptName(row.prompt_condition)} / ${reasoningName(row.reasoning)} · ${answerState(row).text}\nComplete ${clockTime(completedAt(row), true)}\n${format(metric(row, 'elapsed_seconds'))}Seconds ${format(metric(row, 'output_tokens'))} Output tokens`;
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
    $('detail-indicator').textContent = 'Choose waiting';
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
    if (!row) { card.append(make('p', 'pair-empty', 'There are no requests for the same case, type, reference conditions, only the source was planned for Unguided Solving.')); return card; }
    const button = make('button', '', selected ? 'Selected' : 'This is the answer choice.');
    button.type = 'button'; button.disabled = selected;
    button.addEventListener('click', () => {
      for (const key of ['prompt', 'status', 'tag']) { state.filters[key] = ''; $(filterIds[key]).value = ''; }
      state.brushIds = null; updateView(); selectRow(row.trial_id);
    });
    top.append(button);
    const answer = answerState(row);
    card.append(make('div', `pair-answer${answer.kind !== 'value' ? ' null-answer' : ''}`, answer.text));
    card.append(make('p', 'pair-metadata', `${statusNames[row.saved_status] || row.saved_status || 'Unobserved'} · raw response answer=${fieldText(row.response?.answer)} · negative=${fieldText(row.response?.answer_meta?.negative)} · scale=${fieldText(row.response?.answer_meta?.scale)}`));
    card.append(make('p', 'pair-explanation', row.response?.explanation ?? 'Explanation of the sub-observation'));
    const evidence = make('div', 'pair-evidence');
    evidence.append(make('h4', '', 'EVIDENCE · raw response quotes'));
    if (Array.isArray(row.response?.evidence)) {
      if (!row.response.evidence.length) evidence.append(make('p', 'pair-empty', 'The empty quotation array []'));
      for (const quote of row.response.evidence) evidence.append(make('blockquote', '', typeof quote === 'string' ? quote : JSON.stringify(quote)));
    } else evidence.append(make('p', 'pair-empty', 'Cited field subtraction'));
    card.append(evidence);
    return card;
  }

  function renderSources(data) {
    const links = $('source-links'); links.replaceChildren();
    for (const [key, label] of [['raw_path', 'API raw response path'], ['result_path', 'The storage scan results trace'], ['call_path', 'Request-response path of the bundle']]) {
      const path = data[key];
      if (typeof path !== 'string' || !path) continue;
      const record = make('div', 'source-record');
      const top = make('div', 'source-record-top');
      const copy = make('button', '', 'Copy the path.'); copy.type = 'button';
      copy.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(path); copy.textContent = 'It is copied.'; }
        catch { copy.textContent = 'Choose the path below and copy.'; }
      });
      top.append(make('span', '', label), copy);
      record.append(top, make('code', '', path)); links.append(record);
    }
    if (!links.childElementCount) links.append(make('span', 'muted', 'Save paths from the subway'));
  }

  async function renderDetail(row) {
    const sequence = ++state.detailSequence;
    detailController?.abort();
    $('detail-empty').hidden = true; $('detail-content').hidden = false;
    $('detail-indicator').textContent = `${promptName(row.prompt_condition)} / ${reasoningName(row.reasoning)}`;
    $('selected-case').textContent = row.case;
    $('selected-tags').replaceChildren(make('span', 'chip', variantLabel(row)), make('span', 'chip', row.schema_title || 'The form of the sub-observation'));
    $('selected-metrics').textContent = `Complete ${clockTime(completedAt(row), true)} · Cost ${format(metric(row, 'elapsed_seconds'))}Seconds.\nInput ${format(metric(row, 'input_tokens'))} · Output ${format(metric(row, 'output_tokens'))} · Theories ${format(metric(row, 'reasoning_tokens'))} Token · Cost estimate ${metric(row, 'cost_estimate_usd') === null ? 'Unobserved' : '$' + metric(row, 'cost_estimate_usd').toFixed(6)}`;
    $('question-text').textContent = row.question_preview || 'It\x27s bringing up the question.';
    $('pair-scope').textContent = `${row.case} · ${variantLabel(row)} · ${reasoningName(row.reasoning)} / Detailed contrast shows both sides of the list, regardless of the root condition filter.`;
    const pairRows = state.rows.filter(other => samePair(row, other));
    $('pair-cards').replaceChildren(...['P0', 'P1'].map(condition => { const other = pairRows.find(r => r.prompt_condition === condition); return pairCard(other, condition, other?.trial_id === row.trial_id); }));
    $('observation-tags').replaceChildren(...(row.tags || []).map(tag => make('span', `observation-tag${tag.includes('CANDIDATE') ? ' candidate' : ''}`, tagNames[tag] || tag)));
    const quoteLabel = row.saved_all_quotes_present === true ? 'They all exist.' : row.saved_all_quotes_present === false ? 'There is a discrepancy.' : 'The inspection is under surveillance.';
    $('saved-checks').textContent = `The existing citation exists: ${quoteLabel} · Meaning appropriateness: underestimated. ${row.saved_numeric_comparison ? row.saved_numeric_comparison.matches === true ? 'Reference number matching' : row.saved_numeric_comparison.matches === false ? 'Reference number inconsistency' : 'Judgmental subversion' : 'Not evaluated'}.`;
    $('response-json').textContent = row.response === undefined ? 'Response field subtraction' : JSON.stringify(row.response, null, 2);
    $('context-details').open = false; $('context-text').textContent = '';
    renderSources(row);
    const apply = detail => {
      if (sequence !== state.detailSequence) return;
      $('question-text').textContent = detail.question ?? row.question_preview ?? 'Question: Subconsciously';
      $('context-text').textContent = typeof detail.context === 'string' ? detail.context : detail.context == null ? 'The following is a list of the countries of the European Union:' : JSON.stringify(detail.context, null, 2);
      $('detail-load-status').textContent = 'It\x27s the actual questions and lessons that are delivered to the selection request.';
      renderSources({ ...row, ...detail });
    };
    if (state.detailCache.has(row.trial_id)) { apply(state.detailCache.get(row.trial_id)); return; }
    $('detail-load-status').textContent = 'I\x27m bringing back the saved request text...';
    detailController = new AbortController();
    try {
      const response = await fetch('/api/dashboard/response?trial_id=' + encodeURIComponent(row.trial_id), { signal: detailController.signal, cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const detail = await response.json();
      state.detailCache.set(row.trial_id, detail); apply(detail);
    } catch (error) {
      if (error.name !== 'AbortError' && sequence === state.detailSequence) $('detail-load-status').textContent = `I didn\x27t get the article.${error.message}Please select the answer again or check the save path below.`;
    }
  }

  async function loadData(forceRefresh = false) {
    dataController?.abort(); dataController = new AbortController();
    state.loading = true; $('main').setAttribute('aria-busy', 'true'); $('refresh').disabled = true; setNotice('It\x27s bringing in real storage responses.');
    try {
      const response = await fetch('/api/dashboard/data' + (forceRefresh ? '?refresh=1' : ''), { signal: dataController.signal, cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.rows)) throw new Error('There\x27s no answer list.');
      state.data = data; state.rows = data.rows; state.byId = new Map(data.rows.map(row => [row.trial_id, row])); state.detailCache.clear();
      if (/^\d{8}-exp-\d{3,}$/.test(data.run_id || '')) $('experiment-viewer-link').href = `http://127.0.0.1:8894/?run=${encodeURIComponent(data.run_id)}&tab=analysis`;
      fillOptions('variant-filter', [...new Set(data.rows.map(row => row.variant).filter(Boolean))].sort((a, b) => Object.keys(variantNames).indexOf(a) - Object.keys(variantNames).indexOf(b)), variantNames);
      fillOptions('status-filter', [...new Set(data.rows.map(row => row.saved_status).filter(Boolean))].sort(), statusNames);
      fillOptions('tag-filter', [...new Set(data.rows.flatMap(row => row.tags || []))].sort(), tagNames);
      for (const [key, id] of Object.entries(filterIds)) {
        const select = $(id);
        if (select.tagName === 'SELECT' && state.filters[key] && ![...select.options].some(option => option.value === state.filters[key])) {
          const option = make('option', '', state.filters[key] + ' · No value'); option.value = state.filters[key]; select.append(option);
        }
        select.value = state.filters[key];
      }
      $('run-label').textContent = data.run_id || 'Running ID is unobserved';
      const variantInputCount = new Set(data.rows.filter(row => row.variant && row.variant !== 'ORIGINAL').map(row => JSON.stringify([row.case, row.variant]))).size;
      $('run-facts').textContent = `${typeof data.model === 'string' ? data.model : 'The model is under observation.'} · ${number.format(new Set(data.rows.map(row => row.case)).size)}- The original. ${number.format(variantInputCount)}Variant`;
      const completionTimes = data.rows.map(completedAt).filter(value => value !== null);
      $('time-window').textContent = completionTimes.length ? `${clockTime(Math.min(...completionTimes), true)}–${clockTime(Math.max(...completionTimes))} KST` : 'Finished visual subtraction';
      $('dataset-label').textContent = `${number.format(new Set(data.rows.map(row => row.case)).size)}originals · ${number.format(data.rows.length)}items save response · No automatic meaning stamp`;
      const date = data.generated_at ? new Date(data.generated_at) : null;
      $('updated-at').textContent = date && !Number.isNaN(date.getTime()) ? `Creating data ${date.toLocaleString('en-US', { timeZone: 'Asia/Seoul' })} KST` : 'Data creation visual subtraction';
      const requestedTrial = state.pendingTrial;
      state.pendingTrial = null;
      const requestedRow = state.byId.get(requestedTrial);
      const adjusted = requestedRow ? revealTrialFilters(requestedRow) : false;
      updateView();
      if (requestedRow) selectRow(requestedRow.trial_id);
      else if (state.focusId && state.byId.has(state.focusId)) renderDetail(state.byId.get(state.focusId));
      setNotice(requestedTrial && !requestedRow ? 'I couldn\x27t find the requested trial in the connected run. It\x27s showing the response of the current filter.' : adjusted ? 'I adjusted the collision filter to show the connected response.' : data.rows.length ? '' : 'There\x27s no storage response to display on the connected execution.');
    } catch (error) {
      if (error.name !== 'AbortError') setNotice(`I didn\x27t get the data.${error.message}Check the dashboard server connection and re-enact it.${state.rows.length ? ' The data we\x27ve collected is the same.' : ' It doesn\x27t show any sample data.'}`, true);
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
