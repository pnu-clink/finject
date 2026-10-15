import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import os from 'node:os';
import { startViewer } from '../server.mjs';

const root = path.join(os.tmpdir(), 'finarch-launch-test');
const cleanup = (t, server) => t.after(() => { server.closeAllConnections(); return new Promise(resolve => server.close(resolve)); });

test('browser opens only after the real viewer is accepting requests', async t => {
  const events = [], opened = [];
  const result = await startViewer({ port: 0, root, browser: true, log: e => events.push(e.event), launch: async url => {
    const response = await fetch(url, { method: 'HEAD' });
    assert.equal(response.status, 200); assert.equal(response.headers.get('x-finarch-viewer'), 'experiments'); opened.push(url);
  } });
  cleanup(t, result.server);
  assert.deepEqual(opened, [result.url]); assert.equal(result.reused, false);
  assert.ok(events.indexOf('SERVER_READY') < events.indexOf('BROWSER_OPENED'));
});

test('starting twice reopens the same viewer without launching another server', async t => {
  const first = await startViewer({ port: 0, root }); cleanup(t, first.server);
  const opened = [], second = await startViewer({ port: first.server.address().port, root, browser: true, launch: async url => opened.push(url) });
  assert.equal(second.reused, true); assert.equal(second.server, null); assert.deepEqual(opened, [first.url]);
});

test('headless launch also reuses the same server without opening a browser', async t => {
  const first = await startViewer({ port: 0, root }); cleanup(t, first.server);
  const second = await startViewer({ port: first.server.address().port, root, browser: false,
    launch: async () => { throw Error('Browser must stay closed'); } });
  assert.equal(second.reused, true); assert.equal(second.server, null);
});

test('an occupied port serving another root or another app is never silently opened', async t => {
  const first = await startViewer({ port: 0, root }); cleanup(t, first.server);
  let opened = false;
  const launch = async () => { opened = true; };
  await assert.rejects(startViewer({ port: first.server.address().port, root: `${root}-other`, browser: true, launch }), { code: 'EADDRINUSE' });
  const other = http.createServer((req, res) => { res.writeHead(200); res.end('Another app'); });
  await new Promise(resolve => other.listen(0, '127.0.0.1', resolve)); cleanup(t, other);
  await assert.rejects(startViewer({ port: other.address().port, root, browser: true, launch }), { code: 'EADDRINUSE' });
  assert.equal(opened, false);
});

test('opener failure leaves the viewer running and records the address for manual opening', async t => {
  const events = [];
  const result = await startViewer({ port: 0, root, browser: true, log: event => events.push(event), launch: async () => { throw Error('No browser'); } }); cleanup(t, result.server);
  assert.equal((await fetch(result.url, { method: 'HEAD' })).status, 200);
  assert.equal(events.find(e => e.event === 'BROWSER_OPEN_ERROR').url, result.url);
});
