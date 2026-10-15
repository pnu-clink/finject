"""Retry an entirely uncalled batch after native-control verification succeeds."""
import argparse
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
measure = __import__('finarch.dataset.90-operations.execution_timing', fromlist=['measure']).measure
prepare_batch = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['prepare_batch']).prepare_batch
from finarch.shared.providers.cli import inspect_runtime, read_settings


def run(bundle):
    bundle=Path(bundle).resolve()
    selection=read(bundle/'input-selection.json')
    config=bundle/'config.json'
    settings=read_settings(config,'shared.01-02.02-03.review-and-validation')
    if inspect_runtime(settings['provider'])['native_tool_enforcement']!='VERIFIED':
        raise ValueError('NATIVE_CONTROLS_NOT_VERIFIED')
    source=bundle/'01-preparation'
    for name in selection['cases']:
        case=source/name
        report=read(case/'run.json')
        if report.get('audit',{}).get('reason')!='NATIVE_TOOL_ENFORCEMENT_UNVERIFIED':
            raise ValueError('BATCH_HAS_NON_PREFLIGHT_RESULT')
        if list(case.rglob('cli-start.json')) or list(case.rglob('cli-execution.json')):
            raise ValueError('BATCH_HAS_CALL_EVIDENCE')
        if list((case/'07-human-review').rglob('decision.json')):
            raise ValueError('BATCH_HAS_HUMAN_DECISION')
    archive=bundle/'00-preflight-attempts/01-native-controls-unverified'
    archive.mkdir(parents=True,exist_ok=False)
    source.rename(archive/'01-preparation')
    for name in ('summary.json','review-gate.json','timing.json'):
        path=bundle/name
        if path.exists():path.rename(archive/name)
    write(archive/'retry.json',{'reason':'Native control verification refreshed; no previous model call was started.','human_decisions_reused':False})
    (archive/'README.md').write_text('호출 전 차단된 기록을 보존합니다. 모델 호출·사람 판정이 없음을 확인한 뒤 같은 실행에서 처음부터 재시도했습니다. 현재 결과는 런의 01-preparation에서 확인합니다.\n')
    with measure(bundle,'preparation'):
        result=prepare_batch(bundle,PreparedInputs(Path(selection['input_path'])),selection['cases'],config)
        write(bundle/'summary.json',result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    print(run(parser.parse_args().run))
