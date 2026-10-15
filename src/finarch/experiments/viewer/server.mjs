import { readOutcomeComparison } from './outcome-comparison.mjs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promises as fs } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { Repository, ViewError } from './repository.mjs';
import { exportHTML } from './export-html.mjs';
import { createQuadrantReports } from './quadrants.mjs';
import { readSemanticOutcomes } from './semantic-outcomes.mjs';
import { assetDirectory, projectDirectory } from './paths.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
export const defaultRoot = path.join(projectDirectory, 'reports/experiments-run');
const assets = { '/': ['index.html', 'text/html'], '/index.html': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/model.mjs': ['model.mjs', 'text/javascript'], '/json-viewer.mjs': ['json-viewer.mjs', 'text/javascript'], '/input-edits.mjs': ['input-edits.mjs', 'text/javascript'], '/feature-quadrant.mjs': ['feature-quadrant.mjs', 'text/javascript'], '/styles.css': ['styles.css', 'text/css'] };
Object.assign(assets, { '/sync.mjs': ['sync.mjs', 'text/javascript'], '/sync.css': ['sync.css', 'text/css'] });
Object.assign(assets, { '/response-assessments.mjs': ['response-assessments.mjs', 'text/javascript'] });
Object.assign(assets, { '/rq1-materials.mjs': ['rq1-materials.mjs', 'text/javascript'] });
Object.assign(assets, { '/grounding-model.mjs': ['grounding-model.mjs', 'text/javascript'], '/grounding-view.mjs': ['grounding-view.mjs', 'text/javascript'] });
Object.assign(assets, { '/semantic-outcomes.mjs': ['semantic-outcomes.mjs', 'text/javascript'] });
Object.assign(assets, { '/i18n.js': ['../shared/i18n.js', 'text/javascript'], '/i18n.css': ['../shared/i18n.css', 'text/css'], '/progress-dashboard.mjs': ['progress-dashboard.mjs', 'text/javascript'],
  '/progress-dashboard.css': ['progress-dashboard.css', 'text/css'] });
const rootIdentity = root => createHash('sha256').update(path.resolve(root)).digest('hex');

// [EV03.1] This standalone server exposes saved experiment data through GET only.
export function createServer({ root = defaultRoot, log = () => {} } = {}) {
  const repository = new Repository(root);
  const identity = rootIdentity(root);
  const quadrants = createQuadrantReports(root);
  let exporting = false;
  return http.createServer(async (req, res) => {
    const start = Date.now();
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Finarch-Viewer', 'experiments');
    res.setHeader('X-Finarch-Root', identity);
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
    const send = (status, value, type = 'application/json') => {
      res.writeHead(status, { 'Content-Type': `${type}; charset=utf-8` });
      res.end(type === 'application/json' ? JSON.stringify(value) : value);
    };
    try {
      if (req.method !== 'GET' && req.method !== 'HEAD') throw new ViewError('읽기 전용 뷰어입니다.', 405);
      const host = (req.headers.host || '').split(':')[0];
      if (!['127.0.0.1', 'localhost', '['].includes(host)) throw new ViewError('로컬 주소로 열어 주세요.', 403);
      if (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`) throw new ViewError('다른 웹사이트의 요청은 허용하지 않습니다.', 403);
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname === '/' && url.searchParams.get('tab') === 'sync') {
        return send(200, await fs.readFile(path.join(assetDirectory, 'sync.html'), 'utf8'), 'text/html');
      }
      if (url.pathname === '/' && url.searchParams.get('tab') === 'progress') {
        return send(200, await fs.readFile(path.join(assetDirectory, 'progress.html'), 'utf8'), 'text/html');
      }
      if (assets[url.pathname]) {
        const [file, type] = assets[url.pathname]; return send(200, await fs.readFile(path.join(assetDirectory, file), 'utf8'), type);
      }
      if (url.pathname === '/favicon.ico') { res.writeHead(204); return res.end(); }
      if (url.pathname === '/api/outcome-comparison') return send(200, await readOutcomeComparison(repository, url.searchParams.get('scope') || 'all', url.searchParams.get('cohort') || 'source'));
      if (url.pathname === '/api/runs') return send(200, { runs: await repository.runs() });
      if (url.pathname === '/api/sync') {
        const directory = path.resolve(root, '../../log/experiments-a100-sync');
        try {
          const status = JSON.parse(await fs.readFile(path.join(directory, 'status.json'), 'utf8'));
          const age = (Date.now() - Date.parse(status.updated_at)) / 1000;
          return send(200, { ...status, age_seconds: Math.max(0, age), stale: !Number.isFinite(age) || age > 180 });
        } catch (error) { if (error.code === 'ENOENT') return send(200, { status: 'NOT_CHECKED', runs: {}, code: {}, stale: true }); throw error; }
      }
      if (url.pathname === '/api/quadrants') {
        if (req.method === 'HEAD') { res.writeHead(200); return res.end(); }
        const metadata = await quadrants.refresh();
        log({ event: 'QUADRANT_REPORT_READ', datasets: metadata.datasets.length, inventory: metadata.inventory_summary, source_files: metadata.source_files, model_calls: 0 });
        return send(200, metadata);
      }
      const quadrant = url.pathname.match(/^\/quadrants\/([a-f0-9]{64})$/);
      if (quadrant) {
        const report = quadrants.get(quadrant[1]);
        res.setHeader('Content-Security-Policy', report.policy);
        return send(200, report.html, 'text/html');
      }
      const match = url.pathname.match(/^\/api\/runs\/([^/]+)\/(overview|progress|analysis-pairs|rq-pairs|pair-outcomes|rq1-materials|grounding-pairs|semantic-outcomes|rq-source-summaries|case|input-flow|documents|file|activity|export|export-html)$/);
      if (!match) throw new ViewError('없는 조회 주소입니다.', 404);
      if (match[2] === 'progress') return send(200, await repository.progress(decodeURIComponent(match[1]), url.searchParams.get('stage') || undefined));
      const snap = await repository.snapshot(decodeURIComponent(match[1]));
      const filters = Object.fromEntries(url.searchParams);
      switch (match[2]) {
        case 'overview': return send(200, repository.overview(snap, filters));
        case 'analysis-pairs': return send(200, repository.analysisPairs(snap, filters));
        case 'rq-pairs': return send(200, await repository.rqPairs(snap, filters));
        case 'pair-outcomes': return send(200, await repository.pairOutcomes(snap));
        case 'rq1-materials': return send(200, await repository.rq1Materials(snap));
        case 'grounding-pairs': return send(200, await repository.groundingPairs(snap, filters));
        case 'semantic-outcomes': return send(200, await readSemanticOutcomes(snap.root, filters));
        case 'rq-source-summaries': return send(200, await repository.rqSourceSummaries(snap));
        case 'input-flow': return send(200, await repository.input(snap));
        case 'case': return send(200, await repository.detail(snap, filters.case, filters));
        case 'documents': return send(200, { files: await repository.documents(snap) });
        case 'file': return send(200, await repository.file(snap, filters.id));
        case 'activity': return send(200, await repository.activity(snap));
        case 'export': return send(200, repository.export(snap, filters), 'text/markdown');
        case 'export-html': {
          if (exporting) throw new ViewError('다른 HTML을 만드는 중입니다. 완료 후 다시 내보내 주세요.', 409);
          if (req.method === 'HEAD') { res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); return res.end(); }
          exporting = true;
          const abort = new AbortController();
          const onClose = () => { if (!res.writableEnded) abort.abort(); };
          res.on('close', onClose);
          try {
            const exported = await exportHTML(repository, snap, { signal: abort.signal, initialView: filters });
            log({ event: 'HTML_EXPORT_READY', run: snap.id, ...exported.bundle.stats, bytes: Buffer.byteLength(exported.html) });
            res.setHeader('Content-Disposition', `attachment; filename="${exported.filename}"`);
            // The downloaded document contains its own hashes and disallows all connections.
            res.removeHeader('Content-Security-Policy');
            return send(200, exported.html, 'text/html');
          } finally { exporting = false; res.off('close', onClose); }
        }
      }
    } catch (error) {
      const status = error.status ?? (error.code === 'ENOENT' ? 404 : 500);
      send(status, { error: status === 500 ? '자료를 읽는 중 오류가 발생했습니다. 서버 로그를 확인해 주세요.' : error.message });
      log({ event: 'READ_ERROR', status, message: error.message });
    } finally { log({ event: 'HTTP_READ', method: req.method, route: req.url?.split('?')[0], status: res.statusCode, elapsed_ms: Date.now() - start }); }
  });
}

function openInBrowser(url) {
  const command = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'rundll32.exe' : 'xdg-open';
  const args = process.platform === 'win32' ? ['url.dll,FileProtocolHandler', url] : [url];
  return new Promise((resolve, reject) => execFile(command, args, { timeout: 10000 }, error => error ? reject(error) : resolve()));
}
function isSameViewer(url, root) {
  return new Promise(resolve => {
    const request = http.request(url, { method: 'HEAD' }, response => {
      response.resume();
      resolve(response.statusCode === 200 && response.headers['x-finarch-viewer'] === 'experiments' && response.headers['x-finarch-root'] === rootIdentity(root));
    });
    request.on('error', () => resolve(false));
    request.setTimeout(1500, () => request.destroy()); request.end();
  });
}
// [EV13.3] Launch after readiness; a second shortcut reuses only the same viewer/root.
export async function startViewer({ port = 8894, root = defaultRoot, browser = false, launch = openInBrowser, log = () => {} } = {}) {
  const server = createServer({ root, log });
  let reused = false, url = `http://127.0.0.1:${port}/`;
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, '127.0.0.1', () => { server.off('error', reject); resolve(); });
    });
    url = `http://127.0.0.1:${server.address().port}/`;
    server.on('error', error => log({ event: 'SERVER_ERROR', message: error.message }));
    log({ event: 'SERVER_READY', url, root: path.resolve(root), mode: 'READ_ONLY' });
  } catch (error) {
    if (error.code !== 'EADDRINUSE' || !await isSameViewer(url, root)) throw error;
    reused = true; log({ event: 'SERVER_ALREADY_RUNNING', url, root: path.resolve(root) });
  }
  if (browser) {
    try { await launch(url); log({ event: 'BROWSER_OPENED', url }); }
    catch (error) { log({ event: 'BROWSER_OPEN_ERROR', url, message: `브라우저를 열지 못했습니다. 이 주소를 직접 열어 주세요: ${error.message}` }); }
  }
  return { server: reused ? null : server, url, reused };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    process.stdout.write('Experiment viewer: [--port 8894] [--root PATH] [--open | --no-open]\n');
    process.exit(0);
  }
  const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
  const port = Number(option('--port', '8894'));
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port');
  const root = path.resolve(option('--root', defaultRoot));
  const log = value => process.stdout.write(JSON.stringify({ at: new Date().toISOString(), ...value }) + '\n');
  startViewer({ port, root, browser: args.includes('--open') && !args.includes('--no-open'), log }).catch(error => { log({ event: 'SERVER_ERROR', message: error.message }); process.exitCode = 1; });
}
