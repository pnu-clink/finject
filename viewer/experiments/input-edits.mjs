const EDIT_KINDS = {
  VALUE: { className: 'edit-value', label: '추가 값 주장', detail: '제작 시 추가한 값 주장 · 정답 판정과 별개' },
  SOURCE_A: { className: 'edit-source-a', label: '출처 A', detail: 'A 쪽 주장에 추가한 출처' },
  SOURCE_B: { className: 'edit-source-b', label: '출처 B', detail: 'B 쪽 주장에 추가한 출처' },
  RELATION: { className: 'edit-relation', label: '추가 관계', detail: '제작 시 추가한 관계 문장' },
  EA: { className: 'edit-ea', label: '근거 편집', detail: '삭제·교체 후 실제 입력에 남아 있는 내용' }
};
const STEP_KIND = { IC_VALUE_01_BEFORE: 'VALUE', IC_VALUE_01_AFTER: 'VALUE', IC_SOURCE_A_ONLY: 'SOURCE_A', IC_SOURCE_B_ONLY: 'SOURCE_B', IC_RELATION_01: 'RELATION', EA_01: 'EA', EA_02: 'EA' };
const REASONS = {
  CONTRACT: '지원하는 편집 기록 형식이 아닙니다.', REQUEST: '실제 저장 요청의 Q/C가 없습니다.', PUBLIC: '저장 요청과 공개 입력의 Q/C가 다릅니다.',
  BASELINE: '같은 문항의 원본 Q/C 또는 기준 해시가 맞지 않습니다.', FINAL: '최종 Q/C 해시가 맞지 않습니다.', QUESTION: '질문 변경에 대한 편집 기록이 없습니다.', STEPS: '편집 단계와 선택 유형이 맞지 않습니다.',
  STEP_INPUT: '편집 단계의 입력 해시가 맞지 않습니다.', STEP_OUTPUT: '편집 단계의 출력 해시가 맞지 않습니다.', PATCH: '편집 위치 또는 편집 전 문자가 맞지 않습니다.',
  SEGMENTS: '색상 구간과 실제 편집 문자가 맞지 않습니다.', RESULT: '편집을 적용한 본문과 실제 요청 본문이 다릅니다.', HASH: '이 브라우저에서 텍스트 해시를 확인할 수 없습니다.'
};
const failure = (status, reason, detail = '') => ({ status, reason, detail, spans: [], deletions: [] });
const assert = (condition, code) => { if (!condition) throw Error(code); };
async function hash(text) {
  if (!globalThis.crypto?.subtle) throw Error('HASH');
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(v => v.toString(16).padStart(2, '0')).join('');
}
const matchesHash = async (text, expected) => typeof expected === 'string' && /^[a-f\d]{64}$/i.test(expected) && await hash(text) === expected.toLowerCase();

