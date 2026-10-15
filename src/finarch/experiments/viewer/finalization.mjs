import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
export const FINALIZATION_FILES = ['02_analysis/finalization-policy.json', '02_analysis/preparation-state.json', '02_analysis/05_outcomes/summary.json', '02_analysis/05_outcomes/responses.jsonl', '02_analysis/04_quadrant/state.json'];
export function finalizationStatus(policy, root, research, summary, preparation, verified) {
  if (policy?.skip_a04 !== true) return null;
  const post = root?.analysis?.semantic_response_outcomes;
  const collected = research?.status === 'COLLECTED' && Number.isInteger(research.requests) && research.requests === research.valid;
  const complete = collected && verified && summary?.status === 'CLASSIFIED'
    && root?.analysis?.status === 'COMPLETE' && root?.full_pipeline?.status === 'COMPLETE'
    && root.analysis.a04_status === 'SKIPPED_BY_USER' && root.analysis.stage === 'PYTHON_OUTCOMES'
    && post?.path === '02_analysis/05_outcomes/summary.json' && post.schema_version === summary.schema_version
    && JSON.stringify(post.counts) === JSON.stringify(summary.scopes?.variants);
  const newerPreparation = Date.parse(preparation?.updated_at) > Date.parse(root?.analysis?.updated_at || root?.full_pipeline?.updated_at);
  return { skip_a04: true, status: complete ? 'COMPLETE' : newerPreparation && preparation.status === 'WAIT_EVALUATION_AND_TRANSFER' ? 'WAIT_EVALUATION_AND_TRANSFER' : collected ? 'WAIT_PYTHON_OUTCOMES' : 'WAIT_A03',
    a03_collected: collected, outcomes_status: summary?.status || 'NOT_PREPARED', outcomes_verified: verified,
    outcomes_total: summary?.scopes?.all?.total ?? null, preparation_status: preparation?.status || null,
    previous_analysis_status: root?.analysis?.status || null, a04_status: 'SKIPPED_BY_USER',
    explanation: 'A04는 사용자 지시로 생략합니다. A03 수집 완료와 Python 응답 분류의 실제 완료 기록을 함께 확인합니다. 처리 완료는 의미적 정답 보증이 아닙니다.' };
}
export async function readFinalization(root, state, research) {
  async function read(file) { try { return JSON.parse(await fs.readFile(path.join(root, file), 'utf8')); } catch (e) { if (e.code === 'ENOENT') return null; throw e; } }
  const policy = await read(FINALIZATION_FILES[0]);
  if (policy?.skip_a04 !== true) return null;
  const [preparation, summary] = await Promise.all([read(FINALIZATION_FILES[1]), read(FINALIZATION_FILES[2])]);
  let verified = false;
  if (summary?.run === path.basename(root) && summary?.output_hashes?.['responses.jsonl']) {
    try { const bytes = await fs.readFile(path.join(root, FINALIZATION_FILES[3])); verified = createHash('sha256').update(bytes).digest('hex') === summary.output_hashes['responses.jsonl']; }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
  return finalizationStatus(policy, state, research, summary, preparation, verified);
}
