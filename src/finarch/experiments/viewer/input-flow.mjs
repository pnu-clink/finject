import { promises as fs } from 'node:fs';
import path from 'node:path';
import { projectDirectory } from './paths.mjs';
import { artifactPaths, safePath } from './repository.mjs';

// These filenames are the collected-results contract in 00-input/dataset.py.
const DELIVERY_FILES = [
  ['ORIGINAL', '00-input.json'], ['IC_VALUE_01_BEFORE', '01-ic-value-before.json'],
  ['IC_VALUE_01_AFTER', '02-ic-value-after.json'], ['IC_SOURCE_A_ONLY', '03-ic-source-type-1.json'],
  ['IC_SOURCE_B_ONLY', '04-ic-source-type-2.json'], ['IC_RELATION_01', '05-ic-relation.json'],
  ['EA_01', '06-ea-earlier-input.json'], ['EA_02', '07-ea-later-input.json']
];

// [EV19.1] Describe saved provenance; never read arbitrary upstream source files.
export async function inputFlow(repository, snap) {
  const paths = artifactPaths(snap.config), dataset = snap.config.dataset ?? {};
  const recorded = (value, label) => value ? { label, path: value, absolute_path: path.isAbsolute(value) ? value : path.resolve(projectDirectory, value), status: 'RECORDED', relative_base: path.isAbsolute(value) ? null : projectDirectory } : null;
  async function local(relative, label) {
    try {
      const file = await repository.register(snap, relative, label);
      return { label, path: relative, absolute_path: path.resolve(snap.root, relative), status: file ? 'AVAILABLE' : 'MISSING', id: file?.id };
    } catch { return { label, path: relative, absolute_path: path.resolve(snap.root, relative), status: 'UNAVAILABLE' }; }
  }
  const sources = [...snap.privateItems.values()].map(item => ({ case: item.case, variant: item.variant,
    source: recorded(item.source, item.variant === 'ORIGINAL' ? '원본 데이터' : '변형 제작 원기록'),
    files: Object.keys(item.source_hashes ?? {}).map(file => recorded(path.join(item.source ?? '', file), file)) }));
  const savedManifest = sources.find(item => item.variant === 'ORIGINAL' && /[/\\]results[/\\]manifest\.json$/.test(item.source?.path ?? ''))?.source;
  const deliveryManifest = savedManifest ? { ...savedManifest, label: 'private에 기록된 데이터셋 전달 목록' }
    : dataset.require_collected_results && dataset.source_run ? recorded(path.join(dataset.source_run, 'results/manifest.json'), '설정에 기록된 데이터셋 전달 목록') : null;
  const deliveryFiles = deliveryManifest ? DELIVERY_FILES.map(([variant, filename]) => ({ variant,
    ...recorded(path.join(path.dirname(deliveryManifest.path), filename), filename), status: 'CONTRACT_PATH' })) : [];
  for (const item of sources) {
    if (item.source?.path === savedManifest?.path && savedManifest) item.source.label = 'private에 기록된 데이터셋 전달 목록';
    item.input_file = deliveryFiles.find(file => file.variant === item.variant) ?? null;
  }
  const reuse = recorded(dataset.reuse_input_run, '입력을 복사한 이전 회차');
  const reusedInputs = [];
  if (reuse) {
    const id = path.basename(reuse.path);
    const allowed = [path.resolve(repository.root, id), path.join(await fs.realpath(repository.root), id)];
    if (/^\d{8}-exp-\d{3,}(?:-\d{8})?$/.test(id) && allowed.includes(path.resolve(reuse.absolute_path))) {
      try {
        const root = await repository.runPath(id), raw = JSON.parse(await fs.readFile(await safePath(root, 'config.json'), 'utf8'));
        const layout = artifactPaths(raw.evaluation ? { ...raw.evaluation, layout_version: raw.layout_version } : raw);
        for (const name of ['public.jsonl', 'private.jsonl']) {
          const relative = `${layout.input}/${name}`;
          let status = 'MISSING';
          try { status = (await fs.stat(await safePath(root, relative))).isFile() ? 'AVAILABLE' : 'MISSING'; } catch { /* Preserve a missing or unreadable dependency. */ }
          reusedInputs.push({ label: `복사 원본 ${name}`, path: path.join(reuse.path, relative), absolute_path: path.join(root, relative), status });
        }
      } catch { /* The recorded origin remains visible even when unavailable. */ }
    }
  }
  const definition = paths.modern ? '01_evaluation/02_request' : '00-definition';
  const contracts = [];
  for (const [label, names] of [
    ['공통 지시', ['common.md']], ['Unguided Solving 지시', ['prompt-unguided.md', 'p0-standard.md']],
    ['Criteria-Guided Solving 지시', ['prompt-guided.md', 'p1-abstention-aware.md']], ['응답 JSON 형식', ['response.schema.json']]
  ]) {
    let entry;
    for (const name of names) { const candidate = await local(`${definition}/${name}`, label); entry ??= candidate; if (candidate.status === 'AVAILABLE') { entry = candidate; break; } }
    contracts.push(entry);
  }
  const models = await Promise.all(snap.config.models.map(async model => {
    const rows = snap.rows.filter(row => row.model === model.key), call = rows.find(row => row.call_path), result = rows.find(row => row.result_path);
    return { model: model.key, transport: model.transport ?? null,
      manifest: await local(paths.request(model.key), '모델별 요청 목록'), requests: snap.selection?.requests_by_model?.[model.key] ?? null,
      input_fields: snap.selection?.input_fields_by_model?.[model.key] ?? [],
      call: call ? await local(call.call_path, '실제 호출 기록 예시') : null,
      result: result ? await local(result.result_path, '반환 검사 기록 예시') : null,
      results: await local(`${paths.results(model.key)}/results.jsonl`, '반환 결과 목록') };
  }));
  return { run: snap.id, run_root: snap.root, mode: reuse ? 'REUSED_INPUT' : deliveryManifest ? 'COLLECTED_RESULTS' : 'SAVED_SOURCES',
    dataset_run: recorded(dataset.source_run, '데이터셋 제작 실행'), prepared_input: recorded(dataset.input_path, '설정에 기록된 준비 입력'),
    delivery_manifest: deliveryManifest, delivery_files: deliveryFiles,
    reuse, reused_inputs: reusedInputs, sources, contracts, definition_source: recorded(snap.config.definition_source_run, '요청 정의를 가져온 회차'),
    public: await local(`${paths.input}/public.jsonl`, '모델용 문제 데이터'), private: await local(`${paths.input}/private.jsonl`, '평가자용 정답·출처'),
    events: await local('events.jsonl', '선정·실행 이력'), config: await local('config.json', '실행 설정'), models,
    public_fields: [...new Set([...snap.publicItems.values()].flatMap(item => Object.keys(item)))].sort(),
    public_count: snap.publicItems.size, private_count: snap.privateItems.size };
}
