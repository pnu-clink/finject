"""Freeze the first automatically passed originals and their eligible variants."""
from collections import Counter
from pathlib import Path

digest = __import__('finarch.experiments.90-operations.storage', fromlist=['digest']).digest
file_hash = __import__('finarch.experiments.90-operations.storage', fromlist=['file_hash']).file_hash
path_in = __import__('finarch.experiments.90-operations.storage', fromlist=['path_in']).path_in
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
provenance = __import__('finarch.dataset.03-release.edit_provenance', fromlist=['*'])
export_policy = __import__('finarch.dataset.03-release.export_policy', fromlist=['*'])

LABELS = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY',
          'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
RESULT_FILES = ('01-ic-value-before.json', '02-ic-value-after.json',
                '03-ic-source-type-1.json', '04-ic-source-type-2.json',
                '05-ic-relation.json', '06-ea-earlier-input.json', '07-ea-later-input.json')
REJECTED = {'REJECTED', 'REJECT', 'EXCLUDED', 'EXCLUDE', 'GOLD_MISMATCH'}


def rejected(row):
    return any(str(row.get(k, '')).upper() in REJECTED
               for k in ('status', 'decision', 'human_decision', 'disposition'))


def qc(row):
    result = {k: row[k] for k in ('question', 'context')}
    if not all(isinstance(v, str) and v.strip() for v in result.values()):
        raise ValueError('EMPTY_OR_INVALID_QUESTION_CONTEXT')
    return result


def public_input(row, precision):
    """Complete solver inputs at dataset handoff, before splitting evaluation data."""
    if type(precision) is not int or not 0 <= precision <= 100:
        raise ValueError('INVALID_PUBLIC_DECIMAL_PLACES')
    return {**qc(row), 'answer_format': {'decimal_places': precision}}


def collected_results(source, results_path=None):
    root = Path(results_path).resolve() if results_path is not None else source / 'results'
    manifest = root / 'manifest.json'
    if not manifest.exists():
        if results_path is not None:
            raise ValueError('PREPARED_RESULTS_MANIFEST_MISSING')
        return None
    if results_path is not None:
        delivery = read(root / 'prepared-results.json')
        project = __import__('finarch.experiments.90-operations.storage', fromlist=['PROJECT']).PROJECT
        recorded_source = (project / delivery['source_run']).resolve()
        if delivery.get('kind') != 'PREPARED_GENERATION_RESULTS' or recorded_source != source.resolve():
            raise ValueError('PREPARED_RESULTS_SOURCE_MISMATCH')
        if (file_hash(manifest) != delivery['source_manifest_sha256'] or
                file_hash(source / 'results/manifest.json') != delivery['source_manifest_sha256']):
            raise ValueError('PREPARED_RESULTS_SOURCE_CHANGED')
        copied = delivery['copied_files']
        required = {'00-input.json', *RESULT_FILES, 'manifest.json', 'export-log.json', 'SOURCE-README.md'}
        if not required <= set(copied):
            raise ValueError('PREPARED_RESULTS_SNAPSHOT_INCOMPLETE')
        for name, expected in copied.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or file_hash(path) != expected:
                raise ValueError('PREPARED_RESULTS_FILE_CHANGED:' + name)
    definition = read(manifest)
    if definition.get('source_run') != source.name:
        raise ValueError('RESULTS_RUN_MISMATCH')
    if (definition.get('source_report_sha256') and
            file_hash(source / '02-generation/result-report.json') != definition['source_report_sha256']):
        raise ValueError('RESULTS_SOURCE_REPORT_CHANGED')
    files = definition['files']
    for filename in ('00-input.json', *RESULT_FILES):
        if file_hash(root / filename) != files[filename]['sha256']:
            raise ValueError('RESULTS_FILE_HASH_MISMATCH:' + filename)
    originals = read(root / '00-input.json')
    if len(originals) != definition['selected_count']:
        raise ValueError('RESULTS_INPUT_COUNT_MISMATCH')
    original_ids = [row['id'] for row in originals]
    if len(set(original_ids)) != len(original_ids):
        raise ValueError('RESULTS_DUPLICATE_INPUT')
    variants = {}
    for label, filename in zip(LABELS, RESULT_FILES):
        rows = read(root / filename)
        sparse = definition.get('selection_policy') == export_policy.POLICY
        if not export_policy.aligned_ids(rows, original_ids, sparse=sparse) or any(row['type'] != label for row in rows):
            raise ValueError('RESULTS_TYPE_ALIGNMENT_MISMATCH:' + label)
        if sparse:
            omitted = set(original_ids) - {row['id'] for row in rows}
            declared = {entry['case'] for entry in definition.get('exclusions', [])
                        if entry.get('scope') == 'variant' and entry.get('variant') == label
                        and entry.get('decision') in export_policy.REJECTED}
            if omitted != declared:
                raise ValueError('RESULTS_REJECTION_EXCLUSIONS_MISMATCH:' + label)
            if files[filename].get('count') != len(rows):
                raise ValueError('RESULTS_VARIANT_COUNT_MISMATCH:' + label)
        variants[label] = {row['id']: row for row in rows}
    return [row['input'] for row in originals], variants, manifest, {row['id']: row for row in originals}


