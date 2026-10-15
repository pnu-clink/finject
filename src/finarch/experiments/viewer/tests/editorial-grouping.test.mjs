import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Repository } from '../repository.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
const run = '20260928-exp-001-luna';
const folder = path.join(root, 'reports/experiments-run', run);
const stage = '02_analysis/03_research';
const digest = value => createHash('sha256').update(value).digest('hex');

test('current Luna editorial index covers each saved finding exactly once', async () => {
  const [raw, saved, paper, indexed] = await Promise.all([
    readFile(path.join(folder, stage, 'findings.json')),
    readFile(path.join(folder, stage, 'rq-review.json')),
    readFile(path.join(root, 'reports/run/20260924-paper-draft/PAPER-KO.md')),
    readFile(path.join(folder, stage, 'rq-sq-review.json')),
  ]);
  const findings = JSON.parse(raw).findings;
  const review = JSON.parse(saved), index = JSON.parse(indexed);
  assert.equal(findings.length, 183);
  assert.equal(review.source_sha256[`${stage}/findings.json`], digest(raw));
  assert.equal(index.paper.sha256, digest(paper));
  assert.equal(index.saved_review.sha256, digest(saved));
  assert.equal(index.paper_version, '0.27');
  assert.deepEqual(index.questions.map(q => q.id), ['RQ1', 'RQ2', 'SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5', 'SQ6']);
  for (const q of index.questions) assert.ok(paper.toString().includes(q.question_ko));
  const assigned = review.groups.flatMap(g => g.primary_finding_ids);
  assert.equal(assigned.length, findings.length);
  assert.deepEqual(new Set(assigned), new Set(findings.map(f => f.id)));
  assert.equal(new Set(review.finding_review.map(r => r.finding_id)).size, findings.length);
  assert.equal(new Set(index.questions.flatMap(q => q.group_ids)).size, review.groups.length);
  assert.deepEqual(index.questions.filter(q => !q.group_ids.length).map(q => q.id), ['SQ2', 'SQ4', 'SQ5', 'SQ6']);
});

test('viewer document API includes the current question index', async () => {
  const repository = new Repository(path.join(root, 'reports/experiments-run'));
  const snap = { root: folder, id: run, files: new Map() };
  const documents = await repository.documents(snap);
  const index = documents.find(file => file.path === `${stage}/rq-sq-review.json`);
  assert.ok(index);
  assert.ok(documents.some(file => file.path === `${stage}/rq-sq-review-README.md`));
  const loaded = await repository.file(snap, index.id);
  assert.equal(JSON.parse(loaded.content).groups.length, 9);
});
