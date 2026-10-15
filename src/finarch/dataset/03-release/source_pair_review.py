"""Match each frozen SOURCE to its saved VALUE dependency; no generation or API calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
PROJECT = __import__('finarch.dataset.03-release.response_screen', fromlist=['PROJECT']).PROJECT
from finarch.dataset.schemas.source_pair_review import PairRecord, PairReport

PAIRS={'03-ic-source-type-1':('SOURCE1','01-ic-value-before','A','IC_VALUE_01_BEFORE'),
       '04-ic-source-type-2':('SOURCE2','02-ic-value-after','B','IC_VALUE_01_AFTER')}


def observation_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verify_pair(source_item,base_item,source_run,base_run,dependency):
    """Validate exact saved insertion coordinates, replay, and inverse; never remove by regex."""
    case,variant=source_item['id'].split('/');kind,base_variant,side,label=PAIRS[variant]
    reasons=[];inverse=False;location={};identity={}
    if base_item is None or base_run is None:
        return ['MISSING_BASE'],False,identity,location
    if base_item['id']!=case+'/'+base_variant:
        return ['WRONG_BASE_PARENT_OR_VARIANT'],False,identity,location
    if not isinstance(source_run,dict) or not isinstance(dependency,dict) or not dependency:
        return ['MISSING_SOURCE_OR_DEPENDENCY'],False,identity,location
    if dependency.get('source')!=base_run.get('path'):
        reasons.append('DEPENDENCY_PATH_MISMATCH')
    base_observation=base_run.get('observation')
    if observation_hash(base_observation)!=dependency.get('observation_sha256'):
        reasons.append('DEPENDENCY_OBSERVATION_HASH_MISMATCH')
    if base_observation!={k:base_item[k] for k in ('question','context')}:
        reasons.append('BASE_NOT_EXACT_FROZEN_QC')
    if source_run.get('observation')!={k:source_item[k] for k in ('question','context')}:
        reasons.append('SOURCE_NOT_EXACT_FROZEN_QC')
    request=source_run.get('generation_request',{})
    if {k:request.get(k) for k in ('question','context')}!=base_observation:
        reasons.append('SOURCE_REQUEST_NOT_BASE_QC')
    intent=source_run.get('plan',{}).get('intent',{});base_intent=base_run.get('plan',{}).get('intent',{})
    pair=intent.get('value_pair',[])
    identity={'A':pair[0] if len(pair)==2 else None,'B':pair[1] if len(pair)==2 else None,'meaning':'Original and changed input values, not earlier/later positions or answer correctness.', 'attributed_side':side,'source_condition':intent.get('source_condition'),'base_variant':intent.get('base_variant')}
    if intent.get('source_condition')!=side+'_ONLY' or intent.get('base_variant')!=label:
        reasons.append('SOURCE_BASE_CONTRACT_MISMATCH')
    if len(pair)!=2 or pair!=base_intent.get('value_pair') or intent.get('target')!=base_intent.get('target'):
        reasons.append('VALUE_IDENTITY_OR_TARGET_MISMATCH')
    patches=source_run.get('patches',[]);slots=request.get('edit_slots',[])
    if len(patches)!=1 or len(slots)!=1:
        reasons.append('UNSUPPORTED_PATCH_COUNT');return reasons,inverse,identity,location
    patch=patches[0];slot=slots[0];position=patch.get('start');text=patch.get('text')
    if (not isinstance(position,int) or patch.get('end')!=position or patch.get('before')!='' or not isinstance(text,str) or not text
        or any(patch.get(k)!=slot.get(k) for k in ('start','end','before','element_ids')) or slot.get('kind')!='SOURCE_'+side):
        reasons.append('UNAUTHORIZED_SOURCE_INSERTION');return reasons,inverse,identity,location
    context=request.get('context','');final=source_item['context']
    if not 0<=position<=len(context):
        reasons.append('PATCH_OUT_OF_RANGE');return reasons,inverse,identity,location
    line_start=context.rfind('\n',0,position)+1;line_end=context.find('\n',position)
    if line_end<0:line_end=len(context)
    line=context[line_start:line_end]
    location={'insertion_offset_in_base':position,'inserted_text':text,'line_quote':line,
              'layout':'TABLE_CELL' if '|' in line else 'PROSE',
              'position_interpretation':'CELL_LOCAL_NOT_PROSE_ORDER' if '|' in line else 'SAVED_INSTRUCTION_ONLY',
              'saved_claim_instructions':[v for v in request.get('instructions',[]) if 'claim' in v.lower()],
              'slot_kind':slot['kind']}
    if context[:position]+text+context[position:]!=final:
        reasons.append('FORWARD_PATCH_MISMATCH')
    if final[position:position+len(text)]!=text:
        reasons.append('EXACT_INSERTED_TEXT_MISMATCH')
    else:
        inverse=final[:position]+final[position+len(text):]==base_item['context'] and source_item['question']==base_item['question']
        if not inverse:reasons.append('INVERSE_QC_MISMATCH')
    return reasons,inverse,identity,location


def response_pair(source,base,matched):
    def state(r):
        return {'execution':r['execution'],'cues':{k:bool(v) for k,v in (r.get('cues') or {}).items()} if r.get('cues') is not None else None,
                'semantic_status':r['semantic_status'],'ab_match':r['comparison']['match']} if r else {'execution':'MISSING','cues':None,'semantic_status':'NOT_EVALUATED','ab_match':'UNRESOLVED'}
    a,b=state(source),state(base)
    comparison={k:{'base':b['cues'][k],'source':a['cues'][k]} for k in ('conflict','reject','condition')} if matched and a['execution']==b['execution']=='COMPLETE' else None
    return {'source':a,'base':b},comparison


def build(source,output,quality_root,screen_root,*,project=PROJECT):
    source,output,quality_root,screen_root,project=[Path(p).resolve() for p in (source,output,quality_root,screen_root,project)]
    for protected in (source,quality_root,screen_root):
        if output.is_relative_to(protected) or protected.is_relative_to(output):raise ValueError('OUTPUT_MUST_BE_SEPARATE')
    output.relative_to(project);output.mkdir(parents=True,exist_ok=False);snapshot=InputSnapshot(project)
    def save(name,value):(output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    def event(phase,**extra):
        with (output/'events.jsonl').open('a') as f:f.write(json.dumps({'phase':phase,'step':'QI03','time':datetime.now(timezone.utc).isoformat(),'model_calls':0,**extra})+'\n')
    event('START')
    try:
        frozen_path=source/'03-experiment/qwen-8b/dataset.json';frozen=snapshot.capture(frozen_path)
        if len(frozen)!=624 or len({r['id'] for r in frozen})!=624:raise ValueError('FROZEN_DENOMINATOR_OR_DUPLICATE')
        items={r['id']:r for r in frozen};sources=[r for r in frozen if r['id'].split('/')[1] in PAIRS]
        if len(sources)!=176:raise ValueError('SOURCE_DENOMINATOR_MISMATCH')
        qp=quality_root/'quality_scope.json';quality={r['id']:r for r in snapshot.capture(qp)['records']}
        sp=screen_root/'response_screen.json';screens={r['id']:r for r in snapshot.capture(sp)['records']}
        # Freeze the reused screening evidence, including raw/result hashes.
        sm=snapshot.capture(screen_root/'manifest.json')
        for ref in sm['inputs']:
            snapshot.capture(project/ref['path'],parse=False)
            if snapshot.ref(project/ref['path'])!=ref:raise ValueError('SCREEN_INPUT_HASH_MISMATCH:'+ref['path'])
        records=[]
        for item in sources:
            case,variant=item['id'].split('/');kind,base_variant,side,label=PAIRS[variant];base_id=case+'/'+base_variant
            refs={'frozen':snapshot.ref(frozen_path),'quality_scope':snapshot.ref(qp),'response_screen':snapshot.ref(sp)};extra=[]
            def generation(identifier,key):
                ref=quality.get(identifier,{}).get('references',{}).get('generation')
                if not ref:return None,None
                path=project/ref['path'];value=snapshot.capture(path);actual=snapshot.ref(path)
                if actual:refs[key]=actual
                if actual!=ref:extra.append(key.upper()+'_FILE_HASH_MISMATCH_OR_MISSING');return None,path
                return value,path
            src,srcpath=generation(item['id'],'source_generation');base,basepath=generation(base_id,'base_generation')
            dep_path=srcpath.parent/'02-generate-text/00-value-dependency.json' if srcpath else None
            dep=snapshot.capture(dep_path) if dep_path else None
            if dep_path and snapshot.ref(dep_path):refs['dependency']=snapshot.ref(dep_path)
            reasons,inverse,identity,location=verify_pair(item,items.get(base_id),src,base,dep)
            reasons=extra+reasons
            responses,cues=response_pair(screens.get(item['id']),screens.get(base_id),not reasons)
            for key,identifier in [('source',item['id']),('base',base_id)]:
                for name in ('raw','result'):
                    ref=screens.get(identifier,{}).get('references',{}).get(name)
                    if ref:refs[key+'_'+name]=ref
            records.append(PairRecord(id=item['id']+'::'+base_id,case=case,source_type=kind,source_id=item['id'],base_id=base_id,
                match_status='EXCLUDED' if reasons else 'MATCHED',reasons=reasons,dependency_source=dep.get('source') if isinstance(dep,dict) else None,
                dependency_observation_sha256=dep.get('observation_sha256') if isinstance(dep,dict) else None,
                inverse_matches_base=inverse,value_identity=identity,claim_location=location,responses=responses,cue_comparison=cues,references=refs))
        def counts(rows):
            return {'total':len(rows),'matched':sum(r.match_status=='MATCHED' for r in rows),'excluded':sum(r.match_status!='MATCHED' for r in rows),
                'both_complete':sum(all(v['execution']=='COMPLETE' for v in r.responses.values()) for r in rows),
                'either_truncated':sum(any(v['execution']=='TRUNCATED' for v in r.responses.values()) for r in rows),
                'cue_comparable':sum(r.cue_comparison is not None for r in rows),'semantic_effect_evaluated':0,'ab_effect_evaluated':0,
                'reasons':dict(Counter(reason for r in rows for reason in r.reasons)),
                'cue_transitions':{k:dict(Counter(str(r.cue_comparison[k]['base'])+'->'+str(r.cue_comparison[k]['source']) for r in rows if r.cue_comparison is not None)) for k in ('conflict','reject','condition')}}
        summary={'records':176,'frozen_variants':624,'overall':counts(records),**{k:counts([r for r in records if r.source_type==k]) for k in ('SOURCE1','SOURCE2')},
                 'four_variant_cases':len({r.case for r in records if r.source_type=='SOURCE1'} & {r.case for r in records if r.source_type=='SOURCE2'})}
        report=PairReport(run_id=output.name,source_run=source.name,records=records,summary=summary,limitations=[
            'Each SOURCE is compared only to its own saved VALUE-before/after dependency. SOURCE1 vs SOURCE2 is not a causal effect comparison.',
            'A/B identify original/changed input values, not text order or semantic correctness. Table cell attribution is not a later prose claim.',
            'Cue transitions are preliminary lexical observations among exact matched complete pairs, not semantic recognition or correctness.',
            'All 176 SOURCE items remain in the denominator, including absent/mismatched bases and truncated responses.',
            'Semantic and A/B effects remain unassessed. Repeat 1 only; no independent-model interpretation or new API calls.'])
        snapshot.verify();save('pair_manifest.json',report.model_dump());save('sidecar-schema.json',PairReport.model_json_schema())
        save('summary.json',{'workflow':'source_pair_review','status':'COMPLETE',**summary,'model_calls':0})
        save('manifest.json',{'snapshot_status':'UNCHANGED','inputs':list(snapshot.references.values()),'missing':sorted(snapshot.missing)})
        (output/'README.md').write_text(Path(__file__).with_name('source-pair-readme-template.md').read_text().format(run_id=output.name,summary=json.dumps(summary,ensure_ascii=False,indent=2)))
        event('END',status='COMPLETE',records=176);return report
    except Exception as error:
        save('failure.json',{'status':'FAIL','reason':str(error)});event('FAIL',reason=str(error));raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','output','quality-root','screen-root'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.quality_root,a.screen_root).summary))

if __name__=='__main__':main()
