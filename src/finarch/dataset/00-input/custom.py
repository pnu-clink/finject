"""Build a canonical input bundle from a local, deterministic reviewer adapter."""
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
from types import ModuleType

from finarch.dataset.schemas.custom_input import IntermediateSample
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate
from finarch.dataset.shared.adapter import RawSource, ConvertedRecord, ExcludedRecord, Origin

SCHEMA = '01-preparation.01-source.custom-input'
build = import_module('finarch.dataset.00-input.build')
NUMBER = import_module('finarch.dataset.00-input.content').NUMBER


def content_fields(text, index):
    """Map the normalized context, without pretending it is a raw source field."""
    location = {'id': 'paragraph-0', 'text': text,
                'source_pointer': '/c', 'context_span': [0, len(text)]}
    numbers = [{'text': m.group(), 'source_text_span': [m.start(), m.end()],
                'context_span': [m.start(), m.end()]} for m in NUMBER.finditer(text)]
    return {'context': text, 'source_content': {'paragraphs': [location], 'tables': []},
            'context_mapping': {'offset_unit': 'Unicode code points', 'interval': '[start, end)',
                'source_root': f'intermediate.json#/{index}',
                'segments': [{**location, 'numbers': numbers}],
                'number_status': 'lexical candidates only; meaning and units not validated'}}


