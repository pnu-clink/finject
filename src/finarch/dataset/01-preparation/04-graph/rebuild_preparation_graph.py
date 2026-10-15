"""Rebuild a saved POT graph locally while preserving review and failure history."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute


def promote_verified_graph(case):
    """Publish a verified graph repair as current status, independently of review."""
    snapshot = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['snapshot']).snapshot
    case=Path(case).resolve();verification=read(case/'graph-repair.json')
    snapshot(case)
    program_path=case/'03-calculation/02-prepare-code/03-program.json'
    if verification.get('status')!='PASS' or hashlib.sha256(program_path.read_bytes()).hexdigest()!=verification['program_sha256']:
        raise ValueError('GRAPH_REPAIR_STALE')
    payload={**read(program_path),'context':read(case/'data.json')['context']}
    expected,value,_=compile_graph(payload)
    graph=read(case/'04-graph/04-save-graph/01-graph.json')
    if expected!=graph:raise ValueError('GRAPH_REPAIR_STALE')
    execution=execute(payload)
    if execution.status!='PASS' or str(value)!=execution.data['exact_value'] or any(
        execution.data['trace'].get(n['variable'])!=n['computed'] for n in graph['nodes'] if n['kind']=='variable'):
        raise ValueError('PYTHON_GRAPH_MISMATCH')
    current=read(case/'run.json')
    current.update(status='PASS',reason='GRAPH_REPAIR_VERIFIED',
                   resolved_failure=current.get('resolved_failure',current.get('reason')),
                   graph_repair='graph-repair.json')
    current.pop('stopped_at',None)
    decision_path=case/'07-human-review/02-record-decision/decision.json'
    if decision_path.exists():
        decision=read(decision_path)
        current['human_decision']=decision['decision']
        current['allow_next_stage']=decision['decision']=='APPROVED' and decision.get('files')==snapshot(case)
    write(case/'run.json',current)
    write(case/'07-human-review/01-collect-results/01-result.json',current)
    summary_path=case.parent/'summary.json'
    if summary_path.exists():
        summary=read(summary_path)
        archive=case/verification['previous_artifacts']/'batch-summary-before-promotion.json'
        if not archive.exists():write(archive,summary)
        summary['results']=[current if r.get('input_id')==case.name else r for r in summary['results']]
        write(summary_path,summary)
    write(case/'graph-repair-promotion.json',{'status':'PASS','reason':'Current automatic result updated after local revalidation',
          'previous_artifacts':verification['previous_artifacts'],'human_decision_changed':False,
          'recorded_at':datetime.now(timezone.utc).isoformat()})
    write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
    write_index(case)
    return current


def rebuild(case):
    case=Path(case).resolve()
    program_path=case/'03-calculation/02-prepare-code/03-program.json'
    payload={**read(program_path),'context':read(case/'data.json')['context']}
    result=execute(payload)
    if result.status!='PASS':raise ValueError('SAVED_PYTHON_EXECUTION_FAILED:'+result.reason)
    graph,value,normalization=compile_graph(payload)
    mismatches=[name for name,key in graph['variables'].items()
                if result.data['trace'].get(name)!=next(n['computed'] for n in graph['nodes'] if n['id']==key)]
    if str(value)!=result.data['exact_value'] or mismatches:
        raise ValueError('PYTHON_GRAPH_MISMATCH:'+str(mismatches))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive=case/'graph-repair-history'/stamp
    archive.mkdir(parents=True)
    for relative in ('run.json','04-graph','07-human-review/01-collect-results/01-result.json'):
        source=case/relative;target=archive/relative
        if source.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            if source.is_dir():shutil.copytree(source,target)
            else:shutil.copy2(source,target)
    ctx=RunContext.resume(case,{},case.name)
    if (case/'04-graph').exists():shutil.rmtree(case/'04-graph')
    with ctx.trace.activate():
        ctx.save('04-graph/01-read-calculation/01-input.json',{'program':payload,'execution':result.data})
        ctx.invoke('04-graph','02-build-graph','dag.compile',payload,
                   local=lambda p:StepResult('PASS','Saved Python and graph values match',
                       {'graph':graph,'exact_value':str(value),'normalization':normalization}))
        verification={'status':'PASS','python_exact_value':result.data['exact_value'],
                      'graph_exact_value':str(value),'checked_variables':len(graph['variables']),
                      'mismatches':mismatches,'program_sha256':hashlib.sha256(program_path.read_bytes()).hexdigest(),
                      'previous_artifacts':str(archive.relative_to(case)),'llm_calls':0,
                      'review_decision_changed':False,'verified_at':stamp}
        ctx.save('04-graph/03-compare-calculation/01-result.json',verification)
        ctx.save('04-graph/04-save-graph/01-graph.json',graph)
        ctx.save_text('04-graph/README.md',Path(__file__).with_name('graph-repair-readme.md').read_text())
    # Preserve old results in history, and publish the verified current result.
    write(case/'graph-repair.json',verification)
    write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
    write_index(case)
    promote_verified_graph(case)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('case')
    print(json.dumps(rebuild(parser.parse_args().case),indent=2))
