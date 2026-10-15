// [EV09.1] Adapt the dataset viewer's token tree without rewriting saved JSON.
export function jsonSource(value) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

export function parseJsonTree(raw, offset = 0) {
  JSON.parse(raw); // Validate only; numbers, duplicate keys and escapes stay in the source.
  const tokens = /"(?:\\[\s\S]|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\]:,]/g;
  const stack = []; let root, key = null, match;
  while ((match = tokens.exec(raw))) {
    const token = match[0], start = match.index + offset;
    if (token === ':' || token === ',') continue;
    if (token === '}' || token === ']') { stack.pop().end = tokens.lastIndex + offset; continue; }
    if (token[0] === '"' && /^\s*:/.test(raw.slice(tokens.lastIndex))) { key = token; continue; }
    const node = { start, end: tokens.lastIndex + offset, key,
      kind: token === '{' ? 'object' : token === '[' ? 'array' : token[0] === '"' ? 'string' : token === 'null' ? 'null' : /^(true|false)$/.test(token) ? 'boolean' : 'number' };
    key = null;
    if (stack.length) stack.at(-1).children.push(node); else root = node;
    if (node.kind === 'object' || node.kind === 'array') { node.children = []; stack.push(node); }
  }
  return root;
}

export function parseJsonDocument(raw, format = 'json') {
  if (format !== 'jsonl') return { raw, format: 'json', roots: [parseJsonTree(raw)] };
  const roots = []; let offset = 0, line = 0;
  for (const text of raw.split('\n')) {
    line++;
    if (text.trim()) {
      try { const root = parseJsonTree(text, offset); root.recordLine = line; roots.push(root); }
      catch { throw new SyntaxError(`JSONL ${line}행의 JSON이 완성되지 않았거나 형식이 올바르지 않습니다.`); }
    }
    offset += text.length + 1;
  }
  return { raw, format, roots };
}

export function* jsonRows(root, isOpen) {
  const stack = [{ node: root, depth: 0, comma: false }];
  while (stack.length) {
    const row = stack.pop(); yield row;
    if (!row.close && row.node.children?.length && isOpen(row.node)) {
      stack.push({ ...row, close: true });
      const children = row.node.children;
      for (let i = children.length - 1; i >= 0; i--) stack.push({ node: children[i], depth: row.depth + 1, comma: i < children.length - 1 });
    }
  }
}

function* documentRows(data, isOpen) {
  for (const root of data.roots) {
    if (data.format === 'jsonl') yield { recordLine: root.recordLine };
    yield* jsonRows(root, isOpen);
  }
}

// [EV09.2] A bounded page prevents a large response from flooding the DOM.
export function jsonPage(data, isOpen, page = 0, pageSize = 200) {
  const iterator = documentRows(data, isOpen), rows = []; let next;
  for (let i = 0; i < page * pageSize; i++) if (iterator.next().done) break;
  while (rows.length < pageSize && !(next = iterator.next()).done) rows.push(next.value);
  return { rows, more: !iterator.next().done };
}

function element(tag, className = '', text) {
  const node = document.createElement(tag); node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function control(label, action, className = '') {
  const node = element('button', className, label); node.type = 'button'; node.onclick = action; return node;
}
export async function copySource(raw, host) {
  try { if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(raw); return; } } catch { /* Fall back for offline browsers. */ }
  const previous = document.activeElement, area = element('textarea', 'json-copy-buffer');
  area.value = raw; area.setAttribute('aria-label', '복사할 원문'); host.append(area);
  const preserve = event => { if (event.clipboardData) { event.clipboardData.setData('text/plain', raw); event.preventDefault(); } };
  document.addEventListener('copy', preserve);
  try { area.select(); if (!document.execCommand('copy')) throw Error('복사할 수 없습니다. 원문 보기에서 직접 선택해 주세요.'); }
  finally { document.removeEventListener('copy', preserve); area.remove(); previous?.focus(); }
}

