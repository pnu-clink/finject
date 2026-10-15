import { outcomePage } from './semantic-outcomes-model.mjs';
import * as Model from './model.mjs';
import { groundingSummary, groundingPage } from './grounding-model.mjs';

// [EV07.1] Decode only the index and selected case; never fall back to the network.
export function createOfflineStore(bundle) {
  if (bundle.version !== 1) throw Error('지원하지 않는 실험 HTML 버전입니다.');
  const cache = new Map();
  async function chunk(id) {
    if (!Object.hasOwn(bundle.chunks, id)) throw Error('HTML에 필요한 자료가 없습니다. 다시 내보내 주세요.');
    if (!cache.has(id)) {
      const pending = (async () => {
        if (typeof DecompressionStream !== 'function') throw Error('압축 자료를 열 수 있는 최신 Chrome, Edge, Firefox 또는 Safari가 필요합니다.');
        const bytes = Uint8Array.from(atob(bundle.chunks[id]), c => c.charCodeAt(0));
        const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
        return JSON.parse(await new Response(stream).text());
      })();
      cache.set(id, pending);
      pending.catch(() => cache.delete(id));
      while (cache.size > 5) cache.delete(cache.keys().next().value);
    }
    return cache.get(id);
  }
  let snapshot;
  const index = () => snapshot ??= chunk('index');
  async function sourceFile(filePath) {
    const file = bundle.documents.find(item => item.path === filePath);
    if (!file || !Object.hasOwn(bundle.files, file.id)) throw Error('원천 유형별 저장 파일이 없습니다.');
    const saved = (await chunk(bundle.files[file.id])).files[file.id];
    if (saved.error) throw Error(saved.error);
    return JSON.parse(saved.content);
  }
  async function sourceCases(sourceType, runId) {
    const sourceIndex = await sourceFile('02_analysis/source-types/source-type-index.json');
    if (sourceIndex.run !== runId || !Array.isArray(sourceIndex.types)) throw Error('원천 유형 색인이 실행과 일치하지 않습니다.');
    const item = sourceIndex.types.find(entry => entry.source_type === sourceType);
    if (!item || !['FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning'].includes(sourceType)) throw Error('원천 유형 선택값이 올바르지 않습니다.');
    const summary = await sourceFile(`${item.folder}/summary.json`);
    const ids = summary.case_ids;
    if (summary.source_type !== sourceType || !Array.isArray(ids) || ids.length !== item.case_count || new Set(ids).size !== ids.length) throw Error('원천 유형 문항 목록이 색인과 일치하지 않습니다.');
    return { source_type: sourceType, case_count: ids.length, caseIds: ids };
  }
  async function request(address) {
    const url = new URL(address, 'https://offline.invalid'), snap = await index();
    if (url.pathname === '/api/runs') return { runs: [bundle.run] };
    const match = url.pathname.match(/^\/api\/runs\/([^/]+)\/(overview|analysis-pairs|rq-pairs|rq1-materials|grounding-pairs|semantic-outcomes|rq-source-summaries|case|input-flow|documents|file|activity|export)$/);
    if (!match || decodeURIComponent(match[1]) !== bundle.run.id) throw Error('이 HTML에는 선택한 회차만 들어 있습니다.');
    const filters = Object.fromEntries(url.searchParams);
    switch (match[2]) {
      case 'overview': return Model.overview(snap, filters);
      case 'rq1-materials': return snap.rq1Materials ?? { status: 'NOT_PREPARED', run_id: snap.id, groups: [], inverse_reconstruction: { status: 'TBD', result: null } };
      case 'semantic-outcomes': {
        const data = Object.hasOwn(bundle.chunks, 'semantic-outcomes') ? await chunk('semantic-outcomes') : { status: 'NOT_PREPARED' };
        return data.status === 'AVAILABLE' ? outcomePage(data.summary, data.rows, filters) : data;
      }
      case 'grounding-pairs': {
        if (filters.mode && !['summary', 'pairs'].includes(filters.mode)) throw Error('알 수 없는 근거 타당성 조회입니다.');
        const data = Object.hasOwn(bundle.chunks, 'grounding-pairs') ? await chunk('grounding-pairs')
          : { metadata: { run_id: snap.id, status: 'NOT_PREPARED', assessments_available: false }, pairs: [] };
        return filters.mode === 'pairs' ? groundingPage(data, filters) : groundingSummary(data, filters);
      }
      case 'analysis-pairs': {
        const index = Number(filters.group), offset = Number(filters.offset ?? 0);
        if (!Number.isSafeInteger(index) || index < 0 || !Number.isSafeInteger(offset) || offset < 0) throw Error('대응 쌍 위치가 올바르지 않습니다.');
        const group = snap.resultsAnalysis?.comparisons?.paired_groups?.[index];
        if (!group) throw Error('저장된 대응 쌍이 없습니다.');
        const pairs = group.pairs || [], pageSize = 50;
        return { group: index, axis: group.axis, total: pairs.length, offset: Math.min(offset, pairs.length), page_size: pageSize,
          pairs: pairs.slice(offset, offset + pageSize) };
      }
      case 'rq-pairs': {
        const source = filters.source_type ? await sourceCases(filters.source_type, snap.id) : null;
        return Model.rqAnswerPage(snap.resultsAnalysis, { ...filters, caseIds: source?.caseIds });
      }
      case 'rq-source-summaries': {
        const sourceIndex = await sourceFile('02_analysis/source-types/source-type-index.json');
        const types = [];
        for (const item of sourceIndex.types) {
          const source = await sourceCases(item.source_type, snap.id);
          types.push({ source_type: source.source_type, case_count: source.case_count,
            rq_answers: Model.rqAnswerOverview(snap.resultsAnalysis, { caseIds: source.caseIds }) });
        }
        return { types };
      }
      case 'input-flow': return snap.inputFlow ?? null;
      case 'case': {
        if (!Object.hasOwn(bundle.cases, filters.case)) throw Error('이 실행에 없는 문항입니다.');
        const data = await chunk(bundle.cases[filters.case]);
        const local = { ...snap, rows: snap.rows.filter(r => r.case === filters.case), publicItems: new Map(data.publicItems), privateItems: new Map(data.privateItems) };
        const selection = Model.selectCase(local, filters.case, filters);
        const responses = selection.rows.map(({ model, row }) => row ? data.responses[`${model}:${row.trial_id}`] : { model, status: 'NOT_PLANNED', missing: true });
        if (responses.some(r => !r)) throw Error('HTML에 응답 기록이 누락되었습니다. 다시 내보내 주세요.');
        return Model.assembleCase(local, selection, responses, Model.conditionTimings(Model.caseConditionRows(local, selection), data.responses), data.responses);
      }
      case 'documents': return { files: bundle.documents };
      case 'file': {
        if (!Object.hasOwn(bundle.files, filters.id)) throw Error('이 HTML에 포함된 파일이 아닙니다.');
        const data = (await chunk(bundle.files[filters.id])).files[filters.id];
        if (data.error) throw Error(data.error);
        return data;
      }
      case 'activity': return (await chunk('activity')).activity;
      case 'export': return Model.exportMarkdown(snap, filters);
    }
  }
  return { request, run: bundle.run.id, exportedAt: bundle.exported_at, stats: bundle.stats, initialView: bundle.initial_view ?? {} };
}