// [EV23.1] Replay private edit records against the original, then verify the actual request.
// Saved offsets are Unicode code points; rendering offsets are UTF-16 string positions.
export async function verifyInputEdits({ caseId, variant, original, item, request, provenance }) {
  if (!provenance || provenance.status === 'UNAVAILABLE') return failure('UNAVAILABLE', '편집 기록이 없습니다.', provenance?.reason ?? '');
  if (provenance.status !== 'VERIFIED') return failure('MISMATCH', '저장된 편집 기록이 검증되지 않았습니다.', provenance.reason ?? '');
  try {
    assert(provenance.schema_version === 1 && provenance.offset_unit === 'unicode_code_point', 'CONTRACT');
    assert(typeof request?.context === 'string' && typeof request?.question === 'string', 'REQUEST');
    assert(request.context === item?.context && request.question === item?.question, 'PUBLIC');
    assert(typeof original?.context === 'string' && typeof original?.question === 'string' && provenance.baseline?.case === caseId && provenance.baseline?.variant === 'ORIGINAL', 'BASELINE');
    assert(await matchesHash(original.context, provenance.baseline.context_sha256) && await matchesHash(original.question, provenance.baseline.question_sha256), 'BASELINE');
    assert(await matchesHash(request.context, provenance.final?.context_sha256) && await matchesHash(request.question, provenance.final?.question_sha256), 'FINAL');
    assert(request.question === original.question, 'QUESTION');
    const steps = provenance.steps;
    assert(Array.isArray(steps), 'STEPS');
    if (variant === 'ORIGINAL') assert(steps.length === 0 && request.context === original.context && request.question === original.question, 'STEPS');
    else if (['IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY'].includes(variant)) assert(steps.length === 2 && steps[0]?.variant === (variant === 'IC_SOURCE_A_ONLY' ? 'IC_VALUE_01_BEFORE' : 'IC_VALUE_01_AFTER') && steps[1]?.variant === variant, 'STEPS');
    else assert(steps.length === 1 && steps[0]?.variant === variant && Object.hasOwn(STEP_KIND, variant), 'STEPS');
    let chars = Array.from(original.context, text => ({ text, kind: null }));
    const deletions = [];
    for (const [stepIndex, step] of steps.entries()) {
      const text = chars.map(c => c.text).join(''), kind = STEP_KIND[step.variant];
      assert(await matchesHash(text, step.input_context_sha256), 'STEP_INPUT');
      assert(Array.isArray(step.patches), 'PATCH');
      const patches = [...step.patches].sort((a, b) => a.start - b.start);
      let previousEnd = -1, previousStart = -1;
      for (const patch of patches) {
        assert(Number.isInteger(patch.start) && Number.isInteger(patch.end) && patch.start >= 0 && patch.end >= patch.start && patch.end <= chars.length && patch.start >= previousEnd && patch.start !== previousStart, 'PATCH');
        assert(typeof patch.before === 'string' && typeof patch.text === 'string' && chars.slice(patch.start, patch.end).map(c => c.text).join('') === patch.before, 'PATCH');
        const segments = patch.segments;
        assert(Array.isArray(segments) && segments.length > 0 && segments.every(s => typeof s?.text === 'string' && (s.kind === kind || kind.startsWith('SOURCE_') && s.kind === 'VALUE')) && segments.map(s => s.text).join('') === patch.text, 'SEGMENTS');
        previousEnd = patch.end; previousStart = patch.start;
      }
      // Descending application keeps every patch relative to its saved stage input.
      for (const patch of patches.reverse()) {
        const inserted = patch.segments.flatMap(s => Array.from(s.text, text => ({ text, kind: s.kind })));
        const delta = inserted.length - (patch.end - patch.start);
        for (const removal of deletions) {
          if (removal.position >= patch.end) removal.position += delta;
          else if (removal.position > patch.start) removal.position = patch.start;
        }
        chars = [...chars.slice(0, patch.start), ...inserted, ...chars.slice(patch.end)];
        if (kind === 'EA' && patch.before && patch.before !== patch.text) deletions.push({ position: patch.start, text: patch.before, replacement: patch.text, step: stepIndex + 1, start: patch.start, end: patch.end });
      }
      assert(await matchesHash(chars.map(c => c.text).join(''), step.output_context_sha256), 'STEP_OUTPUT');
    }
    assert(chars.map(c => c.text).join('') === request.context, 'RESULT');
    const spans = [], offsets = [0];
    let offset = 0;
    for (const char of chars) {
      const last = spans.at(-1);
      if (last?.kind === char.kind) { last.text += char.text; last.end += char.text.length; }
      else spans.push({ kind: char.kind, text: char.text, start: offset, end: offset + char.text.length });
      offset += char.text.length; offsets.push(offset);
    }
    deletions.sort((a, b) => a.position - b.position);
    return { status: request.context === original.context && request.question === original.question ? 'UNCHANGED' : 'VERIFIED', reason: null, spans,
      deletions: deletions.map((d, i) => ({ ...d, id: i + 1, offset: offsets[d.position] })) };
  } catch (error) { return failure('MISMATCH', REASONS[error.message] ?? '편집 기록을 확인할 수 없습니다.'); }
}

const node = (tag, className, text) => { const n = document.createElement(tag); if (className) n.className = className; if (text !== undefined) n.textContent = text; return n; };