// [EV09.3] Text nodes and stylesheet classes also work under the export's strict CSP.
export function jsonViewer(value, title = 'JSON', { format = 'json', parsed } = {}) {
  const raw = jsonSource(value), wrap = element('div', 'json-viewer');
  const toolbar = element('div', 'toolbar json-toolbar'), status = element('span', 'small muted');
  const viewport = element('div', 'json-scroll'), pager = element('div', 'toolbar json-pager');
  wrap.setAttribute('role', 'group'); wrap.setAttribute('aria-label', `${title} · JSON 뷰어`);
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  viewport.tabIndex = 0; viewport.setAttribute('role', 'region'); viewport.setAttribute('aria-label', `${title} 내용`);
  let data = parsed, error;
  try { data ??= parseJsonDocument(raw, format); } catch (caught) { error = caught; }
  const copy = control('원본 복사', async () => {
    try { await copySource(raw, wrap); status.textContent = '복사 완료'; }
    catch (caught) { status.textContent = caught.message; }
  });
  toolbar.append(element('span', 'json-caption', format === 'jsonl' ? 'JSONL 뷰어' : 'JSON 뷰어'));
  wrap.append(toolbar);
  if (!data) {
    toolbar.append(copy, status);
    wrap.append(element('p', 'notice danger', format === 'jsonl' ? error.message : 'JSON이 완성되지 않았거나 형식이 올바르지 않습니다. 저장된 원문을 그대로 표시합니다.'));
    viewport.append(element('pre', 'json-raw', raw)); wrap.append(viewport); return wrap;
  }
  const opened = new Set(data.roots.map(root => root.start)), closed = new Set();
  let all = false, page = 0, rawMode = false;
  const isOpen = node => all ? !closed.has(node.start) : opened.has(node.start);
  const pageStatus = element('span', 'small muted'); pageStatus.setAttribute('aria-live', 'polite');
  const prev = control('← 이전 200줄', () => { page--; draw(); viewport.scrollTop = 0; });
  const next = control('다음 200줄 →', () => { page++; draw(); viewport.scrollTop = 0; });
  const expand = control('전체 펼치기', () => { rawMode = false; all = true; closed.clear(); page = 0; draw(); viewport.scrollTop = 0; });
  const collapse = control('전체 접기', () => { rawMode = false; all = false; opened.clear(); closed.clear(); page = 0; draw(); viewport.scrollTop = 0; });
  const source = control('원문 보기', () => { rawMode = !rawMode; draw(); });
  toolbar.append(expand, collapse, source, copy, status); pager.append(prev, pageStatus, next);
  wrap.append(viewport, pager);
  function draw(focusId) {
    viewport.replaceChildren(); pager.hidden = rawMode;
    source.textContent = rawMode ? '트리 보기' : '원문 보기'; source.setAttribute('aria-pressed', String(rawMode));
    if (rawMode) { viewport.append(element('pre', 'json-raw', raw)); return; }
    const { rows, more } = jsonPage(data, isOpen, page); let focusButton;
    for (const row of rows) {
      if (row.recordLine) { viewport.append(element('div', 'json-record', `JSONL · 원문 ${row.recordLine}행`)); continue; }
      const { node, depth, comma, close } = row, line = element('div', 'json-line');
      // Whitespace indentation needs no inline styles, even in a standalone export.
      const indent = element('span', 'json-depth', '  '.repeat(Math.min(depth, 40))); indent.setAttribute('aria-hidden', 'true'); line.append(indent);
      const container = !!node.children, expanded = !!(container && node.children.length && isOpen(node));
      if (close) line.append(element('span', 'json-indent'), element('span', '', node.kind === 'array' ? ']' : '}'));
      else {
        if (container && node.children.length) {
          const toggle = control(expanded ? '▾' : '▸', () => {
            if (all) expanded ? closed.add(node.start) : closed.delete(node.start);
            else expanded ? opened.delete(node.start) : opened.add(node.start);
            draw(node.start);
          }, 'json-toggle');
          toggle.setAttribute('aria-expanded', String(expanded));
          toggle.setAttribute('aria-label', `${expanded ? '접기' : '펼치기'} · ${node.key ?? (node.kind === 'array' ? '배열' : '객체')} · 위치 ${node.start}`);
          line.append(toggle); if (node.start === focusId) focusButton = toggle;
        } else line.append(element('span', 'json-indent'));
        if (node.key !== null) line.append(element('span', 'json-key', node.key), element('span', '', ': '));
        if (container) {
          const pair = node.kind === 'array' ? ['[', ']'] : ['{', '}']; line.append(element('span', '', pair[0]));
          if (!expanded) line.append(element('span', 'json-count', node.children.length ? ` … ${node.children.length}개 항목 ` : ''), element('span', '', pair[1]));
        } else line.append(element('span', `json-${node.kind}`, raw.slice(node.start, node.end)));
      }
      if (comma && (close || !expanded)) line.append(element('span', '', ','));
      viewport.append(line);
    }
    if (!rows.length) viewport.append(element('p', 'small muted', '저장된 JSONL 기록이 없습니다.'));
    prev.disabled = page === 0; next.disabled = !more;
    pageStatus.textContent = rows.length ? `${page * 200 + 1}–${page * 200 + rows.length}줄${more ? ' · 다음 내용 있음' : ''}` : '0줄';
    if (focusId !== undefined) (focusButton ?? viewport).focus({ preventScroll: true });
  }
  draw(); return wrap;
}

// [EV09.4] Every structured value shares one viewer; ordinary prose stays text.
export function valueView(value, title = 'JSON', { format = 'auto' } = {}) {
  if (value === undefined) return element('pre', '', '기록 없음');
  if (format === 'json' || format === 'jsonl') return jsonViewer(value, title, { format });
  if (typeof value !== 'string') return jsonViewer(value, title);
  try { return jsonViewer(value, title, { parsed: parseJsonDocument(value) }); }
  catch { return element('pre', '', value); }
}
