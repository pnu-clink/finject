"""Validate shipped FinanceReasoning/TAT-QA examples after provenance registration."""

import importlib
import json
import sys
from hashlib import sha256
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from finarch.shared.reference import load_raw
from finarch.dataset.schemas.validation import validate


def run():
    catalog_path = ROOT / 'data/sample/source-catalog.json'
    catalog = json.loads(catalog_path.read_text())
    adapters = importlib.import_module('finarch.dataset.00-input.adapters')
    samples, counts = [], {}
    for spec in catalog['sources']:
        source = catalog_path.parent / spec['path']
        content = source.read_bytes()
        if sha256(content).hexdigest() != spec['sha256']:
            raise ValueError('SHIPPED_SAMPLE_HASH_MISMATCH')
        provenance = {key: spec[key] for key in ('name', 'sha256', 'url', 'commit')}
        count = 0
        for record in load_raw(content):
            if spec['adapter'] == 'finance':
                converted = [adapters.finance(record, provenance, distributed=True)]
            elif spec['adapter'] == 'tatqa':
                converted = [adapters.tatqa(record, question, provenance)
                             for question in record['questions'] if question['answer_type'] == 'arithmetic']
            else:
                raise ValueError('UNKNOWN_SHIPPED_SAMPLE_ADAPTER')
            for sample in converted:
                samples.append({'id': f'regression-{len(samples) + 1}', **sample})
                count += 1
        counts[spec['adapter']] = count
    if not counts.get('finance') or not counts.get('tatqa'):
        raise ValueError('BOTH_NATIVE_SOURCE_SAMPLES_REQUIRED')
    validate('01-preparation.01-source.prepared-input', samples)
    return {'status': 'PASS', 'samples': counts, 'model_calls': 0}


if __name__ == '__main__':
    print(json.dumps(run()))
