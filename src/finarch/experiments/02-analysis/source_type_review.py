"""Stratify a completed experiment by frozen preparation provenance, without calls."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import islice
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[4]
SOURCE = Path('reports/run/20260917-002/results/00-input.json')
SOURCE_MANIFEST = Path('reports/run/20260917-002/results/manifest.json')
STAGE = Path('02_analysis/source-types')
KINDS = ('FinQA', 'TAT-QA', 'FinanceMath', 'FinanceReasoning')
VARIANTS = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER',
            'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
CONDITIONS = (('unguided', 'off'), ('unguided', 'on'), ('guided', 'off'), ('guided', 'on'))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def kind_of(provenance: dict) -> str:
    source_id = provenance['source_id']
    if source_id.startswith('CodeFinQA-'):
        return 'FinQA'
    if source_id.startswith('CodeTAT-QA-'):
        return 'TAT-QA'
    if source_id.startswith('FinanceMath-'):
        return 'FinanceMath'
    if source_id.startswith('FinanceReasoning-'):
        return 'FinanceReasoning'
    raise ValueError(f'Unrecognized source_id: {source_id}')


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ratio(n: int, d: int) -> str:
    return f'{n}/{d} ({n / d * 100:.1f}%)' if d else '0/0'


def condition_name(prompt: str, reasoning: str) -> str:
    return f'{"Unguided Solving" if prompt == "unguided" else "Criteria-Guided Solving"} · Reasoning {reasoning.upper()}'


def metric(rows: list[dict]) -> dict:
    valid = [row for row in rows if row['status'] == 'VALID']
    answer = [row for row in valid if isinstance(row.get('response'), dict)]
    numeric = [row['case'] for row in answer if row['response'].get('answer') is not None]
    null = [row['case'] for row in answer if row['response'].get('answer') is None]
    failed = [row['case'] for row in rows if row['status'] != 'VALID']
    if len(answer) != len(valid) or len(numeric) + len(null) + len(failed) != len(rows):
        raise ValueError('Saved response cannot be assigned to numeric, null, or format failure.')
    return {
        'planned': len(rows), 'status': dict(sorted(Counter(row['status'] for row in rows).items())),
        'valid': len(valid),
        'numeric_answer': len(numeric), 'numeric_case_ids': sorted(numeric),
        'null_answer': len(null), 'null_case_ids': sorted(null),
        'format_failed_case_ids': sorted(failed),
        'classification': dict(sorted(Counter(str(row['response'].get('classification')) for row in answer).items())),
        'original_result': dict(sorted(Counter(row['original_result'] for row in rows if row['variant'] == 'ORIGINAL').items())),
    }


def render_review(name: str, result: dict, observations: list[dict], linked: dict) -> str:
    count = result['case_count']
    lines = [f'# exp-001-luna-{name} • Reviewing the types of sources', '',
             f'Original {count}case, save the reply {result["response_count"]}I re-ordered the building from the same completed run. '
             'It\'s not a star experiment, a new model call, a purposeful answer judgement.', '',
             f'Source ID prefixed with `{result["source_id_prefix"]}I used `. '
             f'The top dataset is marked `{", ".join(result["dataset_labels"])}`. '
             'This is the source code in the FinanceReasoning selection set, not the independent benchmark score.', '',
             '## Sentencing and testing', '',
             f'- Difficulty: {", ".join(f"{k} {v}" for k, v in result["levels"].items())}',
             f'- External knowledge of the original use label: use {result["original_external_knowledge"]["true"]}entries, '
             f'Unused {result["original_external_knowledge"]["false"]}This is a private record of the production process, not whether or not the model answers are used.',
             f'- Response format: {", ".join(f"{k} {v}" for k, v in result["response_status"].items())}. '
             'Form valid does not mean meaningful.', '',
             'The original record number matches the', '',
             'The following is the list of the most commonly used methods for calculating the value of a given data set.', '|---|---|---:|---:|---:|']
    for prompt, reasoning in CONDITIONS:
        m = result['conditions']['ORIGINAL'][f'{prompt}/{reasoning}']['original_result']
        lines.append(f'|{"Unguided Solving" if prompt == "unguided" else "Criteria-Guided Solving"}|Reasoning {reasoning.upper()}|{m.get("MATCH", 0)}|{m.get("MISMATCH", 0)}|{m.get("UNEVALUATED", 0)}|')
    lines += ['', 'MATCH is a match to the reference numbers stored, not a validity of the explanation, a question meaning of the correct answer.', '',
              '## RQ1 · Transformational response and feedback', '',
              'The denominator of each can is the number of original cases of the type. `Numbers / null / formatting and` in this order.', '',
              'Reasoning on solving the problemCriteria-Guided Solving', '|---|---:|---:|']
    for variant in VARIANTS[1:]:
        cells = []
        for prompt in ('unguided', 'guided'):
            m = result['conditions'][variant][f'{prompt}/on']
            cells.append(f'{m["numeric_answer"]} / {m["null_answer"]} / {count-m["valid"]}')
        lines.append(f'|{variant}|{cells[0]}|{cells[1]}|')
    lines += ['', '## RQ2', '',
              'The table above shows the difference in the direction of the root of the same case-variable, and the table below includes the OFF/ON of the original. '
              'The four settings are not independent iterations, so they don\'t read as the impact of the setup change.', '',
              'The number of responses to the number of responsed responses to null and void responses', '|---|---:|---:|---:|']
    for prompt, reasoning in CONDITIONS:
        m = result['conditions']['ORIGINAL'][f'{prompt}/{reasoning}']
        lines.append(f'|{condition_name(prompt, reasoning)}|{m["numeric_answer"]}|{m["null_answer"]}|{count-m["valid"]}|')
    lines += ['', '### all variations and configurations are in response status', '',
              'Each can is `Numbers / null / formatting and`And the denominator is the number of original cases of this type every time.', '',
              'The following is a list of the most commonly used methods of measuring the quality of a product:',
              '|---|---:|---:|---:|---:|']
    for variant in VARIANTS:
        cells = []
        for prompt, reasoning in CONDITIONS:
            m = result['conditions'][variant][f'{prompt}/{reasoning}']
            cells.append(f'{m["numeric_answer"]} / {m["null_answer"]} / {count-m["valid"]}')
        lines.append('|'+ '|'.join([variant, *cells]) + '|')
    lines += ['', '## The case-by-case observation and the whole A03The connection', '',
              f'A02 Storage observation {len(observations)}items belong to this type of case. '
              + ', '.join(f'{k} {v}' for k, v in result['a02_categories'].items()) + '.',
              'The existing A03 The number of times a subject\'s connection observation ID belongs to this type is as follows: '
              'One observation can be linked to multiple topics, and it\'s not possible to reconfirm the entire group\'s claim itself about this type.', '',
              'RQ/SQ is a 0.3 Subject ID of this type belongs to the link observation ID of the', '|---|---|---:|']
    for group, info in linked.items():
        lines.append(f'|{info["question_id"]}|{group} · {info["title_ko"]}|{info["observation_count"]}|')
    lines += ['', '### A02 The first example of observation', '',
              'The first in the order of storage in each category 2It\'s an example of finding a items, not a representative sample or a complete conclusion of a particular type.', '']
    categories = sorted({item['category'] for item in observations})
    for category in categories:
        lines += [f'#### {category}', '']
        for item in islice((item for item in observations if item['category'] == category), 2):
            ko = item.get('display') or item.get('display_ko') or {}
            lines += [f'- **{item["id"]} · {ko.get("title", item["title"])}**: '
                      f'{ko.get("observation", item["observation"])} '
                      f'Limitation: {ko.get("limitation", item["limitation"])}']
        lines.append('')
    lines += ['', '♪ The range of interpretation ♪', '',
              '- Type-by-type case number: Nanndo: The target of external knowledge usage at the time of manufacture varies from one type to another, and the difference in the ratio between types is not a comparison to the other.',
              '- The original and each variation started from the same original case. 32items independent cases 32They don\'t count like items.',
              '- Number return, null, classification tag, cited description are separate observations. They don\'t change the number of candidates to the correct rate of conflict recognition and near selection.',
              '- The direct conclusions about SQ2, SQ4, SQ5, and SQ6 are not new to this type-re-assortment.', '',
              '## Read the evidence', '',
              '1. [README](README.md)Check the file and range.',
              '2. [summary.json](summary.json)Check the status of all variations and formats of the four settings.',
              '3. [cases.jsonl](cases.jsonl)From the source ID to the Nando problem A02 Check the ID of the observer, '
              '[A02 Source text](../../02_comparison/interpretations.jsonl)And we\'re going back to the same case response as the experimental viewer.',
              '4[A0 as a whole.]3 The color of the subject.](../../03_research/rq-review.md)The argument and the contradiction are read separately.', '']
    return '\n'.join(lines)


def build(run: str) -> dict:
    if run != '20260928-exp-001-luna':
        raise ValueError('This review is bound to the frozen 20260928-exp-001-luna run.')
    root = PROJECT / 'reports/experiments-run' / run
    state = json.loads((root / 'state.json').read_text())
    if state['analysis']['status'] != 'COMPLETE' or state['full_pipeline']['status'] != 'COMPLETE':
        raise ValueError('Evaluation and analysis must be complete before this saved-result review.')
    source_path = PROJECT / SOURCE
    manifest = json.loads((PROJECT / SOURCE_MANIFEST).read_text())
    if digest(source_path) != manifest['files'][SOURCE.name]['sha256']:
        raise ValueError('Frozen source hash differs from its preparation manifest.')
    source = {row['id']: row['input']['provenance'] for row in json.loads(source_path.read_text())}
    private = list(jsonl(root / '00_input/private.jsonl'))
    originals = {row['case']: row for row in private if row['variant'] == 'ORIGINAL'}
    if len(originals) != 1080 or len(private) != 8640:
        raise ValueError('Frozen selection has unexpected size or duplicate originals.')
    if {Path(row['source']).resolve() for row in originals.values()} != {(PROJECT / SOURCE_MANIFEST).resolve()}:
        raise ValueError('Original private input points to another preparation manifest.')
    private_matrix = [(row['case'], row['variant']) for row in private]
    if len(set(private_matrix)) != len(private_matrix) or set(private_matrix) != {(case, variant) for case in originals for variant in VARIANTS}:
        raise ValueError('Frozen private input matrix is incomplete, duplicated, or unexpected.')
    cases = {}
    for case, row in originals.items():
        provenance = source.get(case)
        if not provenance:
            raise ValueError(f'Missing source provenance: {case}')
        cases[case] = {'case': case, 'source_type': kind_of(provenance),
                       'source_id': provenance['source_id'], 'dataset': provenance['dataset'],
                       'level': provenance['level'], 'original_external_knowledge': row['original_external_knowledge']}
    responses = list(jsonl(root / '02_analysis/01_results/responses.jsonl'))
    expected = {(case, variant, prompt, reasoning) for case in cases for variant in VARIANTS for prompt, reasoning in CONDITIONS}
    actual = [(row['case'], row['variant'], row['prompt_condition'], row['reasoning']) for row in responses]
    if len(actual) != 34560 or len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError('Saved response matrix is incomplete, duplicated, or unexpected.')
    observations = list(jsonl(root / '02_analysis/02_comparison/interpretations.jsonl'))
    by_case = defaultdict(list)
    for item in observations:
        case = item['id'].rsplit('-O', 1)[0]
        if case not in cases:
            raise ValueError(f'A02 observation has no selected case: {item["id"]}')
        by_case[case].append(item)
    review = json.loads((root / '02_analysis/03_research/rq-review.json').read_text())
    out = root / STAGE
    out.mkdir(parents=True, exist_ok=True)
    index = {'schema_version': 1, 'run': run, 'method': 'saved-response-provenance-stratification',
             'new_external_model_calls': 0, 'source_hashes': {
                 str(SOURCE): digest(source_path), str(SOURCE_MANIFEST): digest(PROJECT / SOURCE_MANIFEST),
                 '00_input/private.jsonl': digest(root / '00_input/private.jsonl'),
                 '02_analysis/01_results/responses.jsonl': digest(root / '02_analysis/01_results/responses.jsonl'),
                 '02_analysis/02_comparison/interpretations.jsonl': digest(root / '02_analysis/02_comparison/interpretations.jsonl'),
                 '02_analysis/03_research/rq-review.json': digest(root / '02_analysis/03_research/rq-review.json')},
             'types': []}
    summaries = {}
    for name in KINDS:
        selected = sorted((case for case, info in cases.items() if info['source_type'] == name))
        rows = [row for row in responses if row['case'] in set(selected)]
        obs = [item for case in selected for item in by_case[case]]
        obs_ids = {item['id'] for item in obs}
        linked = {group['id']: {'question_id': group['question_id'], 'title_ko': group['title_ko'],
                                'observation_count': len(set(group['interpretation_ids']) & obs_ids)} for group in review['groups']}
        conditions = {variant: {f'{prompt}/{reasoning}': metric([row for row in rows if row['variant'] == variant and row['prompt_condition'] == prompt and row['reasoning'] == reasoning]) for prompt, reasoning in CONDITIONS} for variant in VARIANTS}
        result = {'source_type': name, 'case_count': len(selected), 'response_count': len(rows),
                  'case_ids': selected,
                  'source_id_prefix': {'FinQA': 'CodeFinQA-', 'TAT-QA': 'CodeTAT-QA-', 'FinanceMath': 'FinanceMath-', 'FinanceReasoning': 'FinanceReasoning-'}[name],
                  'dataset_labels': sorted({cases[case]['dataset'] for case in selected}),
                  'levels': dict(sorted(Counter(cases[case]['level'] for case in selected).items())),
                  'original_external_knowledge': {'true': sum(cases[case]['original_external_knowledge']['used'] is True for case in selected),
                                                  'false': sum(cases[case]['original_external_knowledge']['used'] is False for case in selected)},
                  'response_status': dict(sorted(Counter(row['status'] for row in rows).items())),
                  'a02_observation_count': len(obs), 'a02_categories': dict(sorted(Counter(item['category'] for item in obs).items())),
                  'a02_examples': {category: [
                      {'id': item['id'], 'title_ko': (item.get('display') or item['display_ko'])['title'],
                       'observation_ko': (item.get('display') or item['display_ko'])['observation'],
                       'limitation_ko': (item.get('display') or item['display_ko'])['limitation']}
                      for item in islice((item for item in obs if item['category'] == category), 2)]
                      for category in sorted({item['category'] for item in obs})},
                  'linked_a03_observations_by_group': linked, 'conditions': conditions}
        summaries[name] = result
        folder = out / f'exp-001-luna-{name}'
        folder.mkdir(exist_ok=True)
        save(folder / 'summary.json', result)
        (folder / 'cases.jsonl').write_text(''.join(json.dumps({**cases[case], 'a02_observation_ids': [item['id'] for item in by_case[case]]}, ensure_ascii=False) + '\n' for case in selected))
        (folder / 'review.md').write_text(render_review(name, result, obs, linked))
        readme = PROJECT / 'src/finarch/experiments/templates/source-type-review-readme.md'
        (folder / 'README.md').write_text(readme.read_text().format(run=run, name=name, count=len(selected)))
        index['types'].append({'source_type': name, 'case_count': len(selected), 'response_count': len(rows),
                               'observation_count': len(obs), 'folder': str(STAGE / folder.name),
                               'review_path': str(STAGE / folder.name / 'review.md')})
    if sum(item['case_count'] for item in index['types']) != 1080 or sum(item['response_count'] for item in index['types']) != 34560 or sum(item['observation_count'] for item in index['types']) != len(observations):
        raise ValueError('Source partitions do not cover all cases, responses, and observations.')
    save(out / 'source-type-index.json', index)
    overview = ['# exp-001-luna · Contrast between the observed types of source', '',
                'Below is a technical statistic dividing the completed same run into source statistics. The out-of-the-box usage of type-inter-case configuration, data and source-production is different. '
                'So the ratio difference isn\'t a model performance overhead or a type of interaction.', '',
                '## The original case matches the number', '',
                'Criteria-Guided Solving · Reasoning ON original MATCH • Unguided Solving • Reasoning On original MATCH · The formatting of the response',
                '|---|---:|---:|---:|---:|']
    for name in KINDS:
        item = summaries[name]
        original = item['conditions']['ORIGINAL']
        bad = item['response_count'] - item['response_status'].get('VALID', 0)
        overview.append(f'|[{name}](exp-001-luna-{name}/review.md)|{item["case_count"]}|'
                        f'{ratio(original["guided/on"]["original_result"].get("MATCH", 0), item["case_count"])}|'
                        f'{ratio(original["unguided/on"]["original_result"].get("MATCH", 0), item["case_count"])}|{bad}|')
    overview += ['', '## Differential Criteria-Guided Solving · Reasoning ON returns the number', '',
                 'The denominator is the number of original cases for each type. The number returns is different from the corresponding or meaningful correct answer for the candidate number.', '',
                 'The source type is the one before the source is the one after the source is.1|EA_02|',
                 '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name in KINDS:
        item = summaries[name]
        cells = [ratio(item['conditions'][variant]['guided/on']['numeric_answer'], item['case_count']) for variant in VARIANTS[1:]]
        overview.append('|'+ '|'.join([name, *cells]) + '|')
    overview += ['', '## Be careful when reading', '',
                 '- FinanceReasoning native statements and FinQA-TAT-QA embedded statements differ in source format and case structure.',
                 '- EA is a variation that you deleted independently from the original, one by one, and you have to check the individual cases to see if they can be calculated with the rest of the information.',
                 '- The null increment of guided conditions is the model\'s display behavior, not whether the collision identification response rate or knowledge usage.',
                 '- Type A0 for each.2 The case and limitations in each report, the total A03 The connection between the subject and RQ/SQ is read from the existing interpretation of research.', '']
    (out / 'overview.md').write_text('\n'.join(overview))
    template = PROJECT / 'src/finarch/experiments/templates/source-type-index-readme.md'
    (out / 'README.md').write_text(template.read_text().format(run=run))
    (out / 'build.log').write_text(json.dumps({'status': 'COMPLETE', 'case_count': 1080, 'response_count': 34560,
                                               'observation_count': len(observations), 'types': len(KINDS),
                                               'new_external_model_calls': 0}, ensure_ascii=False, indent=2) + '\n')
    return index


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    print(json.dumps(build(parser.parse_args().run)['types'], ensure_ascii=False))
