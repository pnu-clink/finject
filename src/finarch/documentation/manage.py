"""Preserve legacy documents and maintain the pipeline documentation index."""
import argparse
import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = (Path(__file__).resolve().parent / '../../..').resolve()
ARCHIVE = ROOT / 'archive/20260923-documentation-reorganization'
RUN = ROOT / 'reports/run/20260923-dataset-documentation'
TEMPLATES = Path(__file__).parent / 'templates'
LAYOUT = json.loads(Path(__file__).with_name('layout.json').read_text())
READMES = {
    'docs.md': 'docs/README.md', 'dataset.md': 'docs/dataset/README.md',
    'input.md': 'docs/dataset/input/README.md',
    'preparation.md': 'docs/dataset/preparation/README.md',
    'generation.md': 'docs/dataset/generation/README.md',
    'operations.md': 'docs/dataset/operations/README.md',
    'release.md': 'docs/dataset/release/README.md',
    'experiments.md': 'docs/experiments/README.md',
    'run.md': 'reports/run/20260923-dataset-documentation/README.md',
    'archive.md': 'archive/20260923-documentation-reorganization/README.md',
}
READMES = {key: LAYOUT.get(value, value) for key, value in READMES.items()}
READMES.update({
    'annotation-readme.md': 'annotation/README.md',
    'annotation-viewer-readme.md': 'viewer/dataset/annotation/README.md',
    'annotation-code-readme.md': 'src/finarch/dataset/viewer/annotation/README.md',
    'annotation-validation-readme.md': 'log/annotation-manager-20261001/README.md',
    'export-model-migration-check.md': 'reports/run/20261001-export-model-migration-check/README.md',
    'project.md': 'README.md',
    'round-input.md': 'docs/01-dataset/01-preparation/00-round-input/README.md',
    'preparation-records.md': 'docs/01-dataset/01-preparation/08-records/README.md',
    'generation-records.md': 'docs/01-dataset/02-generation/08-records/README.md',
})
READMES.update(json.loads(Path(__file__).with_name('stage-readmes.json').read_text()))
GROUPS = {
    'requirements.md': ['01', '03'],
    'README.md': ['00', '02', '12', '16', '17', '57', '58', '59', '65'],
    'input/selection.md': ['15', '29', '53'],
    'preparation/source.md': ['51'],
    'preparation/calculation.md': ['56', '63', '72', '73'],
    'preparation/graph.md': ['71'],
    'preparation/verification.md': ['54', '67', '68', '74'],
    'preparation/exception-handler.md': ['66'],
    'generation/types.md': ['05', '11', '19', '20', '32'],
    'generation/README.md': ['21'],
    'generation/generate-text.md': ['24', '27'],
    'generation/verification.md': ['23', '25'],
    'operations/execution.md': ['26', '31', '33', '34', '35', '48', '61', '64'],
    'operations/model-calls.md': ['14', '18', '22', '60', '69'],
    'operations/artifacts.md': ['28', '30', '36', '52', '70'],
    'operations/viewer.md': ['13', '49', '50', '55', '62', '75', '76', '77'],
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(action, **details):
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                 'action': action, **details}, ensure_ascii=False) + '\n')


def destination(name):
    if name.startswith(('experiments-', 'exp-viewer-')) or name == 'viewer-experiments.md':
        return LAYOUT['docs/experiments/README.md'], 'EXPERIMENT_HISTORY'
    if name.startswith('quality-improvement-'):
        return LAYOUT['docs/dataset/generation/verification.md'], 'DATASET_REQUIREMENTS_AND_HISTORY'
    if name == 'phase-result-reports.md':
        return LAYOUT['docs/dataset/operations/artifacts.md'], 'DATASET_REQUIREMENTS_AND_HISTORY'
    number = name.split('-')[0]
    for target, numbers in GROUPS.items():
        if number in numbers:
            return LAYOUT['docs/dataset/' + target], 'DATASET_REQUIREMENTS_AND_HISTORY'
    raise ValueError('UNCLASSIFIED_DOCUMENT:' + name)


def anchor(heading):
    return re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')


def source_inventory(rows):
    inventory = []
    for row in rows:
        if not row['original'].endswith('.md'):
            continue
        lines = (ROOT / row['archive']).read_text().splitlines()
        sections, requirements = [], []
        for index, line in enumerate(lines, 1):
            match = re.match(r'^(#{1,6})\s+(.+)', line)
            if match:
                sections.append({'line': index, 'level': len(match[1]),
                                 'title': match[2], 'anchor': anchor(match[2])})
            if re.search(r'사용자|확정|요구|금지|보류|미구현|철회|필수|후속 결정', line):
                requirements.append({'line': index, 'text': line})
        inventory.append({'original': row['original'], 'archive': row['archive'],
                          'destination': row['destination'], 'sections': sections,
                          'requirement_candidates': requirements,
                          'interpretation': 'Extraction is evidence, not automatic adoption.'})
    write_json(RUN / 'source-inventory.json', inventory)


