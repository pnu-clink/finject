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
check('English default and explicit language URL preference', () => {
  assert.equal(runtime().locale.language, 'en');
  assert.equal(runtime({ href: 'http://localhost/?lang=ko' }).locale.language, 'ko');
  assert.equal(runtime({ href: 'http://localhost/?lang=en', saved: 'ko' }).locale.language, 'en');
  assert.equal(runtime({ href: 'file:///review.html?lang=en', unavailable: true }).locale.language, 'en');
});
check('Stored choice, invalid preference and offline storage failure', () => {
  assert.equal(runtime({ saved: 'en' }).locale.language, 'en');
  assert.equal(runtime({ saved: 'invalid' }).locale.language, 'en');
  const { locale, document } = runtime({ unavailable: true });
  locale.setLanguage('en'); assert.equal(document.documentElement.lang, 'en');
  locale.setLanguage('ko'); assert.equal(locale.language, 'ko');
});
check('Language choice persists without changing form values or source objects', () => {
  const { locale, storage } = runtime();
  const record = { question: '\uac80\uc0ac \ud1b5\uacfc', context: '\uc2e4\ud328 \ud574\uc11d', answer: '-35', decision: 'REJECTED' };
  const before = JSON.stringify(record);
  locale.setLanguage('en'); assert.equal(storage.get('finarch.viewer.language'), 'en');
  assert.equal(JSON.stringify(record), before);
  locale.setLanguage('invalid'); assert.equal(locale.language, 'en');
});
check('Complete UI sentences and dynamic counters render without mixed languages', () => {
  const { locale } = runtime();
  const cases = {
    '\ud310\uc815 \uc800\uc7a5 (x key)': 'Save decision (x key)',
    '78 / 100\uac1c \ubb38\ud56d · 78\uac1c \uc720\ud615 \uae30\ub85d': '78 / 100 cases · 78 variant records',
    '\ud574\uc11d\uc5d0 \uc0ac\uc6a9\ud55c \uadfc\uac70 \ud30c\uc77c 79\uac1c': '79 evidence files used in analysis',
    '\uc6d0\ubb38 1,080\uac1c · \ubcc0\ud615 7,560\uac1c · 1\uac1c \ubaa8\ub378\uc758 \uc800\uc7a5\ub41c \uacb0\uacfc': '1,080 originals · 7,560 variants · saved results from 1 models',
    '\uc18c\uc694\uc2dc\uac04 0\uc2dc\uac04 26\ubd84 34\ucd08 · \ub3d9\uc2dc\ucc98\ub9ac \ud55c\ub3c4 200\ubb38\ud56d': 'Elapsed 0h 26m 34s · concurrency limit 200 cases'
  };
  for (const [ko, en] of Object.entries(cases)) { assert.equal(locale.translate(ko, 'en'), en); assert.equal(locale.translate(ko, 'ko'), ko); }
});
check('Untranslated source text is not rewritten into a partial translation', () => {
  const { locale } = runtime();
  const text = '\uc774 \ubb38\ud56d\uc740 \uc544\uc9c1 \uc5f0\uad6c\uc790\uac00 \uc791\uc131\ud55c \ud55c\uad6d\uc5b4 \uc124\uba85\uc785\ub2c8\ub2e4.';
  assert.equal(locale.translate(text, 'en'), text);
});
check('Portable reviewer labels, import errors and dynamic messages are fully English', () => {
  const { locale } = runtime();
  const labels = [
    '\ub370\uc774\ud130 \ud3c9\uac00 · 20261003-concat-002', '\ubb38\uc81c\ubcc4', '\uc720\ud615\ubcc4', '\ubcc0\uacbd \ubb38\uc7a5\uacfc \uadfc\uac70',
    '\uc6d0\ubb38 \ub9e5\ub77d', '\ucd08\ub85d: \ucd94\uac00 · \ucde8\uc18c\uc120: \uc0ad\uc81c · \ubd84\ud64d/\ube68\uac15: \ucd9c\ucc98', '\uc804\uccb4 \ubcf4\uae30',
    '… 4252\uc790 \uc0dd\ub7b5 · \ud3bc\uce58\uae30', '\ubb38\uc7a5·\uc218\uc2dd·\ub178\ub4dc\ub97c \uc120\ud0dd\ud558\uba74 \uc5f0\uacb0 \uacc4\uc0b0\uc774 \uac15\uc870\ub429\ub2c8\ub2e4.',
    '\uc8fc\uc11d (\uc120\ud0dd) · N\uc73c\ub85c \uc785\ub825 · Enter\ub85c \uc800\uc7a5 · Shift+Enter \uc904\ubc14\uafc8', '\ud310\uc815 \ud6c4 \ub2e4\uc74c \ubbf8\ud3c9\uac00',
    '1·2·3 \ud310\uc815 · Q/E \ud544\ud130\ub41c \ubb38\uc81c \uc774\uc804·\ub2e4\uc74c · A/D \uc720\ud615 \uc774\uc804·\ub2e4\uc74c · v \ub2e4\uc74c \uc720\ubcf4·\uc2e4\ud328 / Shift+V \uc774\uc804 · N \uc8fc\uc11d',
    '● \ucd08\ub85d \ud1b5\uacfc · ● \ube68\uac15 \uc2e4\ud328 · ● \ub178\ub791 \uc720\ubcf4', '\ubcc0\uacbd 1 · \ucd94\uac00', '\ubcc0\uacbd 2 · \uad50\uccb4',
    '12 / 8820 \uc644\ub8cc · \ud1b5\uacfc 8 · \uc2e4\ud328 2 · \uc720\ubcf4 2', '\ubaa9\ub85d 1260 / 1260\ubb38\ud56d',
    'test-0007 · IC-VALUE \uc55e \ud1b5\uacfc \uc800\uc7a5\ub428 · \uc774 \uc2e4\ud589\uc758 \ud3c9\uac00\ub97c \ubaa8\ub450 \ub9c8\ucce4\uc2b5\ub2c8\ub2e4.',
    '\ud310\uc815 \uc800\uc7a5 1 / 1260 · IC-VALUE \uc55e', '\ubb38\uc7a5 \ubc30\uce58: \uc6d0\ub798 \uc8fc\uc7a5 \ub4a4',
    'test-0007 · IC-VALUE \uc55e\uc758 \uae30\uc874 \uc0c1\uc138 \ud654\uba74',
    '20261003-concat-002 · \uc784\uc2dc JSON \ub2e4\uc6b4\ub85c\ub4dc\ub97c \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4.',
    '\ud3c9\uac00\uc790 \uc774\ub984\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694.', '\uc774 HTML\uc5d0\uc11c \uc800\uc7a5\ud55c \ud3c9\uac00 \ud30c\uc77c\uc774 \uc544\ub2d9\ub2c8\ub2e4.',
    '\ud30c\uc77c\uc744 \uc77d\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4: \ud3c9\uac00\uc790 \uc774\ub984\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.',
    '\uac04\ub7b5 \uadf8\ub798\ud504\ub97c \ud45c\uc2dc\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4: \uc785\ub825 \ub178\ub4dc \uae30\ub85d\uc774 \uc5c6\uc2b5\ub2c8\ub2e4: n3',
    'A · \ucd5c\uc885 \ub2f5 = \uacc4\uc0b0 \ubd88\uac00\n\ub178\ub4dc n3, n4', '20261003-concat-002 · test-0007 · HTML \ub0b4\uc7a5 \uc790\ub8cc'
  ];
  for (const ko of labels) {
    assert(!/[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/.test(locale.translate(ko, 'en')), ko);
    assert.equal(locale.translate(ko, 'ko'), ko);
  }
  assert.equal(locale.translate('… 4252\uc790 \uc0dd\ub7b5 · \ud3bc\uce58\uae30', 'en'), '… 4252 characters hidden · Expand');
});
check('Reported dataset headings, graph labels and live counters have no Korean', () => {
  const { locale } = runtime();
  const labels = [
    '03-calculation · \uacc4\uc0b0\uacfc \uc815\ub2f5', '\uc678\ubd80\uc9c0\uc2dd \uc694\uad6c \ubb38\uad6c·\ud0dc\uadf8·\uacf5\uc2dd \uc815\uc758',
    '\ucf54\ub4dc·\uc2e4\ud589 \uacb0\uacfc·\uc815\ub2f5 \ube44\uad50', '\ubaa8\ub378\uc774 \uc9c0\uc815\ud55c \uc6d0\ubb38 \uc704\uce58',
    '\uc0c9\uc774 \uc788\ub294 \uc6d0\ubb38 \uc22b\uc790, \ubcc0\uc218 \ud45c, \ucf54\ub4dc \uc904\uc5d0 \ub9c8\uc6b0\uc2a4\ub97c \uc62c\ub9ac\uac70\ub098 \ud074\ub9ad\ud558\uba74 \uc5f0\uacb0\ub41c \ubd80\ubd84\uc744 \uac15\uc870\ud569\ub2c8\ub2e4. \uc0c9\uc0c1\uc740 \uadfc\uac70\uc640 \ucf54\ub4dc\uc758 \ucc38\uc870 \uc5f0\uacb0\uc774\uba70, \uc2e4\ud589 \uc131\uacf5\uc740 \uc544\ub798 \uc2e4\uc81c \uacb0\uacfc\uc5d0\uc11c \ud655\uc778\ud569\ub2c8\ub2e4.',
    '\uc120\ud0dd\ud55c \ucf54\ub4dc 22\ubc88\uc9f8 \uc904', 'appliances_2018 = \uacc4\uc0b0 \ubd88\uac00 · \ucf54\ub4dc 2\ud589',
    '\ubcc0\uc218 · answer', 'IC-VALUE · \uc55e — \ubb38\uc7a5 \uc0dd\uc131 \uba54\ub274\uc5d0\uc11c \uc704\uce58\ub97c \ube44\uad50\ud569\ub2c8\ub2e4. \uc774 \uc55e/\ub4a4 \uc30d\uc740 \ub3d9\uc77c\ud55c A/B \uacc4\uc0b0 \uadf8\ub798\ud504\ub97c \uacf5\uc720\ud569\ub2c8\ub2e4.',
    '\uc18c\uc694\uc2dc\uac04 0\uc2dc\uac04 20\ubd84 11\ucd08 · \ub3d9\uc2dc\ucc98\ub9ac \ud55c\ub3c4 200\ubb38\ud56d',
    '\uc120\ud0dd\ud55c \uc2e4\ud589: 20261003-003 · 717\uac1c \ubb38\ud56d \uae30\ub85d · \uc77d\uae30 \uc644\ub8cc \ud6c4 10\ucd08\ub9c8\ub2e4 \ubcc0\uacbd \ud655\uc778 · \ucd5c\uadfc \ud655\uc778 \uc624\ud6c4 11:16:11'
  ];
  const hangul = /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]/;
  for (const label of labels) {
    assert(!hangul.test(locale.translate(label, 'en')), label);
    assert.equal(locale.translate(label, 'ko'), label);
  }
  assert.equal(locale.translate('undefined (1\ucc28 \uc218\uc815)', 'en'), 'undefined (revision 1)');
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
  const raw = textNode('\uc6d0\ubb38 \ub9e5\ub77d\uc740 \ud55c\uad6d\uc5b4 \uc6d0\ubcf8 \uadf8\ub300\ub85c \ubcf4\uc874\ud569\ub2c8\ub2e4.');
  const gap = element('button', { 'data-i18n-ui': '' }, textNode('… 4252\uc790 \uc0dd\ub7b5 · \ud3bc\uce58\uae30'));
  const note = element('textarea', { placeholder: '\uc8fc\uc11d (\uc120\ud0dd) · N\uc73c\ub85c \uc785\ub825 · Enter\ub85c \uc800\uc7a5 · Shift+Enter \uc904\ubc14\uafc8' });
  note.value = '\uac80\ud1a0\uc790\uac00 \uc791\uc131\ud55c \ud55c\uad6d\uc5b4 \uc758\uacac';
  document.body = element('body', {}, element('div', { class: 'prose' }, raw, gap), note);
  document.createTreeWalker = mockWalker;
  locale.setLanguage('en');
  assert.equal(gap.childNodes[0].nodeValue, '… 4252 characters hidden · Expand');
  assert.equal(raw.nodeValue, '\uc6d0\ubb38 \ub9e5\ub77d\uc740 \ud55c\uad6d\uc5b4 \uc6d0\ubcf8 \uadf8\ub300\ub85c \ubcf4\uc874\ud569\ub2c8\ub2e4.');
  assert.equal(note.value, '\uac80\ud1a0\uc790\uac00 \uc791\uc131\ud55c \ud55c\uad6d\uc5b4 \uc758\uacac');
  assert.equal(note.getAttribute('placeholder'), 'Comment (optional) · N to edit · Enter to save · Shift+Enter for a new line');
  locale.setLanguage('ko');
  assert.equal(gap.childNodes[0].nodeValue, '… 4252\uc790 \uc0dd\ub7b5 · \ud3bc\uce58\uae30');
  assert.equal(note.value, '\uac80\ud1a0\uc790\uac00 \uc791\uc131\ud55c \ud55c\uad6d\uc5b4 \uc758\uacac');
  assert(fs.readFileSync('viewer/dataset/evaluation/review.js', 'utf8').includes("gap.setAttribute('data-i18n-ui','')"));
});
check('Opaque source text keeps UI tooltips, portable paths and status labels reversible', () => {
  const { locale, document } = runtime();
  const source = textNode('\uc9c8\ubb38\uacfc \uc6d0\ubb38\uc740 \uadf8\ub300\ub85c \ubcf4\uc874\ud569\ub2c8\ub2e4.');
  const tooltip = element('button', { 'aria-label': 'other_2019 \uc6d0\ubb38 \uadfc\uac70 44.1' }, textNode('44.1'));
  const question = element('div', { class: 'prose' }, source, tooltip);
  const rawPath = '/Volumes/EX400U/workspace/\u1102\u1169\u11ab\u1106\u116e\u11ab/fin-arch/reports/run/20261003-003/01-preparation/test-0001/01-round/run.json';
  const path = element('span', { class: 'file-path', 'data-copy': rawPath }, textNode(rawPath));
  const status = element('div', { class: 'prose', 'data-i18n-ui': '' }, textNode('\uc6d0\ub798 \uc8fc\uc7a5 \uc55e'));
  const codeText = textNode('# \uc6d0\ubcf8 \ucf54\ub4dc \uc8fc\uc11d\nanswer = 1');
  const code = element('pre', {}, codeText);
  const comment = textNode('\uc0ac\uc6a9\uc790\uac00 \uc785\ub825\ud55c \uc8fc\uc11d');
  const textarea = element('textarea', { placeholder: '\ud310\uc815 \uc774\uc720' }, comment);
  textarea.value = '\uc791\uc131 \uc911\uc778 \ud310\uc815 \uc774\uc720';
  document.body = element('body', {}, question, path, status, code, textarea);
  document.createTreeWalker = mockWalker;
  locale.setLanguage('en');
  assert.equal(source.nodeValue, '\uc9c8\ubb38\uacfc \uc6d0\ubb38\uc740 \uadf8\ub300\ub85c \ubcf4\uc874\ud569\ub2c8\ub2e4.');
  assert.equal(codeText.nodeValue, '# \uc6d0\ubcf8 \ucf54\ub4dc \uc8fc\uc11d\nanswer = 1');
  assert.equal(tooltip.getAttribute('aria-label'), 'other_2019 Source evidence 44.1');
  assert.equal(path.childNodes[0].nodeValue, 'reports/run/20261003-003/01-preparation/test-0001/01-round/run.json');
  assert.equal(path.getAttribute('data-copy'), rawPath);
  assert.equal(locale.originalText(path), rawPath);
  assert.equal(status.childNodes[0].nodeValue, 'Before the original claim');
  assert.equal(textarea.getAttribute('placeholder'), 'Decision reason');
  assert.equal(textarea.value, '\uc791\uc131 \uc911\uc778 \ud310\uc815 \uc774\uc720');
  assert.equal(comment.nodeValue, '\uc0ac\uc6a9\uc790\uac00 \uc785\ub825\ud55c \uc8fc\uc11d');
  locale.setLanguage('ko');
  assert.equal(path.childNodes[0].nodeValue, rawPath);
  assert.equal(status.childNodes[0].nodeValue, '\uc6d0\ub798 \uc8fc\uc7a5 \uc55e');
  assert.equal(tooltip.getAttribute('aria-label'), 'other_2019 \uc6d0\ubb38 \uadfc\uac70 44.1');
});
check('Confirmation text is localized without changing the user answer', () => {
  let message;
  // The wrapper calls the same dialog and preserves its return value.
  const sandbox = { URL, location: { href: 'file:///review.html?lang=en' }, localStorage: { getItem() {} },
    confirm: text => { message = text; return false; } };
  vm.runInNewContext(source, sandbox);
  assert.equal(sandbox.confirm('\ud310\uc815 \uc800\uc7a5'), false);
  assert.equal(message, 'Save decision');
});
check('Saved bilingual findings switch, with an exact original fallback', () => {
  const { locale } = runtime({ href: 'file:///review.html?lang=ko' });
  const node = { isConnected: true, setAttribute(name, value) { this[name] = value; } };
  locale.bindText(node, '\ud310\ub2e8 \uadfc\uac70 \uc6d0\ubb38\uc785\ub2c8\ub2e4.', 'The rejection was too strict.');
  assert.equal(node.textContent, '\ud310\ub2e8 \uadfc\uac70 \uc6d0\ubb38\uc785\ub2c8\ub2e4.');
  locale.setLanguage('en'); assert.equal(node.textContent, 'The rejection was too strict.');
  locale.setLanguage('ko'); assert.equal(node.textContent, '\ud310\ub2e8 \uadfc\uac70 \uc6d0\ubb38\uc785\ub2c8\ub2e4.');
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
