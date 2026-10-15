"""Offline orchestration checks; fake responses never enter production runs."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
REQUIRED = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['REQUIRED']).REQUIRED
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
run = __import__('finarch.dataset.02-generation.generate_schedule', fromlist=['run']).run


def check():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)/'test';root.mkdir()
        write(root/'input-selection.json',{'cases':['test-0001']})
        write(root/'config.json',{})
        case=root/'01-preparation/test-0001'
        for key,path in REQUIRED.items():write(case/path,{'status':'PASS'} if key=='audit' else {'matches':True} if key=='comparison' else {})
        try:run(root)
        except ValueError as error:assert str(error)=='PREPARATION_REVIEW_INCOMPLETE'
        else:raise AssertionError('Generation bypassed human review')
        record_decision(case,'APPROVED','offline-fixture')
        calls=[];feedback_calls=[]
        def process(bundle,round_dir,name,index,config,approved,latest):
            calls.append((round_dir.name,index))
            fail=round_dir.name=='01-round' and index==0
            return {'label':str(index),'axis':'IC_VALUE','status':'FAIL' if fail else 'PASS','path':str((round_dir/name/str(index)).relative_to(bundle)),'restart':'02-generate-text','reason':'fixture failure' if fail else ''}
        with patch.object(__import__('finarch.dataset.02-generation.generate_schedule', fromlist=['*']), 'process',side_effect=process),patch.object(__import__('finarch.dataset.02-generation.generate_schedule', fromlist=['*']), 'feedback',side_effect=lambda *args:feedback_calls.append(args[1].name)):
            result=run(root)
        assert result['status']=='PASS'
        assert [i for r,i in calls if r=='01-round']==list(range(7))
        assert [i for r,i in calls if r=='02-round']==[0,1,2,3]
        assert not any(r=='03-round' for r,i in calls)
        assert feedback_calls==['01-round']
        assert result['latest']['test-0001'][4]['path'].startswith('02-generation/01-round/')
        try:run(root)
        except ValueError as error:assert str(error)=='GENERATION_ALREADY_STARTED'
        else:raise AssertionError('Existing generation was overwritten')
    return {'status':'PASS','model_calls':0,'checks':['human_review_gate','all_seven_initial_types','retry_failed_and_dependents_only','successful_types_preserved','early_stop','single_feedback_for_failed_round','existing_run_not_overwritten']}


if __name__=='__main__':print(json.dumps(check()))