// [EV23.2] Every displayed fragment retains its exact source offsets, including table cells.
export function contextBlocks(text) {
  let offset = 0;
  const lines = text.split('\n').map(value => { const line = { start: offset, end: offset + value.replace(/\r$/, '').length, text: value.replace(/\r$/, '') }; offset += value.length + 1; return line; });
  const cells = line => {
    const pipes = []; let escaped = false, code = false;
    for (let i = 0; i < line.text.length; i++) {
      const c = line.text[i];
      if (escaped) { escaped = false; continue; }
      if (c === '\\') { escaped = true; continue; }
      if (c === '`') code = !code;
      if (c === '|' && !code) pipes.push(i);
    }
    if (!pipes.length) return null;
    const bounds = [-1, ...pipes, line.text.length], ranges = bounds.slice(1).map((end, i) => ({ start: line.start + bounds[i] + 1, end: line.start + end }));
    if (!line.text.slice(0, pipes[0]).trim()) ranges.shift();
    if (!line.text.slice(pipes.at(-1) + 1).trim()) ranges.pop();
    return ranges;
  };
  const blocks = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.text.trim()) continue;
    if (/^\s*```/.test(line.text)) {
      const start = lines[i + 1]?.start ?? line.end; let end = start;
      while (++i < lines.length && !/^\s*```/.test(lines[i].text)) end = lines[i].end;
      blocks.push({ type: 'code', start, end }); continue;
    }
    const header = cells(line), divider = lines[i + 1] && cells(lines[i + 1]);
    if (header && divider?.length === header.length && divider.every(c => /^\s*:?-{3,}:?\s*$/.test(text.slice(c.start, c.end)))) {
      const rows = []; i++;
      while (lines[i + 1]) { const row = cells(lines[i + 1]); if (!row || row.length !== header.length) break; rows.push(row); i++; }
      blocks.push({ type: 'table', header, rows }); continue;
    }
    const heading = line.text.match(/^(#{1,6})\s+/);
    blocks.push({ type: heading ? `h${heading[1].length}` : 'p', start: line.start + (heading?.[0].length ?? 0), end: line.end });
  }
  return blocks;
}

export function inputEditNotice(result) {
  const out = node('div', `input-edit-notice ${result.status.toLowerCase()}`);
  const status = { VERIFIED: '편집 기록 검증됨', UNCHANGED: '원본 동일 · 추가·삭제 없음', UNAVAILABLE: '편집 기록 없음', MISMATCH: '편집 기록 검증 불가' };
  out.append(node('strong', '', status[result.status]));
  if (result.reason) out.append(node('span', '', `${result.reason} ${result.status === 'MISMATCH' ? '색상을 적용하지 않고 실제 입력을 표시합니다.' : '실제 입력 그대로 표시합니다.'}`));
  if (result.detail) out.title = result.detail;
  if (result.status === 'VERIFIED') {
    const legend = node('div', 'input-edit-legend');
    const present = new Set(result.spans.map(s => s.kind));
    for (const kind of ['VALUE', 'SOURCE_A', 'SOURCE_B', 'RELATION', 'EA']) if (present.has(kind)) {
      const entry = EDIT_KINDS[kind], chip = node('span', entry.className, entry.label); chip.title = entry.detail; legend.append(chip);
    }
    if (result.deletions.length) legend.append(node('span', 'edit-deletion-legend', '✕ 삭제 · 취소선 값은 실제 입력에서 빠짐'));
    out.append(legend, node('span', 'small muted', '색상은 제작 시 편집 구간이며 정답 판정이 아닙니다.'));
  }
  return out;
}

export function inputEditDeletions(result) {
  if (!result.deletions.length) return null;
  const out = node('details', 'input-edit-deletions');
  out.append(node('summary', '', `삭제된 원문 ${result.deletions.length}곳 · 실제 입력에 포함되지 않음`), node('p', 'small muted', '본문의 빨간 삭제 표식이 원문에서 삭제된 위치입니다. 취소선 값은 모델에 전달되지 않았습니다. 전체 삭제 내용과 공백·표 구분선은 여기와 원문 그대로 보기에서 확인할 수 있습니다.'));
  for (const d of result.deletions) {
    const entry = node('div', 'input-edit-removal');
    entry.append(node('p', 'small muted', `삭제 ${d.id} · ${d.step}단계 입력의 문자 위치 ${d.start}–${d.end} · ${d.replacement ? '교체 전 내용' : '삭제 내용'}`), node('pre', '', d.text)); out.append(entry);
  }
  return out;
}

