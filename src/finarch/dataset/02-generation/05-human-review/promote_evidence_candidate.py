"""Publish a saved candidate only after local schema, source and calculation checks."""
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
run = __import__('finarch.dataset.02-generation.03-validation.validate_evidence_candidate', fromlist=['run']).run
rebuild = __import__('finarch.dataset.01-preparation.04-graph.rebuild_preparation_graph', fromlist=['rebuild']).rebuild
read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.shared.reference import Reference, compare


def promote(case):
    case=Path(case).resolve()
    checked=run(case)
    if checked['status']!='PASS':
        raise ValueError('CANDIDATE_VALIDATION_FAILED:'+checked.get('reason',''))
    candidate=case/checked['candidate']
    program=read(candidate/'03-calculation/02-prepare-code/03-program.json')
    sample=read(case/'data.json')
    payload={**program,'context':sample['context']}
    execution=execute(payload)
    if execution.status!='PASS':raise ValueError('CANDIDATE_EXECUTION_FAILED')
    comparison=compare(execution.data['exact_value'],Reference(sample['reference_answer'],sample['reference_answer_type'],sample['reference_precision']))
    if not comparison['matches']:raise ValueError('CANDIDATE_GOLD_MISMATCH')
    archive=case/'candidate-promotion-history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive.mkdir(parents=True)
    for rel in ['03-calculation','04-graph','run.json','07-human-review/01-collect-results']:
        src=case/rel;dst=archive/rel
        if src.exists():
            dst.parent.mkdir(parents=True,exist_ok=True)
            if src.is_dir():shutil.copytree(src,dst)
            else:shutil.copy2(src,dst)
    ctx=RunContext.resume(case,{},case.name)
    try:
        for file in (candidate/'03-calculation/02-prepare-code').iterdir():
            if file.is_file():shutil.copy2(file,case/'03-calculation/02-prepare-code'/file.name)
        write(case/'03-calculation/03-execute-python/01-input.json',payload)
        write(case/'03-calculation/03-execute-python/03-result.json',{'status':'PASS','reason':execution.reason,'data':execution.data})
        write(case/'03-calculation/04-compare-answer/01-comparison.json',comparison)
        result=rebuild(case)
    except Exception:
        for rel in ['03-calculation','04-graph','run.json','07-human-review/01-collect-results']:
            src=archive/rel;dst=case/rel
            if src.is_dir():
                if dst.exists():shutil.rmtree(dst)
                shutil.copytree(src,dst)
            elif src.exists():shutil.copy2(src,dst)
        raise
    ctx.save('candidate-promotion.json',{'status':'PASS','candidate':checked['candidate'],'previous_artifacts':str(archive.relative_to(case)), 'validation':checked,'human_decision_changed':False,'llm_calls':0})
    ctx.save_text('CANDIDATE-PROMOTION-README.md',Path(__file__).with_name('candidate-promotion-readme.md').read_text())
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');print(promote(p.parse_args().case))
