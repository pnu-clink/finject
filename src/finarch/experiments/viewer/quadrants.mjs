import path from 'node:path';
import { constants, promises as fs } from 'node:fs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { projectDirectory } from './paths.mjs';
import { ViewError } from './repository.mjs';

const execute = promisify(execFile);
const digest = value => createHash('sha256').update(value).digest('base64');

// Only the experiments viewer may frame this report; inline code is hash-bound.
export function reportPolicy(html) {
  const hashes = tag => [...html.matchAll(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`, 'gi'))]
    .map(match => `'sha256-${digest(match[1])}'`).join(' ');
  return `default-src 'none'; script-src ${hashes('script')}; style-src ${hashes('style')}; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'none'`;
}

async function readReport(root) {
  let python = 'python3';
  for (const candidate of [path.join(projectDirectory, '.venv/bin/python'), '/opt/homebrew/bin/python3', '/usr/local/bin/python3']) {
    try { await fs.access(candidate, constants.X_OK); python = candidate; break; } catch { /* Try the next installed runtime. */ }
  }
  const { stdout } = await execute(python, ['-B', '-m', 'finarch.experiments.viewer.quadrants', '--root', path.resolve(root)], {
    cwd: projectDirectory, timeout: 60000, maxBuffer: 4 * 1024 * 1024,
    env: { ...process.env, PYTHONPATH: path.join(projectDirectory, 'src'), PYTHONDONTWRITEBYTECODE: '1' }
  });
  const result = JSON.parse(stdout);
  if (result.error) throw new ViewError(result.error === 'NO_COMPARABLE_SAVED_RESULTS'
    ? '비교 가능한 7조건 A02 집계가 아직 저장되지 않았습니다. 저장이 완료된 뒤 새로 읽기를 눌러 주세요.'
    : `비교 자료 확인에 실패했습니다 (${result.error}). 저장이 완료된 뒤 새로 읽기를 눌러 주세요.`, result.status);
  return result;
}

// [EV23.1] A metadata response and its framed HTML share one verified read.
export function createQuadrantReports(root, read = readReport) {
  const versions = new Map();
  let pending;
  return {
    async refresh() {
      pending ??= read(root).then(({ html, metadata }) => {
        if (typeof html !== 'string' || Buffer.byteLength(html) > 2 * 1024 * 1024 || !metadata) throw new ViewError('비교 화면 자료 형식이 올바르지 않습니다.', 500);
        const version = createHash('sha256').update(html).digest('hex');
        versions.set(version, { html, policy: reportPolicy(html), metadata });
        while (versions.size > 4) versions.delete(versions.keys().next().value);
        return { ...metadata, url: `/quadrants/${version}` };
      }).finally(() => { pending = undefined; });
      return pending;
    },
    get(version) {
      if (!versions.has(version)) throw new ViewError('비교 화면의 조회 시간이 만료되었습니다. 새로 읽기를 눌러 주세요.', 409);
      return versions.get(version);
    }
  };
}
