"""Continue a completed first round through the existing bounded feedback loop."""
import argparse
import json
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
finish_rounds = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['finish_rounds']).finish_rounds
save = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['save']).save


def run(run_id, maximum_rounds=3):
    if Path(run_id).name != run_id:
        raise ValueError('INVALID_RUN_ID')
    root=Path('reports/run')/run_id
    first=root/'01-round'
    progress=json.loads((first/'production-progress.json').read_text())
    settings=json.loads((root/'config.json').read_text())
    if progress['status']!='FINISHED' or settings['execution_enabled']:
        raise ValueError('FIRST_ROUND_MUST_BE_FINISHED')
    if (root/'02-round').exists():
        raise ValueError('CONTINUATION_ALREADY_STARTED')
    argv=[sys.executable,'-m','finarch.dataset.02-generation.operations.continue_feedback',run_id,'--maximum-rounds',str(maximum_rounds)]
    started=datetime.now().astimezone().isoformat(sep=' ',timespec='milliseconds')
    clock=time.monotonic()
    logs=RunLogs.for_case(root)
    record={'argv':argv,'command':'PYTHONPATH=src '+shlex.join(argv),'cwd':str(Path.cwd()),
            'started_at':started,'maximum_rounds':maximum_rounds}
    logs.write('cli.log','production.continue_feedback',phase='START',value=record)
    print(json.dumps({'event':'START',**record}),flush=True)
    settings.update(execution_enabled=True,maximum_rounds=maximum_rounds)
    save(root/'config.json',settings)
    status='ERROR'
    try:
        result=finish_rounds(root,first,root/'config.json',maximum_rounds=maximum_rounds)
        status=result['status']
        return result
    finally:
        settings['execution_enabled']=False
        save(root/'config.json',settings)
        record.update(ended_at=datetime.now().astimezone().isoformat(sep=' ',timespec='milliseconds'),
                      elapsed_seconds=round(time.monotonic()-clock,3),status=status)
        save(root/'continuation-timing.json',record)
        logs.write('cli.log','production.continue_feedback',phase='END',value=record)
        print(json.dumps({'event':'END',**record}),flush=True)
        from finarch.dataset.viewer.reports.timing_report import build as timing_report
        timing_report(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('--maximum-rounds',type=int,choices=(2,3),default=3)
    args=parser.parse_args()
    run(args.run_id,args.maximum_rounds)
