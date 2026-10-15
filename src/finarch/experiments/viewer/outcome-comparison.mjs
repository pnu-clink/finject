import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { readSemanticOutcomeData, outcomePage } from './semantic-outcomes.mjs';
import { readFinalization } from './finalization.mjs';
export const comparisonRuns = [
 ['TAT-QA','Luna','20261003-exp-004-tatqa-luna-sol-low'],
 ['TAT-QA','Haiku','20261003-exp-005-tatqa-haiku'],
 ['TAT-QA','Qwen3 8B','20261003-exp-012-a100-tatqa-qwen3-8b'],
 ['TAT-QA','Qwen3 14B','20261003-exp-014-a100-tatqa-qwen3-14b'],
 ['TAT-QA','Qwen3.8 27B','20261003-exp-016-a100-tatqa-qwen3-8-27b'],
 ['FR','Luna','20261003-exp-009-concat-002-luna'],
 ['FR','Haiku','20261003-exp-010-concat-002-haiku'],
 ['FR','Qwen3 8B','20261003-exp-013-a100-financereasoning-qwen3-8b'],
 ['FR','Qwen3 14B','20261003-exp-015-a100-financereasoning-qwen3-14b']
];
// Aggregate saved values only; no reclassification or model requests.
export async function readOutcomeComparison(repository, scope = 'all', cohort = 'source') {
 if (!['all','variants','originals','h1'].includes(scope)) throw Error('Unknown outcome scope');
 if(cohort === 'final') return readFinalCohort(repository, scope);
 if(cohort !== 'source') throw Error('Unknown comparison cohort');
 const results=[];
 for (const [dataset, model, run] of comparisonRuns) {
  try {
   const root=await repository.runPath(run), data=await readSemanticOutcomeData(root);
   if(data.status !== 'AVAILABLE') {results.push({dataset,model,run,status:data.status});continue;}
   const allowed=dataset==='FR'?['FinanceReasoning-native','FinanceReasoning-embedded']:['TAT-QA'];
   if(data.rows.some(r=>!allowed.includes(r.dataset))) throw Error('대상과 다른 데이터셋이 포함되어 집계를 중단했습니다.');
   const page=outcomePage(data.summary,data.rows,{scope});
   const read=async file=>JSON.parse(await fs.readFile(path.join(root,file),'utf8').catch(e=>{if(e.code==='ENOENT')return 'null';throw e;}));
   const state=await read('state.json'), research=await read('02_analysis/03_research/state.json');
   const finalization=await readFinalization(root,state,research);
   const datasets=Object.fromEntries(allowed.map(d=>[d,data.summary.groups.filter(g=>g.scope===scope && g.dataset===d).reduce((sum,g)=>sum+g.total,0)]));
   results.push({dataset,model,run,status:'AVAILABLE',analysis_status:finalization?.status || state?.analysis?.status || 'NOT_RECORDED',generated_at:data.summary.generated_at,
    total:page.total,counts:page.counts,categories:page.categories,codes:page.codes,groups:page.groups,datasets});
  }catch(e){results.push({dataset,model,run,status:'UNAVAILABLE',error:e.message});}
 }
 return {scope,results,observed_at:new Date().toISOString()};
}

// FC04.1 Read the fixed PASS snapshot; preserve missing conditions and reviews.
async function readFinalCohort(repository, scope) {
 const project=path.resolve(repository.root,'../..');
 const folder=path.join(project,'reports/analysis/20261008-finject-1354');
 const manifest=JSON.parse(await fs.readFile(path.join(folder,'manifest.json'),'utf8'));
 const content=await fs.readFile(path.join(folder,'summary.json'));
 const digest=data=>createHash('sha256').update(data).digest('hex');
 if(digest(content)!==manifest.outputs['summary.json']) throw Error('FInject 집계 파일의 해시가 달라졌습니다.');
 for(const name of ['data/final/finject-20261007/dataset.jsonl','data/final/finject-20261007-connection-table.csv']) {
  if(digest(await fs.readFile(path.join(project,name)))!==manifest.source_hashes[name]) throw Error('최종 데이터셋이 집계 시점과 달라졌습니다.');
 }
 const summary=JSON.parse(content);
 return {scope,cohort:'final',summary,observed_at:new Date().toISOString()};
}