def migrate():
    originals = json.loads((ARCHIVE / 'original-manifest.json').read_text())
    rows = []
    for item in originals:
        original, archived = ROOT / item['original'], ROOT / item['archive']
        if digest(archived) != item['sha256']:
            raise ValueError('ARCHIVE_HASH_MISMATCH:' + item['original'])
        target, disposition = destination(original.name)
        rows.append({**item, 'destination': target, 'disposition': disposition})
        if original.exists() and digest(original) != item['sha256']:
            raise ValueError('ORIGINAL_CHANGED:' + item['original'])
    write_json(RUN / 'migration.json', rows)
    source_inventory(rows)
    text = '# 기존 문서 이관 대응표\n\n'
    text += '원본은 바이트 그대로 보관했습니다. 새 소속은 현재 읽는 입구이며, 과거 실행 결과·대체된 정책은 보관 이력으로 남깁니다. '
    text += '혼재 문서의 여러 주제는 새 단계 문서에 분산했고, 이 표는 대표 소속을 표시합니다. 절·요구 문장별 원문 위치는 '
    text += '[취합 색인](../../reports/run/20260923-dataset-documentation/source-inventory.json)에 있습니다.\n\n'
    text += '|기존 파일 / 원본|현재 소속|처리|\n|---|---|---|\n'
    for row in rows:
        archived = Path(row['archive']).name
        target = row['destination']
        meaning = '실험 자료 보존·후속 재정리' if row['disposition'] == 'EXPERIMENT_HISTORY' else '요구·흐름 취합 / 당시 결과·변경 이력 보관'
        text += f'|[{archived}](docs/{archived})|[{target}](../../{target})|{meaning}|\n'
    (ARCHIVE / 'MIGRATION.md').write_text(text)
    for row in rows:
        (ROOT / row['original']).unlink(missing_ok=True)
    event('archive_and_route', files=len(rows), model_calls=0)


def refresh():
    for template, target in READMES.items():
        path = ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((TEMPLATES / template).read_text())
    order = sorted((ROOT / 'docs').rglob('*.md'))
    rows = []
    for old_path in order:
        old_relative = old_path.relative_to(ROOT).as_posix()
        path = ROOT / LAYOUT.get(old_relative, old_relative)
        content = path.read_text()
        title = re.search(r'^# (.+)', content, re.M).group(1)
        relative = path.relative_to(ROOT).as_posix()
        rows.append({'path': relative, 'title': title, 'sha256': digest(path),
                     'group': '/'.join(relative.split('/')[1:3]) if len(relative.split('/')) > 3 else 'overview'})
    front = ['docs/README.md', 'docs/01-dataset/README.md', 'docs/01-dataset/00-requirements.md']
    rows.sort(key=lambda row: (front.index(row['path']), '') if row['path'] in front
              else (3, row['path'].replace('/README.md', '/')))
    write_json(RUN / 'documentation.json', {'kind': 'PIPELINE_DOCUMENTATION',
        'title': '데이터셋·실험 파이프라인 · 단계별 요구사항', 'documents': rows,
        'archive_manifest': 'migration.json', 'model_calls': 0,
        'scope': 'Current dataset and experiment pipeline documentation; run results remain separately scoped.'})
    write_json(RUN / 'summary.json', {'kind': 'PIPELINE_DOCUMENTATION', 'documents': len(rows),
                                     'status': 'DOCUMENTATION_READY', 'model_calls': 0})
    migration = json.loads((RUN / 'migration.json').read_text())
    table = '# 기존 문서 이관 대응표\n\n'
    table += '원본은 바이트 그대로 보관했습니다. 대표 소속으로 현재 문서를 연결합니다. 과거 실행·대체된 요구를 모두 현재 기준으로 채택한 표가 아닙니다. '
    table += '[절·요구 문장 취합 색인](../../reports/run/20260923-dataset-documentation/source-inventory.json)과 '
    table += '[R01~R35 대응표](../../reports/run/20260923-dataset-documentation/requirements-map.json)에 상세 근거를 보존합니다.\n\n'
    table += '|기존 파일 / 원본|현재 소속|처리|\n|---|---|---|\n'
    for item in migration:
        name = Path(item['original']).name
        note = '실험 자료 보존·후속 재정리' if item['disposition'] == 'EXPERIMENT_HISTORY' else '단계별 요구·흐름 취합 / 당시 결과·대체안은 보관'
        table += f"|[{name}](docs/{name})|[{item['destination']}](../../{item['destination']})|{note}|\n"
    (ARCHIVE / 'MIGRATION.md').write_text(table)
    event('refresh_readmes_and_index', documents=len(rows), templates=len(READMES))
    refresh_experiments(rows)


