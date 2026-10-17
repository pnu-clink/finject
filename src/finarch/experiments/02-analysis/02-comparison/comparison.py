"""A02: descriptive paired relationships, never an input answerability gate."""
import argparse
import hashlib
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from itertools import combinations
from pathlib import Path

collect = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])
store, VARIANTS = collect.store, collect.VARIANTS
CONDITIONS = [('unguided','off'), ('unguided','on'), ('guided','off'), ('guided','on')]
CLASSIFICATIONS = ['ANSWERABLE','CONFLICT','INSUFFICIENT_EVIDENCE','UNRESOLVED','ABSTAIN']


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except InvalidOperation:
        return None


def choice(row):
    """Compare returned numbers with saved candidate numbers, not correctness."""
    if row['status'] != 'VALID':
        return 'FORMAT_OR_EXECUTION_FAILED'
    answer = (row.get('response') or {}).get('answer')
    if answer is None:
        return 'NULL'
    n = number(answer)
    if n is None:
        return 'NON_NUMERIC'
    a = number(row.get('reference', {}).get('reference_answer'))
    b = number(row.get('alternative_answer'))
    if a is None:
        return 'REFERENCE_MISSING'
    if b is None:
        return 'ORIGINAL_VALUE' if n == a else 'OTHER'
    return 'BOTH' if n==a and n==b else 'A' if n==a else 'B' if n==b else 'OTHER'


def position(row):
    c = choice(row)
    if c not in ('A','B'):
        return c
    if row['variant'] not in ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY'):
        return 'NOT_APPLICABLE'
    return row.get('verified_candidate_positions', {}).get(c, 'UNKNOWN')


def attach_positions(rows, public, private):
    """Resolve boundary insertions from hash-linked edits, never variant names alone."""
    originals = {r['case']: public.get(r['item_id'], {}).get('context')
                 for r in rows if r['variant'] == 'ORIGINAL'}
    output = []
    for row in rows:
        mapping = {}
        original = originals.get(row['case'])
        context = public.get(row['item_id'], {}).get('context')
        provenance = private.get(row['item_id'], {}).get('edit_provenance') or {}
        steps = provenance.get('steps') or []
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        if (isinstance(original, str) and isinstance(context, str)
                and provenance.get('status') == 'VERIFIED' and steps
                and steps[0].get('input_context_sha256') == digest(original)
                and steps[-1].get('output_context_sha256') == digest(context)):
            current = original
            valid = True
            for step in steps:
                if step.get('input_context_sha256') != digest(current):
                    valid = False
                    break
                patches = step.get('patches') or []
                for patch in sorted(patches, key=lambda p: p.get('start', -1), reverse=True):
                    start, end = patch.get('start'), patch.get('end')
                    if (type(start) is not int or type(end) is not int
                            or not 0 <= start <= end <= len(current)
                            or current[start:end] != patch.get('before')
                            or not isinstance(patch.get('text'), str)):
                        valid = False
                        break
                    current = current[:start] + patch['text'] + current[end:]
                if not valid or digest(current) != step.get('output_context_sha256'):
                    valid = False
                    break
            patches = steps[0].get('patches') or []
            if valid and current == context and len(patches) == 1:
                patch = patches[0]
                # Only a recorded numeric insertion establishes the A/B ordering.
                if (steps[0].get('variant') in ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER')
                        and patch.get('before') == '' and patch.get('text')
                        and patch.get('start') == patch.get('end')):
                    if patch['start'] == 0:
                        mapping = {'A': 'BACK', 'B': 'FRONT'}
                    elif patch['start'] == len(original):
                        mapping = {'A': 'FRONT', 'B': 'BACK'}
        output.append({**row, 'verified_candidate_positions': mapping})
    return output


def outcome(row):
    response = row.get('response')
    if not isinstance(response, dict):
        return 'RESPONSE_MISSING'
    label = response.get('classification')
    if label is not None:
        return str(label)
    if row['prompt_condition']=='unguided':
        return 'UNGUIDED_NUMERIC' if number(response.get('answer')) is not None else 'UNGUIDED_NULL'
    return 'CLASSIFICATION_MISSING'


