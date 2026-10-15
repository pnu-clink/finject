"""Select solver inputs from a portable generated archive without opening production paths."""
import hashlib
import json
from collections import Counter
from importlib import import_module
from pathlib import Path

store = import_module('finarch.experiments.90-operations.storage')
contract = import_module('finarch.dataset.03-release.publication.schema')
legacy = import_module('finarch.experiments.00-input.dataset')
REJECTED = legacy.REJECTED


def load(folder):
    folder = Path(folder).resolve()
    manifest = store.read(folder / 'manifest.json')
    if not manifest or manifest.get('format') != contract.FORMAT:
        raise ValueError('GENERATED_FORMAT_REQUIRED')
    raw = (folder / 'dataset.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files']['dataset.jsonl']['sha256']:
        raise ValueError('GENERATED_DATA_HASH_MISMATCH')
    records = [contract.DatasetCase.model_validate_json(line).model_dump()
               for line in raw.splitlines() if line.strip()]
    if len(records) != manifest['counts']['cases']:
        raise ValueError('GENERATED_COUNT_MISMATCH')
    ids = set()
    for row in records:
        if row['run'] != manifest['source_run'] or row['id'] in ids:
            raise ValueError('GENERATED_CASE_ID_MISMATCH')
        ids.add(row['id'])
        eligible = all(item['automatic_validation']['status'] == 'PASS' and
                       item['production_review'].get('decision') not in REJECTED
                       for item in [row['original'], *row['variants']])
        if row['production_selection']['eligible'] != eligible:
            raise ValueError('GENERATED_SELECTION_STATE_MISMATCH:' + row['id'])
    return records, manifest


