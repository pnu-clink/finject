"""Expose the executed POT graph without certifying a mismatched answer."""
from pathlib import Path
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
from finarch.dataset.schemas.llm import executable_program
from finarch.dataset.shared.calculation.python_graph import compile_graph


def build(case):
    case=Path(case);report=read(case/'run.json')
    sample=read(case/'data.json')
    program,_=name_constants(executable_program(read(case/'03-calculation/01-LLM-generate-code/03-result.json')['data']))
    execution=read(case/'03-calculation/03-execute-python/03-result.json')['data']
    graph,value,_=compile_graph({**program,'context':sample['context']})
    values={n['id']:n['computed'] for n in graph['nodes']}
    if str(value)!=execution['exact_value'] or any(values[k]!=execution['trace'].get(n) for n,k in graph['variables'].items()):
        raise ValueError('DIAGNOSTIC_GRAPH_EXECUTION_MISMATCH')
    ctx=RunContext.resume(case,{},case.name)
    stage='04-graph/00-diagnostic'
    with ctx.trace.activate():
        ctx.save(stage+'/01-result.json',{'status':'DIAGNOSTIC_ONLY','graph':graph,'program':program,'calculation_matches_execution':True,'source_status':report['status'],'source_reason':report.get('reason'),'approved_for_generation':False})
        ctx.save_text(stage+'/README.md','실행된 POT 코드에서 만든 진단용 그래프입니다. 중간·최종값은 Python 실행과 대조했습니다. 정답·계산 가정의 타당성이나 Generation 승인을 의미하지 않습니다. 기존 실패·제외 판정은 유지됩니다.\n')
    return str(case/stage/'01-result.json')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);print(build(p.parse_args().case))
