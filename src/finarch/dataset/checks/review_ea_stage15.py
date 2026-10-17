variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""EA15: audit saved deletion plans; inverse/semantic certification stays deferred."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
from importlib import import_module
import io
import json
from pathlib import Path
import unittest

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
build = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['build']).build
from finarch.dataset.shared.calculation.python_graph import load_graph
compose_ea = __import__('finarch.dataset.02-generation.02-generate-text.text_preview', fromlist=['compose_ea']).compose_ea


NUMBER = import_module('finarch.dataset.00-input.content').NUMBER
SCOPE = '\uccab \ubb38\ud56d\uc758 \uad00\uce21 \uc785\ub825 \uc0ad\uc81c·\ubcf4\uc874·\uc624\ub958 \uad6c\ubd84; \uc5ed\uc0b0 \ubc0f \ucd5c\uc885 \ubb38\uc7a5 \uc758\ubbf8 \uac80\uc0ac\ub294 \uc81c\uc678'
DEFERRED = ['T097\uc758 \ub2e8\uc704 \ud658\uc0b0·\uad00\uacc4 \uae30\ubc18 \ubcf5\uc6d0 \uc870\uc0ac', 'T098 \ubcf5\uc6d0 \uacbd\ub85c \uc0ad\uc81c \uc9d1\ud569',
            'T100 \ub2f5 \uc720\uc77c\uc131·\uc0c1\uc1c4·\uc6b0\ud68c', 'T101 \uc11c\ub85c \ub2e4\ub978 \ub2f5\uc758 \ubcf4\uc644 \uc0ac\ub840', 'T104\uc758 \uc5ed\uc0b0·\uc6b0\ud68c']
FOLLOW_UP = ['16·17: \uc2e4\uc81c LLM \ubb38\uc7a5 \uc0dd\uc131·\uc751\ub2f5 \uc2a4\ud0a4\ub9c8·\ucd5c\uc885 \ubcf8\ubb38 \ubc0f \uc758\ubbf8 \uac80\uc0ac',
             '24: public/private \ub3d9\uacb0·\ubd84\ub9ac \uac80\uc0ac']


def occurrences(text, value):
    """Decimal digit notation only; no unit conversion or inferred relationships."""
    target = Decimal(str(value).replace(',', ''))
    return [{'span': [m.start(), m.end()], 'text': m.group()} for m in NUMBER.finditer(text)
            if not m.group().endswith('%') and Decimal(m.group().replace(',', '')) == target]