def select(settings):
    if any(settings.get(k) for k in ('source_run', 'results_path', 'input_path', 'reuse_input_run')):
        raise ValueError('GENERATED_INPUT_CANNOT_MIX_LEGACY_PATHS')
    folder = (store.PROJECT / settings['generated_path']).resolve()
    records, manifest = load(folder)
    public, private, items, selected, excluded, gaps = [], [], [], [], [], []
    knowledge_counts = Counter()
    count = settings['count']
    if type(count) is not int or count < 1:
        raise ValueError('POSITIVE_COUNT_REQUIRED')
    for row in records:
        if len(selected) == count:
            break
        case, original = row['id'], row['original']
        candidates = [original, *row['variants']]
        # Annotation adjudication is not implicit in production PASS or reviewer agreement.
        if any(item['annotation']['ratings'] for item in candidates):
            raise ValueError('ANNOTATION_SELECTION_POLICY_REQUIRED:' + case)
        def reason(item):
            if item['production_review'].get('decision') in REJECTED:
                return 'EXPLICIT_REJECTION'
            if item['automatic_validation']['status'] != 'PASS':
                return 'AUTOMATIC_NOT_PASS'
            return None
        why = ('EXPLICIT_EXCLUSION' if case in settings.get('excluded_ids', []) else reason(original))
        incomplete = [item['type'] for item in row['variants'] if reason(item)]
        if not why and settings.get('require_all_variants_pass') and incomplete:
            why = 'INCOMPLETE_SEVEN_VARIANT_SET'
        if why:
            excluded.append({'case': case, 'scope': 'original', 'reason': why, 'variants': incomplete})
            continue
        meta = original['metadata']
        reference = {k: meta[k] for k in ('reference_answer', 'reference_answer_type', 'reference_precision')}
        knowledge = meta.get('external_knowledge')
        knowledge_fields = {}
        if settings.get('require_external_knowledge'):
            if (not isinstance(knowledge, dict) or type(knowledge.get('used')) is not bool or
                    not isinstance(knowledge.get('used_types'), list) or
                    any(t not in ('EXTERNAL_RULE', 'EXTERNAL_DATA') for t in knowledge['used_types']) or
                    bool(knowledge['used_types']) != knowledge['used']):
                raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_INVALID:' + case)
            knowledge_counts['verified_use' if knowledge['used'] else 'criteria_not_met'] += 1
            knowledge_fields = {'original_external_knowledge': knowledge,
                                'external_knowledge_scope': 'Original production dependency; not revalidated for edited variants.'}
        selected.append(case)
        accepted = {}
        for item in candidates:
            label, item_id = item['type'], item['item_id']
            if reason(item):
                excluded.append({'case': case, 'variant': label, 'scope': 'variant', 'reason': reason(item)})
                continue
            metadata = item['metadata']
            public.append({'item_id': item_id, **legacy.public_input(item, reference['reference_precision'])})
            identity = {'item_id': item_id, 'case': case, 'experiment': 1 if label == 'ORIGINAL' else 2, 'variant': label}
            items.append(identity)
            entry = {**identity, 'reference': reference, **knowledge_fields,
                     'answer_metadata': meta.get('answer_metadata', {}),
                     'source': str(folder / 'dataset.jsonl'), 'content_sha256': item['content_sha256'],
                     'human_decision': item['production_review'].get('decision') or 'UNKNOWN',
                     'annotation': item['annotation'], 'automatic_validation': item['automatic_validation'],
                     'production_review': item['production_review'], 'generated_metadata': metadata,
                     'edit_provenance': metadata.get('edit_provenance', {'status': 'UNAVAILABLE', 'reason': 'NOT_EXPORTED'}),
                     'semantic_answerability': 'NOT_ESTABLISHED'}
            if label != 'ORIGINAL':
                entry['original_item_id'] = original['item_id']
                required = ['baseline_qc_matches_generation_reference', 'automatic_validation_scope']
                if label.startswith('IC_'):
                    required += ['alternative_answer', 'value_pair']
                if label.startswith('IC_SOURCE'):
                    required += ['value_dependency']
                missing = [key for key in required if key not in metadata]
                for key in ('alternative_answer', 'value_pair', 'value_dependency', 'patches',
                            'baseline_qc_matches_generation_reference', 'automatic_validation_scope', 'source_hashes'):
                    if key in metadata:
                        entry[key] = metadata[key]
                if 'patches' not in entry:
                    steps = entry['edit_provenance'].get('steps', [])
                    if steps and steps[-1].get('variant') == label:
                        entry['patches'] = steps[-1].get('patches', [])
                if missing:
                    gaps.append({'item_id': item_id, 'missing': missing})
                accepted[label] = entry
            private.append(entry)
        for entry in accepted.values():
            if entry['variant'].startswith('IC_SOURCE'):
                steps = entry['edit_provenance'].get('steps', [])
                parent_steps = steps[:-1]
                matches = [v['item_id'] for label, v in accepted.items() if label.startswith('IC_VALUE') and
                           parent_steps and v['edit_provenance'].get('steps') == parent_steps]
                entry['matched_value_parent_ids'] = matches
                if not matches:
                    gaps.append({'item_id': entry['item_id'], 'missing': ['matched_value_parent_ids']})
    if len(selected) != count:
        raise ValueError(f'INSUFFICIENT_ELIGIBLE_ORIGINALS:{len(selected)}')
    return public, private, {'case_ids': selected, 'items': items, 'originals': len(selected),
        'variants': len(public) - len(selected),
        'variant_counts': dict(Counter(i['variant'] for i in items if i['experiment'] == 2)),
        'exclusions': excluded, 'policy': 'ALL_SEVEN_PASS_IN_INPUT_ORDER' if settings.get('require_all_variants_pass') else 'FIRST_AUTOMATIC_PASS_IN_INPUT_ORDER',
        'generated_format': manifest['format'], 'generated_run': manifest['source_run'],
        'generated_path': str(folder), 'input_sha256': manifest['files']['dataset.jsonl']['sha256'],
        'generated_manifest_sha256': store.file_hash(folder / 'manifest.json'),
        'original_external_knowledge_counts': dict(knowledge_counts),
        'annotation_policy': 'UNREVIEWED_ALLOWED_ANNOTATED_REQUIRES_EXPLICIT_POLICY',
        'analysis_metadata_status': 'INCOMPLETE' if gaps else 'COMPLETE', 'analysis_metadata_gaps': gaps}
