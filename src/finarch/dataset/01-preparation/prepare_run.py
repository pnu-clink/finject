"""Execute one preparation case within an explicit stage range."""
import argparse
import json
from pathlib import Path
PreparedInputs = __import__('finarch.dataset.90-operations.staging', fromlist=['PreparedInputs']).PreparedInputs
PREPARATION = __import__('finarch.dataset.90-operations.stage_range', fromlist=['PREPARATION']).PREPARATION
select = __import__('finarch.dataset.90-operations.stage_range', fromlist=['select']).select

from importlib import import_module
begin = __import__('finarch.dataset.90-operations.stage_range', fromlist=['begin']).begin
finish = __import__('finarch.dataset.90-operations.stage_range', fromlist=['finish']).finish
require = __import__('finarch.dataset.90-operations.stage_range', fromlist=['require']).require
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
p01_source = import_module("finarch.dataset.01-preparation.01-source.stage")
p02_review = import_module("finarch.dataset.01-preparation.02-review.stage")
p03_calculation = import_module("finarch.dataset.01-preparation.03-calculation.stage")
p04_graph = import_module("finarch.dataset.01-preparation.04-graph.stage")
p05_verification = import_module("finarch.dataset.01-preparation.05-verification.stage")
p06_exception_handler = import_module("finarch.dataset.01-preparation.06-exception-handler.stage")
p07_human_review = import_module("finarch.dataset.01-preparation.07-human-review.stage")


def run(inputs, name, output, config, *, start_stage=None, stop_after=None, only_stage=None, round_number=1, reuse_before=None):
    selected = select(PREPARATION, start_stage, stop_after, only_stage)
    try:
        return execute(inputs, name, Path(output), config, selected, round_number=round_number, reuse_before=reuse_before)
    except Exception as error:
        # Missing prerequisites also belong to the case, not the batch worker.
        RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
        root = Path(output)
        ctx = RunContext.resume(root, {}, name) if root.exists() else RunContext(root, {}, name)
        result = {'input_id': name, 'status': 'FAIL', 'reason': str(error),
                  'stopped_at': selected[0], 'human_decision': 'PENDING'}
        with ctx.trace.activate():
            try:
                result['recovery'] = p06_exception_handler.run(ctx, config, result, error, round_number=round_number)
            except Exception as handler_error:
                result['recovery'] = {'retryable': False, 'handler_error': str(handler_error)}
                ctx.save('06-exception-handler/04-route-retry/handler-failure.json', result['recovery'])
            return finish(ctx, result, selected)

def execute(inputs, name, root, config, selected, *, round_number=1, reuse_before=None):
    root=Path(root);sample=inputs.case(name)['sample'];original=sample
    start=reuse_before or selected[0]
    if start!='01-source':
        sample=require(root,['01-source/01-receive-input/01-input.json'])['01-source/01-receive-input/01-input.json'];original=sample
    if PREPARATION.index(start)>=2:
        values=require(root,['02-review/accepted-audit.json','data.json'])
        if values['02-review/accepted-audit.json']['status']!='PASS':raise ValueError('SOURCE_REVIEW_REQUIRED')
        sample=values['data.json']
    calculation=None
    if start=='04-graph':
        if (root/'03-calculation/05-record-calculation-artifacts/01-stage-output.json').exists():calculation=read(root/'03-calculation/05-record-calculation-artifacts/01-stage-output.json')
        else:calculation=require(root,['04-graph/01-read-calculation/01-input.json'])['04-graph/01-read-calculation/01-input.json']
    if start in ('05-verification', '07-human-review'):
        values=require(root,['04-graph/02-build-graph/04-comparison.json'])
        if values['04-graph/02-build-graph/04-comparison.json']['status']!='PASS':raise ValueError('GRAPH_PASS_REQUIRED')
    if start == '07-human-review':
        verdict = require(root, ['05-verification/08-record-verdict/01-result.json'])['05-verification/08-record-verdict/01-result.json']
        if verdict['status'] != 'PASS': raise ValueError('VERIFICATION_PASS_REQUIRED')
    active = selected[selected.index(start):]
    ctx=begin(root,PREPARATION,active,name)
    result={'input_id':name,'status':'RUNNING','layout':'preparation-generation-v1','human_decision':'PENDING'}
    with ctx.trace.activate():
        try:
            for stage in selected:
                result['stopped_at']=stage
                if reuse_before and PREPARATION.index(stage) < PREPARATION.index(reuse_before):
                    result.setdefault('reused_steps', []).append(stage)
                    continue
                if stage == '01-source':
                    _, sample = p01_source.run(ctx, inputs, name)
                    original = sample
                elif stage=='02-review':
                    sample,audit=p02_review.run(ctx,config,sample,read(config).get('preparation_revision_attempts',0))
                    if audit['status']!='PASS':raise ValueError('ORIGINAL_REVIEW_NOT_PASSED')
                    ctx.save(stage+'/accepted-input.json',sample);ctx.save(stage+'/accepted-audit.json',audit)
                    import_module('finarch.dataset.01-preparation.01-source.working_data').publish(ctx,original,sample,audit)
                elif stage=='03-calculation':
                    p03_calculation.run(ctx,config,sample,result,include_graph=False)
                    calculation=read(root/'03-calculation/05-record-calculation-artifacts/01-stage-output.json');sample=calculation['sample']
                elif stage == '04-graph':
                    p04_graph.run(ctx, sample, calculation['program'], calculation['execution'], result)
                elif stage == '05-verification':
                    p05_verification.run(ctx, config, result)
                else:
                    result.update(status='PASS',reason='AWAITING_HUMAN_REVIEW')
                    p07_human_review.run(ctx,result)
            result.update(status='PASS' if selected[-1]==PREPARATION[-1] else 'PAUSED',reason='AWAITING_HUMAN_REVIEW' if selected[-1]==PREPARATION[-1] else 'REQUESTED_STAGE_BOUNDARY')
        except Exception as error:
            result.update(status='FAIL', reason=str(error))
            try:
                result['recovery'] = p06_exception_handler.run(ctx, config, result, error, round_number=round_number)
            except Exception as handler_error:
                result['recovery'] = {'retryable': False, 'handler_error': str(handler_error)}
                ctx.save('06-exception-handler/04-route-retry/handler-failure.json', result['recovery'])
        return finish(ctx,result,selected)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--config',required=True)
    parser.add_argument('--start-stage');parser.add_argument('--stop-after');parser.add_argument('--only-stage')
    args=parser.parse_args()
    print(json.dumps(run(PreparedInputs(Path(args.input)),args.case,args.output,args.config,
        start_stage=args.start_stage,stop_after=args.stop_after,only_stage=args.only_stage)))

if __name__=='__main__':main()