def inspect(sample, program, plan, binding, graph, preview, original):
    key = plan['fact_id']; fact = program['facts'][key]
    replay, inputs, _ = build({**program, 'context': sample['context']}, key)
    draft = compose_ea(sample, plan, program)
    contexts = {'original': sample['context'], 'question': sample['question'],
                'draft': preview['preview_context']}
    target_matches = {k: occurrences(v, fact['value']) for k, v in contexts.items()}
    gold_matches = {k: occurrences(v, sample['reference_answer']) for k, v in contexts.items()}
    first_reads = list(dict.fromkeys(n['fact_id'] for n in original['nodes'] if n['kind'] == 'fact'))
    structure = lambda g: [(n['id'], n['kind'], n['inputs'], n.get('code_line')) for n in g['nodes']]
    checks = {
        'observed_input_selected': key in first_reads,
        'source_span_matches': fact['span'] == plan['deletion']['span'] and
            sample['context'][slice(*fact['span'])] == fact['text'] == plan['deletion']['before'],
        'one_direct_target_occurrence': [m['span'] for m in target_matches['original']] == [fact['span']],
        'no_target_in_draft_or_question': not target_matches['draft'] and not target_matches['question'],
        'no_direct_gold_in_context_or_question': not any(gold_matches.values()),
        'graph_replay_matches': replay == graph == plan['graphs']['EA'],
        'same_nodes_and_edges': structure(graph) == structure(original) and graph['edges'] == original['edges'],
        'same_code_and_remaining_inputs': inputs == binding and binding['code'] == program['code'],
        'only_selected_fact_missing': binding['missing_facts'] == [key] and
            set(binding['facts']) == set(program['facts']) - {key},
        'preview_replay_matches': all(draft[k] == preview[k] for k in
            ('original_context', 'preview_context', 'question', 'intermediate', 'rewritten_sentence',
             'preserved_evidence', 'python', 'graph_binding', 'calculation_result')) and
            [{k: p[k] for k in ('start', 'end', 'before', 'text', 'element_ids')} for p in draft['patches']] ==
            [{k: p[k] for k in ('start', 'end', 'before', 'text', 'element_ids')} for p in preview['patches']],
        'same_question_and_code': preview['question'] == sample['question'] and preview['python']['code'] == program['code'],
        'remaining_amounts_preserved': all(preview['preview_context'][slice(*v['span'])] == v['text']
            for v in preview['preserved_evidence'].values()) and
            set(preview['preserved_evidence']) == set(program['facts']) - {key},
        'tag_only_in_private_intermediate': preview['intermediate']['context'].count(preview['intermediate']['tag']) == 1
            and '[EA_DELETE:' not in preview['preview_context'],
        'no_numeric_ea_answer': plan['result'] == preview['calculation_result'] == {'answer': None, 'missing_facts': [key]},
        'no_stale_missing_or_blocked_values': all(not any(k in n for k in ('value', 'computed'))
            for n in graph['nodes'] if n['evaluation']['state'] != 'KNOWN'),
        'semantic_and_recovery_not_claimed': plan['semantic_status'] == preview['semantic_status'] == 'NOT_EVALUATED'
            and plan['recovery_review'] == 'SKIPPED_BY_USER' and preview['final_text_status'] == 'NOT_RUN',
    }
    return {'checks': checks, 'direct_occurrences': {'target': target_matches, 'original_gold': gold_matches},
            'selection': {'kind': 'observed_input', 'fact_id': key, 'original_value': fact['value'],
                          'input_order': first_reads.index(key) + 1, 'input_order_base': 1,
                          'order_basis': 'first fact read in Python code', 'target_span': fact['span']},
            'node_states': dict(Counter(n['evaluation']['state'] for n in graph['nodes']))}


