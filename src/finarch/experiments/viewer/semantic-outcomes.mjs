import { promises as fs, createReadStream } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const output = '02_analysis/05_outcomes';
import { outcomePage } from '../../../../viewer/experiments/semantic-outcomes-model.mjs';
export { outcomePage, outcomeCategories } from '../../../../viewer/experiments/semantic-outcomes-model.mjs';
async function hash(file) {
  const h = createHash('sha256');
  try { for await (const data of createReadStream(file)) h.update(data); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  return h.digest('hex');
}
// This endpoint only reads the final Python artifact and verifies its provenance.
export async function readSemanticOutcomeData(root) {
  const summaryPath = path.join(root, output, 'summary.json');
  let summaryBytes;
  try { summaryBytes = await fs.readFile(summaryPath); }
  catch (error) { if (error.code === 'ENOENT') return { status: 'NOT_PREPARED' }; throw error; }
  const summary = JSON.parse(summaryBytes);
  if (summary.schema_version !== 'ResponseOutcomeV1' || summary.run !== path.basename(root)) throw Error('Outcome identity mismatch');
  const allowed = path.dirname(path.resolve(root)) + path.sep;
  for (const [file, expected] of Object.entries(summary.source_hashes)) {
    if (!path.resolve(file).startsWith(allowed)) throw Error('Outcome source is outside experiment runs');
    if (await hash(file) !== expected) throw Error('분류 후 원자료가 변경됐습니다. Python 분류를 다시 실행해 주세요.');
  }
  for (const [folder, expected] of Object.entries(summary.latest_attempts)) {
    if (!path.resolve(folder).startsWith(allowed)) throw Error('Outcome attempt is outside experiment runs');
    const entries = await fs.readdir(folder).catch(error => { if (error.code === 'ENOENT') return []; throw error; });
    const attempts = entries.filter(n => /^attempt-\d+$/.test(n)).sort((a,b) => Number(b.slice(8))-Number(a.slice(8)));
    let latest = null;
    for (const name of attempts) {
      const candidate = path.join(folder, name, 'result.json');
      if (await fs.stat(candidate).catch(() => null)) { latest = candidate; break; }
    }
    if (latest !== expected) throw Error('새 Analysis 판정이 있습니다. Python 분류를 다시 실행해 주세요.');
  }
  const payload = await fs.readFile(path.join(root, output, 'responses.jsonl'));
  if (createHash('sha256').update(payload).digest('hex') !== summary.output_hashes['responses.jsonl']) throw Error('Outcome response hash mismatch');
  const rows = payload.toString().split('\n').filter(Boolean).map(line => JSON.parse(line));
  if (!(await fs.readFile(summaryPath)).equals(summaryBytes)) throw Error('분류 결과 갱신 중입니다. 다시 읽어 주세요.');
  return { status: 'AVAILABLE', summary, rows };
}

export async function readSemanticOutcomes(root, filters = {}) {
  const data = await readSemanticOutcomeData(root);
  return data.status === 'AVAILABLE' ? outcomePage(data.summary, data.rows, filters) : data;
}