def refresh_experiments(documents):
    """Keep the experiment guide, preserved sources and code map in one viewer."""
    run = ROOT / 'reports/run/20260927-experiment-documentation'
    archive = ROOT / 'archive/20260927-experiment-pipeline-reorganization'
    aliases = json.loads(Path(__file__).with_name('experiment-document-aliases.json').read_text())
    originals = json.loads((archive / 'original-manifest.json').read_text())
    migration = [{**row, 'destination': aliases.get(row['original'], row['original'])}
                 for row in originals if row['original'].startswith('docs/')]
    write_json(run / 'migration.json', migration)
    selected = [row for row in documents if row['path'].startswith('docs/02-experiments/')]
    selected.sort(key=lambda row: row['path'].replace('/README.md', '/'))
    references = set()
    for row in selected:
        doc = ROOT / row['path']
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', doc.read_text()):
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            path = (doc.parent / unquote(parsed.path)).resolve()
            if path.is_file() and path.is_relative_to(ROOT):
                references.add(path.relative_to(ROOT).as_posix())
    references.update(p.relative_to(ROOT).as_posix() for p in run.rglob('*') if p.is_file())
    write_json(run / 'documentation.json', {
        'kind': 'PIPELINE_DOCUMENTATION', 'title': '실험 · Input → Evaluation → Analysis',
        'entry_document': 'docs/02-experiments/README.md', 'documents': selected,
        'reference_files': sorted(references), 'model_calls': 0,
        'navigation': [['실험 전체', 'docs/02-experiments/README.md'],
                       ['00 Input', 'docs/02-experiments/00_input/README.md'],
                       ['01 Evaluation', 'docs/02-experiments/01_evaluation/README.md'],
                       ['02 Analysis', 'docs/02-experiments/02_analysis/README.md'],
                       ['작업 기록', 'reports/run/20260927-experiment-documentation/README.md']]})
    steps = json.loads(Path(__file__).with_name('experiment-pipeline.json').read_text())
    source_paths = {call['file'] for stage in steps for step in stage['steps'] for call in step.get('calls', [])}
    source_paths.update(path for stage in steps for path in stage.get('existing_sources', []))
    planned_sources = {path for stage in steps for path in stage.get('planned_sources', [])}
    planned_sources.update(step['planned_source'] for stage in steps for step in stage['steps']
                           if step.get('planned_source'))
    write_json(run / 'source-map.json', {'stages': steps, 'source_sha256':
        {path: digest(ROOT / path) for path in sorted(source_paths)},
        'planned_sources': sorted(planned_sources),
        'analysis_runtime_status': 'CODEX_AND_API_IMPLEMENTED', 'evaluation_source_migration': 'COMPLETE', 'model_calls': 0})
    layout = []
    for run_id in ('20260926-exp-001', '20260923-exp-009', '20260927-exp-005', '20260927-exp-006'):
        root = ROOT / 'reports/experiments-run' / run_id
        samples = sorted(root.glob('*/calls/**/attempt-001'))[:1]
        if not samples:
            samples = sorted(root.glob('01_evaluation/03_execution/*/calls/**/attempt-001'))[:1]
        layout.append({'source': root.relative_to(ROOT).as_posix(),
            'kind': 'SAVED_RUN', 'status': 'OBSERVED_ON_DISK',
            'root_entries': [p.name + ('/' if p.is_dir() else '') for p in sorted(root.iterdir())],
            'analysis_entries': [p.name for p in sorted((root / '02_analysis').iterdir())]
                                if (root / '02_analysis').is_dir() else [],
            'attempt_samples': {p.relative_to(root).as_posix(): [f.name for f in sorted(p.iterdir())] for p in samples},
            'frozen_manifest_sha256': digest(root / 'manifest.json')})
    layout.append({'source': 'docs/02-experiments/02_analysis/README.md',
        'kind': 'ANALYSIS_LAYOUT_CONTRACT', 'status': 'OBSERVED_ON_DISK',
        'stages': [stage['target_run'] for stage in steps if stage.get('target_run')],
        'note': '006 preserves its historical Evaluation reuse. Current source uses 00-input, 01-evaluation and 02-analysis with matching internal stages.'})
    write_json(run / 'run-layout-reference.json', layout)
    write_json(run / 'summary.json', {'kind': 'PIPELINE_DOCUMENTATION', 'documents': len(selected),
        'status': 'DOCUMENTATION_READY', 'analysis_runtime_status': 'CODEX_AND_API_IMPLEMENTED', 'evaluation_source_migration': 'COMPLETE',
        'analysis_entry': 'docs/02-experiments/02_analysis/README.md', 'model_calls': 0})
    with (run / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
            'action': 'REFRESH_EXPERIMENT_DOCUMENTATION', 'documents': len(selected), 'model_calls': 0}) + '\n')
    refresh_experiment_source_layout()


