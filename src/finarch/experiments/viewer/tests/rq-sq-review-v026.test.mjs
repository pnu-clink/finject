import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Repository } from '../repository.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
const run = '20260927-exp-007-luna';
const folder = path.join(root, 'reports/experiments-run', run);
const source = '02_analysis/03_research/rq-review.json';
const index = '02_analysis/03_research/rq-sq-review-v026.json';
const paper = 'reports/run/20260924-paper-draft/PAPER-KO.md';
const digest = value => createHash('sha256').update(value).digest('hex');

test('v0.26 index uses exact paper questions and maps every saved group once', async () => {
  const [raw, paperText, indexText] = await Promise.all([
    readFile(path.join(folder, source)), readFile(path.join(root, paper)), readFile(path.join(folder, index)),
  ]);
  const saved = JSON.parse(raw), review = JSON.parse(indexText);
  assert.equal(review.paper_version, '0.26');
  assert.equal(review.paper.sha256, digest(paperText));
  assert.equal(review.saved_review.sha256, digest(raw));
  assert.deepEqual(review.questions.map(question => question.id), ['RQ1', 'RQ2', 'SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5', 'SQ6']);
  for (const question of review.questions) assert.ok(paperText.includes(question.question_ko), question.id);
  const mapped = review.questions.flatMap(question => question.group_ids);
  assert.equal(new Set(mapped).size, mapped.length);
  assert.deepEqual(new Set(mapped), new Set(saved.groups.map(group => group.id)));
  const findings = review.groups.flatMap(group => group.primary_finding_ids);
  assert.equal(findings.length, 104);
  assert.equal(new Set(findings).size, findings.length);
  for (const question of review.questions.filter(item => !item.group_ids.length)) assert.match(question.scope_ko, /없습니다|보류/);
  assert.match(review.groups.find(group => group.id === 'G01').boundary_ko, /SQ1/);
  assert.doesNotMatch(review.groups.find(group => group.id === 'G01').boundary_ko, /RQ1|H1/);
  assert.equal(saved.groups.find(group => group.id === 'G01').boundary_ko.includes('RQ1'), true);
});

test('online and single-HTML document lists can read the question index', async () => {
  const repository = new Repository(path.join(root, 'reports/experiments-run'));
  const snap = { root: folder, id: run, files: new Map() };
  const documents = await repository.documents(snap);
  const indexed = documents.find(file => file.path === index);
  assert.ok(indexed);
  assert.ok(documents.some(file => file.path === '02_analysis/03_research/rq-sq-review-v026-README.md'));
  const file = await repository.file(snap, indexed.id);
  assert.deepEqual(JSON.parse(file.content).questions.map(question => question.id), ['RQ1', 'RQ2', 'SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5', 'SQ6']);
});
