"""Offline examples from one saved real program, never text regeneration or model calls."""
import argparse
from importlib import import_module
import json
from pathlib import Path
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
PROJECT = __import__('finarch.dataset.03-release.response_screen', fromlist=['PROJECT']).PROJECT


def build(source,output):
    source,output=Path(source).resolve(),Path(output).resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('SEPARATE_OUTPUT_REQUIRED')
    output.mkdir(parents=True,exist_ok=False);snapshot=InputSnapshot(PROJECT)
    def save(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    (output/'events.jsonl').write_text(json.dumps({'phase':'START','step':'QI04','model_calls':0})+'\n')
    try:
        approved=snapshot.capture(source/'02-generation/approved-inputs.json')['test-0001']
        root=source/approved['case_path'];values={}
        for key in ('working_input','program','graph'):
            ref=approved['files'][key];path=root/ref['path'];values[key]=snapshot.capture(path)
            if snapshot.ref(path)['sha256']!=ref['sha256']:raise ValueError('APPROVED_HASH_MISMATCH')
        for relative in ('03-experiment/qwen-8b/dataset.json',):snapshot.capture(source/relative)
        snapshot.capture(PROJECT/'config/hyperparameter.json')
        planner=import_module('finarch.dataset.02-generation.01-perturbation.generation_plan');records=[]
        for seed in range(4):
            for index,family in ((0,'VALUE'),(4,'RELATION')):
                plan=planner.build(values['working_input'],values['program'],values['graph'],index,
                                   perturbation_policy={'name':'bounded-coefficients-v1','seed':seed})
                records.append({'id':f'test-0001/{family}/seed-{seed}','family':family,'seed':seed,'target':plan['target'],
                    'selection':plan['coefficient_selection'],'exact_value':plan['execution']['exact_value'],
                    'intent':plan['intent'],'program':plan['program'],'graph':plan['graph'],'execution':plan['execution']})
        snapshot.verify()
        report={'schema_version':'coefficient-policy-report-v1','run_id':output.name,'model_calls':0,'records':records,
                'summary':{'records':len(records),'original_cases':1,'seeds':4,'selected':len(records),'model_calls':0},
                'limitations':['Fixed target and operand order. No new text generation or frozen624 regeneration.',
                    'Supported numeric domains only: currency sign preservation, nonnegative integer counts, bounded 0..100 percent.',
                    'Domain labels do not prove all semantic constraints. Unknown units/explicit question precision reject as NOT_EVALUATED.',
                    'Question precision stays fixed; graph/execution and legacy normalized-answer checks remain mandatory.',
                    'End-to-end generation/audit API calls are not exercised. Existing g03 recovery config Path handling requires separate follow-up before full live pipeline use.'],
                'references':list(snapshot.references.values())}
        save('coefficient-policy.json',report);save('summary.json',{'workflow':'coefficient_policy','status':'COMPLETE',**report['summary']})
        save('manifest.json',{'snapshot_status':'UNCHANGED','inputs':list(snapshot.references.values()),'missing':sorted(snapshot.missing)})
        (output/'README.md').write_text(Path(__file__).with_name('coefficient-policy-readme-template.md').read_text().format(run_id=output.name))
        with (output/'events.jsonl').open('a') as f:f.write(json.dumps({'phase':'END','records':8,'model_calls':0})+'\n')
        return report
    except Exception as error:
        save('failure.json',{'status':'FAIL','reason':str(error)});raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(build(a.source,a.output)['summary'])
