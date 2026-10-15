"""Retry a failed independent calculation without replacing earlier evidence."""
import argparse
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.schemas.llm import executable_program
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
resolve_mismatch = __import__('finarch.dataset.01-preparation.03-calculation.preparation_repairs', fromlist=['resolve_mismatch']).resolve_mismatch
from finarch.dataset.shared.calculation.python_graph import compile_graph
publish = __import__('finarch.dataset.01-preparation.01-source.working_data', fromlist=['publish']).publish


def resume(case, config, independent_source=None,evidence_source=None):
    case=Path(case); report=read(case/'run.json')
    if report['status']!='FAIL':raise ValueError('FAILED_CASE_REQUIRED')
    decision=case/'07-human-review/02-record-decision/decision.json'
    if decision.exists():raise ValueError('REVIEWED_CASE_REQUIRES_EXPLICIT_REOPEN')
    ctx=RunContext.resume(case,{},case.name)
    parent=case/'03-calculation/07-retry-mismatch'
    number=len(list(parent.glob('attempt-*')))+1
    stage=f'03-calculation/07-retry-mismatch/attempt-{number:02d}'
    sample=read(case/'data.json')
    generated=read(case/'03-calculation/01-LLM-generate-code/03-result.json')['data']
    program,_=name_constants(executable_program(generated))
    execution=read(case/'03-calculation/03-execute-python/03-result.json')['data']
    with ctx.trace.activate():
        ctx.save(stage+'/before-report.json',report)
        try:
            working,program,execution,comparison=resolve_mismatch(ctx,config,sample,program,execution,stage=stage,independent_source=independent_source,evidence_source=evidence_source)
            graph,value,_=compile_graph({**program,'context':working['context']})
            values={n['id']:n['computed'] for n in graph['nodes']}
            if str(value)!=execution['exact_value'] or any(values[key]!=execution['trace'].get(name) for name,key in graph['variables'].items()):raise ValueError('PYTHON_GRAPH_MISMATCH')
            publish(ctx,read(case/'01-source/01-receive-input/01-input.json'),working,read(case/'02-review-and-correct/accepted-audit.json'))
            ctx.save('03-calculation/02-prepare-code/03-program.json',program)
            ctx.save('03-calculation/04-compare-answer/01-comparison.json',comparison)
            ctx.save('04-graph/03-compare-calculation/01-result.json',{'status':'PASS','correction_ref':stage})
            ctx.save('04-graph/04-save-graph/01-graph.json',graph)
            report.update(status='PASS',reason='AWAITING_HUMAN_REVIEW',correction_ref=stage)
        except Exception as error:
            report.update(status='FAIL',reason=str(error),correction_ref=stage)
        ctx.save(stage+'/final-report.json',report)
        ctx.save_text(stage+'/README.md','Read before-report, independent solution, evidence review, correction, and final-report in that order. Previous attempts and raw responses remain unchanged. Human approval remains required.\n')
        write(case/'run.json',report)
        write(case/'07-human-review/01-collect-results/01-result.json',report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--config',required=True)
    parser.add_argument('--independent-source')
    parser.add_argument('--evidence-source')
    args=parser.parse_args();print(resume(args.case,args.config,args.independent_source,args.evidence_source),flush=True)
