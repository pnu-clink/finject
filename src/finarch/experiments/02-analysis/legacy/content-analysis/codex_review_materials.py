"""Collect frozen first-round solver material for interactive Codex review; no API calls."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from finarch.paths import PROJECT


RUN = PROJECT / 'reports/experiments-run/20260927-exp-001'
TARGET = RUN / '02_analysis/01_response_review/00-codex-review.md'
VARIANTS = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
CONDITIONS = (('P0', 'off'), ('P0', 'on'), ('P1', 'off'), ('P1', 'on'))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def link(label, relative):
    return f'[{label}](../../{relative})'


def build():
    sources = ['01-input/public.jsonl', '01-input/private.jsonl', 'luna-api/01-requests/manifest.jsonl',
               'luna-api/03-results/results.jsonl', 'luna-api/02-batches/batch-001/input.jsonl',
               'luna-api/02-batches/batch-001/output.jsonl']
    before = {p: hashlib.sha256((RUN / p).read_bytes()).hexdigest() for p in sources}
    public = {row['item_id']: row for row in rows(RUN / sources[0])}
    private = {row['item_id']: row for row in rows(RUN / sources[1])}
    requests = {row['trial_id']: row for row in rows(RUN / sources[2])}
    outputs = rows(RUN / sources[3])
    wire = {row['custom_id']: row['body'] for row in rows(RUN / sources[4])}
    assert len(public) == len(private) == 800
    assert len(requests) == len(outputs) == len(wire) == 3000
    assert set(requests) == set(wire) == {row['trial_id'] for row in outputs}
    for trial, request in requests.items():
        expected = {key: public[request['item_id']][key] for key in ('question', 'context', 'answer_format')}
        actual = json.loads(wire[trial]['input'][0]['content'][0]['text'])
        assert request['input'] == actual == expected
        assert type(actual['answer_format']['decimal_places']) is int
        assert wire[trial]['instructions'] == request['prompt']
        assert wire[trial]['reasoning']['effort'] == {'off': 'none', 'on': 'medium'}[request['reasoning']]
    lookup = {(row['case'], row['variant'], row['prompt_condition'], row['reasoning']): row for row in outputs}
    assert len(lookup) == len(outputs)
    cases = sorted({row['case'] for row in outputs})
    assert len(cases) == 100
    for case in cases:
        assert all((case, 'ORIGINAL', 'P0', r) in lookup for r in ('off', 'on'))
        assert all((case, v, p, r) in lookup for v in VARIANTS for p, r in CONDITIONS)
    for row in outputs:
        assert (RUN / row['call_path']).is_file() and (RUN / row['result_path']).is_file()
    counts = Counter((r['variant'], r['prompt_condition'], r['reasoning'], r['response']['answer'] is None) for r in outputs)
    original = []
    for reasoning in ('off', 'on'):
        records = [lookup[case, 'ORIGINAL', 'P0', reasoning] for case in cases]
        matches = sum(row['checks'].get('numeric_comparison', {}).get('matches') is True for row in records)
        mismatches = sum(row['checks'].get('numeric_comparison', {}).get('matches') is False for row in records)
        absent = sum(row['response']['answer'] is None for row in records)
        assert matches + mismatches + absent == 100
        original.append(f'|Unguided · {reasoning.upper()}|{matches}|{mismatches}|{absent}|100|')
    matrix = ['|' + variant + '|' + '|'.join(f'{counts[variant,p,r,False]} / {counts[variant,p,r,True]}' for p, r in CONDITIONS) + '|' for variant in VARIANTS]
    def observed(row):
        answer = row['response']['answer']
        mark = 'No numeric answer' if answer is None else 'Match' if row['checks'].get('numeric_comparison', {}).get('matches') is True else 'Mismatch'
        return f'{answer if answer is not None else "null"} · {mark}'
    index = []
    for case in cases:
        off, on = [lookup[case, 'ORIGINAL', 'P0', r] for r in ('off', 'on')]
        reference = private[off['item_id']]['reference']['reference_answer']
        variants = ' · '.join(link(f'{"General" if p == "P0" else "The standard."}/{r.upper()}', lookup[case, VARIANTS[0], p, r]['call_path']) for p, r in CONDITIONS)
        index.append(f'|{case}|{reference}|{link(observed(off),off["call_path"])}|{link(observed(on),on["call_path"])}|{variants}|')
    case = cases[0]
    def sample(variant, conditions):
        parts = []
        for prompt, reasoning in conditions:
            row = lookup[case, variant, prompt, reasoning]
            call = json.loads((RUN / row['call_path']).read_text())
            assert call['response'] == row['response']
            raw = call['records']['raw_response_path']
            assert (RUN / raw).is_file()
            title = f'{"Unguided" if prompt == "P0" else "Criteria-Guided"} Solving · Reasoning {reasoning.upper()}'
            parts += [f'**{title}** · {link("The real request and response", row["call_path"])} · {link("Provider raw response", raw)}',
                      '', '```json', json.dumps(row['response'], ensure_ascii=False, indent=2), '```', '']
        return '\n'.join(parts)
    first = lookup[case, 'ORIGINAL', 'P0', 'off']
    now = datetime.now(timezone.utc).astimezone().isoformat()
    values = {'run': RUN.name, 'updated': now, 'valid': str(sum(r['status'] == 'VALID' for r in outputs)),
              'original_counts': '\n'.join(original), 'answer_counts': '\n'.join(matrix),
              'sample_case': case, 'sample_question': public[first['item_id']]['question'],
              'sample_precision': str(public[first['item_id']]['answer_format']['decimal_places']),
              'sample_reference': str(private[first['item_id']]['reference']['reference_answer']),
              'sample_original': sample('ORIGINAL', CONDITIONS[:2]), 'sample_variant': sample(VARIANTS[0], CONDITIONS),
              'case_index': '\n'.join(index)}
    text = (PROJECT / 'src/finarch/experiments/templates/codex-review-materials.md').read_text()
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    assert '{{' not in text
    TARGET.write_text(text)
    after = {p: hashlib.sha256((RUN / p).read_bytes()).hexdigest() for p in sources}
    assert before == after
    with (RUN / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'time': now, 'event': 'CODEX_REVIEW_MATERIALS_READY', 'document': str(TARGET.relative_to(RUN)),
            'source_sha256': before, 'solver_responses': len(outputs), 'originals': len(cases),
            'public_only_requests_verified': len(requests), 'api_calls': 0, 'semantic_review': 'NOT_STARTED',
            'user_review': 'PENDING'}, ensure_ascii=False) + '\n')
    print(json.dumps({'document': str(TARGET), 'responses': len(outputs), 'api_calls': 0, 'source_hashes': 'UNCHANGED'}, ensure_ascii=False))


if __name__ == '__main__':
    build()