def refresh_experiment_source_layout():
    """Expose source navigation and the local refactor audit in the shared viewer."""
    run = ROOT / 'reports/run/20260927-experiment-source-layout'
    selected = sorted({target for target in READMES.values() if target.startswith((
        'src/finarch/experiments/', 'config/experiments/', 'reports/run/20260927-experiment-source-layout/'))})
    selected.sort(key=lambda path: (0 if path == 'src/finarch/experiments/README.md' else
        1 if path.startswith('config/') else 2 if path.startswith('src/') else 3,
        path.replace('/README.md', '/')))
    documents = [{'path': path, 'title': re.search(r'^# (.+)', (ROOT / path).read_text(), re.M)[1],
                  'sha256': digest(ROOT / path)} for path in selected]
    references = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'src/finarch/experiments').rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts}
    references.update(p.relative_to(ROOT).as_posix() for p in run.rglob('*') if p.is_file())
    references.add('config/experiments/config.toml')
    references.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'docs/02-experiments').rglob('*.md'))
    write_json(run / 'documentation.json', {
        'kind': 'PIPELINE_DOCUMENTATION', 'title': '실험 소스 구성 · Codex/API 분석 설정',
        'entry_document': 'src/finarch/experiments/README.md', 'documents': documents,
        'reference_files': sorted(references), 'model_calls': 0,
        'navigation': [['소스 전체', 'src/finarch/experiments/README.md'],
                       ['00 Input', 'src/finarch/experiments/00-input/README.md'],
                       ['01 Evaluation', 'src/finarch/experiments/01-evaluation/README.md'],
                       ['02 Analysis', 'src/finarch/experiments/02-analysis/README.md'],
                       ['config.toml', 'config/experiments/README.md'],
                       ['검사 기록', 'reports/run/20260927-experiment-source-layout/README.md']]})
    write_json(run / 'summary.json', {'kind': 'PIPELINE_DOCUMENTATION',
        'status': 'DOCUMENTATION_READY', 'documents': len(documents), 'model_calls': 0})