def review(case_dir, labels):
    # [EA15.1] Reuse eligibility and graph checks; excluded gold cases cannot pass.
    case = Path(case_dir).resolve()
    for label in labels:
        if Path(label).name != label or label in ('.', '..'):
            raise ValueError('INVALID_LABEL')
        if (case / '04-perturbation/variants' / label / 'stage15-review.json').exists():
            raise ValueError('REVIEW_ALREADY_EXISTS')
    ctx = RunContext.resume(case, {}, case.name)
    with ctx.trace.activate(), ctx.trace.span('review_ea_stage15', stage='03-graph', step='EA15', role='python') as outcome:
        original = load_graph(case)
        read = lambda p: json.loads((case / p).read_text())
        sample = read('00-data-preparation/01-select-input/01-input.json'); program = read('02-calculation/02-prepare-code/03-program.json')
        stream = io.StringIO()
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'finarch.dataset.checks.test_ea_plan', 'finarch.dataset.checks.test_ea_stage15'])
        tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        results = []
        for label in labels:
            base = variant_root(label)
            plan = read(base + '/plan.json')
            report = inspect(sample, program, plan, read(base + '/calculation-input.json'),
                             read(base + '/graph.json'), read(base + '/05-text-input-preview.json'), original)
            hashes = {p: hashlib.sha256((case / p).read_bytes()).hexdigest()
                      for p in plan['preserved_inputs_sha256']}
            report['checks'].update(original_files_preserved=hashes == plan['preserved_inputs_sha256'],
                                    error_and_residue_regressions_passed=tests.wasSuccessful())
            status = 'PASS' if all(report['checks'].values()) else 'FAIL'
            report.update(status=status, scope=SCOPE, case_id=case.name, variant=label,
                          checklist_status='COMPLETE_CURRENT_SCOPE' if status == 'PASS' else 'NOT_COMPLETE',
                          completed_items=['T096', 'T097 \uc9c1\uc811 \uae30\uc7ac', 'T099', 'T102 \uae30\uc220 \uc624\ub958', 'T103 \uc6d0\ubcf8 \ubcf4\uad00', 'T104 \uc9c1\uc811 \uc794\uc874']
                              if status == 'PASS' else [], deferred=DEFERRED, follow_up=FOLLOW_UP,
                          scan_scope='\uc22b\uc790\ub85c \uc9c1\uc811 \uc801\ud78c \ub3d9\uc77c \uac12\uacfc \uc27c\ud45c \ud45c\uae30\ub9cc \uac80\uc0ac; \ubb38\uc790 \uc218\uc0ac·\ub2e8\uc704 \ud658\uc0b0·\uad00\uacc4 \ucd94\ub860 \ubbf8\uac80\uc0ac',
                          preserved_inputs_sha256=hashes, tests={'run': tests.testsRun, 'passed': tests.wasSuccessful()},
                          semantic_status='NOT_EVALUATED', model_calls=0)
            # [EA15.2] Append a new audit and generated guide; never rewrite original evidence.
            ctx.save(base + '/04-deletion-check.json', report)
            ctx.save_text(base + '/STAGE15-TESTS.txt', stream.getvalue())
            rows = '\n'.join(f'| {name} | {"PASS" if passed else "FAIL"} |' for name, passed in report['checks'].items())
            ctx.save_text(base + '/STAGE15-README.md', f'''# 15\ubc88 EA · \uc774\ubc88 \ubc94\uc704 \uac80\uc0ac

\ud310\uc815: **{status}**. {SCOPE}\uc785\ub2c8\ub2e4. \ub300\uc0c1: {key_label(report)}.

\uc77d\ub294 \uc21c\uc11c: stage15-review.json → STAGE15-TESTS.txt → plan.json → calculation-input.json → graph.json → text-preview-v2.json.
stage15-review.json\uc740 \uc9c1\uc811 \uc22b\uc790 \uae30\uc7ac \uc704\uce58, \uc6d0\ubcf8 \ud574\uc2dc, \uc0ad\uc81c \uc785\ub825 \uc21c\uc11c, \uadf8\ub798\ud504 \uc7ac\uc0dd\uc131\uacfc \ubcf4\uc874 \uac80\uc0ac\ub97c \uc800\uc7a5\ud569\ub2c8\ub2e4.
STAGE15-TESTS.txt\ub294 \uc774\ubc88\uc5d0 \uc2e4\ud589\ud55c {tests.testsRun}\uac1c \ub85c\uceec \uac80\uc0ac\uc758 \uc6d0\ucd9c\ub825\uc785\ub2c8\ub2e4. \uc6d0\ubcf8·\uae30\uc874 checklist-review.json\uc740 \uacfc\uac70 \uae30\ub85d\uc73c\ub85c \ubcf4\uc874\ud569\ub2c8\ub2e4.

| \uac80\uc0ac | \uacb0\uacfc |
|---|---|
{rows}

\uc644\ub8cc\ub294 \uccab \ubb38\ud56d\uc758 \uc9c0\uc815 \uc785\ub825 \uc0ad\uc81c·\ubcf4\uc874·\uae30\uc220 \uc624\ub958 \uac80\uc0ac \ubc94\uc704\uc785\ub2c8\ub2e4. \uc21c\uc11c\ub294 \uc6d0\ubb38 \uc785\ub825\uc744 Python \ucf54\ub4dc\uc5d0\uc11c \ucc98\uc74c \uc77d\ub294 \uc21c\uc11c\uc774\uba70 \ud30c\uc0dd \uc911\uac04\uac12\uc758 \uc0ad\uc81c\uac00 \uc544\ub2d9\ub2c8\ub2e4.
\uc22b\uc790\ub85c \uc9c1\uc811 \uc801\ud78c \ub3d9\uc77c \uac12\ub9cc \uc870\uc0ac\ud569\ub2c8\ub2e4. \ubb38\uc790 \uc218\uc0ac·\ub2e8\uc704 \ud658\uc0b0·\uad00\uacc4 \ucd94\ub860\uc73c\ub85c \ubcf5\uc6d0\ub418\uc9c0 \uc54a\ub294\ub2e4\ub294 \uc99d\uba85\uc740 \uc544\ub2d9\ub2c8\ub2e4.
\ubcf4\ub958: {' / '.join(DEFERRED)}.
\ud6c4\uc18d: {' / '.join(FOLLOW_UP)}.
EA \uc22b\uc790 \ub2f5\uc740 null, \uc758\ubbf8 \ud310\uc815\uc740 NOT_EVALUATED\ub97c \uc720\uc9c0\ud569\ub2c8\ub2e4. \ucd94\uac00 LLM \ud638\ucd9c\uc740 0\ud68c\uc785\ub2c8\ub2e4.

\uacf5\ud1b5 viewer\uc5d0\uc11c \uc774 \uc2e4\ud589 → {case.name} → EA\uc758 \ud574\ub2f9 \uc0ad\uc81c \uc785\ub825 → 4 \uadf8\ub798\ud504 \ubcc0\uacbd\uc744 \uc120\ud0dd\ud558\uba74 \uc774\ubc88 \uac80\uc0ac \uc694\uc57d\uacfc \uc0c1\uc138 \uae30\ub85d\uc744 \ud655\uc778\ud569\ub2c8\ub2e4. 5 \ubb38\uc7a5\uacfc \ub2f5\ubcc0\uc5d0\uc11c \uc0ad\uc81c \ud0dc\uadf8\uc640 \uc218\uc815 \ubb38\uc7a5\uc744 \ud655\uc778\ud558\uace0, 8 \uc804\uccb4 \uae30\ub85d\uc5d0\uc11c \uc6d0\ud30c\uc77c\uc744 \uc77d\uc2b5\ub2c8\ub2e4.
\uc774 README\ub294 \uac80\uc0ac \ud568\uc218\uc758 \ud15c\ud50c\ub9bf\uc5d0\uc11c \uc0dd\uc131\ud569\ub2c8\ub2e4. events.jsonl\uc758 EA15\uc5d0\ub294 \uc2dc\uc791·\uc0b0\ucd9c\ubb3c·\uc885\ub8cc\uac00 \ub0a8\uc2b5\ub2c8\ub2e4. \uc790\ub3d9 \uc7ac\uc2dc\ub3c4\ub294 \uc5c6\uc73c\uba70 \uc2e4\ud328\uba74 \uc6d0\uc778\uc744 \uace0\uce5c \ub4a4 \ubcc4\ub3c4 \uae30\ub85d\uc73c\ub85c \uc7ac\uac80\uc0ac\ud569\ub2c8\ub2e4.
''')
            results.append(report)
        failed = [r['variant'] for r in results if r['status'] != 'PASS']
        outcome.update(status='FAIL' if failed else 'PASS', reason='EA15_CURRENT_SCOPE_AUDIT', failed=failed)
        if failed:
            raise ValueError('EA15_CHECK_FAILED:' + ','.join(failed))
        return [{'variant': r['variant'], 'status': r['status'], 'checks': len(r['checks']), 'tests': r['tests']} for r in results]


def key_label(report):
    item = report['selection']
    return f"{item['fact_id']} ({item['original_value']}, \uc785\ub825 \uc21c\uc11c {item['input_order']})"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_dir'); parser.add_argument('labels', nargs='+')
    args = parser.parse_args()
    print(json.dumps(review(args.case_dir, args.labels), ensure_ascii=False))
