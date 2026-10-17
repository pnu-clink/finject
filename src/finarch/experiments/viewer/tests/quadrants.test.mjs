import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createQuadrantReports, reportPolicy } from '../quadrants.mjs';
import { createServer } from '../server.mjs';

test('metadata and framed HTML share one read; a refresh obtains new data', async () => {
  let calls = 0;
  const reports = createQuadrantReports('/custom', async root => {
    assert.equal(root, '/custom');
    await new Promise(resolve => setTimeout(resolve, 5));
    calls++;
    return { html: `<script>const n=${calls};</script><style>body{margin:0}</style>`, metadata: { calls } };
  });
  const [first, same] = await Promise.all([reports.refresh(), reports.refresh()]);
  assert.equal(calls, 1);
  assert.equal(first.url, same.url);
  const version = first.url.split('/').at(-1);
  assert.match(reports.get(version).html, /n=1/);
  const fresh = await reports.refresh();
  assert.notEqual(fresh.url, first.url);
  assert.equal(fresh.calls, 2);
  assert.match(reports.get(version).html, /n=1/);
});

test('framed report permits only its own hashed scripts and styles', () => {
  const script = 'const n=1;', css = 'body{margin:0}';
  const policy = reportPolicy(`<script>${script}</script><style>${css}</style>`);
  for (const value of [script, css]) assert.ok(policy.includes(`'sha256-${createHash('sha256').update(value).digest('base64')}'`));
  assert.match(policy, /frame-ancestors 'self'/);
  assert.match(policy, /connect-src 'none'/);
  assert.ok(!policy.includes('unsafe-inline'));
});

test('a failed read can be retried, while old frames expire explicitly', async () => {
  let count = 0;
  const reports = createQuadrantReports('/runs', async () => {
    if (++count === 1) throw Error('writing');
    return { html: `<p>${count}</p>`, metadata: {} };
  });
  await assert.rejects(reports.refresh(), /writing/);
  const first = await reports.refresh();
  for (let index = 0; index < 4; index++) await reports.refresh();
  assert.throws(() => reports.get(first.url.split('/').at(-1)), error => error.status === 409);
});

test('HTTP routes use the configured empty root without reading default results or writing files', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'finarch-quadrants-'));
  const server = createServer({ root });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { await new Promise(resolve => server.close(resolve)); await fs.rm(root, { recursive: true, force: true }); });
  const url = `http://127.0.0.1:${server.address().port}`;
  const response = await fetch(url + '/api/quadrants');
  assert.equal(response.status, 404);
  assert.match((await response.json()).error, /\uc9d1\uacc4\uac00 \uc544\uc9c1 \uc800\uc7a5\ub418\uc9c0/);
  assert.deepEqual(await fs.readdir(root), []);
  assert.equal((await fetch(url + '/quadrants/' + '0'.repeat(64))).status, 409);
  assert.equal((await fetch(url + '/api/quadrants', { method: 'POST' })).status, 405);
  assert.equal((await fetch(url + '/api/quadrants', { headers: { Origin: 'https://foreign.example' } })).status, 403);
});
