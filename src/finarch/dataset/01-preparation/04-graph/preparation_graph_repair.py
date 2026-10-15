"""Rebuild failed graphs after a verified syntax-only working-program correction."""
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.python_graph import compile_graph


def repair(case):
    case=Path(case);report=read(case/'run.json')
    if report['status']!='FAIL' or 'GRAPH_REQUIRES_NAMED_STRAIGHT_LINE_ASSIGNMENTS' not in report.get('reason',''):return None
    decision=case/'07-human-review/02-record-decision/decision.json'
    if decision.exists() and read(decision).get('decision')=='APPROVED':raise ValueError('APPROVED_PROGRAM_REQUIRES_NEW_REVIEW')
    sample=read(case/'data.json');program=read(case/'03-calculation/02-prepare-code/03-program.json')
    fixed,changes=name_constants(program)
    if not changes['annotation_changes']:raise ValueError('NO_SUPPORTED_SYNTAX_CORRECTION')
    ctx=RunContext.resume(case,{},case.name);stage='03-calculation/06-normalize-program'
    with ctx.trace.activate(),ctx.trace.span('preparation.normalize_program',kind='python',stage=stage):
        ctx.save(stage+'/01-before.json',program);ctx.save(stage+'/02-changes.json',changes)
        before=execute({**program,'context':sample['context']});after=execute({**fixed,'context':sample['context']})
        ctx.save(stage+'/03-execution-comparison.json',{'before':before.__dict__,'after':after.__dict__})
        if before.status!='PASS' or after.status!='PASS' or before.data['exact_value']!=after.data['exact_value'] or before.data['trace']!=after.data['trace']:
            raise ValueError('NORMALIZATION_CHANGED_CALCULATION')
        graph,value,_=compile_graph({**fixed,'context':sample['context']})
        values={n['id']:n.get('computed') for n in graph['nodes']}
        if str(value)!=after.data['exact_value'] or any(values[key]!=after.data['trace'].get(name) for name,key in graph['variables'].items()):raise ValueError('REBUILT_GRAPH_MISMATCH')
        if read(case/'03-calculation/04-compare-answer/01-comparison.json').get('matches') is not True:raise ValueError('ORIGINAL_COMPARISON_NOT_PASSED')
        ctx.save(stage+'/04-after.json',fixed)
        write(case/'03-calculation/02-prepare-code/03-program.json',fixed)
        ctx.trace.artifact('03-calculation/02-prepare-code/03-program.json',fixed)
        ctx.save('04-graph/05-rebuild-graph/01-result.json',{'status':'PASS','graph':graph,'correction_ref':stage})
        ctx.save('04-graph/04-save-graph/01-graph.json',graph)
        ctx.save('07-human-review/01-collect-results/before-graph-repair.json',report)
        report.update(status='PASS',reason='AWAITING_HUMAN_REVIEW',correction_ref=stage)
        write(case/'run.json',report);write(case/'07-human-review/01-collect-results/01-result.json',report)
        ctx.save_text(stage+'/README.md','Read original program, syntax changes, equivalent Python executions, and corrected program. The original model response remains unchanged. The graph was rebuilt without another model call.\n')
    return report