def prepare(adapter_path, input_paths, output, *, name):
    adapter_path, output = Path(adapter_path).resolve(), Path(output).resolve()
    paths = [Path(path).resolve() for path in input_paths]
    if not paths or len(paths) != len(set(paths)):
        raise ValueError('SUPPLY_DISTINCT_INPUT_FILES')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('DATASET_NAME_REQUIRED')
    # Never replace source data, the adapter or an existing output directory.
    if any(path == output or path.is_relative_to(output) for path in [adapter_path, *paths]):
        raise ValueError('OUTPUT_MUST_NOT_CONTAIN_INPUT_FILES')
    adapter_bytes = adapter_path.read_bytes()
    sources = [RawSource(f'source-{i:04d}', path, path.read_bytes())
               for i, path in enumerate(paths, 1)]
    source_meta = {s.name: {'name': s.name, 'path': str(s.path),
                           'sha256': sha256(s.content).hexdigest()} for s in sources}
    output.mkdir(parents=True, exist_ok=False)
    write = lambda filename, value: build.write_json(output / filename, value)
    adapter_hash = sha256(adapter_bytes).hexdigest()
    write('preparation-start.json', {'status': 'RUNNING', 'model_calls': 0,
          'adapter': {'path': str(adapter_path), 'sha256': adapter_hash},
          'sources': list(source_meta.values())})
    samples, intermediate, providers, exclusions, identities = [], [], {}, [], set()
    current = None
    try:
        module = ModuleType('finject_user_adapter')
        module.__file__ = str(adapter_path)
        exec(compile(adapter_bytes, str(adapter_path), 'exec'), module.__dict__)
        if not callable(getattr(module, 'adapt', None)):
            raise ValueError('ADAPTER_MUST_DEFINE_ADAPT')
        for current, item in enumerate(module.adapt(tuple(sources))):
            if not isinstance(item, (ConvertedRecord, ExcludedRecord)):
                raise ValueError('ADAPTER_MUST_YIELD_MAKE_RECORD_OR_EXCLUDE')
            if not item.origins or any(not isinstance(o, Origin)
                    or not isinstance(o.source, str) or o.source not in source_meta
                    or not isinstance(o.locator, str) or not o.locator.strip()
                    or (o.index is not None and (type(o.index) is not int or o.index < 0))
                    for o in item.origins):
                raise ValueError('VALID_SOURCE_ORIGINS_REQUIRED')
            origins = [asdict(o) for o in item.origins]
            if isinstance(item, ExcludedRecord):
                if not isinstance(item.reason, str) or not item.reason.strip():
                    raise ValueError('EXCLUSION_REASON_REQUIRED')
                exclusions.append({'reason': item.reason, 'origins': origins})
                continue
            data = IntermediateSample.model_validate(item.data.model_dump()).model_dump()
            # Origin + Q distinguishes questions sharing a document, while rejecting
            # a repeated conversion of the same question at the same source location.
            identity = json.dumps({'origins': [(o.source, o.locator) for o in item.origins],
                                   'question': data['q']}, ensure_ascii=False, sort_keys=True)
            if identity in identities:
                raise ValueError('DUPLICATE_SOURCE_QUESTION')
            identities.add(identity)
            raw_id = 'custom-' + sha256(identity.encode()).hexdigest()
            source_ids = list(dict.fromkeys(o.source for o in item.origins))
            sample = {'id': f'test-{len(samples)+1:04d}', 'raw_id': raw_id,
                      'question': data['q'], **content_fields(data['c'], len(samples)),
                      'reference_answer': data['a'], 'reference_answer_type': data['a_type'],
                      'reference_precision': data['a_precision'],
                      'answer_metadata': {'scale': None, 'negative': Decimal(data['a']).is_signed()},
                      'provenance': {'dataset': 'custom', 'name': name,
                          'adapter_sha256': adapter_hash,
                          'sources': [{k: source_meta[s][k] for k in ('name', 'sha256')}
                                      for s in source_ids]}}
            first = item.origins[0]
            providers[raw_id] = {'source': first.source, 'record_index': first.index,
                                'question_id': None, 'record': first.record, 'origins': origins,
                                'intermediate_index': len(samples)}
            samples.append(sample)
            intermediate.append(data)
        if not samples:
            raise ValueError('NO_INPUTS')
        for source in sources:
            if source.path.read_bytes() != source.content:
                raise ValueError('SOURCE_CHANGED_DURING_ADAPTER')
        if adapter_path.read_bytes() != adapter_bytes:
            raise ValueError('ADAPTER_CHANGED_DURING_CONVERSION')
        validate(SCHEMA, samples)
        write('intermediate.json', intermediate)
        write('input.json', samples)
        write('provider-records.json', providers)
        write('selection-log.json', {'selected': len(samples), 'excluded': exclusions,
                                    'selection_policy': 'All adapter outputs; no sampling or context deduplication.'})
        manifest = {'format': 'finject-custom-input-v1', 'families': len(samples), 'model_calls': 0,
                    'input_schema': {k: v for k, v in describe(SCHEMA).items() if k != 'schema'},
                    'sources': list(source_meta.values()),
                    'adapter': {'path': str(adapter_path), 'sha256': adapter_hash},
                    'ids': [{'id': s['id'], 'raw_id': s['raw_id']} for s in samples],
                    'selection_policy': 'All adapter outputs; no sampling or context deduplication.',
                    'exclusions': exclusions,
                    'input_file_sha256': build.sha256((output / 'input.json').read_bytes()),
                    'provider_file_sha256': build.sha256((output / 'provider-records.json').read_bytes()),
                    'intermediate_file_sha256': build.sha256((output / 'intermediate.json').read_bytes())}
        write('selection-manifest.json', manifest)
        template = Path(__file__).with_name('custom-input-readme-template.md').read_text()
        (output / 'README.md').write_text(template.format(count=len(samples), excluded=len(exclusions)))
        result = {'status': 'PASS', 'families': len(samples), 'excluded': len(exclusions), 'model_calls': 0,
                  'manifest_sha256': build.sha256((output / 'selection-manifest.json').read_bytes())}
        write('preparation-result.json', result)
        return {'output': str(output), **result}
    except Exception as error:
        if not (output / 'selection-log.json').exists():
            write('selection-log.json', {'selected': len(samples), 'excluded': exclusions})
        write('preparation-result.json', {'status': 'FAIL', 'model_calls': 0,
              'adapter_output_index': current, 'error_type': type(error).__name__, 'reason': str(error)})
        raise