def summary(rows):
    numeric = [r for r in rows if number((r.get('response') or {}).get('answer')) is not None]
    nulls = [r for r in rows if isinstance(r.get('response'),dict) and r['response'].get('answer') is None]
    original = [r for r in rows if r['variant']=='ORIGINAL']
    return {'planned':len(rows),'collected':sum(isinstance(r.get('response'),dict) for r in rows),
            'format_valid':sum(r['status']=='VALID' for r in rows),
            'statuses':dict(Counter(r['status'] for r in rows)),
            'numeric':len(numeric),'null':len(nulls),'missing':len(rows)-len(numeric)-len(nulls),
            'classifications':dict(Counter(outcome(r) for r in rows)),
            'original_results':dict(Counter(r['original_result'] for r in original)),
            'numeric_candidate_choices':dict(Counter(choice(r) for r in rows)),
            'positions':dict(Counter(position(r) for r in rows if r['variant'] in ('IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY'))),
            'response_ids':[r['response_id'] for r in rows]}


def pair(left, right, axis):
    sides = [r for r in (left,right) if r]
    first = sides[0]
    def endpoint(r):
        if not r:
            return None
        return {k:r[k] for k in ('response_id','trial_id','case','variant','model','prompt_condition','reasoning','status','original_result')} | {
            'answer':(r.get('response') or {}).get('answer'),'classification':outcome(r),
            'choice':choice(r),'position':position(r)}
    both = left is not None and right is not None
    return {'axis':axis,'case':first['case'],'left':endpoint(left),'right':endpoint(right),
            'complete':both,'format_comparable':both and all(r['status']=='VALID' for r in sides),
            'missing_reason':None if both else 'LEFT_MISSING' if left is None else 'RIGHT_MISSING'}


def group_pairs(pairs):
    output=[]
    groups=defaultdict(list)
    for p in pairs:
        left,right=p['left'],p['right']
        sample=left or right
        # Keep the held-fixed condition in every denominator.
        prompt=sample['prompt_condition'] if p['axis']!='PROMPT' else 'unguided_to_guided'
        reasoning=sample['reasoning'] if p['axis']!='REASONING' else 'off_to_on'
        variant=sample['variant'] if p['axis'] in ('PROMPT','REASONING','MODEL') else p['axis']
        model=sample['model'] if p['axis']!='MODEL' else (left['model'] if left else '?')+'→'+(right['model'] if right else '?')
        groups[(p['axis'],model,prompt,reasoning,variant)].append(p)
    for identity, rows in sorted(groups.items()):
        good=[r for r in rows if r['format_comparable']]
        output.append(dict(zip(('axis','model','prompt_condition','reasoning','variant'),identity)) | {
            'planned_pairs':len(rows),'complete_pairs':sum(r['complete'] for r in rows),'comparable_pairs':len(good),
            'missing_pairs':sum(not r['complete'] for r in rows),'failed_pairs':sum(r['complete'] and not r['format_comparable'] for r in rows),
            'classification_transitions':dict(Counter(p['left']['classification']+' → '+p['right']['classification'] for p in good)),
            'choice_transitions':dict(Counter(p['left']['choice']+' → '+p['right']['choice'] for p in good)),
            'position_transitions':dict(Counter(p['left']['position']+' → '+p['right']['position'] for p in good)),
            'pairs':rows})
    return output