def validate_experiments():
    """Check actual function references and preserved documentation bytes."""
    errors = []
    archive = ROOT / 'archive/20260927-experiment-pipeline-reorganization'
    originals = json.loads((archive / 'original-manifest.json').read_text())
    structure_archive = archive / 'analysis-before-results-focus/original-manifest.json'
    if structure_archive.is_file():
        originals.extend(json.loads(structure_archive.read_text()))
    for row in originals:
        if digest(ROOT / row['archive']) != row['sha256']:
            errors.append('EXPERIMENT_ARCHIVE_HASH:' + row['archive'])
    stages = json.loads(Path(__file__).with_name('experiment-pipeline.json').read_text())
    ids = set()
    for stage in stages:
        body = (ROOT / stage['document']).read_text()
        for source in stage.get('existing_sources', []):
            if not (ROOT / source).is_file():
                errors.append('EXPERIMENT_SOURCE_MISSING:' + source)
        target = stage.get('target_run')
        if target and target.get('status') not in ('DESIGN_ONLY', 'OBSERVED_ON_DISK'):
            errors.append('EXPERIMENT_DESIGN_STATUS:' + stage['document'])
        if target and target.get('status') == 'OBSERVED_ON_DISK':
            observed = ROOT / target.get('observed_run', '') / target['path']
            for name in target['files']:
                if not (observed / name).is_file():
                    errors.append('EXPERIMENT_RECORDED_FILE_MISSING:' + str(observed / name))
        for step in stage['steps']:
            if step['id'] in ids or step['id'] not in body:
                errors.append('EXPERIMENT_STEP_ID:' + step['id'])
            ids.add(step['id'])
            if step.get('planned_source') and step.get('calls'):
                errors.append('EXPERIMENT_PLANNED_AS_EXECUTED:' + step['id'])
            for call in step.get('calls', []):
                path = ROOT / call['file']
                functions = {n.name for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                if call['function'] not in functions:
                    errors.append('EXPERIMENT_FUNCTION_MISSING:' + call['file'] + ':' + call['function'])
    return errors, len(originals), len(ids)


def validate():
    rows = json.loads((RUN / 'migration.json').read_text())
    errors, checked = [], 0
    for row in rows:
        if digest(ROOT / row['archive']) != row['sha256']:
            errors.append('ARCHIVE_HASH:' + row['archive'])
        if (ROOT / row['original']).exists():
            errors.append('OLD_DOC_REMAINS:' + row['original'])
        if not (ROOT / row['destination']).is_file():
            errors.append('DESTINATION_MISSING:' + row['destination'])
    documents = json.loads((RUN / 'documentation.json').read_text())['documents']
    current = {str(path.relative_to(ROOT)) for path in (ROOT / 'docs').rglob('*.md')}
    indexed = {doc['path'] for doc in documents}
    if current != indexed:
        errors.append('INDEX_COVERAGE:' + str(sorted(current ^ indexed)))
    files = [ROOT / doc['path'] for doc in documents]
    files.extend(ROOT / path for path in READMES.values())
    files.append(ARCHIVE / 'MIGRATION.md')
    for path in set(files):
        body = path.read_text()
        if path.is_relative_to(ROOT / 'docs'):
            for part in path.relative_to(ROOT / 'docs').parts:
                if part != 'README.md' and not re.match(r'^\d{2}[-_]', part):
                    errors.append('UNNUMBERED_DOCUMENT_PATH:' + str(path.relative_to(ROOT)))
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
            if target.startswith(('http:', 'https:', 'mailto:', '#')):
                continue
            parsed = urlsplit(target)
            if parsed.scheme:
                continue
            local = path.parent / unquote(parsed.path)
            checked += 1
            if not local.exists():
                errors.append(f'BROKEN_LINK:{path.relative_to(ROOT)}:{target}')
        for block in re.findall(r'```mermaid\n(.*?)```', body, re.S):
            if 'flowchart ' not in block:
                errors.append('DIAGRAM_HEADER:' + str(path.relative_to(ROOT)))
    for template, target in READMES.items():
        if (ROOT / target).read_bytes() != (TEMPLATES / template).read_bytes():
            errors.append('TEMPLATE_DRIFT:' + target)
    for path in (ROOT / 'docs').rglob('README.md'):
        if str(path.relative_to(ROOT)) not in READMES.values():
            errors.append('README_TEMPLATE_MISSING:' + str(path.relative_to(ROOT)))
    for doc in documents:
        if digest(ROOT / doc['path']) != doc['sha256']:
            errors.append('INDEX_HASH:' + doc['path'])
    references = json.loads((RUN / 'run-layout-reference.json').read_text())
    for reference in references:
        phase = '01-preparation' if '/01-preparation/' in reference['source'] else '02-generation'
        for stage in reference['stages']:
            doc = ROOT / 'docs/01-dataset' / phase / stage['name'] / 'README.md'
            if not doc.is_file():
                errors.append('RUN_STAGE_DOCUMENT_MISSING:' + str(doc.relative_to(ROOT)))
            elif any(name not in doc.read_text() for name in stage['substeps']):
                errors.append('RUN_SUBSTEP_DOCUMENT_MISSING:' + str(doc.relative_to(ROOT)))
    experiment_errors, experiment_archives, experiment_steps = validate_experiments()
    errors.extend(experiment_errors)
    result = {'status': 'PASS' if not errors else 'FAIL', 'archive_files': len(rows),
              'experiment_archive_files': experiment_archives, 'experiment_steps': experiment_steps,
              'current_documents': len(documents), 'checked_local_links': checked,
              'errors': sorted(set(errors)), 'model_calls': 0,
              'scope': 'File/hash/link/template/index checks; not pipeline execution or semantic dataset validation.'}
    write_json(RUN / 'validation.json', result)
    write_json(ROOT / 'reports/run/20260927-experiment-documentation/validation.json', {
        **result, 'archive_files': experiment_archives,
        'current_documents': sum(doc['path'].startswith('docs/02-experiments/') for doc in documents),
        'overall_archive_files': len(rows), 'overall_current_documents': len(documents)})
    event('validate', **result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['migrate', 'refresh', 'validate'])
    args = parser.parse_args()
    if args.action == 'migrate':
        migrate()
    elif args.action == 'refresh':
        refresh()
    elif validate()['errors']:
        raise SystemExit(1)
