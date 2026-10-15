"""Check live comparison collection without touching saved experiment runs."""
import json
import tempfile
import unittest
from pathlib import Path

from finarch.documentation import research_ic_value_quadrant as view
from finarch.documentation.checks.test_research_ic_value_quadrant import fixture
from finarch.experiments.viewer.quadrants import build_report


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def saved_run(project, runs):
    run = runs / 'saved'
    source = 'reports/run/source'
    config = {'dataset': {'source_run': source}, 'models': [{'key': 'demo', 'model': 'gpt-6-luna'}]}
    write(run / 'config.json', json.dumps(config))
    write(project / source / 'results/00-input.json', json.dumps([
        {'id': case, 'input': {'provenance': {'dataset': 'TAT-QA'}}} for case in ('one', 'two')]))
    private, public, matrix, pairs = [], [], [], []
    for feature in view.FEATURE_INDEX:
        choice = 'ORIGINAL_VALUE' if feature.startswith('EA_') else 'A'
        rows, groups = fixture(feature, choice)
        matrix.extend(rows)
        pairs.extend(groups)
        for case in ('one', 'two'):
            item = f'{case}/{feature}'
            private.append({'case': case, 'item_id': item, 'variant': feature,
                            'source': source + '/results/input.json', 'reference': 20, 'alternative_answer': 21})
            public.append({'item_id': item})
    for name, rows in [('private', private), ('public', public)]:
        write(run / f'00_input/{name}.jsonl', '\n'.join(json.dumps(row) for row in rows) + '\n')
    responses = run / '02_analysis/01_results/responses.jsonl'
    write(responses, '{}\n')
    write(run / '02_analysis/02_comparison/comparisons.json', json.dumps({
        'response_rows_sha256': view.sha(responses), 'generated_at': '2026-10-03T00:00:00+00:00',
        'matrix': matrix, 'paired_groups': pairs}))
    for name in view.CONTRACT_FILES:
        write(run / '01_evaluation/02_request' / name, '{}')
    return run


class ViewerQuadrantTests(unittest.TestCase):
    def test_custom_root_is_read_and_source_files_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project, runs = base / 'project', base / 'custom-runs'
            saved_run(project, runs)
            before = {str(path): view.sha(path) for path in base.rglob('*') if path.is_file()}
            report = build_report(runs, project)
            self.assertEqual(report['metadata']['inventory_summary'], {'INCLUDED': 1})
            self.assertEqual(report['metadata']['model_calls'], 0)
            self.assertIn('"viewer":true', report['html'])
            self.assertIn('"FORMAT_OR_EXECUTION_FAILED":1', report['html'])
            self.assertEqual(before, {str(path): view.sha(path) for path in base.rglob('*') if path.is_file()})

    def test_empty_custom_root_cannot_fall_back_to_project_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            saved_run(project, project / 'reports/experiments-run')
            with self.assertRaisesRegex(ValueError, 'NO_COMPARABLE_SAVED_RESULTS'):
                build_report(project / 'empty-runs', project)

    def test_changed_saved_responses_are_not_shown_as_current_results(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            run = saved_run(project, project / 'reports/experiments-run')
            write(run / '02_analysis/01_results/responses.jsonl', '{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'NO_COMPARABLE_SAVED_RESULTS'):
                build_report(project / 'reports/experiments-run', project)

    def test_saved_text_cannot_escape_the_json_script(self):
        html = view.render_page({'unsafe': '</script><script>bad()</script>'})
        self.assertNotIn('</script><script>bad()', html)
        self.assertIn('\\u003c/script>', html)


if __name__ == '__main__':
    unittest.main()
