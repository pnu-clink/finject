import test from 'node:test';
import assert from 'node:assert/strict';
import { parseJsonTree, parseJsonDocument, jsonRows, jsonPage } from '../../../../../viewer/experiments/json-viewer.mjs';

test('token trees preserve large numbers, duplicate keys, escapes and source order', () => {
  const raw = '{"value":900719925474099312345,"value":-0,"exp":1.2300e+40,"\\u006b":"a\\n\\\"b","__proto__":{"safe":true}}';
  const root = parseJsonTree(raw);
  assert.deepEqual(root.children.map(node => node.key), ['"value"', '"value"', '"exp"', '"\\u006b"', '"__proto__"']);
  assert.deepEqual(root.children.map(node => raw.slice(node.start, node.end)), ['900719925474099312345', '-0', '1.2300e+40', '"a\\n\\\"b"', '{"safe":true}']);
  assert.equal(root.children.at(-1).children[0].kind, 'boolean');
  assert.equal({}.safe, undefined);
});

test('all JSON scalar and empty container roots remain inspectable', () => {
  for (const [raw, kind] of [['"text"', 'string'], ['false', 'boolean'], ['null', 'null'], ['1e999', 'number'], ['[]', 'array'], ['{}', 'object']]) {
    const root = parseJsonTree(` \n${raw}\t`), rows = [...jsonRows(root, () => true)];
    assert.equal(root.kind, kind);
    assert.equal(rows.length, 1);
    assert.equal(` \n${raw}\t`.slice(root.start, root.end), raw);
  }
});

test('partial, malformed and trailing JSON is rejected instead of repaired', () => {
  for (const raw of ['', '{"a":', '{"a":1,}', '[1,]', '{"a":01}', '{"a":NaN}', '{} trailing', '{"a":"\n"}']) {
    assert.throws(() => parseJsonTree(raw), SyntaxError);
  }
});

test('nested closure and comma positions remain valid when containers are folded', () => {
  const root = parseJsonTree('{"items":[{"x":1},false],"last":null}');
  const folded = [...jsonRows(root, node => node === root)];
  assert.deepEqual(folded.map(row => [row.node.kind, !!row.close, row.comma]), [
    ['object', false, false], ['array', false, true], ['null', false, false], ['object', true, false],
  ]);
  assert.equal([...jsonRows(root, () => false)].length, 1);
  const expanded = [...jsonRows(root, () => true)];
  assert.equal(expanded.filter(row => row.close).length, 3);
  assert.equal(expanded.find(row => row.close && row.node.kind === 'array').comma, true);
});

test('JSONL preserves CRLF, blank line numbers, Unicode separators and raw offsets', () => {
  const raw = '{"id":9007199254740993}\r\n\r\n{"text":"a\u2028b"}\nnull\n';
  const data = parseJsonDocument(raw, 'jsonl');
  assert.equal(data.raw, raw);
  assert.deepEqual(data.roots.map(root => root.recordLine), [1, 3, 4]);
  assert.deepEqual(data.roots.map(root => raw.slice(root.start, root.end)), ['{"id":9007199254740993}', '{"text":"a\u2028b"}', 'null']);
  assert.deepEqual(jsonPage(data, () => true).rows.filter(row => row.recordLine).map(row => row.recordLine), [1, 3, 4]);
  assert.equal(parseJsonDocument('\r\n', 'jsonl').roots.length, 0);
});

test('a malformed JSONL record reports its real line without omitting broken data', () => {
  assert.throws(() => parseJsonDocument('{"ok":1}\n\n{"broken":\n', 'jsonl'), /JSONL 3행/);
});

test('paged expansion bounds rendered rows and keeps every value reachable', () => {
  const raw = JSON.stringify(Array.from({ length: 997 }, (_, i) => i)), data = parseJsonDocument(raw);
  let page = 0, more = true; const rows = [];
  while (more) {
    const result = jsonPage(data, () => true, page++);
    assert.ok(result.rows.length <= 200); rows.push(...result.rows); more = result.more;
  }
  assert.equal(page, 5); assert.equal(rows.length, 999);
  assert.deepEqual(rows.filter(row => row.node.kind === 'number').map(row => Number(raw.slice(row.node.start, row.node.end))), Array.from({ length: 997 }, (_, i) => i));
  assert.deepEqual(jsonPage(data, () => false), { rows: [{ node: data.roots[0], depth: 0, comma: false }], more: false });
});

test('deep nesting is traversed without recursive rendering', () => {
  const raw = '['.repeat(6000) + 'null' + ']'.repeat(6000), data = parseJsonDocument(raw);
  const page = jsonPage(data, () => true, 29);
  assert.equal(page.rows.length, 200); assert.equal(page.more, true);
  assert.equal([...jsonRows(data.roots[0], () => true)].length, 12001);
});
