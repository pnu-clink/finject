"""Collect immutable failure references for agent-led instruction refinement."""
import hashlib
import json
from pathlib import Path
save = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['save']).save


def collect(bundle):
    bundle=Path(bundle);entries=[]
    for directory in sorted(bundle.glob('0[123]-round')):
        path=directory/'05-text/03-final-validator/03-result.json'
        if not path.exists():continue
        verdict=json.loads(path.read_text())
        for item in verdict.get('failures',[]):
            entries.append({'round':directory.name,'source':str(path.relative_to(bundle)),
                'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**item})
    root=bundle/'01-round'
    for case in sorted(root.glob('test-*')):
        path=case/'run.json'
        if not path.exists():continue
        result=json.loads(path.read_text())
        if result.get('status')=='FAIL':
            entries.append({'round':'01-round','case':case.name,'label':'PIPELINE','axis':'ANSWER',
                'target_role':'01-preparation.03-calculation.pot','reason':result.get('reason',''),
                'source':str(path.relative_to(bundle)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'request':{'source_input':str((case/'00-data-preparation/01-select-input/01-input.json').relative_to(bundle))},
                'response':{'program':str((case/'02-calculation/02-prepare-code/03-program.json').relative_to(bundle))}})
        planned=case/'production-plan-failure.json'
        if planned.exists():
            entries.append({'round':'01-round','case':case.name,'label':'PLANNING','axis':'PLANNING',
                'reason':json.loads(planned.read_text()).get('reason',''),'source':str(planned.relative_to(bundle)),
                'source_sha256':hashlib.sha256(planned.read_bytes()).hexdigest()})
    output=bundle/'feedback-review';output.mkdir(exist_ok=True)
    save(output/'01-evidence.json',{'run':bundle.name,'entries':entries})
    save(output/'02-reason-index.json',{'entries':[{k:v for k,v in i.items() if k not in ('request','response')} for i in entries]})
    (output/'README.md').write_text('# Supplemental guidance review\n\nRead 01-evidence.json for original failure references and payloads, 02-reason-index.json for the reason index, then the agent review and instructions. Generated responses and recorded verdicts are preserved. Instructions contain behavioral guidance, never prewritten answers or replacements.\n')
    return entries

if __name__=='__main__':
    import sys
    from collections import Counter
    entries=collect(Path(sys.argv[1]));print(dict(Counter(i['axis'] for i in entries)))
