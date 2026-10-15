"""Validate a saved evidence-backed candidate without changing the human decision."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
from finarch.dataset.schemas.validation import validate
from finarch.dataset.shared.calculation.python_runtime import execute, validate_facts
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.external_evidence import resolve
from finarch.shared.reference import Reference, compare


def run(case):
    case=Path(case).resolve();diagnostic=read(case/'04-graph/00-diagnostic/01-result.json')
    candidate=case/diagnostic['origin'];program=read(candidate/'03-calculation/02-prepare-code/03-program.json')
    sample=read(case/'data.json');payload={**program,'context':sample['context']}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    ctx=RunContext(candidate/('validation-'+stamp),{},case_id=case.name)
    ctx.save_text('README.md',Path(__file__).with_name('evidence-validation-readme.md').read_text())
    checks=[]
    report={'status':'FAIL','application_status':'REQUIRES_REVIEW','llm_calls':0,'checks':checks,
            'candidate':diagnostic['origin'],'program_sha256':hashlib.sha256(json.dumps(program,sort_keys=True).encode()).hexdigest()}
    try:
        with ctx.trace.activate():
            response={**program,'facts':[{'id':k,**v} for k,v in program['facts'].items()]}
            validate('01-preparation.03-calculation.pot.response',response);checks.append({'check':'response_schema','status':'PASS'})
            validate_facts(payload);checks.append({'check':'source_fact_spans_and_values','status':'PASS','count':len(program['facts'])})
            records=resolve(payload)
            stored=read(candidate/'03-calculation/02-prepare-code/external-evidence.json')['records']
            if records!=stored:raise ValueError('EXTERNAL_SOURCE_RECORD_CHANGED')
            checks.append({'check':'external_source_catalog_and_saved_record','status':'PASS'})
            result=ctx.invoke('03-calculation','execute','pot.execute',payload,local=execute)
            checks.append({'check':'python_execution','status':'PASS','value':result['exact_value']})
            comparison=compare(result['exact_value'],Reference(sample['reference_answer'],sample['reference_answer_type'],sample['reference_precision']))
            ctx.save('comparison.json',comparison)
            if not comparison['matches']:raise ValueError('GOLD_MISMATCH')
            checks.append({'check':'gold_comparison','status':'PASS','computed':comparison['computed'],'gold':comparison['gold']})
            graph,value,_=compile_graph(payload)
            if graph!=diagnostic['graph']:raise ValueError('SAVED_GRAPH_MISMATCH')
            checks.append({'check':'saved_graph_reproduction','status':'PASS'})
            variables=[n for n in graph['nodes'] if n['kind']=='variable']
            if str(value)!=result['exact_value'] or any(n['computed']!=result['trace'].get(n['variable']) for n in variables):
                raise ValueError('PYTHON_GRAPH_MISMATCH')
            checks.append({'check':'python_graph_all_variables','status':'PASS','count':len(variables),'value':str(value)})
            nodes={n['id']:n for n in graph['nodes']}
            selections=[{'evidence_id':n['evidence_id'],'inputs':[nodes[i]['computed'] for i in n['inputs']],
                         'selected_value':n['computed'],'unit':graph['external_evidence'][n['evidence_id']]['unit']}
                        for n in graph['nodes'] if n.get('operator')=='evidence']
            checks.append({'check':'external_table_selection','status':'PASS','selections':selections})
            report.update(status='PASS',python_value=result['exact_value'],graph_value=str(value),gold=sample['reference_answer'],
                          checked_variables=len(variables),assumptions=[a for d in program['external_evidence'] for a in d['assumptions']])
    except Exception as error:report['reason']=str(error)
    ctx.save('run.json',report)
    write(case/'04-graph/00-diagnostic/02-validation.json',{**report,'record_path':str(ctx.root.relative_to(case))})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('case')
    print(json.dumps(run(parser.parse_args().case),indent=2))