// [EV23.3] CSS pseudo-elements preview deletions without inserting them into the model's context text.
export function renderInputContext(text, result, mode = 'formatted', quote = '') {
  const verified = ['VERIFIED', 'UNCHANGED'].includes(result.status);
  const spans = verified ? result.spans : [], deletions = verified ? result.deletions : [], placed = new Set();
  const quotes = [];
  if (typeof quote === 'string' && quote) for (let at = 0, index; (index = text.indexOf(quote, at)) >= 0; at = index + quote.length) quotes.push({ start: index, end: index + quote.length });
  const marker = (parent, d) => {
    if (placed.has(d.id)) return; placed.add(d.id);
    const compact = d.text.replace(/\s+/g, ' ').trim(), chars = Array.from(compact);
    const preview = compact ? `${chars.slice(0, 24).join('')}${chars.length > 24 ? '…' : ''}` : '(공백)';
    const n = node('span', 'input-edit-deletion-marker');
    n.tabIndex = 0; n.setAttribute('role', 'img');
    n.setAttribute('aria-label', `삭제 ${d.id}: 원문 값 ${preview}, 실제 모델 입력에 포함되지 않음`);
    n.title = `삭제 ${d.id} · 원문 값 미리보기: ${preview} · 실제 모델 입력에는 포함되지 않습니다. 전체 삭제 내용은 아래에서 확인하세요.`;
    n.dataset.deletionId = String(d.id); n.dataset.markerLabel = `✕ 삭제 ${d.id}`; n.dataset.preview = preview;
    parent.append(n);
  };
  const appendRange = (parent, start, end) => {
    const relevant = spans.filter(s => s.end > start && s.start < end), removals = deletions.filter(d => d.offset >= start && d.offset <= end);
    const cuts = [...new Set([start, end, ...relevant.flatMap(s => [Math.max(start, s.start), Math.min(end, s.end)]), ...removals.map(d => d.offset), ...quotes.filter(q => q.end > start && q.start < end).flatMap(q => [Math.max(start, q.start), Math.min(end, q.end)])])].sort((a, b) => a - b);
    for (let i = 0; i < cuts.length; i++) {
      const at = cuts[i], to = cuts[i + 1];
      for (const d of removals) if (d.offset === at) marker(parent, d);
      if (to === undefined) continue;
      const kind = relevant.find(s => s.start <= at && s.end >= to)?.kind;
      let target = parent;
      if (kind) { target = node('span', `input-edit ${EDIT_KINDS[kind].className}`); target.title = EDIT_KINDS[kind].detail; target.dataset.editKind = kind; parent.append(target); }
      if (quotes.some(q => q.start <= at && q.end >= to)) { const mark = node('mark', 'quote-hit'); target.append(mark); target = mark; }
      target.append(text.slice(at, to));
    }
  };
  const inline = (parent, start, end) => {
    const value = text.slice(start, end), pattern = /\\[\\`*_{}\[\]()#+\-.!|>]|\*\*([^*]+)\*\*|`([^`]+)`/g; let at = start;
    for (const m of value.matchAll(pattern)) {
      const index = start + m.index; appendRange(parent, at, index);
      if (m[0].startsWith('\\')) appendRange(parent, index + 1, index + m[0].length);
      else { const tag = node(m[1] !== undefined ? 'strong' : 'code'), pad = m[1] !== undefined ? 2 : 1; appendRange(tag, index + pad, index + m[0].length - pad); parent.append(tag); }
      at = index + m[0].length;
    }
    appendRange(parent, at, end);
  };
  if (mode === 'raw') { const out = node('pre', 'input-context-raw'); appendRange(out, 0, text.length); return out; }
  const out = node('div', 'prose input-context-formatted');
  for (const block of contextBlocks(text)) {
    if (block.type === 'table') {
      const wrap = node('div', 'table-wrap'), table = node('table'), head = node('thead'), body = node('tbody');
      for (const [index, cells] of [block.header, ...block.rows].entries()) { const row = node('tr'); for (const cell of cells) { const c = node(index === 0 ? 'th' : 'td'); inline(c, cell.start, cell.end); row.append(c); } (index === 0 ? head : body).append(row); }
      table.append(head, body); wrap.append(table); out.append(wrap);
    } else { const p = node(block.type === 'code' ? 'pre' : block.type); if (block.type === 'code') appendRange(p, block.start, block.end); else inline(p, block.start, block.end); out.append(p); }
  }
  return out;
}
