"""Build attribution-only requests from the current run's assigned audited IC-VALUE variant."""
import json
candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root


def base_variant(variant):
    return variant['plan'].get('base_variant', 'IC_VALUE_01_BEFORE')


def value_base(case, label='IC_VALUE_01_BEFORE'):
    read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
    digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
    from finarch.dataset.shared.review.dtt_audit import observation_hash
    root=case/candidate_root(label)
    stage=read(root/'latest-realization.json')['stage']
    observation=read(case/stage/'04-final-observation.json')
    audit=read(root/'latest-audit.json')['stage']
    report=read(case/audit/'03-result.json')
    if (report['status']!='PASS' or report['stage16_ref']!=stage
            or report['observation_sha256']!=observation_hash(observation)):
        raise ValueError('IC_VALUE_BEFORE_AUDIT_REQUIRED')
    if read(case/stage/'03-result/validation.json')['status']!='PASS':
        raise ValueError('IC_VALUE_BEFORE_GENERATION_REQUIRED')
    return observation,read(case/stage/'03-result/patches.json'),read(case/stage/'01-input.json'),{
        'label':label,'generation_ref':stage,'audit_ref':audit,
        'observation_sha256':observation_hash(observation),
        'request_sha256':digest(case/stage/'01-input.json')}


def request_from_value(case, variant, sample, program, nodes, fact):
    slot = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['slot']).slot
    label=base_variant(variant)
    observation,patches,base_request,binding=value_base(case,label)
    if observation['question']!=sample['question']:
        raise ValueError('IC_VALUE_QUESTION_CHANGED')
    if len(patches)!=1 or patches[0]['start']!=patches[0]['end']:
        raise ValueError('IC_VALUE_BEFORE_INSERTION_REQUIRED')
    patch=patches[0];source=variant['plan']['sources'][0];side=source['side']
    # The added B claim precedes the original A claim. Insert attribution at the
    # relevant claim start, never at the numeric token's trailing boundary.
    position=patch['start']+(len(patch['text']) if side=='A' else 0)
    after=label=='IC_VALUE_01_AFTER'
    if after:
        position=patch['start']+len(patch['text'])-len(patch['text'].lstrip())
    instructions=[
        f'The context is the audited IC-VALUE-{"after" if after else "before"} result from this run. Preserve both value claims, their numbers, order, and the question exactly.',
        'Add attribution only to the assigned claim. Do not regenerate the competing value claim.',
        'Write only the attribution insertion. Fit its grammar and punctuation to the surrounding text, including a trailing separator. Do not repeat or replace existing words.',
        'Assigned claim: '+json.dumps({'side':side,'position':'later original claim' if side=='A' else ('later added claim' if after else 'earlier added claim'),'source':source}),
        'The attribution applies only to the selected quantity: '+json.dumps(fact),
    ]
    return {**observation,'axis':'IC_SOURCE','python_code':program['code'],'graph_structure':nodes,
            'edit_slots':[slot(position,position,'',patch['element_ids'],'SOURCE_'+side,
                              'Compose a natural attribution for the assigned claim at this insertion boundary. Preserve the following claim verbatim.')],
            'instructions':instructions,'tagged_context':None},binding
