'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('comparison-data').textContent);
  const node = (tag, text, cls) => {
    const element = document.createElement(tag);
    if (text != null) element.textContent = text;
    if (cls) element.className = cls;
    return element;
  };
  const key = item => item.type + '/' + item.id;
  const state = {type: 'EA_01', scope: 'any', inverse: 'all', search: '', active: null, expanded: true};
  let visible = [], scrollFrame;

  // Use Unicode code points to retain the Python-verified evidence offsets.
  function appendMarked(parent, chars, spans, start, end, removal = false) {
    const ranges = [];
    for (const span of [...spans].sort((a, b) => a.start - b.start)) {
      const clipped = {start: Math.max(start, span.start), end: Math.min(end, span.end)};
      if (clipped.start >= clipped.end) continue;
      const last = ranges.at(-1);
      if (last && clipped.start <= last.end) last.end = Math.max(last.end, clipped.end);
      else ranges.push(clipped);
    }
    let at = start;
    for (const range of ranges) {
      parent.append(document.createTextNode(chars.slice(at, range.start).join('')));
      parent.append(node(removal ? 'del' : 'mark', chars.slice(range.start, range.end).join(''), removal ? 'removed-value' : null));
      at = range.end;
    }
    parent.append(document.createTextNode(chars.slice(at, end).join('')));
  }

  function reading(text, spans = [], removal = false, excerpt = false) {
    const body = node('div', null, excerpt ? 'removal-excerpt' : 'prose');
    const chars = Array.from(text);
    if (excerpt) {
      const start = Math.max(0, Math.min(...spans.map(span => span.start)) - 150);
      const end = Math.min(chars.length, Math.max(...spans.map(span => span.end)) + 150);
      if (start) body.append(document.createTextNode('…'));
      appendMarked(body, chars, spans, start, end, removal);
      if (end < chars.length) body.append(document.createTextNode('…'));
      return body;
    }
    let offset = 0;
    const lines = text.split('\n').map(text => {
      const record = {text, start: offset, end: offset + Array.from(text).length};
      offset = record.end + 1;
      return record;
    });
    const isRow = line => /^\s*\|.*\|\s*$/.test(line?.text || '');
    const isDivider = line => isRow(line) && /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(line.text);
    const rawColumns = line => !/^\s*\|/.test(line?.text || '') ? (line?.text.match(/\|/g) || []).length + 1 : 0;
    const tableStart = index => isRow(lines[index]) && isDivider(lines[index + 1]) ||
      rawColumns(lines[index]) >= 3 && rawColumns(lines[index]) === rawColumns(lines[index + 1]);
    for (let index = 0; index < lines.length;) {
      if (tableStart(index)) {
        const scroll = node('div', null, 'table-scroll'), table = node('table');
        const rawWidth = rawColumns(lines[index]);
        let header = true;
        while (index < lines.length && (rawWidth ? rawColumns(lines[index]) === rawWidth : isRow(lines[index]))) {
          const line = lines[index++];
          if (isDivider(line)) continue;
          const tr = node('tr'), local = Array.from(line.text), pipes = [];
          local.forEach((char, at) => { if (char === '|') pipes.push(at); });
          if (rawWidth) { pipes.unshift(-1); pipes.push(local.length); }
          for (let cell = 1; cell < pipes.length; cell++) {
            let start = pipes[cell - 1] + 1, end = pipes[cell];
            while (start < end && /\s/.test(local[start])) start++;
            while (end > start && /\s/.test(local[end - 1])) end--;
            const td = node(header ? 'th' : 'td');
            if (header) td.scope = 'col';
            appendMarked(td, chars, spans, line.start + start, line.start + end, removal);
            tr.append(td);
          }
          const section = node(header ? 'thead' : 'tbody');
          section.append(tr); table.append(section); header = false;
        }
        scroll.append(table); body.append(scroll);
      } else {
        const first = index;
        while (index < lines.length && !tableStart(index)) index++;
        const paragraph = node('p');
        appendMarked(paragraph, chars, spans, lines[first].start, lines[index - 1].end, removal);
        body.append(paragraph);
      }
    }
    return body;
  }

  function annotation(record) {
    const panel = node('section', null, 'annotation ' + record.decision_effective);
    const top = node('div', null, 'annotation-top');
    top.append(node('strong', record.annotator), node('span', {
      accept: 'Accept · 동의', reject: 'Reject · 비동의', pending: 'Pending · 보류'
    }[record.decision_effective], 'verdict ' + record.decision_effective));
    panel.append(top, node('p', record.comment || '의견 없음', 'comment' + (record.comment ? '' : ' empty')));
    if (record.decision_original !== record.decision_effective) {
      panel.append(node('p', '원본 Pending → 비교용 Accept', 'original-decision'));
    }
    return panel;
  }

  function contextPanel(title, text, spans, {original = false, open = false} = {}) {
    const details = node('details', null, 'context-panel' + (original ? ' original' : ''));
    details.open = open;
    if (!original) details.dataset.context = 'true';
    details.append(node('summary', title), reading(text, spans, original));
    return details;
  }

  function card(item, index) {
    const article = node('article', null, 'review-card ' + (item.type === 'EA_02' ? 'er2' : 'er1'));
    article.id = 'item-' + item.type + '-' + item.id;
    article.dataset.key = key(item);
    const heading = node('div', null, 'card-heading'), title = node('div', null, 'card-title');
    title.append(node('h2', item.id), node('span', data.taxonomy[item.type].label, 'type-pill'),
      node('span', item.source_dataset, 'source-label'));
    const meta = node('div', null, 'card-title');
    meta.append(node('span', item.agreement_effective ? '두 분 모두 Reject' : '판정 불일치',
      'pair-badge' + (item.agreement_effective ? ' both' : '')), node('span', (index + 1) + ' / ' + visible.length, 'card-number'));
    heading.append(title, meta);
    const body = node('div', null, 'card-body'), ratings = node('div', null, 'annotations');
    ratings.append(annotation(item.first), annotation(item.second));
    body.append(ratings, node('h3', '질문 · Question'), node('p', item.question, 'question'));
    const inverse = node('section', null, 'inverse-section'), inverseTop = node('div', null, 'inverse-top');
    const review = item.inverse_review;
    inverseTop.append(node('h3', '저장된 역산 판정'), node('span', review.inverse_possible ? 'true · 역산 가능' : 'false · 유일한 복원 미확립',
      'inverse-badge' + (review.inverse_possible ? '' : ' false')));
    inverse.append(inverseTop);
    for (const [label, field] of [['누락 수량', 'missing_quantity'], ['판정 이유', 'reason']]) {
      const fact = node('p', null, 'review-fact');
      fact.append(node('b', label + '  '), document.createTextNode(globalThis.FinarchI18n?.language === 'ko' ? item.display_ko[field] : review[field]));
      inverse.append(fact);
    }
    if (review.formula) inverse.append(node('pre', review.formula, 'formula'));
    const english = node('details', null, 'english');
    english.append(node('summary', '영어 원판정 보기'), node('p', review.missing_quantity), node('p', review.reason));
    inverse.append(english); body.append(inverse);
    const removed = node('section', null, 'removal-box');
    removed.append(node('h3', '삭제된 수치 · 원본 위치'), reading(item.original_context, item.removals, true, true),
      node('p', item.removals.map(span => span.label + (span.unit ? ' · ' + span.unit : '')).join(' / '), 'removal-meta'));
    body.append(removed,
      contextPanel('삭제 후 본문 · Context (노란색은 역산 근거)', item.context,
        review.evidence.filter(span => span.field === 'context'), {open: state.expanded}),
      contextPanel('원본 전체 · 제거 위치 대조', item.original_context, item.removals, {original: true}));
    article.append(heading, body);
    return article;
  }

  function filtered() {
    const search = state.search.toLocaleLowerCase();
    return data.items.filter(item => {
      if (state.type !== 'all' && item.type !== state.type) return false;
      if (state.scope === 'both' && !item.agreement_effective) return false;
      if (state.scope === 'disagree' && item.agreement_effective) return false;
      if (['first', 'second'].includes(state.scope) && item[state.scope].decision_effective !== 'reject') return false;
      if (state.inverse !== 'all' && String(item.inverse_review.inverse_possible) !== state.inverse) return false;
      return !search || [item.id, item.question, item.context, item.first.comment, item.second.comment,
        item.source_dataset, item.display_ko.reason, item.display_ko.missing_quantity].join(' ').toLocaleLowerCase().includes(search);
    });
  }

  function active(keyValue, updateHash = true) {
    if (!visible.some(item => key(item) === keyValue)) return;
    state.active = keyValue;
    for (const link of $('case-nav').children) {
      const selected = link.dataset.key === keyValue;
      link.classList.toggle('active', selected);
      if (selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }
    if (updateHash && location.protocol !== 'file:') history.replaceState(null, '', '#item-' + keyValue.replace('/', '-'));
  }

  function jump(keyValue) {
    const item = visible.find(item => key(item) === keyValue);
    if (!item) return;
    active(keyValue);
    $('item-' + item.type + '-' + item.id).scrollIntoView({block: 'start', behavior: 'instant'});
    const nav = $('case-nav'), link = nav.querySelector('[aria-current]');
    if (link) {
      const top = link.offsetTop - nav.offsetTop;
      if (top < nav.scrollTop) nav.scrollTop = top;
      else if (top + link.offsetHeight > nav.scrollTop + nav.clientHeight) nav.scrollTop = top + link.offsetHeight - nav.clientHeight;
    }
  }

  function render({scroll = false} = {}) {
    const previous = state.active;
    visible = filtered();
    if (!visible.some(item => key(item) === state.active)) state.active = visible[0] ? key(visible[0]) : null;
    for (const tab of document.querySelectorAll('[data-type]')) tab.setAttribute('aria-pressed', String(tab.dataset.type === state.type));
    const disagrees = visible.filter(item => !item.agreement_effective).length;
    $('visible-summary').textContent = (state.type === 'all' ? 'ER-1 + ER-2' : data.taxonomy[state.type].label) +
      ' · ' + visible.length + '건 표시 · 불일치 ' + disagrees + ' / 모두 Reject ' + (visible.length - disagrees);
    $('list-count').textContent = visible.length + '건';
    $('empty').hidden = visible.length !== 0;
    $('items').replaceChildren(...visible.map(card));
    $('case-nav').replaceChildren(...visible.map(item => {
      const link = node('a', null, 'case-link');
      link.href = '#item-' + item.type + '-' + item.id; link.dataset.key = key(item);
      const title = node('span', item.id);
      if (state.type === 'all') title.append(node('small', ' ' + data.taxonomy[item.type].label));
      const dots = node('span', null, 'dots');
      for (const side of ['first', 'second']) {
        const dot = node('span', null, 'dot ' + item[side].decision_effective);
        dot.title = item[side].annotator + ' · ' + item[side].decision_effective;
        dot.setAttribute('aria-label', dot.title); dots.append(dot);
      }
      link.append(title, dots); link.onclick = event => { event.preventDefault(); jump(key(item)); };
      return link;
    }));
    if (state.active) active(state.active, false);
    if (scroll && state.active) jump(state.active);
    if (!state.active && previous) $('message').textContent = '이 조건에는 해당 항목이 없습니다.';
    else $('message').textContent = '';
  }

  function selectType(type) {
    const previousId = state.active?.split('/')[1];
    state.type = type;
    const next = filtered().find(item => item.id === previousId);
    if (next) state.active = key(next);
    render({scroll: true});
  }

  function reset() {
    state.scope = 'any'; state.inverse = 'all'; state.search = '';
    $('scope').value = 'any'; $('inverse').value = 'all'; $('search').value = '';
    render();
  }

  $('reviewers').textContent = data.sources.map(source => source.annotator).join(' × ');
  for (const [count, label] of [[data.totals.all.items, '한 분 이상 Reject'], [data.totals.all.disagreements, '판정 불일치'], [data.totals.all.both_reject, '두 분 모두 Reject']]) {
    const stat = node('div', null, 'stat'); stat.append(node('strong', count), document.createTextNode(label)); $('overview').append(stat);
  }
  for (const tab of document.querySelectorAll('[data-type]')) {
    tab.querySelector('span').textContent = data.totals[tab.dataset.type].items;
    tab.onclick = () => selectType(tab.dataset.type);
  }
  for (const [id, field] of [['scope', 'scope'], ['inverse', 'inverse']]) $(id).onchange = () => { state[field] = $(id).value; render(); };
  $('search').oninput = () => { state.search = $('search').value.trim(); render(); };
  $('reset').onclick = $('empty-reset').onclick = reset;
  $('font').onchange = () => document.documentElement.style.setProperty('--reading', $('font').value + 'px');
  for (const [id, expanded] of [['expand', true], ['collapse', false]]) $(id).onclick = () => {
    state.expanded = expanded; for (const panel of document.querySelectorAll('[data-context]')) panel.open = expanded;
  };
  for (const source of data.sources) {
    const panel = node('section', null, 'source-file');
    panel.append(node('strong', source.annotator), node('p', source.filename), node('small', 'SHA-256 ' + source.sha256));
    $('sources').append(panel);
  }
  $('scope').options[3].textContent = data.sources[0].annotator + ' Reject';
  $('scope').options[4].textContent = data.sources[1].annotator + ' Reject';
  $('mapping-note').textContent = data.sources[1].annotator + '님의 Pending ' + data.pending_mapped_to_accept + '건은 비교용 Accept로 처리했습니다. 전체 ' + data.source_items.toLocaleString() + '건 중 Reject가 있는 ' + data.totals.all.items + '건을 담았습니다.';
  for (const [button, dialog] of [['sources-open', 'sources-dialog'], ['help-open', 'help-dialog']]) $(button).onclick = () => $(dialog).showModal();
  for (const button of document.querySelectorAll('[data-close]')) button.onclick = () => $(button.dataset.close).close();
  document.addEventListener('keydown', event => {
    if (event.isComposing || event.repeat || event.ctrlKey || event.metaKey || event.altKey || document.querySelector('dialog[open]') || event.target.closest('input,textarea,select,[contenteditable=true]')) return;
    if (event.code === 'KeyQ' || event.code === 'KeyE') {
      event.preventDefault();
      const index = visible.findIndex(item => key(item) === state.active);
      const next = Math.max(0, Math.min(visible.length - 1, index + (event.code === 'KeyQ' ? -1 : 1)));
      if (visible[next]) jump(key(visible[next]));
    } else if (event.code === 'KeyA' || event.code === 'KeyD') {
      event.preventDefault(); selectType(event.code === 'KeyA' ? 'EA_01' : 'EA_02');
    } else if (event.key === '/') { event.preventDefault(); $('search').focus(); }
    else if (event.key === '?') { event.preventDefault(); $('help-dialog').showModal(); }
  });
  $('export-html').onclick = () => {
    const clone = document.documentElement.cloneNode(true);
    clone.querySelector('#items').replaceChildren(); clone.querySelector('#case-nav').replaceChildren();
    clone.querySelector('#overview').replaceChildren(); clone.querySelector('#sources').replaceChildren();
    const link = clone.querySelector('#html-download'); link.removeAttribute('href'); link.hidden = true;
    for (const dialog of clone.querySelectorAll('dialog')) dialog.removeAttribute('open');
    clone.querySelector('#search').value = ''; clone.querySelector('#search').removeAttribute('value');
    const bytes = new TextEncoder().encode('<!doctype html>\n' + clone.outerHTML);
    let binary = '';
    for (let at = 0; at < bytes.length; at += 32768) binary += String.fromCharCode(...bytes.subarray(at, at + 32768));
    const downloadUrl = 'data:text/html;charset=utf-8;base64,' + btoa(binary);
    const filename = data.run + '-er-reject-comparison.html';
    $('html-download').href = downloadUrl; $('html-download').download = filename; $('html-download').hidden = false;
    $('message').textContent = 'ER-1·ER-2의 Reject ' + data.totals.all.items + '건 전체를 HTML 한 파일에 담았습니다.';
    $('html-download').click();
  };
  let hash = '';
  try { hash = decodeURIComponent(location.hash.slice(1)); } catch {}
  const anchor = /^item-(EA_0[12])-(id-\d{4})$/.exec(hash);
  if (anchor) hash = anchor[1] + '/' + anchor[2];
  if (/^EA_0[12]\/id-\d{4}$/.test(hash) && data.items.some(item => key(item) === hash)) {
    state.type = hash.split('/')[0]; state.active = hash;
  }
  new ResizeObserver(() => document.documentElement.style.setProperty('--sticky', $('filters').offsetHeight + 'px')).observe($('filters'));
  window.addEventListener('scroll', () => {
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = null;
      const top = $('filters').getBoundingClientRect().bottom + 24;
      const current = [...$('items').children].find(card => card.getBoundingClientRect().bottom > top);
      if (current) active(current.dataset.key, false);
    });
  }, {passive: true});
  document.addEventListener('finarch:language-change', () => render());
  const initialSelection = state.active;
  render({scroll: Boolean(initialSelection)});
  if (initialSelection) {
    requestAnimationFrame(() => jump(initialSelection));
    window.addEventListener('load', () => jump(initialSelection), {once: true});
  }
})();
