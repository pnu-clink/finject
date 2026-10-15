"""One fresh POT call, followed by local source/runtime/graph verification."""
import argparse
import json
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.shared.providers.cli import call
from finarch.dataset.schemas.llm import executable_program
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
from finarch.dataset.shared.calculation.external_evidence import publish
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.python_graph import compile_graph


def run(case,config,saved_response=None):
    case=Path(case).resolve();root=case/'external-evidence-review'
    if root.exists():
        from datetime import datetime, timezone
        root=case/('external-evidence-review-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    ctx=RunContext(root,{},case_id=case.name)
    ctx.save_text('README.md',Path(__file__).with_name('external-evidence-readme.md').read_text())
    request=read(case/'03-calculation/01-LLM-generate-code/01-input.json')
    report={'status':'FAIL','scope':'External evidence candidate; existing decision preserved','llm_calls':0 if saved_response else 1}
    try:
        if saved_response:
            import ast
            original=read(saved_response)['data'];program=executable_program(original)
            ctx.save('03-calculation/01-LLM-generate-code/saved-response.json',{'path':str(saved_response),'original':original,'new_llm_call':False})
            try:ast.parse(program['code'])
            except IndentationError as error:
                if error.msg!='unexpected indent':raise
                lines=program['code'].splitlines(keepends=True);before=lines[error.lineno-1]
                lines[error.lineno-1]=before.lstrip(' \t');fixed=''.join(lines);ast.parse(fixed)
                program['code']=fixed
                ctx.save('03-calculation/02-prepare-code/syntax-repair.json',{'kind':'Remove unexpected leading whitespace','line':error.lineno,'before':before,'after':lines[error.lineno-1]})
        else:
            sample=read(case/'data.json')
            request.update({key:sample[key] for key in ('reference_answer_type','reference_precision')})
            request['answer_metadata']={key:sample['answer_metadata'][key] for key in ('scale','negative')}
            program=executable_program(ctx.invoke('03-calculation','01-LLM-generate-code','01-preparation.03-calculation.pot',request,
                local=lambda p,response_schema:call(config,'01-preparation.03-calculation.pot',p,profile_id='luna-low',
                    save=lambda n,v:ctx.save('03-calculation/01-LLM-generate-code/03-LLM-call/'+n,v))))
        program,layout=name_constants(program)
        ctx.save('03-calculation/02-prepare-code/03-program.json',program)
        records=publish(ctx,program)
        if not records:raise ValueError('EXTERNAL_EVIDENCE_NOT_DECLARED')
        payload={**program,'context':read(case/'data.json')['context']}
        result=ctx.invoke('03-calculation','03-execute-python','pot.execute',payload,local=execute)
        def compile_payload(p):
            g,v,n=compile_graph(p)
            return StepResult('PASS','Graph built from the new code',{'graph':g,'exact_value':str(v)})
        built=ctx.invoke('04-graph','02-build-graph','dag.compile',payload,local=compile_payload)
        graph=built['graph']
        if result['exact_value']!=built['exact_value'] or any(result['trace'].get(n['variable'])!=n['computed'] for n in graph['nodes'] if n['kind']=='variable'):
            raise ValueError('PYTHON_GRAPH_MISMATCH')
        report.update(status='PASS',python_value=result['exact_value'],graph_value=built['exact_value'],application_status='REQUIRES_REVIEW')
        ctx.save('04-graph/04-save-graph/01-graph.json',graph)
        write(case/'04-graph/00-diagnostic/01-result.json',{'status':'PASS','graph':graph,'program':program,
              'scope':'New evidence-backed candidate; assumptions require review','origin':root.name})
        write(case/'03-calculation/02-prepare-code/external-evidence.json',{'status':'SOURCE_VERIFIED','records':records,'origin':root.name,'applies_to':'Candidate program, not the original saved program'})
    except Exception as e:report['reason']=str(e)
    ctx.save('run.json',report)
    write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
    write_index(case)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('config');p.add_argument('--saved-response')
    a=p.parse_args();print(json.dumps(run(a.case,a.config,a.saved_response),indent=2))
