import { projectDirectory, assetDirectory } from '../paths.mjs';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// [EV05.1] Generate the user guide from the saved local verification record.
const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const project = projectDirectory;
const verification = JSON.parse(await fs.readFile(path.join(project, 'log/viewer-experiments-v1/verification.json'), 'utf8'));
const testLog = await fs.readFile(path.join(project, 'log/viewer-experiments-v1/tests.log'), 'utf8');
const exportVerification = JSON.parse(await fs.readFile(path.join(project, 'log/viewer-experiments-html-export/verification.json'), 'utf8'));
const values = { latest_run: verification.runs.find(r => r.state === 'FINISHED')?.id ?? '', node_version: process.version, verified_at: verification.at, tests: testLog.match(/tests (\d+)/)?.[1] ?? '로그 참조', run_count: verification.runs.length,
  export_tests: exportVerification.tests, export_run_count: exportVerification.runs.length, export_verified_at: exportVerification.at,
  export_file_rows: [...exportVerification.runs].sort((a, b) => a.id.localeCompare(b.id)).map(r => `|[${r.id}](${path.basename(r.output)})|${r.requests.toLocaleString('en-US')}|${r.cases.toLocaleString('en-US')}|${(r.html_bytes / 1024 / 1024).toFixed(1)} MB|${r.unavailable_files.length}개|`).join('\n') };
const render = template => template.replace(/\{\{(\w+)\}\}/g, (_, key) => { if (!(key in values)) throw Error(`Unknown template field: ${key}`); return values[key]; });
// Keep the current guide in the central documentation template registry.
const template = await fs.readFile(path.join(project, 'src/finarch/documentation/templates/viewer-experiments.md'), 'utf8');
await fs.writeFile(path.join(assetDirectory, 'README.md'), template);
await fs.writeFile(path.join(project, 'exp-viewer/README.md'), await fs.readFile(path.join(directory, 'templates/legacy-readme.template.md'), 'utf8'));
await fs.writeFile(path.join(project, 'log/viewer-experiments-v1/README.md'), await fs.readFile(path.join(directory, 'templates/log-readme.template.md'), 'utf8'));
for (const [template, target] of [['export-log-readme.template.md', 'log/viewer-experiments-html-export/README.md'], ['export-files-readme.template.md', 'outputs/experiment-exports/README.md']]) {
  await fs.writeFile(path.join(project, target), render(await fs.readFile(path.join(directory, 'templates', template), 'utf8')));
}
console.log('Generated viewer/experiments/README.md');
const collapseLog = path.join(project, 'log/viewer-experiments-input-collapse');
await fs.mkdir(collapseLog, { recursive: true });
await fs.writeFile(path.join(collapseLog, 'README.md'), await fs.readFile(path.join(directory, 'templates/input-collapse-log-readme.template.md'), 'utf8'));
