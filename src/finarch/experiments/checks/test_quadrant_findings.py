"""Check finding-only scope, complete grouping and traceable condition summaries."""
import copy
import importlib
from pathlib import Path
import tempfile
import unittest

from finarch.experiments import assets

grouping = importlib.import_module('finarch.experiments.02-analysis.04-quadrant.01-findings.grouping')
contracts = importlib.import_module('finarch.experiments.02-analysis.contracts')


def grouped_response(request):
    members = request['input']['findings']
    profiles = []
    for condition in grouping.CONDITIONS:
        eligible = [f for f in members if condition in f['cited_conditions']]
        profiles.append({'condition': condition, 'finding_ids': [f['id'] for f in eligible],
            'analysis': 'Shared recorded finding.' if eligible else 'No cited findings.',
            'display_ko': {'analysis': '저장된 발견 공유.' if eligible else '인용 발견 없음.'},
            'citations': [{'finding_id': eligible[0]['id'], 'field': 'claim', 'quote': eligible[0]['claim']}] if eligible else []})
    return {'run': request['input']['run'], 'groups': [{'id': 'G01', 'title': 'Shared topic',
        'summary': 'Saved findings only.', 'display_ko': {'title': '공통 주제', 'summary': '저장된 발견만.'},
        'finding_ids': [f['id'] for f in members], 'condition_profiles': profiles}]}


class FindingGroupsTest(unittest.TestCase):
    def setUp(self):
        self.findings = [{'id': 'F001', 'title': 'Finding', 'claim': 'An explicit claim.',
            'alternatives': 'Another explanation.', 'limitation': 'No causal identification.',
            'decision': 'ACCEPT_DESCRIPTIVE', 'interpretation_ids': ['O1']}]
        self.observations = [{'id': 'O1', 'response_ids': ['R1', 'R2'], 'observation': 'Not an input finding.'}]
        self.responses = [{'response_id': 'R1', 'case': 'C1', 'model': 'target', 'variant': 'EA_01', 'prompt_condition': 'unguided', 'reasoning': 'off'},
                          {'response_id': 'R2', 'case': 'C1', 'model': 'target', 'variant': 'EA_01', 'prompt_condition': 'guided', 'reasoning': 'on'}]
        self.linked = grouping.trace(self.findings, self.observations, self.responses)
        self.request = {'stage': '04_quadrant', 'response_schema': assets.schema('quadrant_response'),
                        'input': {'run': 'fixture', 'findings': grouping.model_input(self.linked)}}
        self.value = grouped_response(self.request)

    def test_only_findings_enter_request_and_originals_are_preserved(self):
        self.assertNotIn('observation', str(self.request['input']))
        self.assertNotIn('discussion', self.request['input'])
        self.assertEqual(contracts.validate_response(self.value, self.request), [])
        collected = grouping.collect(self.value, self.linked)
        self.assertEqual(collected['findings'][0]['finding'], self.findings[0])
        self.assertEqual(collected['counts']['findings'], 1)
        self.assertEqual(collected['counts']['condition_mentions'], 2)
        self.assertEqual([c['finding_count'] for c in collected['cells']], [1, 0, 0, 1])

    def test_unknown_provenance_blocks_before_model_call(self):
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_RESPONSE'):
            grouping.trace(self.findings, self.observations, self.responses[:1])
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_OBSERVATION'):
            grouping.trace(self.findings, [], self.responses)

    def test_non_finding_cannot_be_grouped(self):
        self.findings[0]['id'] = 'D001'
        with self.assertRaisesRegex(ValueError, 'FINDINGS_ONLY'):
            grouping.trace(self.findings, self.observations, self.responses)

    def test_missing_or_duplicate_members_cannot_pass(self):
        for mutate in ('missing', 'duplicate', 'unknown'):
            value = copy.deepcopy(self.value)
            if mutate == 'missing': value['groups'] = []
            elif mutate == 'duplicate': value['groups'].append({**value['groups'][0], 'id': 'G02'})
            else: value['groups'][0]['finding_ids'].append('F999')
            self.assertTrue(contracts.validate_response(value, self.request), mutate)

    def test_condition_links_cannot_be_invented_or_omitted(self):
        for index, ids in ((0, []), (1, ['F001'])):
            value = copy.deepcopy(self.value)
            value['groups'][0]['condition_profiles'][index]['finding_ids'] = ids
            self.assertTrue(contracts.validate_response(value, self.request))

    def test_invented_quotes_cannot_pass(self):
        self.value['groups'][0]['condition_profiles'][0]['citations'][0]['quote'] = 'Invented quote.'
        self.assertTrue(contracts.validate_response(self.value, self.request))

    def test_all_four_profiles_required(self):
        self.value['groups'][0]['condition_profiles'].pop()
        self.assertTrue(contracts.validate_response(self.value, self.request))

    def test_unfinished_a03_blocks_before_reading_findings_or_calling_model(self):
        pipeline = importlib.import_module('finarch.experiments.02-analysis.04-quadrant.pipeline')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline.store.write(root / '02_analysis/03_research/state.json', {'status': 'RUNNING'})
            with self.assertRaisesRegex(ValueError, 'REQUIRES_COMPLETED_A03'):
                pipeline.prepare(root)
            self.assertFalse((root / '02_analysis/04_quadrant').exists())


if __name__ == '__main__':
    unittest.main()