def external_knowledge_groups(rows):
    """Stratify responses by the original's private production annotation."""
    labels = {}
    for row in rows:
        label = row.get('original_external_knowledge')
        if label is None:
            continue
        case = row['case']
        if case in labels and labels[case] != label:
            raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_CONFLICT:' + case)
        labels[case] = label
    if not labels:
        return None
    if len(labels) != len({row['case'] for row in rows}):
        raise ValueError('ORIGINAL_EXTERNAL_KNOWLEDGE_INCOMPLETE')
    groups = defaultdict(list)
    for row in rows:
        label = labels[row['case']]
        status = 'VERIFIED_USE' if label['used'] else 'CRITERIA_NOT_MET'
        groups[(status, row['model'], row['variant'], row['prompt_condition'], row['reasoning'])].append(row)
    return {
        'scope': 'Private original production dependency; not observed model use or a validated edited-variant label.',
        'false_meaning': 'Criteria for confirmed use were not met; absence of external knowledge is not established.',
        'original_cases': dict(Counter('VERIFIED_USE' if label['used'] else 'CRITERIA_NOT_MET'
                                       for label in labels.values())),
        'used_types': dict(Counter(kind for label in labels.values() if label['used']
                                   for kind in label['used_types'])),
        'response_groups': [dict(zip(('original_external_knowledge', 'model', 'variant',
                                      'prompt_condition', 'reasoning'), key)) | {
            'planned': len(group), 'format_valid': sum(row['status'] == 'VALID' for row in group),
            'original_numeric_matches': sum(row['original_result'] == 'MATCH' for row in group
                                            if row['variant'] == 'ORIGINAL')}
            for key, group in sorted(groups.items())]}