def select(settings):
    if settings.get('generated_path'):
        return __import__('finarch.experiments.00-input.generated', fromlist=['select']).select(settings)
    if settings.get('require_generated'):
        raise ValueError('GENERATED_DATASET_REQUIRED')
    source = Path(settings['source_run']).resolve()
    input_path = Path(settings['input_path']).resolve()
    collected = collected_results(source, settings.get('results_path'))
    if settings.get('require_collected_results') and not collected:
        raise ValueError('CONSOLIDATED_RESULTS_REQUIRED')
    if settings.get('require_external_knowledge') and not collected:
        raise ValueError('EXTERNAL_KNOWLEDGE_REQUIRES_CONSOLIDATED_RESULTS')
    originals = collected[0] if collected else read(input_path)
    if not isinstance(originals, list):
        raise ValueError('INPUT_MUST_BE_A_LIST')
    prep = {r['input_id']: r for r in read(source / '01-preparation/summary.json')['results']}
    latest = read(source / '02-generation/summary.json')['latest']
    selected, excluded, public, private, items = [], [], [], [], []
    seen = set()
    explicit = set(settings.get('excluded_ids', []))
    knowledge_counts = Counter()
    for original in originals:
        case = original['id']
        if case in seen:
            raise ValueError('DUPLICATE_ORIGINAL_ID')
        seen.add(case)
        if len(selected) == settings['count']:
            break
        report = read(path_in(source, f'01-preparation/{case}/run.json'), prep.get(case, {}))
        prep_folder = source / '01-preparation' / case
        if report.get('active_round'):
            prep_folder /= report['active_round']
        prep_human = export_policy.review(prep_folder, 'preparation')[0]
        if collected and collected[3][case]['status'] != report.get('status', 'NOT_RUN'):
            raise ValueError(f'RESULTS_PREPARATION_STATUS_CHANGED:{case}')
        reason = ('EXPLICIT_EXCLUSION' if case in explicit else
                  'HUMAN_REJECTED_OR_EXCLUDED' if rejected(prep_human) or (
                      not export_policy.decision(prep_human) and rejected(report)) else
                  'PREPARATION_NOT_PASS' if report.get('status') != 'PASS' else None)
        if reason:
            excluded.append({'case': case, 'scope': 'original', 'reason': reason})
            continue
        variants = {v['label']: v for v in latest.get(case, {}).values()}
        if collected:
            for label in LABELS:
                saved = collected[1][label].get(case)
                current = variants.get(label, {})
                if saved is None:
                    folder = path_in(source, current['path']) if current.get('path') else None
                    state = read(folder / 'run.json', {}) if folder else {}
                    human = export_policy.review(folder, 'generation')[0] if folder else {}
                    if export_policy.current_decision(state, human) not in export_policy.REJECTED:
                        raise ValueError(f'RESULTS_REJECTION_STATUS_CHANGED:{case}:{label}')
                    continue
                if (saved['status'] != current.get('status', 'NOT_RUN') or
                        saved['result'] != current.get('path')):
                    raise ValueError(f'RESULTS_GENERATION_STATUS_CHANGED:{case}:{label}')
            variants = {label: {'label': label, 'status': collected[1][label][case]['status'],
                                'path': collected[1][label][case]['result'],
                                'reason': collected[1][label][case].get('reason')}
                        for label in LABELS if case in collected[1][label]}
        for label, variant in list(variants.items()):
            if not variant.get('path'):
                continue
            folder = path_in(source, variant['path'])
            actual = read(folder / 'run.json', {})
            human = export_policy.review(folder, 'generation')[0]
            if export_policy.current_decision(actual, human) in export_policy.REJECTED:
                excluded.append({'case': case, 'scope': 'variant', 'variant': label,
                                 'reason': 'EXPLICIT_REJECTION'})
                del variants[label]
        if settings.get('require_all_variants_pass'):
            incomplete = [label for label in LABELS if variants.get(label, {}).get('status') != 'PASS']
            if incomplete:
                excluded.append({'case': case, 'scope': 'original',
                                 'reason': 'INCOMPLETE_SEVEN_VARIANT_SET', 'variants': incomplete})
                continue
        reference = {k: original[k] for k in ('reference_answer', 'reference_answer_type', 'reference_precision')}
        knowledge = collected[3][case].get('external_knowledge') if collected else None
        if settings.get('require_external_knowledge'):
            if not isinstance(knowledge, dict) or type(knowledge.get('used')) is not bool:
                raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_MISSING:' + case)
            types = knowledge.get('used_types')
            if (not isinstance(types, list) or any(t not in ('EXTERNAL_RULE', 'EXTERNAL_DATA') for t in types)
                    or bool(types) != knowledge['used']):
                raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_INVALID:' + case)
            knowledge_counts['verified_use' if knowledge['used'] else 'criteria_not_met'] += 1
        knowledge_fields = ({'original_external_knowledge': knowledge,
                             'external_knowledge_scope': 'Original production dependency; not revalidated for edited variants.'}
                            if settings.get('require_external_knowledge') else {})
        selected.append(case)
        original_id = digest({'source': str(source), 'case': case, 'variant': 'ORIGINAL'})[:24]
        public.append({'item_id': original_id, **public_input(original, original['reference_precision'])})
        items.append({'item_id': original_id, 'case': case, 'experiment': 1, 'variant': 'ORIGINAL'})
        private.append({'item_id': original_id, 'case': case, 'experiment': 1,
                        'variant': 'ORIGINAL', 'reference': reference,
                        **knowledge_fields,
                        'answer_metadata': original.get('answer_metadata', {}),
                        'source': str(collected[2]) if collected else str(input_path),
                        'human_decision': export_policy.current_decision(report, prep_human) or 'UNKNOWN',
                        'edit_provenance': provenance.checked(collected[3][case].get('edit_provenance'),
                            case, 'ORIGINAL', original, original) if collected else
                            provenance.build(case, 'ORIGINAL', original, original)})
        accepted = {}
        for label in LABELS:
            v = variants.get(label, {})
            if v.get('status') != 'PASS':
                excluded.append({'case': case, 'scope': 'variant', 'variant': label,
                                 'reason': v.get('reason') or 'GENERATION_NOT_PASS',
                                 'status': v.get('status', 'MISSING')})
                continue
            folder = path_in(source, v['path'])
            actual = read(folder / 'run.json', {})
            audit = read(folder / '03-validation/03-result.json', {})
            human = export_policy.review(folder, 'generation')[0]
            legacy_human = read(folder / '05-human-review/01-result.json', {})
            current_rejection = export_policy.current_decision(actual, human) in export_policy.REJECTED
            if current_rejection or rejected(audit) or (not export_policy.decision(human) and rejected(legacy_human)):
                excluded.append({'case': case, 'scope': 'variant', 'variant': label, 'reason': 'EXPLICIT_REJECTION'})
                continue
            if actual.get('status') != 'PASS' or audit.get('status') != 'PASS':
                raise ValueError(f'PASS_ARTIFACT_DISAGREEMENT:{case}:{label}')
            collected_row = collected[1][label][case] if collected else None
            if collected_row and (collected_row['status'] != 'PASS' or
                                  collected_row['result'] != str(v['path'])):
                raise ValueError(f'RESULTS_SOURCE_DISAGREEMENT:{case}:{label}')
            observation = qc(collected_row) if collected_row else read(folder / '02-generate-text/04-observation.json')
            comparison = read(folder / '03-validation/04-comparison.json')
            if qc(observation) != qc(comparison['working']):
                raise ValueError(f'OBSERVATION_COMPARISON_MISMATCH:{case}:{label}')
            if audit.get('observation_sha256'):
                import hashlib
                import json
                generated_hash = hashlib.sha256(json.dumps(observation, ensure_ascii=False, sort_keys=True,
                                                           separators=(',', ':')).encode()).hexdigest()
                if generated_hash != audit['observation_sha256']:
                    raise ValueError(f'AUDIT_OBSERVATION_HASH_MISMATCH:{case}:{label}')
            item_id = digest({'source': str(source), 'case': case, 'variant': label})[:24]
            public.append({'item_id': item_id, **public_input(observation, original['reference_precision'])})
            items.append({'item_id': item_id, 'case': case, 'experiment': 2, 'variant': label})
            plan = actual.get('plan', {})
            entry = {'item_id': item_id, 'case': case, 'experiment': 2, 'variant': label,
                     'reference': reference, 'source': str(folder),
                     **knowledge_fields,
                     'original_item_id': original_id,
                     'human_decision': export_policy.current_decision(actual, human) or audit.get('human_decision', 'UNKNOWN'),
                     'alternative_answer': plan.get('execution', {}).get('exact_value'),
                     'value_pair': plan.get('intent', {}).get('value_pair'),
                     'value_dependency': comparison.get('value_dependency'),
                     'patches': comparison.get('patches', []),
                     'baseline_qc_matches_generation_reference': qc(original) == qc(comparison['reference']),
                     'semantic_answerability': 'NOT_ESTABLISHED',
                     'automatic_validation_scope': audit.get('scope'),
                     'source_hashes': {f: file_hash(folder / f) for f in
                        ('run.json', '02-generate-text/04-observation.json', '03-validation/03-result.json')}}
            entry['edit_provenance'] = (provenance.checked(collected_row.get('edit_provenance'),
                case, label, original, observation) if collected_row else provenance.from_file(
                    source, case, label, original, observation, folder / '03-validation/04-comparison.json'))
            private.append(entry)
            accepted[label] = entry
        for entry in accepted.values():
            if entry['variant'].startswith('IC_SOURCE'):
                matches = [v['item_id'] for k, v in accepted.items() if k.startswith('IC_VALUE')
                           and v['patches'] == entry['value_dependency']]
                entry['matched_value_parent_ids'] = matches
        if settings.get('require_all_variants_pass') and len(accepted) != len(LABELS):
            raise ValueError(f'COMPLETE_COHORT_REJECTED_ARTIFACT:{case}')
    if len(selected) != settings['count']:
        raise ValueError(f'INSUFFICIENT_ELIGIBLE_ORIGINALS:{len(selected)}')
    return public, private, {'case_ids': selected, 'items': items, 'originals': len(selected),
        'variants': len(public) - len(selected), 'variant_counts': dict(Counter(p['variant'] for p in items if p['experiment'] == 2)),
        'original_external_knowledge_counts': dict(knowledge_counts),
        'original_external_knowledge_source_sha256': file_hash(source / 'results/00-input.json') if settings.get('require_external_knowledge') else None,
        'exclusions': excluded, 'policy': ('ALL_SEVEN_PASS_IN_INPUT_ORDER' if settings.get('require_all_variants_pass')
                                         else 'FIRST_AUTOMATIC_PASS_IN_INPUT_ORDER'),
        'input_sha256': file_hash(collected[2]) if collected else file_hash(input_path),
        'preparation_summary_sha256': file_hash(source / '01-preparation/summary.json'),
        'generation_summary_sha256': file_hash(source / '02-generation/summary.json')}
