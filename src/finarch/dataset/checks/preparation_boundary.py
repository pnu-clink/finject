"""Offline checks for batch review and source-before-POT ordering."""
import tempfile
from pathlib import Path
from unittest.mock import patch

REQUIRED = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['REQUIRED']).REQUIRED
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
require_generation_inputs = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['require_generation_inputs']).require_generation_inputs
original_request = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['original_request']).original_request
run_case = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['run_case']).run_case


def run():
    with tempfile.TemporaryDirectory() as temporary:
        bundle = Path(temporary)
        write(bundle / 'input-selection.json', {'cases': ['test-0001', 'test-0002']})
        for name in ('test-0001', 'test-0002'):
            case = bundle / '01-preparation' / name
            for kind, relative in REQUIRED.items():
                write(case / relative, {'status': 'PASS'} if kind == 'audit' else {'matches': True} if kind == 'comparison' else {'value': kind})
        first = bundle / '01-preparation/test-0001'
        from finarch.dataset.viewer.server import save_preparation_review, batch_data
        from finarch.dataset.viewer.build import collect
        payload={'case':'test-0001','review':{'decision':'APPROVED','reviewer':'offline-test','snapshot_sha256':collect(first,allow_partial=True)['snapshot_sha256']}}
        result=save_preparation_review(bundle,payload)
        assert not result['review_gate']['allow_generation']
        for number,status in ((1,'FAIL'),(2,'PASS')):
            write(bundle/f'02-generation/{number:02d}-round/test-0001/01-ic-value-before/03-validation/03-result.json',{'status':status})
        first_round=batch_data(bundle.parent,bundle.name,'01-round')
        second_round=batch_data(bundle.parent,bundle.name,'02-round')
        artifact='01-ic-value-before/03-validation/03-result.json'
        assert first_round['runs'][0]['generation'][artifact]['status']=='FAIL'
        assert second_round['runs'][0]['generation'][artifact]['status']=='PASS'
        assert not first_round['runs'][1]['generation']
        try:
            save_preparation_review(bundle,payload)
        except ValueError as error:
            assert str(error)=='REVIEW_SNAPSHOT_CHANGED'
        else:
            raise AssertionError('Stale viewer review was accepted')
        record_decision(first, 'APPROVED', 'offline-test')
        assert not evaluate(bundle)['allow_generation']
        record_decision(bundle / '01-preparation/test-0002', 'REJECTED', 'offline-test', 'Excluded fixture')
        assert list(require_generation_inputs(bundle)) == ['test-0001']
        write(first / REQUIRED['working_input'], {'value': 'modified'})
        assert evaluate(bundle)['invalid'][0]['reason'] == 'APPROVED_INPUT_CHANGED'
        try:
            require_generation_inputs(bundle)
        except ValueError as error:
            assert str(error) == 'PREPARATION_REVIEW_INCOMPLETE'
        else:
            raise AssertionError('Changed approval was accepted')
    sample = {'context': 'Source text.', 'question': 'Which value?', 'reference_answer': 'secret'}
    assert 'reference_answer' not in original_request(sample)
    class Inputs:
        def case(self, name):
            return {'sample': sample, 'comparison': {'status': 'PASS'}}
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / 'config.json'
        write(config, {'preparation_revision_attempts': 0})
        with patch.object(__import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['*']), 'audit_one', return_value={'status': 'FAIL'}), patch.object(__import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['*']), 'calculate') as calculate:
            report = run_case(Inputs(), 'test-0001', Path(temporary) / 'case', config)
            assert report['reason'] == 'ORIGINAL_AUDIT_NOT_PASSED'
            calculate.assert_not_called()
    return {'status': 'PASS', 'checks': ['generation_round_isolation', 'missing_generation_not_inherited', 'viewer_review_saved', 'stale_viewer_review_rejected', 'batch_review_required', 'approved_only', 'changed_input_invalidates_approval', 'gold_not_in_original_audit', 'failed_original_blocks_POT'], 'model_calls': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(run()))
