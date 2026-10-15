"""Case-scoped feedback records, with explicit provenance for each retry."""
import hashlib
import json
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def preparation_evidence(old, before):
    old=Path(old)
    program=old/'03-calculation/02-prepare-code/03-program.json'
    if not program.exists():program=old/'03-calculation/01-LLM-generate-code/03-result.json'
    previous=json.loads(program.read_text()) if program.exists() else None
    if isinstance(previous,dict):
        previous=previous.get('data',previous)
        previous={k:previous[k] for k in ('code','facts','grounding','external_evidence') if k in previous}
    return {'case':old.name,'source_attempt':str(old),'failure':before.get('reason'),
            'previous_program':previous,
            'instruction':'Repair the specific failure using the source and previous program below. Identify the affected input or operation; preserve unrelated valid work. Do not infer a reference answer or introduce assumptions to force agreement.'}


def generation_feedback(ctx,bundle,root,name,index,latest,types):
    """Copy exact applicable records; VALUE's shared sentence uses both pair audits."""
    read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
    write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
    folder,axis,label=types[index];records=[]
    for source_index in ([0,1] if index==0 else [index]):
        prior=latest.get(source_index)
        if not prior:continue
        source=Path(bundle)/prior['path']/'feedback/02-result.json'
        if not source.exists():continue
        record=read(source)
        if record.get('case')!=name or record.get('label')!=types[source_index][2]:
            raise ValueError('CASE_FEEDBACK_SCOPE_MISMATCH')
        records.append({'source':str(source.relative_to(bundle)),'sha256':fingerprint(record),'record':record})
    directory=Path(root)/'feedback'
    if records:
        publish = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['publish']).publish
        refs=[]
        target_round=Path(root).parents[1].name
        for r in records:
            record=r['record']
            origin=Path(bundle)/r['source']
            source_round=record.get('evidence_round') or origin.parents[3].name
            canonical=origin.parents[1]/'04-exception-handler'/'feedback'/target_round/'feedback.json'
            refs.append(publish(canonical,case=name,variant=record['label'],
                source_round=source_round,target_round=target_round,
                target_role='02-generation.02-generate-text.realization',axis=axis,
                guidance=record['guidance'],source=origin))
        ctx.save('feedback/01-applied.json',{'case':name,'label':label,'records':records,'shared_value_pair':index==0})
        guidance='\n\n'.join('Feedback for '+r['record']['label']+':\n'+r['record']['guidance'] for r in records)
        write(directory/'02-generation.02-generate-text.realization'/f'{axis.lower()}.json',{'feedback_refs':refs,'case':name,'label':label})
    return directory
