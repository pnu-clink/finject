import { promises as fs } from 'node:fs';
import path from 'node:path';
import { Repository } from '../repository.mjs';
import { exportHTML } from '../export-html.mjs';
import { defaultRoot } from '../server.mjs';

const [run, output] = process.argv.slice(2);
if (!run || !output) throw Error('Usage: node src/finarch/experiments/viewer/scripts/export-html.mjs RUN OUTPUT.html');
const repository = new Repository(defaultRoot), snap = await repository.snapshot(run);
const result = await exportHTML(repository, snap);
await fs.mkdir(path.dirname(path.resolve(output)), { recursive: true });
await fs.writeFile(output, result.html, { flag: 'wx' });
console.log(JSON.stringify({ event: 'HTML_EXPORTED', run, output: path.resolve(output), bytes: Buffer.byteLength(result.html), ...result.bundle.stats }));