def build(root, *, preserve_execution_state=False):
    root=Path(root).resolve()
    collect.verify_reuse(root)
    rows=store.rows(root/collect.ANALYSIS/'01_results/responses.jsonl')
    collect.unique(rows,'response_id','ANALYSIS_RESPONSE')
    rows = attach_positions(rows,
        collect.unique(store.rows(root / '00_input/public.jsonl'), 'item_id', 'PUBLIC'),
        collect.unique(store.rows(root / '00_input/private.jsonl'), 'item_id', 'PRIVATE'))
    indexed={(r['model'],r['case'],r['variant'],r['prompt_condition'],r['reasoning']):r for r in rows}
    if len(indexed)!=len(rows):
        raise ValueError('REPEATS_REQUIRE_EXPLICIT_PAIRING_KEY')
    models=sorted({r['model'] for r in rows}); cases=sorted({r['case'] for r in rows})
    matrix=[]; original_groups=[]; profiles=[]; pairs=[]
    for model in models:
        for variant in VARIANTS:
            for prompt,reasoning in CONDITIONS:
                selected=[r for r in rows if (r['model'],r['variant'],r['prompt_condition'],r['reasoning'])==(model,variant,prompt,reasoning)]
                matrix.append({'model':model,'variant':variant,'prompt_condition':prompt,'reasoning':reasoning,**summary(selected)})
        for prompt,reasoning in CONDITIONS:
            for verdict in ('MATCH','MISMATCH','UNEVALUATED','ORIGINAL_MISSING'):
                originals=[indexed.get((model,c,'ORIGINAL',prompt,reasoning)) for c in cases]
                ids=[c for c,o in zip(cases,originals) if (o['original_result'] if o else 'ORIGINAL_MISSING')==verdict]
                id_set=set(ids)
                subset=[r for r in rows if r['model']==model and r['case'] in id_set and r['variant']!='ORIGINAL' and (r['prompt_condition'],r['reasoning'])==(prompt,reasoning)]
                original_groups.append({'model':model,'prompt_condition':prompt,'reasoning':reasoning,'baseline_result':verdict,
                                       'original_cases':ids,'original_count':len(ids),**summary(subset)})
            for case in cases:
                original=indexed.get((model,case,'ORIGINAL',prompt,reasoning))
                variants=[indexed[(model,case,v,prompt,reasoning)] for v in VARIANTS[1:]
                          if (model,case,v,prompt,reasoning) in indexed]
                profiles.append({'case':case,'model':model,'prompt_condition':prompt,'reasoning':reasoning,
                    'baseline_result':original['original_result'] if original else 'ORIGINAL_MISSING',
                    'original_response_id':original['response_id'] if original else None,
                    'variants':summary(variants)})
                get=lambda v:indexed.get((model,case,v,prompt,reasoning))
                for a,b,axis in [('IC_VALUE_01_BEFORE','IC_VALUE_01_AFTER','VALUE_POSITION'),
                                 ('IC_VALUE_01_BEFORE','IC_SOURCE_A_ONLY','SOURCE_A'),
                                 ('IC_VALUE_01_AFTER','IC_SOURCE_B_ONLY','SOURCE_B'),('EA_01','EA_02','EA_DELETION')]:
                    if axis in ('SOURCE_A','SOURCE_B') and get(a) and get(b):
                        if get(a)['item_id'] not in get(b).get('matched_value_parent_ids', []):
                            raise ValueError('SOURCE_VALUE_PARENT_MISMATCH:' + get(b)['response_id'])
                    if get(a) or get(b): pairs.append(pair(get(a),get(b),axis))
        for case in cases:
            for variant in VARIANTS:
                for reasoning in ('off','on'):
                    a,b=(indexed.get((model,case,variant,p,reasoning)) for p in ('unguided','guided'))
                    if a or b:pairs.append(pair(a,b,'PROMPT'))
                for prompt in ('unguided','guided'):
                    a,b=(indexed.get((model,case,variant,prompt,r)) for r in ('off','on'))
                    if a or b:pairs.append(pair(a,b,'REASONING'))
    for a,b in combinations(models,2):
        for case in cases:
            for variant in VARIANTS:
                for prompt,reasoning in CONDITIONS:
                    left,right=(indexed.get((m,case,variant,prompt,reasoning)) for m in (a,b))
                    if left or right:pairs.append(pair(left,right,'MODEL'))
    comparisons={'schema_version':1,'method':collect.METHOD,'run':root.name,'generated_at':store.now(),
        'scope':'EXPLORATORY_SAVED_RESPONSES_NOT_INDEPENDENT_REPLICATION','evaluation_source':store.read(root/'config.json').get('evaluation_reuse',{}).get('source_run',root.name),
        'overall':summary(rows),'matrix':matrix,'original_groups':original_groups,'paired_groups':group_pairs(pairs),
        'original_external_knowledge':external_knowledge_groups(rows),
        'case_profiles':profiles,'model_comparison_available':len(models)>1,
        'repeat_comparison_available':False,
        'interpretation_boundaries':['Numeric candidate coincidence is not inferred preference or semantic correctness.',
            'Source placement and parent links require supplied edit evidence; unknown placement is not FRONT or BACK.',
            'EA_01 and EA_02 separately delete original facts, not cumulative deletions.',
            'Unguided classification null is by contract, not a missing Guided label.',
            'No input answerability judgments or old semantic scores are consumed.'],
        'response_rows_sha256':store.file_hash(root/collect.ANALYSIS/'01_results/responses.jsonl')}
    folder=root/collect.ANALYSIS/'02_comparison'
    store.write(folder/'comparisons.json',comparisons)
    previous = store.read(folder/'state.json') if preserve_execution_state else None
    if previous is None:
        store.write(folder/'state.json',{'status':'COUNTS_READY_INTERPRETATION_PENDING','responses':len(rows),
                                       'paired_records':len(pairs),'method':collect.METHOD})
    status = (f"Numeric aggregation complete · interpretations {previous['status']} · valid {previous.get('valid', 0)}/{previous.get('requests', 0)}"
              if previous and 'requests' in previous else 'Numeric aggregation complete \xb7 response interpretation in progress')
    collect.render(root,'02_comparison',source=comparisons['evaluation_source'],planned=len(rows),pairs=len(pairs),status=status)
    store.event(root,'A02_RELATION_COUNTS_BUILT',responses=len(rows),paired_records=len(pairs),new_target_model_calls=0)
    return comparisons


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True)
    args=parser.parse_args();out=build(args.run)
    print({k:v for k,v in out['overall'].items() if k!='response_ids'})
