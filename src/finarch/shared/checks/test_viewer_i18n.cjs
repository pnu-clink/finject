// Presentation contracts; no model calls or production review writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('viewer/shared/i18n.js', 'utf8');
function runtime({ href = 'file:///review.html', saved, unavailable = false, confirm } = {}) {
  const storage = new Map(saved ? [['finarch.viewer.language', saved]] : []);
  const document = { readyState: 'loading', body: null, documentElement: {},
    addEventListener() {}, dispatchEvent() {}, querySelector() { return null; }, querySelectorAll() { return []; } };
  const context = { URL, document, location: { href }, CustomEvent: class {}, confirm,
    NodeFilter: { SHOW_ELEMENT: 1, SHOW_TEXT: 4, FILTER_REJECT: 2, FILTER_ACCEPT: 1 },
    localStorage: { getItem(key) { if (unavailable) throw Error('blocked'); return storage.get(key); },
      setItem(key, value) { if (unavailable) throw Error('blocked'); storage.set(key, value); } } };
  vm.runInNewContext(source, context);
  return { locale: context.FinarchI18n, document, storage };
}
let checks = 0;
function check(name, fn) { fn(); checks++; console.log('PASS: ' + name); }
check('Korean default and explicit English URL preference', () => {
  assert.equal(runtime().locale.language, 'ko');
  assert.equal(runtime({ href: 'http://localhost/?lang=en', saved: 'ko' }).locale.language, 'en');
  assert.equal(runtime({ href: 'file:///review.html?lang=en', unavailable: true }).locale.language, 'en');
});
check('Stored choice, invalid preference and offline storage failure', () => {
  assert.equal(runtime({ saved: 'en' }).locale.language, 'en');
  assert.equal(runtime({ saved: 'invalid' }).locale.language, 'ko');
  const { locale, document } = runtime({ unavailable: true });
  locale.setLanguage('en'); assert.equal(document.documentElement.lang, 'en');
  locale.setLanguage('ko'); assert.equal(locale.language, 'ko');
});
check('Language choice persists without changing form values or source objects', () => {
  const { locale, storage } = runtime();
  const record = { question: '검사 통과', context: '실패 해석', answer: '-35', decision: 'REJECTED' };
  const before = JSON.stringify(record);
  locale.setLanguage('en'); assert.equal(storage.get('finarch.viewer.language'), 'en');
  assert.equal(JSON.stringify(record), before);
  locale.setLanguage('invalid'); assert.equal(locale.language, 'en');
});
check('Complete UI sentences and dynamic counters render without mixed languages', () => {
  const { locale } = runtime();
  const cases = {
    '판정 저장 (x key)': 'Save decision (x key)',
    '78 / 100개 문항 · 78개 유형 기록': '78 / 100 cases · 78 variant records',
    '해석에 사용한 근거 파일 79개': '79 evidence files used in analysis',
    '원문 1,080개 · 변형 7,560개 · 1개 모델의 저장된 결과': '1,080 originals · 7,560 variants · saved results from 1 models',
    '소요시간 0시간 26분 34초 · 동시처리 한도 200문항': 'Elapsed 0h 26m 34s · concurrency limit 200 cases'
  };
  for (const [ko, en] of Object.entries(cases)) { assert.equal(locale.translate(ko, 'en'), en); assert.equal(locale.translate(ko, 'ko'), ko); }
});
check('Untranslated source text is not rewritten into a partial translation', () => {
  const { locale } = runtime();
  const text = '이 문항은 아직 연구자가 작성한 한국어 설명입니다.';
  assert.equal(locale.translate(text, 'en'), text);
});
check('Portable reviewer labels, import errors and dynamic messages are fully English', () => {
  const { locale } = runtime();
  const labels = [
    '데이터 평가 · 20261003-concat-002', '문제별', '유형별', '변경 문장과 근거',
    '원문 맥락', '초록: 추가 · 취소선: 삭제 · 분홍/빨강: 출처', '전체 보기',
    '… 4252자 생략 · 펼치기', '문장·수식·노드를 선택하면 연결 계산이 강조됩니다.',
    '주석 (선택) · N으로 입력 · Enter로 저장 · Shift+Enter 줄바꿈', '판정 후 다음 미평가',
    '1·2·3 판정 · Q/E 필터된 문제 이전·다음 · A/D 유형 이전·다음 · v 다음 유보·실패 / Shift+V 이전 · N 주석',
    '● 초록 통과 · ● 빨강 실패 · ● 노랑 유보', '변경 1 · 추가', '변경 2 · 교체',
    '12 / 8820 완료 · 통과 8 · 실패 2 · 유보 2', '목록 1260 / 1260문항',
    'test-0007 · IC-VALUE 앞 통과 저장됨 · 이 실행의 평가를 모두 마쳤습니다.',
    '판정 저장 1 / 1260 · IC-VALUE 앞', '문장 배치: 원래 주장 뒤',
    'test-0007 · IC-VALUE 앞의 기존 상세 화면',
    '20261003-concat-002 · 임시 JSON 다운로드를 시작했습니다.',
    '평가자 이름을 입력해 주세요.', '이 HTML에서 저장한 평가 파일이 아닙니다.',
    '파일을 읽지 못했습니다: 평가자 이름이 올바르지 않습니다.',
    '간략 그래프를 표시하지 못했습니다: 입력 노드 기록이 없습니다: n3',
    'A · 최종 답 = 계산 불가\n노드 n3, n4', '20261003-concat-002 · test-0007 · HTML 내장 자료'
  ];
  for (const ko of labels) {
    assert(!/[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/.test(locale.translate(ko, 'en')), ko);
    assert.equal(locale.translate(ko, 'ko'), ko);
  }
  assert.equal(locale.translate('… 4252자 생략 · 펼치기', 'en'), '… 4252 characters hidden · Expand');
});
check('Reported dataset headings, graph labels and live counters have no Korean', () => {
  const { locale } = runtime();
  const labels = [
    '03-calculation · 계산과 정답', '외부지식 요구 문구·태그·공식 정의',
    '코드·실행 결과·정답 비교', '모델이 지정한 원문 위치',
    '색이 있는 원문 숫자, 변수 표, 코드 줄에 마우스를 올리거나 클릭하면 연결된 부분을 강조합니다. 색상은 근거와 코드의 참조 연결이며, 실행 성공은 아래 실제 결과에서 확인합니다.',
    '선택한 코드 22번째 줄', 'appliances_2018 = 계산 불가 · 코드 2행',
    '변수 · answer', 'IC-VALUE · 앞 — 문장 생성 메뉴에서 위치를 비교합니다. 이 앞/뒤 쌍은 동일한 A/B 계산 그래프를 공유합니다.',
    '소요시간 0시간 20분 11초 · 동시처리 한도 200문항',
    '선택한 실행: 20261003-003 · 717개 문항 기록 · 읽기 완료 후 10초마다 변경 확인 · 최근 확인 오후 11:16:11'
  ];
  const hangul = /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/;
  for (const label of labels) {
    assert(!hangul.test(locale.translate(label, 'en')), label);
    assert.equal(locale.translate(label, 'ko'), label);
  }
  assert.equal(locale.translate('undefined (1차 수정)', 'en'), 'undefined (revision 1)');
  assert.equal(locale.translate('A: -12.6 / B: -11.4', 'en'), 'A: -12.6 / B: -11.4');
});
function element(tag, attrs = {}, ...children) {
  const node = { nodeType: 1, tagName: tag, attrs: { ...attrs }, childNodes: children, isConnected: true,
    hasAttribute(key) { return Object.hasOwn(this.attrs, key); },
    getAttribute(key) { return this.attrs[key] ?? null; },
    setAttribute(key, value) { this.attrs[key] = value; },
    matches(selectors) { return selectors.split(',').some(s => {
      s = s.trim();
      if (s.startsWith('.')) return (this.attrs.class || '').split(' ').includes(s.slice(1));
      if (s.startsWith('#')) return this.attrs.id === s.slice(1);
      if (s.startsWith('[')) { const [, key, value] = s.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/); return this.hasAttribute(key) && (value === undefined || this.getAttribute(key) === value); }
      return this.tagName === s;
    }); },
    closest(selectors) { for (let current = this; current; current = current.parentElement) if (current.matches(selectors)) return current; return null; }
  };
  children.forEach(child => child.parentElement = node);
  return node;
}
const textNode = value => ({ nodeType: 3, nodeValue: value, childNodes: [], isConnected: true });
function mockWalker(root, flags, filter) {
  const nodes = [];
  function walk(node) { for (const child of node.childNodes) { if (filter.acceptNode(child) === 2) continue; nodes.push(child); walk(child); } }
  walk(root); let index = -1;
  return { nextNode() { return ++index < nodes.length; }, get currentNode() { return nodes[index]; } };
}
check('Reviewer context expansion translates inside opaque source without rewriting it', () => {
  const { locale, document } = runtime();
  const raw = textNode('원문 맥락은 한국어 원본 그대로 보존합니다.');
  const gap = element('button', { 'data-i18n-ui': '' }, textNode('… 4252자 생략 · 펼치기'));
  const note = element('textarea', { placeholder: '주석 (선택) · N으로 입력 · Enter로 저장 · Shift+Enter 줄바꿈' });
  note.value = '검토자가 작성한 한국어 의견';
  document.body = element('body', {}, element('div', { class: 'prose' }, raw, gap), note);
  document.createTreeWalker = mockWalker;
  locale.setLanguage('en');
  assert.equal(gap.childNodes[0].nodeValue, '… 4252 characters hidden · Expand');
  assert.equal(raw.nodeValue, '원문 맥락은 한국어 원본 그대로 보존합니다.');
  assert.equal(note.value, '검토자가 작성한 한국어 의견');
  assert.equal(note.getAttribute('placeholder'), 'Comment (optional) · N to edit · Enter to save · Shift+Enter for a new line');
  locale.setLanguage('ko');
  assert.equal(gap.childNodes[0].nodeValue, '… 4252자 생략 · 펼치기');
  assert.equal(note.value, '검토자가 작성한 한국어 의견');
  assert(fs.readFileSync('viewer/dataset/evaluation/review.js', 'utf8').includes("gap.setAttribute('data-i18n-ui','')"));
});
check('Opaque source text keeps UI tooltips, portable paths and status labels reversible', () => {
  const { locale, document } = runtime();
  const source = textNode('질문과 원문은 그대로 보존합니다.');
  const tooltip = element('button', { 'aria-label': 'other_2019 원문 근거 44.1' }, textNode('44.1'));
  const question = element('div', { class: 'prose' }, source, tooltip);
  const rawPath = '/Volumes/EX400U/workspace/논문/fin-arch/reports/run/20261003-003/01-preparation/test-0001/01-round/run.json';
  const path = element('span', { class: 'file-path', 'data-copy': rawPath }, textNode(rawPath));
  const status = element('div', { class: 'prose', 'data-i18n-ui': '' }, textNode('원래 주장 앞'));
  const codeText = textNode('# 원본 코드 주석\nanswer = 1');
  const code = element('pre', {}, codeText);
  const comment = textNode('사용자가 입력한 주석');
  const textarea = element('textarea', { placeholder: '판정 이유' }, comment);
  textarea.value = '작성 중인 판정 이유';
  document.body = element('body', {}, question, path, status, code, textarea);
  document.createTreeWalker = mockWalker;
  locale.setLanguage('en');
  assert.equal(source.nodeValue, '질문과 원문은 그대로 보존합니다.');
  assert.equal(codeText.nodeValue, '# 원본 코드 주석\nanswer = 1');
  assert.equal(tooltip.getAttribute('aria-label'), 'other_2019 Source evidence 44.1');
  assert.equal(path.childNodes[0].nodeValue, 'reports/run/20261003-003/01-preparation/test-0001/01-round/run.json');
  assert.equal(path.getAttribute('data-copy'), rawPath);
  assert.equal(locale.originalText(path), rawPath);
  assert.equal(status.childNodes[0].nodeValue, 'Before the original claim');
  assert.equal(textarea.getAttribute('placeholder'), 'Decision reason');
  assert.equal(textarea.value, '작성 중인 판정 이유');
  assert.equal(comment.nodeValue, '사용자가 입력한 주석');
  locale.setLanguage('ko');
  assert.equal(path.childNodes[0].nodeValue, rawPath);
  assert.equal(status.childNodes[0].nodeValue, '원래 주장 앞');
  assert.equal(tooltip.getAttribute('aria-label'), 'other_2019 원문 근거 44.1');
});
check('Confirmation text is localized without changing the user answer', () => {
  let message;
  // The wrapper calls the same dialog and preserves its return value.
  const sandbox = { URL, location: { href: 'file:///review.html?lang=en' }, localStorage: { getItem() {} },
    confirm: text => { message = text; return false; } };
  vm.runInNewContext(source, sandbox);
  assert.equal(sandbox.confirm('판정 저장'), false);
  assert.equal(message, 'Save decision');
});
check('Saved bilingual findings switch, with an exact original fallback', () => {
  const { locale } = runtime();
  const node = { isConnected: true, setAttribute(name, value) { this[name] = value; } };
  locale.bindText(node, '판단 근거 원문입니다.', 'The rejection was too strict.');
  assert.equal(node.textContent, '판단 근거 원문입니다.');
  locale.setLanguage('en'); assert.equal(node.textContent, 'The rejection was too strict.');
  locale.setLanguage('ko'); assert.equal(node.textContent, '판단 근거 원문입니다.');
  locale.bindText(node, undefined, 'Original only'); assert.equal(node.textContent, 'Original only');
  assert.equal(node['data-i18n-skip'], '');
});
check('Both export builders include the shared locale assets without fetching them', () => {
  const dataset = fs.readFileSync('viewer/dataset/index.html', 'utf8');
  assert(dataset.includes('global.FinarchI18n ='));
  assert(!dataset.includes('@include ../shared/i18n'));
  const experiments = fs.readFileSync('src/finarch/experiments/viewer/export-html.mjs', 'utf8');
  assert(experiments.includes('${localeJS}'));
  assert(experiments.includes(".replace('<script src=\"/i18n.js\" defer></script>', '')"));
});
console.log(JSON.stringify({ status: 'PASS', checks, model_calls: 0 }));
